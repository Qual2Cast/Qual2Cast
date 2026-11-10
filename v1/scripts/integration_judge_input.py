"""Freeze reviewed peer pairs for a label-blind source-citing judge run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/judge_input_293"


def main() -> None:
    review_path = V1 / "integration/review/pairs.csv"
    review = pd.read_csv(review_path, dtype=str)[["target_id", "comp_id"]].rename(
        columns={"target_id": "target", "comp_id": "comp"})
    if review.duplicated(["target", "comp"]).any() or len(review) != 293:
        raise ValueError("Expected 293 unique reviewer pairs")
    ranked = pd.read_csv(V1 / "integration/candidate_methods/rankings.csv.gz",
                         dtype={"target": str, "comp": str})
    ranked = ranked[ranked["method"] == "B3 embedding plus TF-IDF"]
    pairs = review.merge(ranked[["target", "comp", "rank", "similarity"]],
                         on=["target", "comp"], how="left", validate="one_to_one")
    if pairs[["rank", "similarity"]].isna().any().any():
        raise ValueError("At least one reviewed pair lacks a frozen B3 rank")
    pairs["selected"] = True
    OUT.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(OUT / "candidates.csv", index=False)
    pairs[["target", "comp", "rank", "similarity"]].to_csv(
        OUT / "ranking.csv.gz", index=False, compression="gzip")
    (OUT / "run.json").write_text(json.dumps({
        "universe_run": "20261025T060358Z", "split_run": "20261027T204930Z",
        "method": "reviewer pair input, labels removed; rank from corrected Sonnet B3",
        "pairs": len(pairs), "targets": pairs["target"].nunique(),
        "source_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "scores_present_in_judge_input": False
    }, indent=2), encoding="utf-8")
    print(f"Frozen {len(pairs)} label-blind pairs")


if __name__ == "__main__":
    main()
