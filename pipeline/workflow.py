"""Orchestrate existing stages; each stage owns its own implementation."""
from pathlib import Path
from dataclasses import asdict
import json
import hashlib
import numpy as np
import pandas as pd
from pipeline.config import Configuration,FACTOR_SETS
from pipeline.inputs import aligned_inputs
from matching.retrieval import CandidateRetrieval
from matching.factors import rank_distances
from matching.activity import ACTIVITY_METHODS,retrieve_activity
from valuation.aggregators import aggregate_multiple
from valuation.measurement import financial_comparability
from growth_signals.workflow_adapter import growth_evidence

class CompanyWorkflow:
    def __init__(self, descriptors, finance, features, cluster_labels=None,
                 profiles=None, documents=None, reviews=None, growth=None):
        forbidden = {'target_ev_to_ebitda','actual','target_margin','target_sic4_code'}
        if forbidden.intersection(descriptors.columns):
            raise ValueError('Matching descriptors contain a forbidden outcome, SIC or financial field')
        self.data = descriptors.reset_index(drop=True).copy()
        self.ids = self.data.IQ_COMPANY_ID.tolist()
        if len(set(self.ids)) != len(self.ids):
            raise ValueError('Duplicate company IDs')
        self.index = {v:i for i,v in enumerate(self.ids)}
        self.ticker = dict(zip(self.data.target_ciq_ticker, self.ids))
        self.finance = finance.copy()
        self.profiles = profiles or {}; self.documents = documents or []
        self.reviews = reviews or {}; self.growth = growth
        self.activity_scores = None
        self.retrieval = CandidateRetrieval(self.data,features,cluster_labels)
    @classmethod
    def from_snapshot(cls, data_path, reviews=None):
        path = Path(data_path)
        raw = pd.read_json(path/'companies.json',dtype={'IQ_COMPANY_ID':str,'target_sic4_code':str})
        raw = raw[raw.words >= 100].reset_index(drop=True)
        descriptors, finance, outcomes = aligned_inputs(raw)
        manifest = json.loads((path/'features/manifest.json').read_text(encoding='utf-8'))
        if manifest['company_ids'] != descriptors.IQ_COMPANY_ID.tolist():
            raise ValueError('Embedding manifest order differs from descriptor order')
        if hashlib.sha256('\x00'.join(raw.text).encode()).hexdigest() != manifest['text_sha256']:
            raise ValueError('Text changed: cached representations cannot be reused')
        features = {n:np.load(path/'features'/f'team_{n}.npy') for n in ['mpnet','tfidf','lsa']}
        workflow = cls(descriptors,finance,features,dict(np.load(path/'features/cluster_labels_seed0.npz')),
                   json.loads((path/'profiles/profiles.json').read_text(encoding='utf-8')),
                   json.loads((path/'profiles/evidence_documents.json').read_text(encoding='utf-8')), reviews,
                   pd.read_csv(path/'growth_features.csv'))
        workflow.activity_scores = pd.read_csv(path/'profile_scores.csv')
        return workflow, outcomes

    def retrieve(self, company_id, method, limit=20, candidate_ids=None):
        if method in ACTIVITY_METHODS:
            return retrieve_activity(self.activity_scores,self.data,company_id,method,limit,candidate_ids)
        return self.retrieval.retrieve(company_id,method,limit,candidate_ids)

    def select(self, company_id, config, candidate_ids=None):
        candidates = self.retrieve(company_id,config.retrieval,config.shortlist,candidate_ids)
        cols = FACTOR_SETS[config.factors]
        reference_ids = [x for x in (candidate_ids if candidate_ids is not None else self.ids) if x != company_id]
        reference = self.finance.loc[reference_ids]
        if cols:
            candidates['factor_distance'] = rank_distances(self.finance.loc[company_id],
                self.finance.loc[candidates.peer_id],reference,cols,config.factor_weights)
            candidates = candidates[np.isfinite(candidates.factor_distance)].sort_values(
                ['factor_distance','retrieval_rank','peer_id'],kind='stable')
        else:
            candidates['factor_distance'] = np.nan
        candidates['review_status'] = [self.reviews.get(company_id+'|'+p,{}).get('validated_verdict','unreviewed') for p in candidates.peer_id]
        if config.review_gate == 'model_supported':
            candidates = candidates[candidates.review_status=='strong']
        candidates = candidates.head(config.k).copy()
        candidates['selection_rank'] = np.arange(1,len(candidates)+1)
        return candidates

    def target_evidence(self, company_id):
        profile = self.profiles.get(company_id,{})
        return {'status':profile.get('status','profile_unavailable'),
                'all_known_activities':profile.get('known_activities',[]),
                'scope_notes':profile.get('scope_notes','Scope completeness not established'),
                'human_verified':False}

    def run(self, ticker, config=Configuration(), peer_multiples=None, candidate_ids=None):
        """Descriptor -> retrieval -> factor ranking -> review -> multiple -> EV.

        peer_multiples is the separate public-candidate valuation table. The
        target observation is removed before values are read. No equity value
        is fabricated from gross debt without cash or other senior claims.
        """
        cid = self.ticker[ticker]; i = self.index[cid]
        peers = self.select(cid,config,candidate_ids)
        f = self.finance.loc[cid]
        if peer_multiples is None:
            values = np.full(len(peers),np.nan)
        else:
            public_values = peer_multiples.drop(index=cid,errors='ignore')
            values = public_values.reindex(peers.peer_id).to_numpy(float)
        peers['public_peer_multiple'] = values
        valuation = aggregate_multiple(values,config.aggregation,config.min_peers)
        valuation['ev_source_units'] = (valuation['multiple']*float(f.ebitda)
            if valuation['multiple'] is not None and np.isfinite(f.ebitda) and f.ebitda>0 else None)
        if not np.isfinite(f.ebitda) or f.ebitda<=0:
            valuation['status'] = 'abstain_target_ebitda_missing_or_nonpositive'
            valuation['multiple'] = None
        valuation['equity_value'] = None
        valuation['equity_status'] = 'missing_cash_other_claims_and_verified_dates'
        valuation['interval_meaning'] = 'peer-multiple dispersion, not calibrated valuation uncertainty'
        valuation['ebitda_basis'] = 'supplied snapshot; definition and period unverified'
        valuation['measurement'] = financial_comparability({},[{'peer_id':p} for p in peers.peer_id])
        valuation['verified_enterprise_value'] = None
        valuation['release_status'] = 'proxy_only_pending_financial_and_business_review'
        history = growth_evidence(self.growth,ticker)
        return {'target':ticker,'company_id':cid,'company_name':self.data.target_company_name[i],
                'configuration':asdict(config),'configuration_id':config.key,
                'target_inputs':{'website':self.data.target_ciq_website[i],
                                 'revenue':float(f.revenue),'ebitda':float(f.ebitda),
                                 'debt_derived_from_ratio':float(f.debt_derived)},
                'business_evidence':self.target_evidence(cid),
                'peers':peers.astype(object).where(pd.notna(peers),None).to_dict('records'),
                'valuation':valuation,'growth_evidence':history,
                'growth_forecast':{'status':'not_fitted_missing_historical_panel','value':None},
                'audit':{'self_match':cid in peers.peer_id.tolist(),
                         'target_multiple_used_for_matching':False,'human_approved':False,
                         'dates_and_units_verified':False,'candidate_universe':len(self.ids)-1,
                         'source_mode':'cached_company_websites','model_review_gate':config.review_gate,
                         'intended_use':'development diagnostic; investment decision requires review'}}
