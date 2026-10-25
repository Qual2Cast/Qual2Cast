"""Track preselected, source-audited challenges; never create human labels."""
import os,json,hashlib
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('QUAL2CAST_EXPERIMENT_DIR',ROOT/'outputs-local/pilot-validation-2026-10-18'))
if not OUT.is_absolute():OUT=ROOT/OUT
CHALLENGES=[('HRMY','RMD'),('GTII','MAPS'),('PCTY','HURN'),('CARG','PAL'),('SABR','RAMP')]
def main():
    parts=[pd.read_csv(OUT/s/'rankings.csv') for s in ['core','profiles','factors','llm']]
    if (OUT/'llm-protocol-v2/rankings.csv').exists():parts.append(pd.read_csv(OUT/'llm-protocol-v2/rankings.csv'))
    ranks=pd.concat(parts,ignore_index=True)
    folder=OUT/'agent-assessment';folder.mkdir(exist_ok=True)
    reviews=[];companies={};provenance={}
    for name in ['ic_case_reviews_health.json','ic_case_reviews_software.json']:
        p=OUT/name;x=json.loads(p.read_text(encoding='utf-8'));reviews.extend(x['pairs']);companies.update(x['companies'])
        provenance[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    tickers={cid:r.get('ticker') for cid,r in companies.items()}
    challenges=[p for p in reviews if (tickers.get(p['target_id']),tickers.get(p['candidate_id'])) in CHALLENGES]
    if len(challenges)!=5:raise RuntimeError('Expected exact five preselected source challenges')
    rows=[]
    for p in challenges:
        for method in sorted(ranks.method.unique()):
            r=ranks[(ranks.method==method)&(ranks.target_id==p['target_id'])&(ranks.candidate_id==p['candidate_id'])]
            if len(r)!=1:raise ValueError('Missing challenge candidate ledger')
            rank=r.iloc[0]['rank']
            rows.append({'method':method,'target_id':p['target_id'],'target_ticker':tickers[p['target_id']],
              'candidate_id':p['candidate_id'],'candidate_ticker':tickers[p['candidate_id']],
              'rank':rank,'returned_top5':bool(pd.notna(rank) and rank<=5),'rank_available':bool(pd.notna(rank)),
              'source_grounded_caution':' '.join(c['claim'] for c in p['material_mismatches']),
              'interpretation':'A purposive challenge, not a binary gold label or representative accuracy observation.'})
    pd.DataFrame(rows).to_csv(folder/'challenge_case_tracking.csv',index=False)
    detail={'actor_type':'ai','reviewer':'Automated source-grounded assessment; not independent human validation',
      'scope':'50 original baseline candidate explanations plus five purposively selected operating-role/product/customer challenges, frozen before new ranks or target outcomes.',
      'not_a_relevance_benchmark':True,'numeric_grades_created':False,'independent_human_labels':0,
      'source_review_sha256':provenance,'cases':challenges,
      'interpretation_rules':['A method avoiding these pairs is not thereby correct overall.',
        'Unavailable candidates and explicit abstentions are distinguished from low ranks.',
        'Retain overlaps, differences, unknowns and all observed businesses in every review.',
        'Evaluate valuation error separately from business explanation quality.',
        'The automated analysis follows these source-backed cases; quantitative human metrics wait for independent grades.']}
    (folder/'challenge_case_evidence.json').write_text(json.dumps(detail,indent=2),encoding='utf-8')
    top=ranks[ranks['rank'].le(5)]
    priority=top.groupby(['target_id','candidate_id']).agg(methods_returning=('method','nunique'),best_rank=('rank','min')).reset_index()
    priority['independent_human_grade']='';priority['independent_human_reviewer']=''
    priority.sort_values(['target_id','methods_returning','candidate_id']).to_csv(folder/'review_priority.csv',index=False)
    print('AGENT_ASSESSMENT_PACKET',len(reviews),'source-grounded reviews;',len(rows),'challenge-method observations;',len(priority),'top5 union pairs')
if __name__=='__main__':main()
