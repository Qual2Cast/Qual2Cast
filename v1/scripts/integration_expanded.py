"""Test the published larger peer pool with private-safe target website text."""

from __future__ import annotations

import gzip
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/expanded_pool"
SHARDS = V1 / "integration/barbara_shards/research"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=("tfidf", "mpnet"), default="tfidf")
    args = parser.parse_args()
    with gzip.open(V1 / "barbara_catalog_probe.json.gz", "rt", encoding="utf-8") as stream:
        catalog = json.load(stream)
    with gzip.open(V1 / "barbara_comparison_probe.json.gz", "rt", encoding="utf-8") as stream:
        targets = json.load(stream)
    allowed = {item["key"] for item in catalog["companies"]
               if item["listing_status"] != "LISTING_OR_LEGAL_ENTITY_MAPPING_REQUIRES_REVIEW"}
    rows = []
    for path in sorted(SHARDS.glob("profiles_*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            profiles = json.load(stream)
        for key, profile in profiles.items():
            if key not in allowed:
                continue
            description = profile.get("business_description") or {}
            if not isinstance(description, dict):
                description = {}
            text = str(description.get("text") or "").strip()
            rows.append({"group_key": key, "name": profile.get("name", ""),
                         "text": text, "original_target_ids": profile.get("original_target_ids", []),
                         "source_count": len(profile.get("sources") or {})})
    profiles = pd.DataFrame(rows)
    if len(profiles) != len(allowed) or profiles["group_key"].duplicated().any():
        raise ValueError("Expanded profile pool does not match the frozen catalog")
    crosswalk = pd.read_csv(V1 / "integration/sources/barbara_crosswalk.csv", dtype=str)
    target_to_group = dict(zip(crosswalk["IQ_COMPANY_ID"], crosswalk["group_key"]))
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    ids = split["IQ_COMPANY_ID"].tolist()
    reviewed = pd.read_csv(V1 / "integration/review/pairs.csv")
    by_target = reviewed.groupby("target_id")
    target_text = {}
    for target_id in ids:
        quotes = targets[target_id].get("website_quotes") or []
        target_text[target_id] = " ".join(str(q.get("text") or "") for q in quotes[:12])
    if args.method == "tfidf":
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                     min_df=2, max_features=180_000, sublinear_tf=True,
                                     dtype=np.float32)
        peer_vectors = normalize(vectorizer.fit_transform(profiles["text"].fillna("")))
        query_vectors = normalize(vectorizer.transform([target_text[x] for x in ids]))
    else:
        import torch
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2",
                                    device="cuda" if torch.cuda.is_available() else "cpu",
                                    local_files_only=True)
        peer_vectors = model.encode(profiles["text"].fillna("").tolist(), batch_size=64,
                                    normalize_embeddings=True, show_progress_bar=False)
        query_vectors = model.encode([target_text[x] for x in ids], batch_size=64,
                                     normalize_embeddings=True, show_progress_bar=False)
        with torch.no_grad():
            scores_all = (torch.as_tensor(query_vectors, device=model.device)
                          @ torch.as_tensor(peer_vectors, device=model.device).T).cpu().numpy()
    peer_pos = {key: i for i, key in enumerate(profiles["group_key"])}
    top_rows, label_rows = [], []
    for n, target_id in enumerate(ids):
        scores = ((query_vectors[n] @ peer_vectors.T).toarray().ravel()
                  if args.method == "tfidf" else scores_all[n].copy())
        own = peer_pos.get(target_to_group[target_id])
        if own is not None:
            scores[own] = -1
        take = np.argpartition(-scores, min(10, len(scores)-1))[:10]
        take = take[np.argsort(-scores[take], kind="stable")]
        for rank, pos in enumerate(take, 1):
            top_rows.append({"target": target_id, "rank": rank,
                             "group_key": profiles.at[pos, "group_key"],
                             "peer_name": profiles.at[pos, "name"], "similarity": float(scores[pos]),
                             "source_count": int(profiles.at[pos, "source_count"])})
        if target_id in by_target.groups:
            for pair in by_target.get_group(target_id).itertuples():
                pos = peer_pos.get(target_to_group.get(pair.comp_id, ""))
                if pos is None:
                    continue
                value = scores[pos]
                label_rows.append({"target": target_id, "comp": pair.comp_id,
                                   "grade": pair.score_barbara, "rank": int((scores > value).sum() + 1),
                                   "similarity": float(value), "in_top_10": bool(pos in take)})
    top = pd.DataFrame(top_rows)
    labeled = pd.DataFrame(label_rows)
    result_dir = OUT / args.method
    result_dir.mkdir(parents=True, exist_ok=True)
    top.to_csv(result_dir / "top10.csv", index=False)
    labeled.to_csv(result_dir / "reviewed_pair_ranks.csv", index=False)
    target_coverage = pd.DataFrame({"target": ids,
                                    "website_quote_count": [len(targets[x].get("website_quotes") or []) for x in ids],
                                    "query_chars": [len(target_text[x]) for x in ids]})
    target_coverage.to_csv(result_dir / "target_coverage.csv", index=False)
    good = labeled[labeled["grade"] >= 1]
    metrics = {"method": args.method, "pool_groups": len(profiles),
               "descriptions_present": int(profiles["text"].ne("").sum()),
               "targets": len(ids), "targets_with_website_text": int(target_coverage["query_chars"].gt(0).sum()),
               "reviewed_pairs_mapped": len(labeled), "reviewed_good_top10": int(good["in_top_10"].sum()),
               "reviewed_good_total": len(good),
               "mean_target_good_recall_top10": float(good.groupby("target")["in_top_10"].mean().mean())}
    (result_dir / "summary.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
