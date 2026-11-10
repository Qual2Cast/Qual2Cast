"""Score all saved B3 facet variants on the 45-target reviewer cohort."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import b3_facet_add_drop as b3
import facet_weighting as fw
import facets as fc


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/facet_293"


def build_variants() -> tuple[list[str], list[str], dict[str, object]]:
    _, ids, training, sectors = b3.read_inputs()
    general, sector, industry = b3.load_facet_sources(ids)
    general["corrected"] = b3.general_texts(
        V1 / "integration/sources/facets_sonnet_corrected.csv", ids)
    vectors = b3.vectors_for(b3.required_texts(general, sector, industry))
    components = {}
    for name, table in general.items():
        per, info, _ = b3.general_components(table, vectors)
        components[name] = (per, info)
    additions = b3.addition_matrices(ids, sectors, vectors, sector, industry)
    variants = {}
    for name, (per, info) in components.items():
        prefix = name.title()
        variants[f"B3 {prefix}"] = fw.combine(per, info)
        for facet in per:
            variants[f"{prefix} minus {fc.FACET_ID.get(facet, facet)} {facet}"] = fw.combine(
                {key: value for key, value in per.items() if key != facet}, info)
    for name in ("sonnet", "corrected"):
        per, info = components[name]
        for label, matrix in additions.items():
            variants[f"{name.title()} + {label}"] = fw.combine({**per, label: matrix}, info)
        variants[f"{name.title()} + all additions"] = fw.combine({**per, **additions}, info)
    return ids, training, variants


def main() -> None:
    ids, training, variants = build_variants()
    reviewer = pd.read_csv(V1 / "integration/review/pairs.csv")
    labels = reviewer.rename(columns={"target_id": "target", "comp_id": "comp",
                                      "score_barbara": "grade"})[["target", "comp", "grade"]]
    rows, selected = [], []
    for method, matrix in variants.items():
        scored, _, peers = b3.score_variant(method, matrix, ids, training,
                                             {"Barbara 293": labels})
        rows.extend(scored)
        peers["method"] = method
        selected.append(peers)
    metrics = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(OUT / "metrics.csv", index=False)
    pd.concat(selected).to_csv(OUT / "selected_peers.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({"reviewer": "Barbara only",
        "labeled_pairs": len(labels), "targets": labels["target"].nunique(),
        "methods": len(variants), "pool": "373 fixed training firms",
        "note": "Exploratory facet selection; no independent holdout labels"}, indent=2), encoding="utf-8")
    print(metrics.sort_values("pairwise_accuracy", ascending=False)[
        ["variant", "pairwise_accuracy", "good_recall", "direct_recall",
         "labeled_bad_selected"]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
