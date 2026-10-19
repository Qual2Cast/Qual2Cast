"""Measure retention of original rankings, without calling it relevance recall."""
from pathlib import Path
import json
import os
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('QUAL2CAST_EXPERIMENT_DIR', ROOT / 'outputs-local/pilot-validation-2026-10-18'))
if not OUT.is_absolute():
    OUT = ROOT / OUT


def main():
    ids = set(json.loads((OUT / 'candidate_pool_freeze.json').read_text())['company_ids'])
    rankings = pd.read_csv(OUT / 'global-controls/core/rankings.csv')
    rows = []
    for (target, method), group in rankings.groupby(['target_id', 'method']):
        group = group[group['rank'].notna()].sort_values('rank')
        for k in [3, 5, 10]:
            top = group.head(k)
            retained = top.candidate_id.isin(ids)
            rows.append({'target_id': target, 'method': method, 'k': k,
                         'original_returned': len(top),
                         'retained_in_common_pilot': int(retained.sum()),
                         'ranked_candidate_retention': float(retained.mean()) if len(top) else None,
                         'omitted_original_ids': '|'.join(top.loc[~retained, 'candidate_id']),
                         'interpretation': 'Coverage of original ranking only, not relevance recall; pool selected partly using four original retrievers.'})
    pd.DataFrame(rows).to_csv(OUT / 'candidate_pool_retention.csv', index=False)
    print('POOL_RETENTION_AUDIT_COMPLETE', len(rows))


if __name__ == '__main__':
    main()
