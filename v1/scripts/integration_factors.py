"""Compare private-supplied factor subsets after a fixed business shortlist."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pre-v0"))
from matching.factors import rank_distances  # noqa: E402
from pipeline.config import FACTOR_SETS  # noqa: E402
from valuation.aggregators import aggregate_multiple  # noqa: E402

V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/factors"
FIELDS = {"revenue": "target_revenue", "margin": "target_margin",
          "debt_to_revenue": "target_debt_to_revenue"}
AGGREGATORS = ("mean", "weighted_mean", "median", "harmonic", "geometric", "rank_weighted")


def aggregate(peers: pd.DataFrame, method: str) -> dict:
    values = peers["target_ev_to_ebitda"].to_numpy(float)
    if method not in ("mean", "weighted_mean"):
        return aggregate_multiple(values, method, min_peers=3)
    valid = np.isfinite(values) & (values > 0)
    if valid.sum() < 3:
        return {"multiple": None, "valid_peers": int(valid.sum()),
                "status": "abstain_insufficient_positive_multiples"}
    weights = peers.loc[valid, "similarity"].clip(lower=0).to_numpy(float)
    estimate = (np.average(values[valid], weights=weights) if method == "weighted_mean" and weights.sum()
                else float(np.mean(values[valid])))
    return {"multiple": float(estimate), "valid_peers": int(valid.sum()), "status": "exploratory_snapshot"}


def main() -> None:
    shortlist = pd.read_csv(V1 / "integration/scope_eval/holdout_top10.csv",
                            dtype={"target": str, "comp": str})
    shortlist = shortlist[shortlist["method"] == "Sonnet dated corrections"]
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    training = split.loc[split["sample"] == "training", "IQ_COMPANY_ID"]
    holdout = split.loc[split["sample"] == "holdout", "IQ_COMPANY_ID"]
    reference = financials.reindex(training).rename(columns={v: k for k, v in FIELDS.items()})
    results, chosen_rows = [], []
    for target in holdout:
        own = financials.loc[target].rename(index={v: k for k, v in FIELDS.items()})
        original = shortlist[shortlist["target"] == target].sort_values("rank").copy()
        if len(original) != 10:
            raise ValueError(f"Expected ten fixed business candidates: {target}")
        peer_fields = financials.reindex(original["comp"]).rename(columns={v: k for k, v in FIELDS.items()})
        for policy, columns in FACTOR_SETS.items():
            selected = original.copy()
            selected["factor_distance"] = rank_distances(own, peer_fields, reference, columns)
            selected = selected[np.isfinite(selected["factor_distance"])].sort_values(
                ["factor_distance", "rank", "comp"], kind="stable")
            for count in (3, 5, 10):
                peers = selected.head(count).copy()
                peers["factor_set"] = policy
                peers["peer_budget"] = count
                chosen_rows.append(peers)
                values = financials.reindex(peers["comp"]).reset_index(drop=True)
                values["similarity"] = peers["similarity"].to_numpy(float)
                for estimator in AGGREGATORS:
                    output = aggregate(values, estimator)
                    actual = own["target_ev_to_ebitda"]
                    estimate = output["multiple"]
                    results.append({"target": target, "factor_set": policy,
                                    "factors": "; ".join(columns), "peer_budget": count,
                                    "aggregation": estimator, "selected_peers": len(peers),
                                    "valid_peers": output["valid_peers"], "status": output["status"],
                                    "estimate": estimate, "actual": actual,
                                    "absolute_percentage_error":
                                    abs(estimate / actual - 1) * 100 if estimate is not None and actual > 0 else np.nan})
    table = pd.DataFrame(results)
    if table.duplicated(["target", "factor_set", "peer_budget", "aggregation"]).any():
        raise ValueError("Duplicate factor configuration/target")
    summary = table.groupby(["factor_set", "peer_budget", "aggregation"], as_index=False).agg(
        targets=("target", "nunique"), coverage=("estimate", "count"),
        median_ape=("absolute_percentage_error", "median"),
        mean_ape=("absolute_percentage_error", "mean"))
    baseline = table[table["factor_set"] == "business_only"][
        ["target", "peer_budget", "aggregation", "absolute_percentage_error"]].rename(
            columns={"absolute_percentage_error": "baseline_ape"})
    paired = table.merge(baseline, on=["target", "peer_budget", "aggregation"], how="left")
    paired["paired_delta"] = paired["absolute_percentage_error"] - paired["baseline_ape"]
    changes = paired.groupby(["factor_set", "peer_budget", "aggregation"], as_index=False).agg(
        common_targets=("paired_delta", "count"),
        median_paired_delta=("paired_delta", "median"),
        mean_paired_delta=("paired_delta", "mean"),
        targets_better=("paired_delta", lambda x: int((x < 0).sum())),
        targets_worse=("paired_delta", lambda x: int((x > 0).sum())),
        targets_equal=("paired_delta", lambda x: int((x == 0).sum())))
    summary = summary.merge(changes, on=["factor_set", "peer_budget", "aggregation"])
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "target_results.csv", index=False)
    pd.concat(chosen_rows).to_csv(OUT / "selected_peers.csv", index=False)
    summary.to_csv(OUT / "method_results.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({"shortlist": "Sonnet dated corrections B3 top ten",
       "targets": len(holdout), "pool": len(training), "factor_sets": list(FACTOR_SETS),
       "aggregators": AGGREGATORS,
       "caution": "Snapshot financial periods and units require verification; exploratory public-as-private test"}, indent=2), encoding="utf-8")
    print(summary.query("peer_budget == 5 and aggregation == 'median'").to_string(index=False))


if __name__ == "__main__":
    main()
