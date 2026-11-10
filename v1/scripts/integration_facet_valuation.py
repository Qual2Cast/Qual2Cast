"""Value the fixed 160 targets under every saved B3 facet configuration."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import facet_eval as fe
import facet_weighting as fw
import integration_facet_293 as facets
import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/facet_valuation"


def main() -> None:
    ids, training, variants = facets.build_variants()
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    targets = split.loc[split["sample"] == "holdout", "IQ_COMPANY_ID"].tolist()
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    actual = multiples.reindex(targets)
    results = {"No matching": vl.no_matching(targets, training, multiples)}
    peer_rows = []
    for index, (name, similarity) in enumerate(variants.items(), 1):
        ranked = fe.rank(similarity, ids, targets, training)
        top = ranked[ranked["rank"] <= 10].copy()
        selected = fw.mutual_top_k(similarity, ids, targets, training)
        for rule, peers, weight, how in (
            ("top 10 weighted mean", top, "similarity", "mean"),
            ("top 10 median", top, None, "median"),
            ("mutual/top-up weighted mean", selected, "similarity", "mean"),
        ):
            results[f"{name}: {rule}"] = vl.estimate(peers, multiples, weight=weight, how=how)
            if rule in ("top 10 weighted mean", "mutual/top-up weighted mean"):
                peer_rows.append(peers.assign(variant=name, rule=rule))
        print(f"[{index}/{len(variants)}] {name}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    summary = vl.summary(results, actual, "No matching").reset_index()
    summary[["variant", "rule"]] = summary["comp rule"].str.rsplit(": ", n=1, expand=True)
    summary.loc[summary["comp rule"] == "No matching", ["variant", "rule"]] = ["No matching", "baseline"]
    summary.to_csv(OUT / "summary.csv", index=False)
    pd.concat(peer_rows, ignore_index=True).to_csv(OUT / "selected_peers.csv", index=False)
    target_rows = []
    for name, result in results.items():
        errors = vl.errors(result, actual)
        errors["target"] = errors.index
        errors["method"] = name
        target_rows.append(errors.reset_index(drop=True))
    pd.concat(target_rows, ignore_index=True).to_csv(OUT / "target_results.csv", index=False)
    baseline = vl.errors(results["B3 Sonnet: top 10 weighted mean"], actual)["error %"].abs()
    rng = np.random.default_rng(2026)
    intervals = []
    for name, result in results.items():
        ape = vl.errors(result, actual)["error %"].abs()
        common = baseline.index.intersection(ape.index)
        if name == "No matching" or not len(common):
            continue
        delta = baseline.loc[common].to_numpy() - ape.loc[common].to_numpy()
        draws = rng.choice(delta, size=(2000, len(delta)), replace=True).mean(axis=1)
        intervals.append({"method": name, "common_targets": len(common),
                          "mean_ape_gain_vs_b3_sonnet": float(np.mean(delta)),
                          "bootstrap_low": float(np.quantile(draws, .025)),
                          "bootstrap_high": float(np.quantile(draws, .975))})
    pd.DataFrame(intervals).to_csv(OUT / "paired_gains.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "pool": "373 fixed training peers", "targets": len(targets),
        "facet_variants": len(variants), "valuation_rules_per_variant": 3,
        "status": "development; the 160 targets have informed team decisions"
    }, indent=2), encoding="utf-8")
    print(summary.sort_values("median abs % error").head(15)[
        ["comp rule", "targets", "median abs % error"]].to_string(index=False))


if __name__ == "__main__":
    main()
