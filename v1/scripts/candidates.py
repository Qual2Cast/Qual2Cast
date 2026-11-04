"""
Recipe step 4: suggest comps by embedding similarity (as in pre-v0 method 1).

Each facet value of every universe company is embedded on its own
(all-mpnet-base-v2, unit vectors), so no text is cut at the model's
384-token limit and each facet has its own similarity. The similarity of a
target and a comp is the weighted mean of their per-facet cosines, over the
facets both have (an unknown facet is left out of that pair). For now the
weights are equal; weights fit on training pairs (decided 2026-10-25)
replace them later. A facet that doesn't apply ("sells no products") is
embedded as "none", so two companies without products match on it.

Company size (F9) isn't in the similarity: it is scale, which the target's
financials cover, and it is what the split is stratified on.

For each target, every firm in the comp pool (not the target itself) is
ranked; z is the similarity's distance from the target's mean over the
pool, in SDs. Candidates are the top k, or those with z at or above a level
(pre-v0: 2 and 2.5); step 6 chooses among them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

import facets as fc

EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
SIMILARITY_FACETS = [f.name for f in fc.FACETS if f.name != "company_size"]
NOT_APPLICABLE_TEXT = "none"
TOP_K = 10
Z_LEVELS = (2.0, 2.5)


def facet_texts(facets: pd.DataFrame) -> pd.DataFrame:
    """One row per company (its first business profile, indexed by
    IQ_COMPANY_ID), one column per similarity facet: the value text, "none"
    if not applicable, None if unknown."""
    b1 = facets[facets["business_id"] == "B1"].set_index("IQ_COMPANY_ID")
    out = {}
    for name in SIMILARITY_FACETS:
        status = b1[f"{name}_status"]
        out[name] = (b1[name].fillna("").str.strip()
                     .where(status != "not_applicable", NOT_APPLICABLE_TEXT)
                     .where(status != "unknown", None))
    return pd.DataFrame(out)


def embed(texts: list[str], model_name: str = EMBED_MODEL) -> np.ndarray:
    """One unit vector per text. The model is loaded from the local Hugging
    Face cache, so no Hub request is made (and no token warning); it is
    downloaded only if it isn't cached yet (~420 MB)."""
    from sentence_transformers import SentenceTransformer
    from transformers.utils import logging as hf_logging
    hf_logging.disable_progress_bar()       # the "Loading weights" bar
    try:
        model = SentenceTransformer(model_name, local_files_only=True)
    except (OSError, ValueError):           # not cached yet: download it once
        model = SentenceTransformer(model_name)
    return model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)


def embed_facets(texts: pd.DataFrame, cache_dir: Path, model_name: str = EMBED_MODEL
                 ) -> tuple[dict[str, np.ndarray], Path]:
    """Per facet, an array (companies x dimensions) in the order of `texts`,
    with a zero row where the facet is unknown. Cached under `cache_dir` by a
    hash of the model, the ids and the texts, so a rerun with the same facets
    doesn't embed again."""
    key = json.dumps([model_name, list(texts.index), texts.to_dict("list")], ensure_ascii=False)
    cache = Path(cache_dir) / f"facets_{model_name.split('/')[-1]}_{hashlib.sha256(key.encode()).hexdigest()[:16]}.npz"
    if cache.exists():
        with np.load(cache) as z:
            return {name: z[name] for name in texts.columns}, cache
    known = {name: texts[name].notna().to_numpy() for name in texts.columns}
    flat = [t for name in texts.columns for t in texts[name][known[name]]]
    vectors = embed(flat, model_name)
    out, start = {}, 0
    for name in texts.columns:
        E = np.zeros((len(texts), vectors.shape[1]), dtype=np.float32)
        n = int(known[name].sum())
        E[known[name]] = vectors[start:start + n]
        out[name], start = E, start + n
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **out)
    return out, cache


def similarity(embeddings: dict[str, np.ndarray], weights: dict[str, float] | None = None
               ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """The combined similarity matrix (weighted mean of the per-facet cosines
    over the facets both companies have; NaN if they share none) and the
    per-facet cosine matrices (NaN where either company's facet is unknown)."""
    weights = weights or {name: 1.0 for name in embeddings}
    num = den = 0.0
    per_facet = {}
    for name, E in embeddings.items():
        known = np.linalg.norm(E, axis=1) > 0
        both = known[:, None] & known[None, :]
        C = np.where(both, E @ E.T, np.nan)
        per_facet[name] = C
        num = num + weights[name] * np.nan_to_num(C)
        den = den + weights[name] * both
    with np.errstate(invalid="ignore", divide="ignore"):
        S = np.where(den > 0, num / den, np.nan)
    return S, per_facet


def rank_candidates(S: np.ndarray, ids: Sequence[str], targets: Sequence[str], pool: Sequence[str],
                    k: int = TOP_K, z_levels: Sequence[float] = Z_LEVELS) -> pd.DataFrame:
    """For each target, every firm in the pool except itself, most similar
    first: rank, similarity, z (over the pool, without the target), whether it
    is in the top k, and a flag per z level."""
    pos = {x: i for i, x in enumerate(ids)}
    pool_pos = np.array([pos[x] for x in pool])
    rows = []
    for t in targets:
        i = pos[t]
        cand = pool_pos[pool_pos != i]
        s = S[i, cand]
        cand, s = cand[~np.isnan(s)], s[~np.isnan(s)]
        order = np.argsort(-s, kind="stable")
        z = (s - s.mean()) / s.std()
        r = pd.DataFrame({"target": t, "rank": np.arange(1, len(order) + 1),
                          "comp": [ids[j] for j in cand[order]], "similarity": s[order], "z": z[order]})
        r["in_top_k"] = r["rank"] <= k
        for lvl in z_levels:
            r[f"z_ge_{lvl:g}"] = r["z"] >= lvl
        rows.append(r)
    return pd.concat(rows, ignore_index=True)


def candidates(ranking: pd.DataFrame, z_levels: Sequence[float] = Z_LEVELS) -> pd.DataFrame:
    """The rows step 6 chooses from: the top k, or z at or above the loosest level."""
    return ranking[ranking["in_top_k"] | (ranking["z"] >= min(z_levels))].reset_index(drop=True)


def add_facet_similarities(rows: pd.DataFrame, per_facet: dict[str, np.ndarray], ids: Sequence[str]) -> pd.DataFrame:
    """Each row's per-facet cosines (`sim_<facet>`): the inputs for fitting the weights."""
    pos = {x: i for i, x in enumerate(ids)}
    ti, ci = rows["target"].map(pos).to_numpy(), rows["comp"].map(pos).to_numpy()
    return rows.assign(**{f"sim_{name}": C[ti, ci] for name, C in per_facet.items()})
