"""Create a separate ten-target pilot without reading valuation outcomes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'outputs-local/modular-validation'
OUT=ROOT/'outputs-local/pilot-validation-2026-10-18'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2),encoding='utf-8')

def main():
    pool=json.loads((OUT/'candidate_pool_freeze.json').read_text())
    ids=set(pool['company_ids'])
    if (OUT/'design_freeze.json').exists():raise FileExistsError('Preserve pilot freeze')
    original=json.loads((OLD/'design_freeze.json').read_text())
    design={**original,'version':'pilot-first-v2','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
      'original_design_sha256':digest(OLD/'design_freeze.json'),
      'candidate_pool_sha256':digest(OUT/'candidate_pool_freeze.json'),'pilot_company_ids':sorted(ids),
      'full_text_eligible_count':534,'pilot_company_count':len(ids),
      'scope':'Ten fixed targets, common evidence/retrieval pilot pool; no claim of full-universe retrieval recall.',
      'selection_rule':original['selection_rule']+' Targets unchanged. Common pilot pool: all eligible members of the two SIC groups; union of original top5 from four independent retrievers; twenty seeded random controls. Never selected for cache availability or outcomes.',
      'scale_up_gate':'Review ten cases and failures; lock final choices; validate on a new ten-company batch before broad deployment.',
      'target_outcomes_opened':False}
    params=json.loads((ROOT/'config/modular_validation_parameters.json').read_text())
    params.update(version='pilot-first-v2',candidate_universe=f'Common fixed {len(ids)}-company pilot pool, excluding each target itself. Original 534-company controls retained separately.')
    params['factor_ablation']={
      'financial_subsets':'All nonempty subsets of revenue, EBITDA margin and debt/revenue; the full set is the existing financial_rank_adapted arm.',
      'reference_population':'Original 534 eligible companies for percentile transforms; only pilot candidates may be returned.',
      'derived_leverage_alternative':'Replace debt/revenue with debt/EBITDA = (debt/revenue)/(EBITDA/revenue), only with positive EBITDA margin; this is a transformation, not new information.',
      'redundancy_policy':'Do not simultaneously treat revenue, EBITDA and EBITDA margin as independent factors. Do not add both debt ratios to one equal-weight set.',
      'missing_quality_factors':'ROIC, owner earnings, gross profit/assets, retention, historical growth and cash conversion are unavailable, never inferred from EBITDA or website marketing.'}
    new=['financial_size_only','financial_margin_only','financial_debt_revenue_only',
         'financial_size_margin','financial_size_debt_revenue','financial_margin_debt_revenue',
         'financial_size_margin_debt_ebitda','business_product_customer','business_role_monetization',
         'business_multifacet_equal']
    design['methods_predeclared']=sorted(set(design['methods_predeclared'])|set(new))
    design['additional_factor_methods']=new
    design['combination_blocks']=[
      {'block':'financial_factor_subsets','choices':'seven nonempty subsets of three supplied predictors, plus one alternative leverage transform','inference':'factor ablation; not proof that single-factor peers are suitable'},
      {'block':'business_factor_groups','choices':['product_customer','role_monetization','equal_all_known_groups'],'inference':'whole observed activity inventory retained; absent groups remain unknown'},
      {'block':'ranking_peer_count_aggregation','choices':{'ranker':'all declared methods','k':[3,5,10],'aggregation':['median','harmonic','weighted']},'inference':'complete compatible cross, paired targets and coverage reported'},
      {'block':'direct_model_information','choices':{'model':['ridge','hist_gradient_boosting'],'information':['financial_only','financial_plus_website']},'inference':'exploratory snapshot prediction, not business-peer approval'}]
    save(OUT/'parameters.json',params);save(OUT/'design_freeze.json',design)
    (OUT/'core').mkdir();(OUT/'global-controls').mkdir()
    shutil.copytree(OLD/'core',OUT/'global-controls/core')
    for p in (OLD/'core').iterdir():
        if p.is_file():shutil.copy2(p,OUT/'core'/p.name)
    r=pd.read_csv(OLD/'core/rankings.csv')
    filtered=r[r.candidate_id.isin(ids)].copy()
    blocks=[]
    for _,g in filtered.groupby(['method','target_id'],sort=True):
        g=g.sort_values(['available','score','candidate_id'],ascending=[False,False,True]).copy()
        ok=g.available.astype(str).str.lower().eq('true')
        g['rank']=pd.array([i+1 if v else None for i,v in enumerate(ok)],dtype='Int64');blocks.append(g)
    pd.concat(blocks,ignore_index=True).to_csv(OUT/'core/rankings.csv',index=False)
    for name in ['text_coverage.csv','company_identifiers.csv','permitted_financial_predictors.csv']:
        f=pd.read_csv(OLD/'core'/name,dtype={'IQ_COMPANY_ID':str})
        f[f.IQ_COMPANY_ID.isin(ids)].to_csv(OUT/'core'/name,index=False)
    save(OUT/'core/ranking_freeze.json',{'sha256':digest(OUT/'core/rankings.csv'),'target_outcomes_opened':False,'original_full_rankings_sha256':digest(OLD/'core/rankings.csv'),'operation':'restrict original scores to common pool; stable rerank; no model refit'})
    save(OUT/'core/pilot_transform.json',{'candidate_pool_sha256':digest(OUT/'candidate_pool_freeze.json'),'scores_fitted_on_original_534_corpus':True,'candidate_pool_count':len(ids),'full_universe_controls':'global-controls/core','current_rankings_sha256':digest(OUT/'core/rankings.csv')})
    for p in OLD.iterdir():
        if p.is_file() and p.suffix in {'.json','.txt','.csv'} and p.name not in {'design_freeze.json'}:
            shutil.copy2(p,OUT/p.name)
    for name in ['growth-integration','growth-readiness','live-cleaning-diagnostic']:
        if (OLD/name).exists():shutil.copytree(OLD/name,OUT/name)
    save(OUT/'pilot_stage_status.json',{'stage':'candidate and method design frozen; profile extraction underway','created_at_utc':datetime.now(timezone.utc).isoformat(),'target_outcomes_opened':False,'original_full_profile_cache_preserved':True,'human_labels_new':0})
    print('PILOT_PREPARED',len(ids),'companies',len(filtered),'core ranking rows')

if __name__=='__main__':main()
