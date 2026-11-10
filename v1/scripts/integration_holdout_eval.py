"""Evaluate frozen B3 and three LLM routes on identical v1 holdout targets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from llm_then_cosine import rank_selected
import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
SPLIT = V1 / "split/20261027T204930Z/split.csv"
FINANCIALS = V1 / "universe/20261025T060358Z/financials.csv"


def evaluate(candidates: Path, llm: Path, output: Path) -> None:
    config = json.loads((candidates / "run.json").read_text(encoding="utf-8"))
    model_run = json.loads((llm / "llm_run.json").read_text(encoding="utf-8"))
    split = pd.read_csv(SPLIT, dtype=str)
    targets = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    training = split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"].tolist()
    if len(targets) != 160 or len(training) != 373 or not model_run["complete"]:
        raise ValueError("A complete fixed-split LLM run is required")
    if model_run["candidate_run"] != str(candidates):
        raise ValueError("LLM run and candidate inputs differ")
    ranking = pd.read_csv(candidates / "ranking.csv.gz", dtype={"target": str, "comp": str})
    chosen = pd.read_csv(candidates / "candidates.csv", dtype={"target": str, "comp": str})
    direct = pd.read_csv(llm / "direct.csv", dtype={"target": str, "comp": str})
    judgment = pd.read_csv(llm / "judge.csv", dtype={"target": str, "comp": str})
    expected = len(targets) * len(training)
    if len(ranking) != expected or ranking.duplicated(["target", "comp"]).any():
        raise ValueError("Candidate rankings are incomplete or duplicated")
    if not set(ranking["target"]) == set(targets) or not set(ranking["comp"]) == set(training):
        raise ValueError("Candidate ranking identities differ from the fixed split")
    for table in (chosen, direct, judgment):
        if table.duplicated(["target", "comp"]).any():
            raise ValueError("Duplicate peer decisions")
        if not set(table["target"]) <= set(targets) or not set(table["comp"]) <= set(training):
            raise ValueError("A peer decision is outside the fixed split")
    shortlist = chosen[chosen["selected"].astype(str).str.lower().eq("true")]
    if len(judgment.merge(shortlist[["target", "comp"]], on=["target", "comp"],
                          how="left", indicator=True).query("_merge != 'both'")):
        raise ValueError("Judge evaluated a peer outside the frozen shortlist")
    if judgment["score"].isna().any() or not judgment["score"].isin([0, 1]).all():
        raise ValueError("The binary judge left ungraded candidates")

    multiples = pd.read_csv(FINANCIALS, dtype={"IQ_COMPANY_ID": str}).set_index(
        "IQ_COMPANY_ID")["target_ev_to_ebitda"]
    actual = multiples.reindex(targets)
    good = judgment[judgment["score"].eq(1)].merge(
        ranking[["target", "comp", "similarity"]], on=["target", "comp"],
        how="left", validate="one_to_one")
    reranked = rank_selected(direct, ranking)
    methods = {
        "No matching": vl.no_matching(targets, training, multiples),
        "B3 selected": vl.estimate(shortlist, multiples, weight="similarity"),
        "B3 top 10": vl.estimate(ranking[ranking["rank"] <= 10], multiples,
                                  weight="similarity"),
        "B3 then LLM": vl.estimate(good, multiples, weight="similarity"),
        "Direct LLM": vl.estimate(direct, multiples),
        "LLM then B3": vl.estimate(reranked, multiples, weight="similarity"),
    }
    summary = vl.summary(methods, actual, "No matching").reset_index()
    output.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output / "summary.csv", index=False)
    pd.concat({name: vl.errors(table, actual).reindex(targets)
               for name, table in methods.items()}, names=["method", "target"]).to_csv(
        output / "target_results.csv")
    good.to_csv(output / "judge_kept.csv", index=False)
    reranked.to_csv(output / "llm_then_b3_peers.csv", index=False)
    errors = pd.concat({name: vl.errors(table, actual)["error %"].abs()
                        for name, table in methods.items()}, axis=1)
    full_common = errors.dropna()
    rng = np.random.default_rng(2026)
    comparisons = []
    for name in methods:
        pair = errors[["B3 selected", name]].dropna() if name != "B3 selected" else errors[[name]].dropna()
        if pair.empty:
            comparisons.append({"method": name, "common_targets": 0,
                                "median_ape_common": np.nan, "median_paired_gain_vs_b3": np.nan,
                                "gain_ci_low": np.nan, "gain_ci_high": np.nan,
                                "targets_better_than_b3": 0})
            continue
        delta = (pair["B3 selected"] - pair[name]).to_numpy() if name != "B3 selected" else np.zeros(len(pair))
        boot = rng.integers(0, len(delta), (2000, len(delta)))
        medians = np.median(delta[boot], axis=1)
        comparisons.append({"method": name, "common_targets": len(pair),
                            "median_ape_common": float(pair[name].median()),
                            "median_paired_gain_vs_b3": float(np.median(delta)),
                            "gain_ci_low": float(np.quantile(medians, .025)),
                            "gain_ci_high": float(np.quantile(medians, .975)),
                            "targets_better_than_b3": int((delta > 0).sum())})
    pd.DataFrame(comparisons).to_csv(output / "paired_common.csv", index=False)
    (output / "run.json").write_text(json.dumps({
        "model": model_run["model"], "candidate_rule": model_run["candidate_rule"],
        "targets": len(targets), "training_pool": len(training),
        "llm_candidates": len(judgment), "direct_peers": len(direct),
        "common_targets_all_routes": len(full_common),
        "candidate_sha256": hashlib.sha256((candidates / "candidates.csv").read_bytes()).hexdigest(),
        "judge_sha256": hashlib.sha256((llm / "judge.csv").read_bytes()).hexdigest(),
        "direct_sha256": hashlib.sha256((llm / "direct.csv").read_bytes()).hexdigest(),
        "status": "development: no independent final labels or private outcomes",
    }, indent=2), encoding="utf-8")
    print(summary[["comp rule", "targets", "median abs % error"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--llm", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.candidates, args.llm, args.out)
