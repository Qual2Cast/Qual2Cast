"""Named stage configuration; no company observations."""
from dataclasses import dataclass, asdict
import hashlib, json
import numpy as np
from matching.activity import ACTIVITY_METHODS
FACTOR_SETS = {
    'business_only': (), 'revenue': ('revenue',), 'margin': ('margin',),
    'leverage': ('debt_to_revenue',),
    'revenue_margin': ('revenue', 'margin'),
    'revenue_leverage': ('revenue', 'debt_to_revenue'),
    'margin_leverage': ('margin', 'debt_to_revenue'),
    'all_three': ('revenue', 'margin', 'debt_to_revenue'),
}
RETRIEVERS = ('mpnet', 'tfidf', 'lsa', 'rrf', 'z2', 'mutual20',
              'cluster_eom', 'tree_complete', 'tree_ward')
PRIMARY_RETRIEVERS = RETRIEVERS
RETRIEVERS = RETRIEVERS + tuple(ACTIVITY_METHODS)
AGGREGATORS = ('median', 'harmonic', 'geometric', 'rank_weighted')

@dataclass(frozen=True)
class Configuration:
    retrieval: str = 'mpnet'
    factors: str = 'business_only'
    aggregation: str = 'median'
    shortlist: int = 20
    k: int = 5
    min_peers: int = 3
    factor_weights: tuple = ()
    review_gate: str = 'off'

    def __post_init__(self):
        if self.retrieval not in RETRIEVERS or self.factors not in FACTOR_SETS:
            raise ValueError('Unknown retrieval or factor policy')
        if self.aggregation not in AGGREGATORS:
            raise ValueError('Unknown aggregation')
        if not 1 <= self.min_peers <= self.k <= self.shortlist:
            raise ValueError('Require 1 <= min_peers <= k <= shortlist')
        if self.review_gate not in ('off', 'model_supported'):
            raise ValueError('Unknown review gate')
        if self.factor_weights:
            w = np.asarray(self.factor_weights, float)
            if len(w) != len(FACTOR_SETS[self.factors]) or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
                raise ValueError('Factor weights must be finite nonnegative and match selected factors')

    @property
    def key(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()[:12]
