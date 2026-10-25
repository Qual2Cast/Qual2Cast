"""Outcome-blind factor-family comparisons on the frozen common pilot pool."""
from pathlib import Path
from datetime import datetime, timezone
import os,sys,json,hashlib,time
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from run_modular_validation import score_rows
from modular_validation.evidence_policy import profile_eligibility
OUT=Path(os.environ.get('QUAL2CAST_EXPERIMENT_DIR',ROOT/'outputs-local/pilot-validation-2026-10-18'))
if not OUT.is_absolute():OUT=ROOT/OUT
UNKNOWN={'','unknown','not stated','not specified','none','n/a'}
FINANCIAL_SETS={
 'financial_size_only':['target_revenue'],
 'financial_margin_only':['target_margin'],
 'financial_debt_revenue_only':['target_debt_to_revenue'],
 'financial_size_margin':['target_revenue','target_margin'],
 'financial_size_debt_revenue':['target_revenue','target_debt_to_revenue'],
 'financial_margin_debt_revenue':['target_margin','target_debt_to_revenue'],
 'financial_size_margin_debt_ebitda':['target_revenue','target_margin','derived_debt_to_ebitda']}
GROUPS=['product','customer','role','monetization','delivery','stage']
BUSINESS_SETS={'business_product_customer':['product','customer'],
 'business_role_monetization':['role','monetization','delivery','stage'],
 'business_multifacet_equal':GROUPS}
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
def known(value):return isinstance(value,str) and value.strip().casefold() not in UNKNOWN
def activity_groups(record):
    """Retain every activity; product fallback avoids dropping unclassified lines."""
    collected={g:[] for g in GROUPS};fallback=0
    for a in record.get('known_activities',[]):
        f=a.get('facets',{})
        product=[f.get(k) for k in ['product_function','product_type'] if known(f.get(k))]
        if not product and known(a.get('activity')):product=[a['activity']];fallback+=1
        collected['product'].extend(product)
        for group,keys in {'customer':['customer','customer_industry'],'monetization':['revenue_model'],
                           'delivery':['delivery_model'],'stage':['commercialization_stage']}.items():
            collected[group].extend(f[k] for k in keys if known(f.get(k)))
        roles=[a.get('role'),f.get('operating_role')]
        collected['role'].extend(x.replace('_',' ') for x in roles if known(x))
    return {g:'; '.join(dict.fromkeys(v)) for g,v in collected.items()},fallback

