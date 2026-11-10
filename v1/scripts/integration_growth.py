"""Re-score the saved growth-event rule benchmark by cohort and event type."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pre-v0"))
from growth_signals.eval.score_rules import DEFAULT_DIR, SETS, score_set  # noqa: E402

OUT = ROOT / "outputs-local/v1/integration/growth"


def main() -> None:
    rows, errors = [], []
    for cohort in SETS:
        labels = json.loads((DEFAULT_DIR / f"labels_{cohort}.json").read_text(encoding="utf-8"))
        scored = score_set(labels, DEFAULT_DIR / "records" / cohort)
        for event_type, item in scored["rows"].items():
            rows.append({"cohort": cohort, "event_type": event_type, **item,
                         "precision": item["correct"] / item["predicted"] if item["predicted"] else None,
                         "recall": item["correct"] / item["true"] if item["true"] else None})
        for key in sorted(scored["scored"] - scored["truth"]):
            errors.append({"cohort": cohort, "kind": "false_positive", "company": key[0],
                           "page": key[1], "event_type": key[2]})
        for key in sorted(scored["truth"] - set(scored["predicted"])):
            errors.append({"cohort": cohort, "kind": "false_negative", "company": key[0],
                           "page": key[1], "event_type": key[2]})
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "rule_metrics.csv", index=False)
    pd.DataFrame(errors).to_csv(OUT / "rule_errors.csv", index=False)
    print(pd.DataFrame(rows).query("event_type == 'ALL'").to_string(index=False))


if __name__ == "__main__":
    main()
