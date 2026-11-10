"""Compare the existing factor policies on each saved GPT B3 shortlist."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration"
INPUT = BASE / "factors_by_facet"
OUTPUT = INPUT / "comparison.csv"


def main() -> None:
    old = pd.read_csv(BASE / "factors/method_results.csv").sort_values(
        ["factor_set", "peer_budget", "aggregation"]).reset_index(drop=True)
    control = pd.read_csv(INPUT / "sonnet_control/method_results.csv").sort_values(
        ["factor_set", "peer_budget", "aggregation"]).reset_index(drop=True)
    if not old.equals(control):
        raise ValueError("Parameterized factor runner changed the saved Sonnet control")

    frames = []
    source_hashes = {}
    for folder in sorted(path for path in INPUT.iterdir() if path.is_dir() and path.name != "sonnet_control"):
        run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        source = Path(run["shortlist_path"])
        if not source.is_absolute():
            source = ROOT / source
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != run["shortlist_sha256"]:
            raise ValueError(f"Candidate input changed: {folder.name}")
        source_hashes[folder.name] = digest
        target = pd.read_csv(folder / "target_results.csv", dtype={"target": str})
        if (len(target) != 160 * 8 * 3 * 6 or target["target"].nunique() != 160
                or target.duplicated(["target", "factor_set", "peer_budget", "aggregation"]).any()):
            raise ValueError(f"Incomplete factor run: {folder.name}")
        target["facet_condition"] = folder.name
        frames.append(target)
    if len(frames) != 12:
        raise ValueError("Expected the twelve saved GPT facet conditions")
    all_targets = pd.concat(frames, ignore_index=True)
    keys = ["target", "factor_set", "peer_budget", "aggregation"]
    base = all_targets[all_targets["facet_condition"].eq("gpt_general")][
        keys + ["absolute_percentage_error"]].rename(
        columns={"absolute_percentage_error": "general_ape"})
    paired = all_targets.merge(base, on=keys, validate="many_to_one")
    paired["error_gain_vs_general"] = (
        paired["general_ape"] - paired["absolute_percentage_error"])
    groups = ["facet_condition", "factor_set", "peer_budget", "aggregation"]
    summary = paired.groupby(groups, as_index=False).agg(
        coverage=("estimate", "count"),
        median_ape=("absolute_percentage_error", "median"),
        common_targets=("error_gain_vs_general", "count"),
        median_paired_gain=("error_gain_vs_general", "median"),
        mean_paired_gain=("error_gain_vs_general", "mean"),
        targets_better=("error_gain_vs_general", lambda x: int((x > 0).sum())),
        targets_worse=("error_gain_vs_general", lambda x: int((x < 0).sum())),
    )
    if len(summary) != 12 * 8 * 3 * 6 or not summary["coverage"].between(0, 160).all():
        raise ValueError("Incomplete facet-by-factor comparison")
    summary.to_csv(OUTPUT, index=False)
    (INPUT / "run.json").write_text(json.dumps({
        "facet_conditions": 12, "factor_sets": 8, "peer_budgets": [3, 5, 10],
        "aggregators": 6, "targets_per_condition": 160,
        "rows": len(summary), "sonnet_control_reproduced": True,
        "source_sha256": source_hashes,
        "interpretation": "Public development sample; exploratory financial factors supplied by a private target",
    }, indent=2), encoding="utf-8")
    selected = summary[summary["peer_budget"].eq(5) & summary["aggregation"].eq("median")]
    print(selected[["facet_condition", "factor_set", "coverage", "median_ape",
                    "median_paired_gain"]].to_string(index=False))


if __name__ == "__main__":
    main()
