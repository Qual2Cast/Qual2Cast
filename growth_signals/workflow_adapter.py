"""Expose the existing event-feature output to company valuation reports.

The event extractor and temporal feature code remain in growth_signals/. This
adapter does not invent a growth forecast when historical outcomes are missing.
"""
def growth_evidence(features,ticker,arm='decimal_guard_extension'):
    if features is None:
        return []
    return features[(features.ticker==ticker)&(features.arm==arm)].to_dict('records')
