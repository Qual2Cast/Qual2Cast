"""Run comparable retrieval rules on one frozen company and facet view."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import b3_facet_add_drop as b3
import candidates as cd
import facet_eval as fe
import facet_weighting as fw
import facets as fc
import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pre-v0"))
from matching import peer_selectors as ps

V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/candidate_methods"


def group_only(matrix: np.ndarray, ids: list[str], groups: pd.Series) -> np.ndarray:
    values = groups.reindex(ids).fillna("").astype(str).to_numpy()
    return np.where((values[:, None] == values[None, :]) &
                    (values[:, None] != ""), matrix, np.nan)


def whole_profile_matrices(texts: pd.DataFrame) -> dict[str, np.ndarray]:
    """Apply the team's dense, lexical, LSA and RRF recipes to identical profiles."""
    profiles = ["; ".join(f"{name}: {value}" for name, value in row.items()
                          if pd.notna(value) and str(value).strip())
                for _, row in texts.iterrows()]
    dense = cd.embed(profiles)
    lexical = TfidfVectorizer(ngram_range=(1, 2), stop_words="english").fit_transform(profiles)
    if lexical.shape[1] < 3:
        raise ValueError("Insufficient vocabulary for whole-profile LSA")
    latent = TruncatedSVD(n_components=min(100, len(profiles) - 1, lexical.shape[1] - 1),
                          random_state=4511).fit_transform(lexical)
    matrices = {"Whole-profile MPNet": cosine_similarity(dense),
                "Whole-profile TF-IDF": cosine_similarity(lexical),
                "Whole-profile LSA": cosine_similarity(latent)}
    fusion = np.zeros((len(profiles), len(profiles)), dtype=np.float32)
    for score in matrices.values():
        order = np.argsort(-score, axis=1, kind="stable")
        for row, ranked in enumerate(order):
            ranked = ranked[ranked != row]
            fusion[row, ranked] += 1 / (60 + np.arange(1, len(ranked) + 1))
    matrices["Whole-profile RRF"] = fusion
    normalized, cosine, nearest, rank = ps.cosine_geometry(dense)
    _, members, parent = ps.tree_parts(normalized, cosine, "ward")
    tree = ps.select_tree(nearest, members, parent, min_peers=5)
    _, labels = ps.umap_clusters(normalized, seed=4511)
    eom, _ = ps.select_clusters(nearest, rank, labels, start="eom")
    leaf, _ = ps.select_clusters(nearest, rank, labels, start="leaf")
    for name, peers in (("Whole-profile Ward tree", tree),
                        ("Whole-profile UMAP HDBSCAN EOM", eom),
                        ("Whole-profile UMAP HDBSCAN leaf", leaf)):
        gated = np.full(cosine.shape, np.nan)
        for row, chosen in enumerate(peers):
            gated[row, chosen] = cosine[row, chosen]
        matrices[name] = gated
    return matrices


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facets", type=Path,
                        default=V1 / "integration/sources/facets_sonnet_corrected.csv")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--facet-label", default="Yiming-corrected Sonnet whole-company B1 profiles")
    args = parser.parse_args()
    universe, ids, training, _ = b3.read_inputs()
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    holdout = split.loc[split["sample"] == "holdout", "IQ_COMPANY_ID"].tolist()
    corrected = pd.read_csv(args.facets, dtype=str).fillna("")
    b1 = corrected[corrected["business_id"].eq("B1")]
    if (len(b1) != len(ids) or b1["IQ_COMPANY_ID"].duplicated().any()
            or set(b1["IQ_COMPANY_ID"]) != set(ids)
            or not b1["llm_status"].eq("ok").all()
            or not b1["prompt_version"].eq(fc.PROMPT_VERSION).all()):
        raise ValueError("The facet source must contain one completed B1 profile per firm")
    original = cd.facet_texts(corrected).reindex(ids)
    texts = fw.facet_texts(corrected).reindex(ids)
    embeddings, cache = cd.embed_facets(original, V1 / "embeddings")
    b0, _ = cd.similarity(embeddings)
    pieces = {piece for name in texts for value in texts[name].dropna()
              for piece in fw.pieces(value)}
    vectors = b3.vectors_for(b3.required_texts({"current": texts},
        pd.DataFrame(columns=["sub_sector_status", "sub_sector"]),
        pd.DataFrame(columns=["status", "value"])) | pieces)
    embed = fw.embedding_cosines(texts, vectors)
    lexical, raw, _ = fw.lexical(texts)
    info, saturation = fw.information(raw)
    blend = fw.blend(embed, lexical)
    piece_blend = fw.blend(fw.piece_cosines(texts, vectors), lexical)
    gate = fw.gate(info, fw.sharpness(piece_blend, ids, training))
    b3_score = fw.combine(blend, info)
    matrices = {
        "B0 embedding, none as text": b0,
        "B1 embedding, none missing": fw.combine(embed),
        "B2 embedding, information weights": fw.combine(embed, info),
        "B3 embedding plus TF-IDF": b3_score,
        "M2 piece matching and gate": fw.gated_similarity(piece_blend, gate),
        "TF-IDF only": fw.combine(lexical),
    }
    matrices.update(whole_profile_matrices(texts))
    fields = universe.set_index("IQ_COMPANY_ID")
    for level in (2, 3, 4):
        matrices[f"B3 same SIC{level}"] = group_only(
            b3_score, ids, fields[f"target_sic{level}_code"])
    rules = {name: "mutual10_topup3" for name in matrices}
    for name in ("Whole-profile MPNet", "Whole-profile TF-IDF",
                 "Whole-profile LSA", "Whole-profile RRF",
                 "Whole-profile Ward tree", "Whole-profile UMAP HDBSCAN EOM",
                 "Whole-profile UMAP HDBSCAN leaf"):
        rules[name] = "one_way10"
    rules["B0 embedding, none as text"] = "one_way10"
    matrices["B0 mutual10"] = b0
    rules["B0 mutual10"] = "mutual10_topup3"
    matrices["B3 one-way10"] = b3_score
    rules["B3 one-way10"] = "one_way10"
    matrices["B3 z>=2"] = b3_score
    rules["B3 z>=2"] = "z2"
    matrices["B3 mutual20"] = b3_score
    rules["B3 mutual20"] = "mutual20"

    reviewer = pd.read_csv(V1 / "integration/review/pairs.csv")
    labels = reviewer.rename(columns={"target_id": "target", "comp_id": "comp",
                                      "score_barbara": "grade"})[["target", "comp", "grade"]]
    gain = labels.rename(columns={"grade": "gain"}).copy()
    gain["gain"] = gain["gain"].astype(float) / 2
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    estimates = {"No matching": vl.no_matching(holdout, training, multiples)}
    peers, rank_rows, scores = [], [], []
    for name, matrix in matrices.items():
        ranking = fe.rank(matrix, ids, ids, training)
        ranking["method"] = name
        rank_rows.append(ranking)
        policy = rules[name]
        if policy == "one_way10":
            selected = ranking[ranking["rank"] <= 10].copy()
        elif policy == "z2":
            selected = cd.rank_candidates(matrix, ids, ids, training)
            selected = selected[selected["z_ge_2"]].copy()
        else:
            selected = fw.mutual_top_k(matrix, ids, ids, training,
                                       k=20 if policy == "mutual20" else 10,
                                       min_comps=0 if policy == "mutual20" else 3)
        selected["method"] = name
        selected["rule"] = policy
        peers.append(selected)
        metric = fe.rank_metrics(ranking, gain)
        observed = selected.merge(labels, on=["target", "comp"], how="inner")
        scores.append({"method": name, "rule": policy, **metric,
                       "selected_pairs": len(selected),
                       "targets_with_peers": selected["target"].nunique(),
                       "good_selected": int((observed["grade"] >= 1).sum()),
                       "bad_selected": int((observed["grade"] == 0).sum()),
                       "good_recall": float((observed["grade"] >= 1).sum() /
                                            (labels["grade"] >= 1).sum())})
        estimates[name] = vl.estimate(selected[selected["target"].isin(holdout)],
                                      multiples, weight="similarity")
        print(f"{name}: {len(selected)} selected pairs", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    pd.concat(rank_rows, ignore_index=True).to_csv(args.out / "rankings.csv.gz",
                                                   index=False, compression="gzip")
    pd.concat(peers, ignore_index=True).to_csv(args.out / "selected_peers.csv", index=False)
    pd.DataFrame(scores).to_csv(args.out / "reviewed_metrics.csv", index=False)
    vl.summary(estimates, multiples.reindex(holdout), "No matching").to_csv(
        args.out / "valuation_summary.csv")
    (args.out / "run.json").write_text(json.dumps({
        "facet_source": args.facet_label,
        "facet_path": str(args.facets),
        "facet_sha256": hashlib.sha256(args.facets.read_bytes()).hexdigest(),
        "company_count": len(ids), "pool": len(training), "valuation_targets": len(holdout),
        "reviewer": "Barbara, 293 pairs, 45 targets", "method_count": len(matrices),
        "embedding_cache": cache.name, "saturation_k": saturation,
        "notes": "Same frozen inputs; valuation is a development comparison. Ward and UMAP/HDBSCAN use team selectors on the whole-profile MPNet vectors, then rank eligible fixed-pool peers."
    }, indent=2), encoding="utf-8")
    print(pd.DataFrame(scores)[["method", "pairwise accuracy", "good_recall",
                                "bad_selected"]].to_string(index=False))


if __name__ == "__main__":
    main()
