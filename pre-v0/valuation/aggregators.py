"""Positive peer-multiple aggregation and dispersion diagnostics."""
import numpy as np

def aggregate_multiple(values, method, min_peers=3, _sensitivity=True):
    """Aggregate selected positive peer multiples, keeping peer weights explicit."""
    values = np.asarray(values, float)
    valid = np.isfinite(values) & (values > 0)
    v = values[valid]
    if len(v) < min_peers:
        return {'multiple':None,'valid_peers':int(len(v)),'peer_weights':[],
                'q25':None,'q75':None,'leave_one_peer_out_span':None,
                'status':'abstain_insufficient_positive_multiples'}
    if method == 'median':
        estimate = np.median(v); weights = []
    elif method == 'harmonic':
        estimate = len(v)/np.sum(1/v); weights = (np.ones(len(v))/len(v)).tolist()
    elif method == 'geometric':
        estimate = np.exp(np.mean(np.log(v))); weights = (np.ones(len(v))/len(v)).tolist()
    elif method == 'rank_weighted':
        # Preserve original selection ranks even when an invalid multiple is dropped.
        w = 1 / (np.flatnonzero(valid)+1); w = w / w.sum()
        estimate = np.dot(w,v); weights = w.tolist()
    else:
        raise ValueError(method)
    # Recompute this estimator; retain original ranks by masking, not deleting.
    leave = []
    if _sensitivity and len(v)>1:
        for j in np.flatnonzero(valid):
            masked=values.copy(); masked[j]=np.nan
            leave.append(aggregate_multiple(masked,method,min_peers=1,_sensitivity=False)['multiple'])
    return {'multiple':float(estimate),'valid_peers':int(len(v)), 'peer_weights':weights,
            'q25':float(np.quantile(v,.25)),'q75':float(np.quantile(v,.75)),
            'leave_one_peer_out_span':float(max(leave)-min(leave)) if leave else None,
            'sensitivity_meaning':'same estimator after omitting each peer; not a confidence interval',
            'status':'exploratory_snapshot'}
