"""Compare ranked peers only where Barbara supplied a 0–2 label."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration"


def ndcg_at_3(grades: np.ndarray) -> float:
    gains = np.power(2.0, grades) - 1.0
    discounts = np.log2(np.arange(2, 5))
    observed = float(np.sum(gains[:3] / discounts))
    ideal = float(np.sum(np.sort(gains)[::-1][:3] / discounts))
    return observed / ideal if ideal else np.nan


def main() -> None:
    labels = pd.read_csv(BASE / "review/pairs.csv", dtype={"target_id": str, "comp_id": str})
    labels = labels.rename(columns={"target_id": "target", "comp_id": "comp",
                                    "score_barbara": "grade"})[["target", "comp", "grade"]]
    if len(labels) != 293 or labels[["target", "comp"]].duplicated().any():
        raise ValueError("The reviewer cohort changed")
    rows = []
    for condition in ("candidate_methods", "candidate_methods_gpt", "candidate_methods_cited"):
        path = BASE / condition
        ranks = pd.read_csv(path / "rankings.csv.gz",
                            dtype={"target": str, "comp": str, "method": str})
        observed = ranks.merge(labels, on=["target", "comp"], validate="many_to_one")
        if observed[["method", "target", "comp"]].duplicated().any():
            raise ValueError(f"Duplicate ranked peer in {condition}")
        for method, subset in observed.groupby("method", sort=True):
            precision, ndcg = [], []
            for _, target in subset.groupby("target"):
                target = target.sort_values("rank", kind="stable")
                if len(target) < 3:
                    continue
                grades = target["grade"].to_numpy(dtype=float)
                precision.append(float(np.mean(grades[:3] >= 1)))
                ndcg.append(ndcg_at_3(grades))
            rows.append({
                "facet_source": condition,
                "method": method,
                "reviewed_pairs_ranked": len(subset),
                "reviewed_targets_ranked": subset["target"].nunique(),
                "targets_with_three_reviewed_peers": len(precision),
                "labeled_precision_at_3": float(np.mean(precision)) if precision else np.nan,
                "labeled_ndcg_at_3": float(np.nanmean(ndcg)) if np.isfinite(ndcg).any() else np.nan,
                "reviewed_pairs_in_actual_top_10": int((subset["rank"] <= 10).sum()),
            })
    result = pd.DataFrame(rows)
    if result.groupby("facet_source")["method"].nunique().to_dict() != {
        name: 20 for name in ("candidate_methods", "candidate_methods_gpt", "candidate_methods_cited")
    }:
        raise ValueError("Expected 20 methods for each facet source")
    result.to_csv(BASE / "reviewed_rank_metrics.csv", index=False)
    print(result.groupby("facet_source")["method"].nunique().to_string())


if __name__ == "__main__":
    main()
