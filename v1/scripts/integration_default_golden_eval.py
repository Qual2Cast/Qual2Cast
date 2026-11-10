"""Score the source-reviewed retrieval routes on the existing reviewer cohorts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

import b3_facet_add_drop as b3
from integration_reviewed_ranks import score_cohort


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration"
SOURCE = BASE / "source_reviewed_default/retrieval"
OUT = BASE / "source_reviewed_default/golden"


def main() -> None:
    _, _, training, _ = b3.read_inputs()
    cohorts = {name: frame for name, frame in b3.load_labels(training).items()
               if name.startswith("human_")}
    single = pd.read_csv(BASE / "review/pairs.csv", dtype={"target_id": str, "comp_id": str})
    cohorts["barbara_293"] = single.rename(columns={
        "target_id": "target", "comp_id": "comp", "score_barbara": "grade"
    })[["target", "comp", "grade"]]
    targets = set().union(*(set(cohort["target"]) for cohort in cohorts.values()))
    parts = []
    for chunk in pd.read_csv(SOURCE / "rankings.csv.gz", chunksize=100_000,
                             dtype={"target": str, "comp": str}):
        parts.append(chunk.loc[chunk["target"].isin(targets) & chunk["rank"].le(10),
                               ["method", "target", "comp", "rank"]])
    top = pd.concat(parts, ignore_index=True)
    selected = pd.read_csv(SOURCE / "selected_peers.csv",
                           usecols=["method", "target", "comp"], dtype=str)
    selected = selected[selected["target"].isin(targets)]
    methods = sorted(top["method"].unique())
    if len(methods) != 20:
        raise ValueError("Expected all twenty source-reviewed retrieval methods")
    rows, target_rows = [], []
    for method in methods:
        ranked = top.loc[top["method"].eq(method), ["target", "comp", "rank"]]
        peers = selected.loc[selected["method"].eq(method), ["target", "comp"]]
        for name, labels in cohorts.items():
            result, per_target = score_cohort("source_reviewed_default", method,
                                               ranked, peers, name, labels)
            rows.append(result)
            target_rows.extend(per_target)
    result = pd.DataFrame(rows)
    if len(result) != 20 * len(cohorts) or result.duplicated(
            ["facet_source", "method", "label_source"]).any():
        raise ValueError("Incomplete reviewer comparison")
    OUT.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT / "metrics.csv", index=False)
    pd.DataFrame(target_rows).to_csv(OUT / "target_metrics.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "methods": len(methods), "label_cohorts": len(cohorts), "rows": len(result),
        "retrieval_sha256": hashlib.sha256((SOURCE / "rankings.csv.gz").read_bytes()).hexdigest(),
        "label_counts": {name: len(frame) for name, frame in cohorts.items()},
    }, indent=2), encoding="utf-8")
    print(f"Scored {len(methods)} source-reviewed methods on {len(cohorts)} reviewer cohorts")


if __name__ == "__main__":
    main()
