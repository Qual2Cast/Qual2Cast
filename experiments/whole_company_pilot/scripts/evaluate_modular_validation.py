"""Evaluate frozen rankings and supplied financial snapshot; no model selection.

Independent human relevance fields remain blank. Financial dates/definitions are
unknown, so all observed-multiple errors are explicitly snapshot proxies.
"""
from pathlib import Path
from datetime import datetime, timezone
import sys, json, hashlib, os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from modular_validation.numeric import aggregate_multiples
from modular_validation.evaluation import ranking_agreement, evidence_coverage_abstention, common_pool_metrics, strict_valuation_indication, verify_experiment_seal
from modular_validation.evidence_policy import profile_eligibility
OUT=Path(os.environ.get('QUAL2CAST_EXPERIMENT_DIR') or 'outputs-local/modular-validation')
OUT=(OUT if OUT.is_absolute() else ROOT/OUT).resolve()
PARAMETERS=OUT/'parameters.json' if (OUT/'parameters.json').exists() else ROOT/'config/modular_validation_parameters.json'

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value): Path(path).write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')

def evaluate():
    design=json.loads((OUT/'design_freeze.json').read_text())
    paths=[OUT/'core/rankings.csv',OUT/'profiles/rankings.csv',OUT/'llm/rankings.csv']
    if 'local_llm_derived_activity_ledger' in design['methods_predeclared']:paths.append(OUT/'llm-protocol-v2/rankings.csv')
    if (OUT/'factors/rankings.csv').exists():paths.append(OUT/'factors/rankings.csv')
    if not all(p.exists() for p in paths): raise RuntimeError('Every predeclared core/profile/LLM stage must finish before outcomes are opened')
    # Preserve serialized IEEE floats; the default parser can collapse adjacent
    # scores into artificial ties and falsely reject the original stable ranks.
    rankings=pd.concat([pd.read_csv(p,float_precision='round_trip') for p in paths],ignore_index=True)
    assert not rankings.duplicated(['target_id','candidate_id','method']).any()
    assert (rankings.target_id!=rankings.candidate_id).all()
    missing=set(design['methods_predeclared'])-set(rankings.method)
    if missing: raise RuntimeError(f'Predeclared methods absent: {sorted(missing)}')
    expected_ids={t['IQ_COMPANY_ID'] for t in design['targets']}
    coverage=pd.read_csv(OUT/'core/text_coverage.csv').set_index('IQ_COMPANY_ID')
    eligible_ids=set(coverage.index)
    for method,group in rankings.groupby('method'):
        if set(group.target_id)!=expected_ids:raise RuntimeError(f'Incomplete target coverage for {method}')
        for cid,rows in group.groupby('target_id'):
            if set(rows.candidate_id)!=eligible_ids-{cid}:
                raise RuntimeError(f'Incomplete candidate ledger for {method}/{cid}')
            available=rows.available.astype(str).str.lower().eq('true')
            if not np.array_equal(available.to_numpy(),np.isfinite(rows.score.to_numpy(float))):
                raise RuntimeError(f'Availability/score mismatch for {method}/{cid}')
            if not np.array_equal(available.to_numpy(),rows['rank'].notna().to_numpy()):
                raise RuntimeError(f'Availability/rank mismatch for {method}/{cid}')
            ranked=rows[available].sort_values(['score','candidate_id'],ascending=[False,True])
            if ranked['rank'].tolist()!=list(range(1,len(ranked)+1)):
                raise RuntimeError(f'Noncontiguous or incorrectly sorted ranks for {method}/{cid}')
    expected_profile_digest=json.loads((OUT/'profiles/run_freeze.json').read_text())['profile_map_sha256']
    profile_paths=[p for p in (OUT/'profile-cache').glob('*/all_profiles_validated.json') if digest(p)==expected_profile_digest]
    if len(profile_paths)!=1:raise RuntimeError('Canonical profile evidence does not match ranked inputs')
    profiles=json.loads(profile_paths[0].read_text(encoding='utf-8'))
    if set(profiles)!=eligible_ids:raise RuntimeError('Canonical profile map is incomplete')
    evidence={cid:profile_eligibility(record)[0] for cid,record in profiles.items()}
    destination=OUT/'evaluation'; destination.mkdir(exist_ok=True)
    freeze={'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
            'ranking_inputs':{str(p.relative_to(OUT)):digest(p) for p in paths},
            'evaluation_script_sha256':digest(__file__),
            'direct_valuation_script_sha256':digest(ROOT/'scripts/run_direct_valuation.py'),
            'module_sha256':{p.name:digest(p) for p in sorted((ROOT/'src/modular_validation').glob('*.py'))},
            'design_sha256':digest(OUT/'design_freeze.json'),
            'parameter_sha256':digest(PARAMETERS),'parameter_path':str(PARAMETERS),
            'experiment_dir':str(OUT),
            'purpose':'Seal all rankings before reading held-out target valuation outcomes'}
    seal=destination/'all_rankings_freeze.json'
    if seal.exists():
        previous=json.loads(seal.read_text())
        verify_experiment_seal(previous,freeze)
    else:
        save(seal,freeze)
    # Only now unseal target valuation outcomes. Do not use them to modify rankings.
    snapshot=Path(design['team_root'])/'data-local/snapshots/company_list_v3_websites_fixed.csv'
    F=pd.read_csv(snapshot,dtype=str).set_index('IQ_COMPANY_ID')
    numeric=['target_revenue','target_ebitda','target_margin','target_debt_to_revenue','target_ev_to_ebitda']
    F[numeric]=F[numeric].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    roles={t['IQ_COMPANY_ID']:t['role'] for t in design['targets']}
    outcomes=[]; contributions=[]; diagnostics=[]; policy_rows=[]; agreement_rows=[]
    for (cid,method),group in rankings.groupby(['target_id','method'],sort=True):
        r=group[group['available'].astype(str).str.lower().eq('true') & group['rank'].notna()].sort_values('rank')
        observed=float(F.loc[cid,'target_ev_to_ebitda'])
        target_ebitda=float(F.loc[cid,'target_ebitda'])
        ok_observed=np.isfinite(observed) and observed>0 and np.isfinite(target_ebitda) and target_ebitda>0
        common=r[r.candidate_id.isin(coverage.index)]
        length_corr=spearmanr(common.score,coverage.loc[common.candidate_id,'clean_words']).statistic if len(common)>2 and common.score.nunique()>1 else np.nan
        top=r.head(5)
        ordered=r.candidate_id.tolist()
        reference=rankings[(rankings.target_id==cid)&(rankings.method=='team_mpnet_cosine')&rankings['rank'].notna()].sort_values('rank').candidate_id.tolist()
        agreement_rows.append({'target_id':cid,'method':method,**ranking_agreement(ordered,reference,k=5)})
        diagnostics.append({'target_id':cid,'target_ticker':F.loc[cid,'target_ciq_ticker'],'role':roles[cid],
                            'method':method,'available_candidates':len(r),'returned_top5':len(top),
                            'same_sic4_fraction_at5':float(F.loc[top.candidate_id,'target_sic4_code'].astype(str).eq(str(F.loc[cid,'target_sic4_code'])).mean()) if len(top) else np.nan,
                            'score_textlength_spearman':length_corr,
                            'independent_human_precision_at5':None,'independent_human_ndcg_at10':None})
        for k in [3,5,10]:
            guard=evidence_coverage_abstention(ordered,evidence,target_supported=evidence.get(cid),k=k)
            policy_rows.append({'target_id':cid,'method':method,'k':k,**guard})
            selected=r.head(k); peers=selected.candidate_id.tolist()
            values=F.loc[peers,'target_ev_to_ebitda'].to_numpy(float)
            ebitda=F.loc[peers,'target_ebitda'].to_numpy(float)
            values=np.where(np.isfinite(ebitda)&(ebitda>0),values,np.nan)
            weights=1/selected['rank'].to_numpy(float)
            for agg in ['median','harmonic','weighted']:
                result=aggregate_multiples(peers,values,method=agg,weights=weights if agg=='weighted' else None)
                estimate=result['estimate'] if result['valid_count']>=3 else None
                valid=estimate is not None and ok_observed
                strict=strict_valuation_indication(guard,estimate_multiple=estimate,target_ebitda=target_ebitda,
                    valid_peer_count=result['valid_count'],dates_and_definitions_confirmed=False)
                strict['strict_indication_reasons']=json.dumps(strict['strict_indication_reasons'])
                row={'target_id':cid,'target_ticker':F.loc[cid,'target_ciq_ticker'],'role':roles[cid],
                     'sic4':str(F.loc[cid,'target_sic4_code']),'method':method,'k':k,'aggregation':agg,
                     'estimate_multiple':estimate,'observed_multiple':observed if np.isfinite(observed) else None,
                     'estimated_ev_supplied_millions':float(estimate*target_ebitda) if estimate is not None and np.isfinite(target_ebitda) and target_ebitda>0 else None,
                     'ev_unit':'supplied dollar millions; currency not independently confirmed',
                     'ev_interpretation':'indicative enterprise value, not equity price or investment recommendation',
                     'target_ebitda':target_ebitda,'selected_peers':len(peers),'valid_peers':result['valid_count'],
                     'effective_peers':result['effective_peer_count'],'valid_peer_ids':'|'.join(result['valid_ids']),
                     'snapshot_ape':abs(estimate-observed)/observed if valid else None,
                     'snapshot_signed_error':(estimate-observed)/observed if valid else None,
                     'snapshot_absolute_log_error':abs(np.log(estimate/observed)) if valid else None,
                     'valuation_status':'exploratory_snapshot_proxy' if valid else 'unavailable',
                      'exploratory_estimate_policy':'unguarded_fixed_rank_snapshot_diagnostic',
                      'evidence_guard_accepted':guard['accepted'],
                      'evidence_guard_reasons':json.dumps(guard['reasons']),
                      **strict,
                     'reason':None if valid else ('fewer_than_three_valid_selected_peers' if estimate is None else 'nonpositive_or_missing_target_multiple_or_ebitda'),
                     'aligned_date_status':'unavailable_dates_and_definitions_unconfirmed'}
                outcomes.append(row)
                contributions.append({'target_id':cid,'method':method,'k':k,**result})
    result=pd.DataFrame(outcomes); result.to_csv(destination/'valuation_results.csv',index=False)
    pd.DataFrame(diagnostics).to_csv(destination/'ranking_diagnostics.csv',index=False)
    save(destination/'peer_contributions.json',contributions)
    save(destination/'evidence_coverage_policy.json',policy_rows)
    pd.DataFrame(agreement_rows).to_csv(destination/'agreement_with_dense_baseline.csv',index=False)
    rankings.to_csv(destination/'all_rankings.csv',index=False)
    summary=result[(result.k==5)&(result.aggregation=='median')].groupby(['role','method']).agg(
        valid_targets=('snapshot_ape','count'),median_ape=('snapshot_ape','median'),mean_ape=('snapshot_ape','mean'),
        median_absolute_log_error=('snapshot_absolute_log_error','median')).reset_index()
    summary.to_csv(destination/'snapshot_proxy_summary.csv',index=False)
    # Common paired set prevents changing coverage from masquerading as improvement.
    fresh=result[(result.role=='fresh_pilot')&(result.k==5)&(result.aggregation=='median')]
    pivot=fresh.pivot(index='target_id',columns='method',values='snapshot_ape')
    paired=[]
    baseline='team_mpnet_cosine'
    for method in pivot:
        if baseline not in pivot: continue
        common=pivot[[baseline,method]].dropna() if method!=baseline else pivot[[baseline]].dropna()
        paired.append({'method':method,'common_target_count':len(common),
                       'baseline_median_ape_on_same_targets':float(common[baseline].median()) if len(common) else None,
                       'method_median_ape_on_same_targets':float(common[method].median()) if len(common) else None,
                       'median_paired_difference':float((common[method]-common[baseline]).median()) if len(common) else None})
    pd.DataFrame(paired).to_csv(destination/'paired_snapshot_proxy_comparisons.csv',index=False)
    # Blinded review pool: union top10 plus deterministic random controls; all judgments blank.
    U=pd.read_csv(OUT/'core/company_identifiers.csv',dtype=str).set_index('IQ_COMPANY_ID')
    eligible=coverage.index.tolist(); rng=np.random.default_rng(4511); review=[]
    for t in design['targets']:
        cid=t['IQ_COMPANY_ID']; selected=set(rankings[(rankings.target_id==cid)&(rankings['rank']<=10)].candidate_id)
        control=[x for x in eligible if x!=cid and x not in selected]
        selected.update(rng.choice(control,size=min(5,len(control)),replace=False).tolist())
        for peer in sorted(selected):
            review.append({'pair_id':hashlib.sha256(f'{cid}|{peer}'.encode()).hexdigest()[:12],
                           'target_id':cid,'candidate_id':peer,'target':U.loc[cid,'target_company_name'],
                           'candidate':U.loc[peer,'target_company_name'],'target_url':U.loc[cid,'target_ciq_website'],
                           'candidate_url':U.loc[peer,'target_ciq_website'],'reviewer_name':'','whole_company_grade':'',
                           'source_urls_checked':'','supported_activities':'','material_mismatches':'','unknown_scope':'','reason':''})
    pd.DataFrame(review).sample(frac=1,random_state=4511).to_csv(destination/'blind_human_review.csv',index=False)
    # Identical pools and explicit unjudged labels for later independent review.
    metric_readiness=[]
    for cid,group in pd.DataFrame(review).groupby('target_id'):
        pool=group.candidate_id.tolist()
        for method,ranked in rankings[rankings.target_id==cid].groupby('method'):
            ordered=ranked[ranked['rank'].notna()].sort_values('rank').candidate_id.tolist()
            metric_readiness.append({'target_id':cid,'method':method,**common_pool_metrics(ordered,{},pool_ids=pool,k=10)})
    save(destination/'human_metric_readiness.json',metric_readiness)
    review_entities={r['target_id'] for r in review}|{r['candidate_id'] for r in review}
    save(destination/'review_evidence.json',{cid:{'company':U.loc[cid,'target_company_name'],
         'website':U.loc[cid,'target_ciq_website'],'profile_status':profiles.get(cid,{}).get('status','unknown'),
         'known_activities':profiles.get(cid,{}).get('known_activities',[]),
         'scope_complete':False,'independent_human_reviewed':False} for cid in sorted(review_entities)})
    save(destination/'evaluation_status.json',{'completed_at_utc':datetime.now(timezone.utc).isoformat(),
         'ranking_methods':int(rankings.method.nunique()),'targets':int(rankings.target_id.nunique()),
         'valuation_rows':len(result),'independent_human_labels_new':0,'review_pairs':len(review),
         'financial_dates':'unknown','financial_definition_alignment':'unconfirmed',
         'claims':'Snapshot proxy evaluation only; no independent relevance validation, no causal effect, no temporal forecast.'})
    print(summary.to_string(index=False)); print('EVALUATION_COMPLETE',len(result),flush=True)

if __name__=='__main__': evaluate()
