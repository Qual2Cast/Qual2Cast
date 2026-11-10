"""Build the company-input index from the source-reviewed retrieval run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs-local/v1/integration/source_reviewed_default"


def main() -> None:
    source = OUT / "retrieval"
    run = json.loads((source / "run.json").read_text(encoding="utf-8"))
    expected = hashlib.sha256((OUT / "facets.csv").read_bytes()).hexdigest()
    if run["facet_sha256"] != expected or run["method_count"] != 20:
        raise ValueError("Retrieval run does not use the source-reviewed default facets")
    parts = []
    for chunk in pd.read_csv(source / "rankings.csv.gz", chunksize=100_000,
                             dtype={"target": str, "comp": str}):
        parts.append(chunk.loc[chunk["method"].eq("B3 embedding plus TF-IDF") &
                               chunk["rank"].le(10),
                               ["target", "comp", "rank", "similarity"]])
    top = pd.concat(parts, ignore_index=True).sort_values(["target", "rank"])
    if len(top) != 5330 or top["target"].nunique() != 533 or top.duplicated(
            ["target", "comp"]).any():
        raise ValueError("Company report index must contain ten distinct peers for each firm")
    holdout = pd.read_csv(OUT / "candidates/top10.csv", dtype={"target": str, "comp": str})
    merged = top.merge(holdout[["target", "comp", "rank", "similarity"]],
                       on=["target", "comp", "rank"], suffixes=("_all", "_holdout"),
                       validate="one_to_one")
    if len(merged) != 1600 or (merged["similarity_all"] -
                               merged["similarity_holdout"]).abs().max() > 1e-10:
        raise ValueError("All-company index and holdout B3 rankings differ")
    top.to_csv(OUT / "all_targets_top10.csv", index=False)
    (OUT / "report_index_run.json").write_text(json.dumps({
        "source": str(source / "rankings.csv.gz"), "facet_sha256": expected,
        "companies": 533, "peers_per_company": 10,
        "holdout_rows_exactly_reproduced": len(merged),
    }, indent=2), encoding="utf-8")
    print("Indexed ten B3 peers for all 533 source-reviewed companies")


if __name__ == "__main__":
    main()
