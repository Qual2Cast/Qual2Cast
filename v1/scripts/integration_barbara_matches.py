"""Evaluate Barbara's published match lists on the shared reviewed pairs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
import re
from urllib.request import urlopen

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/barbara_matches"
VERSION = "unified-public-research-20261030"
BASE = "https://barbara069.github.io/private-company-comparables-research/data/"


def fetch(name: str, targets: set[str]) -> tuple[dict, dict]:
    path = OUT / f"{name}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urlopen(f"{BASE}{name}.json.gz?v={VERSION}", timeout=45) as response:
            payload = response.read()
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    if set(data) != targets:
        raise ValueError(f"Changed target membership: {name}")
    return data, {"shard": name, "bytes": path.stat().st_size,
                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pairwise_accuracy(pairs: pd.DataFrame, rank_col: str) -> tuple[int, int, float]:
    count = resolved = correct = 0
    for _, group in pairs.groupby("target_id"):
        grade = group["score_barbara"].to_numpy()
        rank = group[rank_col].to_numpy()
        better = grade[:, None] > grade[None, :]
        count += int(better.sum())
        resolved += int((better & (rank[:, None] != rank[None, :])).sum())
        correct += int((better & (rank[:, None] < rank[None, :])).sum())
    return count, resolved, correct / resolved if resolved else np.nan


def main() -> None:
    html = (V1 / "integration/sources/barbara_site_20261030.html").read_text(encoding="utf-8")
    match = re.search(r"COMPARISON_GROUPS=(\{[^;]+\});", html)
    if not match:
        raise ValueError("Site no longer exposes a comparable-match manifest")
    mapping = json.loads(match.group(1))
    shards: dict[str, set[str]] = {}
    for target, name in mapping.items():
        shards.setdefault(name, set()).add(target)
    gathered, manifest = {}, []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(fetch, name, targets): name for name, targets in shards.items()}
        for future in as_completed(futures):
            data, record = future.result()
            gathered.update(data)
            manifest.append(record)
    if len(gathered) != 560:
        raise ValueError("The published comparison lists do not cover all original targets")
    rows = []
    for target, suggestions in gathered.items():
        for item in suggestions:
            rows.append({"target_id": target, "rank": item["Candidate Order"],
                         "group_key": item["Canonical Company ID"],
                         "candidate": item["Candidate Name"],
                         "retrieval_index": item["Retrieval Index"],
                         "similarity_percent": item["Similarity Percent"],
                         "status": item["Status"],
                         "source_url": item.get("Candidate Source URL", ""),
                         "universe_descriptions": item.get("Universe Descriptions")})
    lists = pd.DataFrame(rows)
    if lists.duplicated(["target_id", "group_key"]).any():
        raise ValueError("A target has a duplicate economic group in the published list")
    crosswalk = pd.read_csv(V1 / "integration/sources/barbara_crosswalk.csv", dtype=str)
    original_to_group = dict(zip(crosswalk["IQ_COMPANY_ID"], crosswalk["group_key"]))
    reviewed = pd.read_csv(V1 / "integration/review/pairs.csv")
    reviewed = reviewed.rename(columns={"rank": "sheet_rank"})
    reviewed["group_key"] = reviewed["comp_id"].map(original_to_group)
    looked_up = reviewed.merge(lists[["target_id", "group_key", "rank", "retrieval_index"]],
                               on=["target_id", "group_key"], how="left")
    looked_up["in_top10"] = looked_up["rank"].le(10)
    max_rank = lists.groupby("target_id")["rank"].max()
    looked_up["evaluated_rank"] = looked_up["rank"].fillna(
        looked_up["target_id"].map(max_rank) + 1)
    comparisons, resolved, accuracy = pairwise_accuracy(looked_up, "evaluated_rank")
    good = looked_up[looked_up["score_barbara"] >= 1]
    common = looked_up[looked_up["group_key"].notna()]
    count_common, resolved_common, accuracy_common = pairwise_accuracy(common, "evaluated_rank")
    result = {"shards": len(shards), "targets": len(gathered), "published_pairs": len(lists),
              "median_list_length": float(lists.groupby("target_id").size().median()),
              "reviewed_pairs": len(looked_up), "reviewed_pairs_mapped": len(common),
              "reviewed_pairs_in_published_list": int(looked_up["rank"].notna().sum()),
              "good_top10": int(good["in_top10"].sum()), "good_total": len(good),
              "pairwise_label_comparisons": comparisons,
              "pairwise_order_resolved_by_published_top10": resolved,
              "pairwise_accuracy_on_resolved": accuracy,
              "common_pairwise_label_comparisons": count_common,
              "common_pairwise_order_resolved": resolved_common,
              "common_pairwise_accuracy_on_resolved": accuracy_common,
              "published_universe_descriptions": sorted(lists["universe_descriptions"].dropna().unique().tolist())}
    OUT.mkdir(parents=True, exist_ok=True)
    lists.to_csv(OUT / "published_rankings.csv", index=False)
    looked_up.to_csv(OUT / "reviewed_pairs.csv", index=False)
    (OUT / "manifest.json").write_text(json.dumps({"version": VERSION,
        "summary": result, "shards": sorted(manifest, key=lambda row: row["shard"])}, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
