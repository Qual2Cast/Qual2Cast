"""Compare facet conditions on the same targets for each selection route."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration/holdout_routes"
OUT = BASE / "condition_comparison.csv"
PAIRS = (("control_sonnet", "gpt_general"),
         ("gpt_general", "gpt_all"),
         ("control_sonnet", "gpt_all"))


def errors(condition: str) -> pd.DataFrame:
    path = BASE / condition / "evaluation/target_results.csv"
    table = pd.read_csv(path, dtype={"target": str})
    if table.duplicated(["method", "target"]).any():
        raise ValueError(f"Duplicate target error: {condition}")
    return table.pivot(index="target", columns="method", values="error %").abs()


def main() -> None:
    sources = {name: errors(name) for pair in PAIRS for name in pair}
    rows = []
    for left_name, right_name in PAIRS:
        left, right = sources[left_name], sources[right_name]
        if set(left.index) != set(right.index) or len(left.index) != 160:
            raise ValueError("Facet conditions use different target IDs")
        if set(left.columns) != set(right.columns):
            raise ValueError("Facet conditions use different selection routes")
        for method in left.columns:
            pair = pd.concat([left[method].rename("old"), right[method].rename("new")],
                             axis=1).dropna()
            a, b = pair["old"].to_numpy(), pair["new"].to_numpy()
            if not len(pair):
                continue
            sample = np.random.default_rng(4511).integers(0, len(pair), (2000, len(pair)))
            gains = np.median(a[sample], axis=1) - np.median(b[sample], axis=1)
            rows.append({"old_condition": left_name, "new_condition": right_name,
                         "method": method, "common_targets": len(pair),
                         "old_median_ape_common": float(np.median(a)),
                         "new_median_ape_common": float(np.median(b)),
                         "median_gain_percentage_points": float(np.median(a) - np.median(b)),
                         "gain_ci_low": float(np.quantile(gains, .025)),
                         "gain_ci_high": float(np.quantile(gains, .975)),
                         "targets_better": int((b < a).sum()),
                         "targets_worse": int((b > a).sum()),
                         "targets_equal": int((b == a).sum())})
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(pd.DataFrame(rows)[["old_condition", "new_condition", "method",
                              "common_targets", "median_gain_percentage_points"]].to_string(index=False))


if __name__ == "__main__":
    main()
