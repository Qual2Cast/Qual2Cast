"""Conditional whole-activity methods from the morning experiment.

The cached model/transport scores have a smaller, explicitly identified pool.
They never silently fall back to the 535-company text experiment.
"""
import pandas as pd

ACTIVITY_METHODS={
    'activity_dense_control':'dense_same_profile_eligible_pool',
    'activity_centroid':'profile_centroid',
    'activity_balanced_ot':'balanced_ot',
    'activity_uot025':'uot_rho025',
    'activity_uot1':'uot_rho1',
    'activity_uot4':'uot_rho4',
}

def retrieve_activity(scores, descriptors, company_id, method, limit, candidate_ids=None):
    columns=['peer_id','peer','retrieval_rank','retrieval_score','measure','source_urls']
    if scores is None: return pd.DataFrame(columns=columns)
    data=descriptors.set_index('IQ_COMPANY_ID')
    ticker=data.loc[company_id,'target_ciq_ticker']
    rows=scores[(scores.target==ticker)&(scores.method==ACTIVITY_METHODS[method])].copy()
    allowed=set(candidate_ids) if candidate_ids is not None else set(data.index)
    allowed.discard(company_id)
    rows=rows[rows.peer_id.isin(allowed)].sort_values(['score','peer_id'],ascending=[False,True]).head(limit)
    return pd.DataFrame([{'peer_id':p.peer_id,'peer':data.loc[p.peer_id,'target_ciq_ticker'],
        'retrieval_rank':r,'retrieval_score':float(p.score),'measure':method,
        'source_urls':data.loc[p.peer_id,'urls']} for r,p in enumerate(rows.itertuples(),1)],columns=columns)
