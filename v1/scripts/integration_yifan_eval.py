"""Test the Orbis-aligned qualitative fields against fixed peer and value labels."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import b3_facet_add_drop as b3
import facet_eval as fe
import facet_weighting as fw
import integration_yifan_facets as yf
import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/yifan_eval"
TEXT = {"primary_offering", "end_markets"}


def main() -> None:
    _, ids, training, _ = b3.read_inputs()
    filled = pd.read_csv(yf.OUT / "facets.csv", dtype=str).fillna("")
    if filled["IQ_COMPANY_ID"].duplicated().any() or set(filled["IQ_COMPANY_ID"]) != set(ids):
        raise ValueError("The Yifan extraction does not cover all 533 IDs")
    if not filled["llm_status"].isin(["ok", "no_saved_evidence"]).all():
        raise ValueError("An unresolved model failure remains in the Yifan extraction")
    table = filled.set_index("IQ_COMPANY_ID").reindex(ids)
    names = [f["name"] for f in yf.definitions()]
    texts = pd.DataFrame({name: table[name].where(table[name + "_status"].eq("stated"), None)
                          for name in names}, index=ids)
    vectors = b3.vectors_for({str(value) for name in names for value in texts[name].dropna()})
    lexical, raw, _ = fw.lexical(texts)
    info, _ = fw.information(raw)
    embedded = fw.embedding_cosines(texts, vectors)
    blended = fw.blend(embedded, lexical)
    exact = {}
    for name in names:
        if name in TEXT:
            exact[name] = blended[name]
            continue
        values = texts[name].to_numpy(dtype=object)
        known = pd.notna(values)
        exact[name] = np.where(known[:, None] & known[None, :],
                               (values[:, None] == values[None, :]).astype(float), np.nan)
    variants = {"Yifan B3 text": fw.combine(blended, info),
                "Yifan exact categories": fw.combine(exact)}
    review = pd.read_csv(V1 / "integration/review/pairs.csv")
    labels = review.rename(columns={"target_id": "target", "comp_id": "comp",
                                    "score_barbara": "grade"})[["target", "comp", "grade"]]
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    holdout = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    results = {"No matching": vl.no_matching(holdout, training, multiples)}
    rows, peers = [], []
    for name, matrix in variants.items():
        scored, _, _ = b3.score_variant(name, matrix, ids, training,
                                         {"Barbara 293": labels})
        rows.extend(scored)
        chosen = fw.mutual_top_k(matrix, ids, holdout, training)
        results[name] = vl.estimate(chosen, multiples, weight="similarity")
        peers.append(chosen.assign(method=name))
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "reviewed_metrics.csv", index=False)
    pd.concat(peers).to_csv(OUT / "selected_peers.csv", index=False)
    vl.summary(results, multiples.reindex(holdout), "No matching").to_csv(
        OUT / "valuation_summary.csv")
    vl.bootstrap(results, multiples.reindex(holdout), "No matching").to_csv(
        OUT / "valuation_intervals.csv")
    coverage = pd.DataFrame([{"facet": name,
                              "companies_with_cited_value": int(texts[name].notna().sum())}
                             for name in names])
    coverage.to_csv(OUT / "coverage.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "model": yf.MODEL, "field_count": len(names), "targets": len(holdout),
        "peer_labels": len(labels), "reviewer": "Barbara, one reviewer",
        "source": str(yf.OUT / "facets.csv"),
        "missing_facets": "missing pairwise fields omitted, not treated as mismatches",
        "evaluation_status": "development comparison",
    }, indent=2), encoding="utf-8")
    print(pd.DataFrame(rows)[["variant", "pairwise_accuracy", "good_recall"]].to_string(index=False))


if __name__ == "__main__":
    main()
