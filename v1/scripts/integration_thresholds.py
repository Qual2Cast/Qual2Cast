"""Calibrate a B3 z cutoff on reviewer targets, then test valuation separately."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
BASE = V1 / "integration"
OUT = BASE / "thresholds"
GRID = tuple(float(x) for x in np.arange(2, 5.01, .25))
METHOD = "B3 embedding plus TF-IDF"


def balanced(rows: pd.DataFrame, threshold: float) -> float:
    good = rows["grade"].ge(1)
    predicted = rows["z"].ge(threshold)
    return float((predicted[good].mean() + (~predicted[~good]).mean()) / 2)


def choose(rows: pd.DataFrame) -> float:
    if not rows["grade"].ge(1).any() or not rows["grade"].eq(0).any():
        raise ValueError("Threshold training needs positive and negative reviewer pairs")
    return min(GRID, key=lambda threshold: (-balanced(rows, threshold), threshold))


def main() -> None:
    ranking = pd.read_csv(BASE / "candidate_methods/rankings.csv.gz",
                          usecols=["target", "comp", "method", "rank", "similarity"],
                          dtype={"target": str, "comp": str})
    ranking = ranking[ranking["method"].eq(METHOD)].copy()
    stats = ranking.groupby("target")["similarity"]
    ranking["z"] = (ranking["similarity"] - stats.transform("mean")) / stats.transform("std")
    if ranking["z"].isna().any():
        raise ValueError("Every B3 target needs a nonconstant candidate score distribution")
    reviewer = pd.read_csv(BASE / "review/pairs.csv",
                           dtype={"target_id": str, "comp_id": str}).rename(
        columns={"target_id": "target", "comp_id": "comp", "score_barbara": "grade"})
    if len(reviewer) != 293 or reviewer.duplicated(["target", "comp"]).any():
        raise ValueError("The 293 reviewer pairs changed")
    labeled = reviewer[["target", "comp", "grade"]].merge(
        ranking[["target", "comp", "rank", "similarity", "z"]],
        on=["target", "comp"], validate="one_to_one")
    if len(labeled) != 293 or labeled["target"].nunique() != 45:
        raise ValueError("The B3 ranking does not cover the 45 reviewer targets")
    held_rows, fold_rows = [], []
    for target in sorted(labeled["target"].unique()):
        train = labeled[labeled["target"].ne(target)]
        held = labeled[labeled["target"].eq(target)].copy()
        threshold = choose(train)
        held["threshold"] = threshold
        held["selected"] = held["z"].ge(threshold)
        held_rows.append(held)
        fold_rows.append({"held_target": target, "threshold": threshold,
                          "training_pairs": len(train), "held_pairs": len(held)})
    crossfit = pd.concat(held_rows, ignore_index=True)
    good = crossfit["grade"].ge(1)
    accepted = crossfit["selected"]
    final_threshold = choose(labeled)
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    training = split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"].tolist()
    holdout = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    assert set(labeled["target"]).issubset(training)
    eligible = ranking[ranking["target"].isin(holdout)].copy()
    selected = eligible[eligible["z"].ge(final_threshold)].copy()
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    saved = pd.read_csv(BASE / "candidate_methods/selected_peers.csv",
                        usecols=["target", "comp", "method", "similarity"],
                        dtype={"target": str, "comp": str})
    fixed_b3 = saved[saved["method"].eq(METHOD) & saved["target"].isin(holdout)]
    estimates = {
        "No matching": vl.no_matching(holdout, training, multiples),
        "B3 fixed mutual top ten": vl.estimate(fixed_b3, multiples, weight="similarity"),
        "B3 reviewer-calibrated z": vl.estimate(selected, multiples, weight="similarity"),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    crossfit.to_csv(OUT / "reviewer_crossfit.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(OUT / "folds.csv", index=False)
    selected.to_csv(OUT / "holdout_selected_peers.csv", index=False)
    vl.summary(estimates, multiples.reindex(holdout), "No matching").to_csv(
        OUT / "valuation_summary.csv")
    vl.bootstrap(estimates, multiples.reindex(holdout), "No matching").to_csv(
        OUT / "valuation_intervals.csv")
    rows = []
    for name, result in estimates.items():
        errors = vl.errors(result, multiples.reindex(holdout))
        rows.extend({"target": target, "method": name, **item.to_dict()}
                    for target, item in errors.iterrows())
    pd.DataFrame(rows).to_csv(OUT / "target_errors.csv", index=False)
    fixed = vl.errors(estimates["B3 fixed mutual top ten"], multiples.reindex(holdout))["error %"].abs()
    learned = vl.errors(estimates["B3 reviewer-calibrated z"], multiples.reindex(holdout))["error %"].abs()
    common = pd.DataFrame({"fixed_b3_ape": fixed, "calibrated_ape": learned}).dropna()
    draws = np.random.default_rng(2026).integers(0, len(common), (2000, len(common)))
    a, b = common["fixed_b3_ape"].to_numpy(), common["calibrated_ape"].to_numpy()
    gains = np.median(a[draws], axis=1) - np.median(b[draws], axis=1)
    pd.DataFrame([{"common_targets": len(common),
                   "fixed_b3_median_ape": float(np.median(a)),
                   "calibrated_median_ape": float(np.median(b)),
                   "calibrated_gain_percentage_points": float(np.median(a) - np.median(b)),
                   "gain_ci_low": float(np.quantile(gains, .025)),
                   "gain_ci_high": float(np.quantile(gains, .975))}]).to_csv(
        OUT / "paired_comparison.csv", index=False)
    report = {
        "facet_source": "Yiming-corrected Sonnet general", "candidate_pool": len(training),
        "reviewer": "Barbara, one reviewer", "reviewed_pairs": len(labeled),
        "reviewer_targets": labeled["target"].nunique(), "development_targets": len(holdout),
        "grid": GRID, "objective": "target-disjoint balanced accuracy, ties favor recall",
        "final_threshold": final_threshold,
        "crossfit_balanced_accuracy": float((accepted[good].mean() + (~accepted[~good]).mean()) / 2),
        "crossfit_good_recall": float(accepted[good].mean()),
        "crossfit_bad_kept": int(accepted[~good].sum()),
        "holdout_targets_with_peers": selected["target"].nunique(),
        "note": "Cutoff learned only on training reviewer targets; 160 valuation targets remain development evidence.",
    }
    (OUT / "run.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(pd.read_csv(OUT / "valuation_summary.csv").to_string(index=False))


if __name__ == "__main__":
    main()
