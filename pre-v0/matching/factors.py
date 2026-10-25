"""Replaceable factor-distance methods; no valuation outcome input."""
import numpy as np

def rank_distances(target, candidates, reference, columns, weights=()):
    """Reference-only empirical percentile distances; missing values never match.

    Percentiles are mid-distribution ranks (ties receive their midpoint). This
    is a SARD-inspired adaptation, not a replication of its original variables.
    """
    if not columns:
        return np.zeros(len(candidates))
    parts = []
    for col in columns:
        ref = np.sort(reference[col].dropna().to_numpy(float))
        if not len(ref) or not np.isfinite(target[col]):
            return np.full(len(candidates), np.inf)
        def percentile(x):
            return (np.searchsorted(ref,x,'left') + np.searchsorted(ref,x,'right')) / (2*len(ref))
        x = candidates[col].to_numpy(float)
        parts.append(np.where(np.isfinite(x), abs(percentile(x)-percentile(target[col])), np.inf))
    w = np.asarray(weights if weights else np.ones(len(columns)), float)
    positive = w > 0
    return np.average(np.asarray(parts)[positive], axis=0, weights=w[positive])
