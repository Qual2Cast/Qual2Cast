"""Compare the same retrieval rules across two facet sources on common targets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
BASE = V1 / "integration"
OUT = BASE / "retrieval_paired"


def main() -> None:
    sources = {"corrected_sonnet": BASE / "candidate_methods",
               "gpt_general": BASE / "candidate_methods_gpt"}
    runs = {name: json.loads((path / "run.json").read_text(encoding="utf-8"))
            for name, path in sources.items()}
    for run in runs.values():
        if (run["company_count"], run["pool"], run["valuation_targets"],
                run["reviewer"]) != (533, 373, 160, "Barbara, 293 pairs, 45 targets"):
            raise ValueError("The retrieval comparison inputs differ")
        facet_path = Path(run["facet_path"])
        if not facet_path.is_absolute():
            facet_path = ROOT / facet_path
        if hashlib.sha256(facet_path.read_bytes()).hexdigest() != run["facet_sha256"]:
            raise ValueError(f"Retrieval facet input changed: {facet_path}")
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    targets = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    metrics = {name: pd.read_csv(path / "reviewed_metrics.csv").set_index("method")
               for name, path in sources.items()}
    if set(metrics["corrected_sonnet"].index) != set(metrics["gpt_general"].index):
        raise ValueError("The two facet sources must use the same retrieval rules")
    peers = {name: pd.read_csv(path / "selected_peers.csv",
                               dtype={"target": str, "comp": str})
             for name, path in sources.items()}
    rng = np.random.default_rng(2026)
    rows, target_rows = [], []
    for method in metrics["corrected_sonnet"].index:
        errors = {}
        for source, table in peers.items():
            chosen = table[table["method"].eq(method) & table["target"].isin(targets)]
            estimate = vl.estimate(chosen, multiples, weight="similarity")
            errors[source] = vl.errors(estimate, multiples.reindex(targets))["error %"].abs()
        paired = pd.concat(errors, axis=1).reindex(targets)
        for target, item in paired.iterrows():
            target_rows.append({"method": method, "target": target,
                                "sonnet_absolute_percent_error": item["corrected_sonnet"],
                                "gpt_absolute_percent_error": item["gpt_general"]})
        both = paired.dropna()
        if both.empty:
            raise ValueError(f"No common valuation targets for {method}")
        sample = rng.integers(0, len(both), (2000, len(both)))
        a = both["corrected_sonnet"].to_numpy()
        b = both["gpt_general"].to_numpy()
        gains = np.median(a[sample], axis=1) - np.median(b[sample], axis=1)
        rows.append({"method": method, "common_targets": len(both),
                     "sonnet_median_ape_common": float(np.median(a)),
                     "gpt_median_ape_common": float(np.median(b)),
                     "gpt_gain_percentage_points": float(np.median(a) - np.median(b)),
                     "gain_ci_low": float(np.quantile(gains, .025)),
                     "gain_ci_high": float(np.quantile(gains, .975)),
                     "sonnet_pairwise_accuracy": metrics["corrected_sonnet"].loc[
                         method, "pairwise accuracy"],
                     "gpt_pairwise_accuracy": metrics["gpt_general"].loc[
                         method, "pairwise accuracy"]})
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "comparison.csv", index=False)
    pd.DataFrame(target_rows).to_csv(OUT / "target_errors.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "facet_sources": {name: run["facet_sha256"] for name, run in runs.items()},
        "rules": len(rows), "valuation_targets": len(targets),
        "interpretation": "paired development comparison; the two facet protocols differ",
    }, indent=2), encoding="utf-8")
    print(pd.DataFrame(rows)[["method", "common_targets", "gpt_gain_percentage_points",
                              "gain_ci_low", "gain_ci_high"]].to_string(index=False))


if __name__ == "__main__":
    main()
