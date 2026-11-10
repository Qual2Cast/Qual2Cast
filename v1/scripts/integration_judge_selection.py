"""Evaluate the team's two judge filters on the same frozen reviewed pairs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
BASE = V1 / "integration"
OUT = BASE / "judge_gpt61sol/eval_293"


def main() -> None:
    frozen = pd.read_csv(BASE / "judge_input_293/candidates.csv",
                         dtype={"target": str, "comp": str})
    reviewed = pd.read_csv(BASE / "review/pairs.csv",
                           dtype={"target_id": str, "comp_id": str}).rename(
        columns={"target_id": "target", "comp_id": "comp", "score_barbara": "human"})
    judged = pd.read_csv(BASE / "judge_gpt61sol/verdicts.csv",
                         dtype={"target": str, "comp": str})
    if (len(frozen) != len(reviewed) or len(judged) != len(reviewed)
            or any(frame.duplicated(["target", "comp"]).any()
                   for frame in (frozen, reviewed, judged))):
        raise ValueError("The 293-pair cohort is incomplete or duplicated")
    pairs = frozen.merge(reviewed[["target", "comp", "human"]], on=["target", "comp"],
                         validate="one_to_one").merge(
        judged[["target", "comp", "score", "status"]], on=["target", "comp"],
        validate="one_to_one")
    if len(pairs) != 293 or not pairs["human"].isin([0, 1, 2]).all():
        raise ValueError("The reviewer cohort changed")
    pairs["score"] = pd.to_numeric(pairs["score"], errors="coerce")
    if not pairs["score"].dropna().isin([0, 1, 2]).all():
        raise ValueError("Judge grades must use the 0–2 rubric")
    lists = {
        "Reviewed B3 pairs": pairs,
        "Judge score >= 1": pairs[pairs["score"].ge(1)],
        "Judge score = 2": pairs[pairs["score"].eq(2)],
    }
    measures = []
    for name, selected in lists.items():
        measures.append({
            "rule": name, "selected_pairs": len(selected),
            "targets_with_pairs": selected["target"].nunique(),
            "reviewed_direct_kept": int(selected["human"].eq(2).sum()),
            "reviewed_adjacent_kept": int(selected["human"].eq(1).sum()),
            "reviewed_nonpeer_kept": int(selected["human"].eq(0).sum()),
            "good_recall": float(selected["human"].ge(1).sum() /
                                 pairs["human"].ge(1).sum()),
            "selected_good_fraction": float(selected["human"].ge(1).mean())
            if len(selected) else np.nan,
        })
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    training = split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"].tolist()
    targets = sorted(pairs["target"].unique())
    if not set(targets).issubset(training):
        raise ValueError("The reviewer cohort is not entirely in the training split")
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    estimates = {name: vl.estimate(selected, multiples, weight="similarity")
                 for name, selected in lists.items()}
    estimates["No matching"] = vl.no_matching(targets, training, multiples)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(measures).to_csv(OUT / "selection_metrics.csv", index=False)
    vl.summary(estimates, multiples.reindex(targets), "No matching").to_csv(
        OUT / "selection_valuation.csv")
    vl.bootstrap(estimates, multiples.reindex(targets), "No matching").to_csv(
        OUT / "selection_intervals.csv")
    rows = []
    for name, result in estimates.items():
        errors = vl.errors(result, multiples.reindex(targets))
        rows.extend({"target": target, "rule": name, **item.to_dict()}
                    for target, item in errors.iterrows())
    pd.DataFrame(rows).to_csv(OUT / "selection_target_errors.csv", index=False)
    baseline = vl.errors(estimates["Reviewed B3 pairs"], multiples.reindex(targets))["error %"].abs()
    comparisons = []
    for name in ("Judge score >= 1", "Judge score = 2"):
        alternative = vl.errors(estimates[name], multiples.reindex(targets))["error %"].abs()
        common = pd.DataFrame({"baseline_ape": baseline, "filtered_ape": alternative}).dropna()
        a, b = common["baseline_ape"].to_numpy(), common["filtered_ape"].to_numpy()
        draws = np.random.default_rng(2026).integers(0, len(common), (2000, len(common)))
        gain = np.median(a[draws], axis=1) - np.median(b[draws], axis=1)
        comparisons.append({"rule": name, "common_targets": len(common),
                            "baseline_median_ape": float(np.median(a)),
                            "filtered_median_ape": float(np.median(b)),
                            "filtered_gain_percentage_points": float(np.median(a) - np.median(b)),
                            "gain_ci_low": float(np.quantile(gain, .025)),
                            "gain_ci_high": float(np.quantile(gain, .975))})
    pd.DataFrame(comparisons).to_csv(OUT / "selection_paired.csv", index=False)
    (OUT / "selection_run.json").write_text(json.dumps({
        "pair_count": len(pairs), "targets": len(targets),
        "reviewer": "Barbara, one reviewer", "candidate_source": "frozen reviewed B3 pairs",
        "rules": list(lists),
        "interpretation": "Same reviewed-pair cohort only; not a full holdout policy test."
    }, indent=2), encoding="utf-8")
    print(pd.DataFrame(measures).to_string(index=False))
    print(pd.read_csv(OUT / "selection_valuation.csv").to_string(index=False))


if __name__ == "__main__":
    main()
