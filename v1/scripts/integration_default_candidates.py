"""Recompute the B3 shortlist from the source-reviewed default facets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

import b3_facet_add_drop as b3
import facet_weighting as fw
import method1_candidates as mc
import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
BASE = V1 / "integration/source_reviewed_default"
OUT = BASE / "candidates"


def main() -> None:
    facets = BASE / "facets.csv"
    _, ids, training, _ = b3.read_inputs()
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    targets = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    universe = pd.read_csv(V1 / "universe/20261025T060358Z/universe.csv", dtype=str)
    tickers = universe.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
    texts = fw.facet_texts(pd.read_csv(facets, dtype=str).fillna("")).reindex(ids)
    vectors = b3.vectors_for({str(value) for column in texts for value in
                              texts[column].dropna()})
    similarity, _, saturation = fw.method1_similarity(texts, vectors)
    ranking, candidates = mc.tables_from_similarity(
        similarity, ids, targets, training, tickers)
    if len(ranking) != 160 * 373 or ranking.duplicated(["target", "comp"]).any():
        raise ValueError("Incomplete fixed-pool ranking")
    if len(candidates) != 1600 or candidates.groupby("target").size().ne(10).any():
        raise ValueError("Expected ten candidate peers for each holdout target")
    selected = candidates[candidates["selected"]].copy()
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    estimates = vl.estimate(selected, multiples, weight="similarity")
    errors = vl.errors(estimates, multiples.reindex(targets))["error %"].abs()
    OUT.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(OUT / "ranking.csv.gz", index=False, compression="gzip")
    candidates.to_csv(OUT / "candidates.csv", index=False)
    ranking[ranking["rank"].le(10)].to_csv(OUT / "top10.csv", index=False)
    selected.to_csv(OUT / "selected_peers.csv", index=False)
    errors.rename("absolute_percentage_error").to_csv(OUT / "target_errors.csv")
    (OUT / "run.json").write_text(json.dumps({
        "method": "source-reviewed Sonnet default B3",
        "split_run": "20261027T204930Z", "universe_run": "20261025T060358Z",
        "targets": len(targets), "pool": len(training),
        "facet_sha256": hashlib.sha256(facets.read_bytes()).hexdigest(),
        "candidate_sha256": hashlib.sha256((OUT / "candidates.csv").read_bytes()).hexdigest(),
        "selected_pairs": len(selected), "saturation_k": saturation,
    }, indent=2), encoding="utf-8")
    print(f"Recomputed B3 for {len(targets)} targets: {len(selected)} selected peers")


if __name__ == "__main__":
    main()