def main(profile_path):
    from modular_validation.features import _encode_groups
    design=json.loads((OUT/'design_freeze.json').read_text())
    ids=pd.read_csv(OUT/'core/text_coverage.csv',dtype=str).IQ_COMPANY_ID.tolist()
    identifiers=pd.read_csv(OUT/'core/company_identifiers.csv',dtype=str)
    tickers=dict(zip(identifiers.IQ_COMPANY_ID,identifiers.target_ciq_ticker));idx={c:i for i,c in enumerate(ids)}
    profiles=json.loads(Path(profile_path).read_text(encoding='utf-8'))
    if set(profiles)!=set(ids):raise ValueError('Exact common pool profile map required')
    folder=OUT/'factors';folder.mkdir(exist_ok=True)
    if (folder/'rankings.csv').exists():raise FileExistsError('Preserve existing factor experiment')
    F=pd.read_csv(OUT/'global-controls/core/permitted_financial_predictors.csv',dtype={'IQ_COMPANY_ID':str}).set_index('IQ_COMPANY_ID')
    F=F.apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    F['derived_debt_to_ebitda']=(F.target_debt_to_revenue/F.target_margin.where(F.target_margin>0)).replace([np.inf,-np.inf],np.nan)
    rank=F.rank(method='average',pct=True)
    parts=[];metadata={};runtime=[]
    for method,cols in FINANCIAL_SETS.items():
        started=time.monotonic()
        for t in design['targets']:
            cid=t['IQ_COMPANY_ID'];distance=(rank[cols]-rank.loc[cid,cols]).abs().mean(axis=1)
            complete=F[cols].notna().all(axis=1)&F.loc[cid,cols].notna().all()
            values=(-distance.where(complete)).reindex(ids).to_numpy(float)
            parts.append(score_rows(ids,cid,values,method,tickers))
        runtime.append({'method':method,'ranking_seconds':time.monotonic()-started,'shared_preprocessing':'permitted predictor percentile ranks over original534 eligible companies'})
        metadata[method]={'acquisition':'supplied financial snapshot','representation':'average percentile ranks on original534 eligible companies',
          'similarity':'negative mean absolute percentile-rank distance','factor_family':cols,
          'candidate_policy':'common frozen183 pilot companies minus self','information_regime':'mentor-permitted financial augmentation',
          'weights':'equal; no outcome-tuned weights','source_family':'SARD-inspired ablation, not published five-factor replication',
          'limitations':'Undated snapshot; supplied debt/EBITDA definitions unconfirmed; size/margin/debt alone do not establish business identity.'}
    texts=[];keys=[];coverage=[]
    for cid in ids:
        groups,fallback=activity_groups(profiles[cid]);ok,reason=profile_eligibility(profiles[cid])
        for g in GROUPS:texts.append(groups[g]);keys.append((cid,g))
        coverage.append({'company_id':cid,'eligible':ok,'eligibility_reason':reason,'known_groups':[g for g in GROUPS if groups[g]],'product_activity_fallback_count':fallback,'scope_complete':False})
    start=time.monotonic();M,encoding_info=_encode_groups(texts);encoding_seconds=time.monotonic()-start
    V=dict(zip(keys,M));np.save(folder/'business_factor_vectors.npy',M,allow_pickle=False);save(folder/'business_factor_keys.json',keys)
    shared=[]
    for method,groups in BUSINESS_SETS.items():
        start=time.monotonic()
        for t in design['targets']:
            cid=t['IQ_COMPANY_ID'];scores=np.full(len(ids),np.nan)
            for peer in ids:
                if peer==cid:continue
                ok=profile_eligibility(profiles[cid])[0] and profile_eligibility(profiles[peer])[0]
                available=[g for g in groups if np.isfinite(V[(cid,g)]).all() and np.isfinite(V[(peer,g)]).all()] if ok else []
                vals=[float(np.clip(V[(cid,g)]@V[(peer,g)],-1,1)) for g in available]
                if vals:scores[idx[peer]]=float(np.mean(vals))
                shared.append({'method':method,'target_id':cid,'candidate_id':peer,'shared_groups':available,'known_group_count':len(vals),'declared_group_count':len(groups)})
            parts.append(score_rows(ids,cid,scores,method,tickers))
        runtime.append({'method':method,'ranking_seconds':time.monotonic()-start,'shared_factor_encoding_seconds':encoding_seconds})
        metadata[method]={'acquisition':'frozen company website evidence and supported unreviewed extraction',
          'representation':'all observed activities pooled within explicit semantic groups; same pinned MPNet encoder',
          'similarity':'mean cosine across shared known groups','factor_family':groups,
          'candidate_policy':'common frozen183 pilot companies minus self','information_regime':'website only',
          'weights':'equal known groups, with explicit pairwise coverage; not revenue weights',
          'source_family':'operating-taxonomy and whole-business factor hypotheses',
          'limitations':'No numeric moat score; source support is not human verification. Group pooling loses within-activity associations; text is not economic segment weight. Changing shared group counts affects comparability.'}
    ranking=pd.concat(parts,ignore_index=True);ranking.to_csv(folder/'rankings.csv',index=False)
    save(folder/'method_metadata.json',metadata);save(folder/'runtime.json',runtime);save(folder/'factor_coverage.json',coverage)
    save(folder/'pair_factor_coverage.json',shared);save(folder/'encoding_metadata.json',encoding_info)
    save(folder/'factor_specification.json',{'financial_subsets':FINANCIAL_SETS,'business_groups':BUSINESS_SETS,'shared_transform_population':len(F),'financial_reference_sha256':digest(OUT/'global-controls/core/permitted_financial_predictors.csv'),
      'prohibited_inferences':['EBITDA margin is not ROIC','EBITDA is not owner earnings','leverage is not total business risk','website marketing is not a calibrated moat score','stock-return factor evidence is not company-matching validation']})
    save(folder/'ranking_freeze.json',{'created_at_utc':datetime.now(timezone.utc).isoformat(),'rankings_sha256':digest(folder/'rankings.csv'),'profile_map_sha256':digest(profile_path),'runner_sha256':digest(__file__),'parameters_sha256':digest(OUT/'parameters.json'),'design_sha256':digest(OUT/'design_freeze.json'),'target_outcomes_opened':False})
    print('FACTOR_ABLATION_COMPLETE',ranking.method.nunique(),'methods',len(ranking),'rows',flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('profiles');a=p.parse_args();main(a.profiles)
