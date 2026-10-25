"""Training-only factor-weight selection, kept distinct from business relevance."""
import itertools
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from pipeline.config import Configuration
from matching.factors import rank_distances
from pipeline.evaluation import flatten_result

def weight_grid():
    """15 nonnegative quarter-step triples; no arbitrary missing fourth weight."""
    return [tuple(x/4 for x in v) for v in itertools.product(range(5),repeat=3) if sum(v)==4]

def fit_weights(workflow, training_multiples, seed=4511):
    """Accept training outcomes only. Outer evaluation outcomes are inaccessible.

    Within each inner fold, candidates, reference percentile distributions and
    peer multiples are drawn exclusively from that fold's training partition.
    Minimize mean absolute log error; coefficients are ranking weights, not causal
    effects. This procedure is an adaptation, not the GBM decomposition in JAR.
    """
    y=training_multiples.dropna()
    y=y[y>0].sort_index()
    ids=y.index.to_numpy(); grid=weight_grid(); rows=[]
    if len(ids)<50: raise ValueError('At least 50 positive training observations required')
    for fold,(train,test) in enumerate(KFold(5,shuffle=True,random_state=seed).split(ids)):
        train_ids=ids[train].tolist(); reference=workflow.finance.loc[train_ids]
        for cid in ids[test]:
            peers=workflow.retrieve(cid,'mpnet',20,train_ids)
            factors=workflow.finance.loc[peers.peer_id]
            columns=['revenue','margin','debt_to_revenue']
            D=np.column_stack([rank_distances(workflow.finance.loc[cid],factors,reference,[col]) for col in columns])
            values=y.reindex(peers.peer_id).to_numpy(float)
            for w in grid:
                wv=np.asarray(w); positive=wv>0
                d=D[:,positive]@wv[positive]
                order=np.argsort(d,kind='stable')[:5]
                order=order[np.isfinite(d[order])]
                pred=float(np.median(values[order])) if len(order)>=3 else np.nan
                rows.append({'fold':fold,'validation_id':cid,'w_revenue':w[0],
                             'w_margin':w[1],'w_leverage':w[2],
                             'absolute_log_error':abs(np.log(pred/y[cid])) if pred>0 else np.nan})
    scores=pd.DataFrame(rows)
    summary=scores.groupby(['w_revenue','w_margin','w_leverage']).absolute_log_error.agg(['mean','count']).reset_index()
    summary['coverage']=summary['count']/len(ids)
    # Complete coverage is required for the learner to compete on a common set.
    eligible=summary[summary.coverage==1].copy()
    if eligible.empty: raise ValueError('No fully covered inner-CV weight configuration')
    eligible['equal_distance']=abs(eligible.w_revenue-1/3)+abs(eligible.w_margin-1/3)+abs(eligible.w_leverage-1/3)
    best=eligible.sort_values(['mean','equal_distance','w_revenue','w_margin','w_leverage']).iloc[0]
    weights=tuple(float(best[c]) for c in ['w_revenue','w_margin','w_leverage'])
    return weights,summary,scores

def compare_weights(workflow, outcomes, targets):
    y=outcomes.set_index('IQ_COMPANY_ID').target_ev_to_ebitda
    target_ids=[workflow.ticker[t] for t in targets]
    training=y.drop(index=target_ids)
    learned,summary,folds=fit_weights(workflow,training)
    options={'business_only':Configuration(),
             'equal_rank_distance':Configuration(factors='all_three'),
             'learned_rank_distance':Configuration(factors='all_three',factor_weights=learned)}
    rows=[]
    for label,c in options.items():
        for t in targets:
            # Every comparison searches the same candidate pool, excluding all 19 evaluation cases.
            report=workflow.run(t,c,training,candidate_ids=training.index.tolist())
            rows.append({'weight_policy':label,**flatten_result(report,float(y[workflow.ticker[t]]))})
    return pd.DataFrame(rows),summary,folds,{'learned_weights':learned,'training_companies':len(training),
        'evaluation_companies':len(target_ids),'training_ids':training.index.tolist(),
        'target_ids':target_ids,'inner_folds':5,'objective':'mean absolute log error',
        'interpretation':'Computationally separated development evaluation; prior inspection prevents an untouched-test claim.'}
