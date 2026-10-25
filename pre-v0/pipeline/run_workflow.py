"""Run the complete cached-input workflow, then controlled method substitutions."""
import os
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','QUAL2CAST_CPU_THREADS']:
    os.environ[key]='2'
os.environ['QUAL2CAST_GPU_MEMORY_FRACTION']='0.60'
os.environ['TOKENIZERS_PARALLELISM']='false'
import sys
import json
import itertools
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]   # pre-v0/: the packages imported below
REPO=ROOT.parent                            # repo root: outputs-local/
sys.path[:0]=[str(ROOT),str(ROOT/'experiments/whole_company_pilot/src')]
from pipeline.workflow import CompanyWorkflow
from pipeline.config import Configuration,PRIMARY_RETRIEVERS as RETRIEVERS,FACTOR_SETS,AGGREGATORS
from pipeline.evaluation import flatten_result
from matching.evidence_review import execute_reviews
from matching.peer_selectors import paired_bootstrap

import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-root',type=Path,default=REPO/'outputs-local/integration-19')
parser.add_argument('--output',type=Path,default=REPO/'outputs-local/company-workflow')
parser.add_argument('--review',action='store_true',help='Run the separately cached local language model')
args=parser.parse_args() if __name__=='__main__' else parser.parse_args([])
DATA=args.data_root
OUT=args.output/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
TEAM_TEN=['PCTY','BV','ROAD','FIX','BRO','ADUS','LOPE','ODFL','WING','DXPE']

def configuration_grid():
    # One complete baseline first; factorial substitutions follow on identical inputs.
    return [Configuration(retrieval=r,factors=f,aggregation=a,k=k)
            for r,f,a,k in itertools.product(RETRIEVERS,FACTOR_SETS,AGGREGATORS,[3,5,10])]

def summarize(results):
    rows=[]
    for key,d in results.groupby('configuration_id',sort=False):
        row=d.iloc[0]
        rows.append({c:row[c] for c in ['configuration_id','retrieval','factors','aggregation','k']} |
            {'targets':len(d),'scored':int(d.ape.notna().sum()),'coverage':float(d.ape.notna().mean()),
             'median_ape':float(d.ape.median()),'mean_ape':float(d.ape.mean()),
             'p90_ape':float(d.ape.quantile(.9)),
             'median_log_error':float(d.absolute_log_error.median()),
             'within25_all_targets':float((d.ape<=25).sum()/len(d))})
    return pd.DataFrame(rows)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    workflow,outcomes=CompanyWorkflow.from_snapshot(DATA)
    observed=outcomes.set_index('IQ_COMPANY_ID').target_ev_to_ebitda
    targets=json.loads((DATA/'design_freeze.json').read_text(encoding='utf-8'))['targets']
    configs=configuration_grid()
    freeze={'created_utc':datetime.now(timezone.utc).isoformat(),'targets':targets,
      'team_ten':TEAM_TEN,'configurations':[dict(id=c.key,**c.__dict__) for c in configs],
      'primary':Configuration().__dict__,'review_scope':'Union of baseline MPNet, RRF and all-three factor top-five for team ten; frozen without reviewing valuation results.',
      'inference':'cached representations and original whole-business profiles; new source-bounded pair review',
      'interpretation':'Exploratory extension after previous results; not an untouched test or preregistration',
      'resource_policy':{'numeric_threads':2,'inference_batch':2,'gpu_memory_fraction':.6,'workers':1}}
    freeze_path=OUT/'design.json'
    if not freeze_path.exists(): freeze_path.write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    reports=[workflow.run(t,peer_multiples=observed) for t in targets]
    (OUT/'baseline_reports.json').write_text(json.dumps(reports,indent=2,allow_nan=True),encoding='utf-8')
    pairs={}
    for t in TEAM_TEN:
        cid=workflow.ticker[t]
        for c in [Configuration(),Configuration(retrieval='rrf'),Configuration(factors='all_three')]:
            for p in workflow.select(cid,c).to_dict('records'):
                pairs[cid+'|'+p['peer_id']]={'target':t,'target_id':cid,'peer':p['peer'],'peer_id':p['peer_id']}
    (OUT/'review_scope.json').write_text(json.dumps(list(pairs.values()),indent=2),encoding='utf-8')
    rows=[];selected=[]
    # Selection is independent of aggregation; avoid repeating the same retrieval work.
    for r,f,k in itertools.product(RETRIEVERS,FACTOR_SETS,[3,5,10]):
        for t in targets:
            cid=workflow.ticker[t]
            c=Configuration(retrieval=r,factors=f,k=k)
            peers=workflow.select(cid,c)
            selected.extend({'target':t,'retrieval':r,'factors':f,'k':k,**p} for p in peers.to_dict('records'))
            for a in AGGREGATORS:
                c=Configuration(retrieval=r,factors=f,k=k,aggregation=a)
                report=workflow.run(t,c,observed)
                rows.append(flatten_result(report,float(observed[cid])))
        print('Completed',r,f,k,flush=True) if f=='all_three' and k==10 else None
    results=pd.DataFrame(rows); results.to_csv(OUT/'configuration_results.csv',index=False)
    summary=summarize(results);summary.to_csv(OUT/'configuration_summary.csv',index=False)
    pd.DataFrame(selected).to_csv(OUT/'selected_peers.csv',index=False)
    base=results[results.configuration_id==Configuration().key].set_index('target').ape.reindex(targets)
    paired=[]
    for c in configs:
        if c.aggregation!='median' or c.k!=5: continue
        arm=results[results.configuration_id==c.key].set_index('target').ape.reindex(targets)
        paired.append(dict(configuration_id=c.key,retrieval=c.retrieval,factors=c.factors,
                           **paired_bootstrap(arm,base)))
    pd.DataFrame(paired).to_csv(OUT/'paired_comparisons.csv',index=False)
    # No fabricated grades: a human supplies labels and an evidence-based rationale.
    queue=pd.DataFrame(list(pairs.values()))
    descriptors=workflow.data.set_index('IQ_COMPANY_ID')
    queue['target_sources']=queue.target_id.map(descriptors.urls)
    queue['peer_sources']=queue.peer_id.map(descriptors.urls)
    for col in ['reviewer','business_grade_0_3','scope_complete','role_compatible','rationale']:
        queue[col]=''
    queue.sample(frac=1,random_state=4511).to_csv(OUT/'human_review.csv',index=False)
    complete=pd.DataFrame(selected)[['target','peer_id','peer']].drop_duplicates().copy()
    complete['target_id']=complete.target.map(workflow.ticker)
    complete['target_sources']=complete.target_id.map(descriptors.urls)
    complete['peer_sources']=complete.peer_id.map(descriptors.urls)
    for col in ['reviewer','business_grade_0_3','scope_complete','role_compatible','rationale']:
        complete[col]=''
    complete.sample(frac=1,random_state=4511).to_csv(OUT/'human_review_all.csv',index=False)
    print(json.dumps({'targets':len(targets),'configurations':len(configs),'results':len(results),'review_pairs':len(pairs)}),flush=True)
    if '--review' in sys.argv:
        website=json.loads((DATA/'website_records.json').read_text(encoding='utf-8'))
        records=execute_reviews(list(pairs.values()),website,OUT/'review-cache')
        (OUT/'pair_reviews.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        workflow.reviews=records
        reports=[workflow.run(t,Configuration(review_gate='model_supported'),observed) for t in TEAM_TEN]
        (OUT/'reviewed_reports.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Review verdicts',pd.Series([r['validated_verdict'] for r in records.values()]).value_counts().to_dict(),flush=True)

if __name__=='__main__':main()
