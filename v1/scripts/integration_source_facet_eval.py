"""Compare memory-first and cited-only whole-company B3 facets on fixed labels."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import b3_facet_add_drop as b3
import facet_weighting as fw
import facets as fc
import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/source_facet_eval"


def main() -> None:
    _, ids, training, _ = b3.read_inputs()
    paths = {"GPT memory-first": V1 / "facets_codex_gpt61sol/tables/facets.csv",
             "GPT cited-only": V1 / "facets_source_gpt61sol/tables/facets.csv"}
    texts = {}
    for name, path in paths.items():
        filled = pd.read_csv(path, dtype=str).fillna("")
        if filled["IQ_COMPANY_ID"].duplicated().any() or set(filled["IQ_COMPANY_ID"]) != set(ids):
            raise ValueError(f"Facet table does not cover 533 unique IDs: {path}")
        if not filled["llm_status"].eq("ok").all():
            raise ValueError(f"GPT facet run is incomplete: {name}")
        run = json.loads((path.parents[1] / "run.json").read_text(encoding="utf-8"))
        if (run["model"] != "gpt-6.1-sol" or run["companies"] != 533
                or not filled["prompt_version"].eq(fc.PROMPT_VERSION).all()):
            raise ValueError(f"GPT facet model or company count differs: {name}")
        texts[name] = fw.facet_texts(filled).reindex(ids)
    vectors = b3.vectors_for(b3.required_texts(texts,
        pd.DataFrame(columns=["sub_sector_status", "sub_sector"]),
        pd.DataFrame(columns=["status", "value"])))
    review = pd.read_csv(V1 / "integration/review/pairs.csv")
    labels = review.rename(columns={"target_id": "target", "comp_id": "comp",
                                    "score_barbara": "grade"})[["target", "comp", "grade"]]
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    holdout = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    results = {"No matching": vl.no_matching(holdout, training, multiples)}
    rows, coverage = [], []
    for name, table in texts.items():
        per, info, _ = b3.general_components(table, vectors)
        matrix = fw.combine(per, info)
        scored, _, _ = b3.score_variant(name, matrix, ids, training,
                                         {"Barbara 293": labels})
        rows.extend(scored)
        chosen = fw.mutual_top_k(matrix, ids, holdout, training)
        results[name] = vl.estimate(chosen, multiples, weight="similarity")
        coverage.append({"variant": name,
                         "companies_with_any_facet": int(table.notna().any(axis=1).sum()),
                         "available_facet_values": int(table.notna().sum().sum()),
                         "holdout_targets_with_peers": int(chosen["target"].nunique())})
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "reviewed_metrics.csv", index=False)
    pd.DataFrame(coverage).to_csv(OUT / "coverage.csv", index=False)
    vl.summary(results, multiples.reindex(holdout), "No matching").to_csv(
        OUT / "valuation_summary.csv")
    vl.bootstrap(results, multiples.reindex(holdout), "No matching").to_csv(
        OUT / "valuation_intervals.csv")
    actual = multiples.reindex(holdout)
    old = vl.errors(results["GPT memory-first"], actual)["error %"].abs()
    cited = vl.errors(results["GPT cited-only"], actual)["error %"].abs()
    paired = pd.DataFrame({"memory_first_ape": old, "cited_only_ape": cited}).reindex(holdout)
    paired.to_csv(OUT / "target_errors.csv", index_label="target")
    common = paired.dropna()
    rng = np.random.default_rng(2026)
    draws = rng.integers(0, len(common), (2000, len(common)))
    a, b = common["memory_first_ape"].to_numpy(), common["cited_only_ape"].to_numpy()
    gains = np.median(a[draws], axis=1) - np.median(b[draws], axis=1)
    pd.DataFrame([{"comparison": "cited-only minus memory-first",
                   "common_targets": len(common),
                   "memory_first_median_ape": float(np.median(a)),
                   "cited_only_median_ape": float(np.median(b)),
                   "cited_gain_percentage_points": float(np.median(a) - np.median(b)),
                   "gain_ci_low": float(np.quantile(gains, .025)),
                   "gain_ci_high": float(np.quantile(gains, .975))}]).to_csv(
        OUT / "paired_comparison.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "methods": list(paths), "peer_labels": len(labels), "targets": len(holdout),
        "pool": len(training), "reviewer": "Barbara, one reviewer",
        "note": "Cited-only missing facets remain missing; targets without peers have no estimate",
    }, indent=2), encoding="utf-8")
    print(pd.DataFrame(coverage).to_string(index=False))


if __name__ == "__main__":
    main()
