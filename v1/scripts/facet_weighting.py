"""
Facet weighting for the comp similarity (v1, 2026-11-03): an updated
baseline (method 1) and a FAME-inspired method 2. Builds on candidates.py's
per-facet embeddings; nothing here reads a financial column.

Method 1, the updated baseline. Per facet, two scores are blended:
  - the embedding cosine (all-mpnet-base-v2, as in step 4);
  - a TF-IDF word-overlap cosine. IDF is BM25's, computed within the facet
    over every company, so wording most firms share ("B2B:", "direct
    sales:") counts for little and a shared rare word ("dialysis") for a lot.
The facets are combined with one weight per pair and facet: the geometric
mean of the two companies' information scores. A company's information on a
facet is the summed IDF of its distinct words, passed through a BM25-style
saturation curve, raw / (raw + K), with K the median over all companies and
facets. A specific facet counts more than a thin one, with diminishing
returns, so a long facet can't dominate. BM25's length discount is not used:
the cosine doesn't grow with text length, so there is no length bias to
correct, and padding with common words earns almost no IDF.

"Not applicable" ("none") is treated as missing, like unknown, so a pair
where both firms are "none" skips the facet instead of scoring 1.00, and
company size (F9) is left out (both team decisions, 2026-11-03).

Comps are the mutual top k: a comp is kept when each company is among the
other's k most similar (k = 10), so a list can't exceed k. A target with
fewer than MIN_COMPS mutual comps is topped up from its one-way list, in
rank order.

Method 2 adapts FAME (Liu et al., "Facet-Aware Multi-Head Mixture-of-Experts
Model for Sequential Recommendation", arXiv 2411.01457) without training:
  - heads = facets: each facet scores the pool on its own (method 1's blend);
  - experts within a head = the pieces of a facet written as a ";" list
    ("service provider: ...; OEM / manufacturer: ..."). The facet's embedding
    score is the mean, over each side's pieces, of the best-matching piece on
    the other side, averaged over both directions;
  - gate: per target, the facet weights are information x sharpness,
    rescaled to sum to 1. Sharpness is how far the target's k closest pool
    firms on that facet stand above its average pool firm, in SDs (>= 0). A
    fixed rule: no labels, no LLM, no fitting.
Row i of a method 2 matrix scores every company from company i's side (its
own gate), so the matrix is not symmetric; mutual_top_k uses each company's
own row.

The facet list is facets.py's FACETS minus EXCLUDED_FACETS, so a facet added
there is picked up. Any precomputed similarity matrix (e.g. a category
Jaccard) can be passed to combine() or gated_similarity() beside the text
facets; without an information score it gets weight 1 in combine().
"""

from __future__ import annotations

import hashlib
import re
import warnings
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

import candidates as cd
import facets as fc

EXCLUDED_FACETS = ("company_size",)   # F9: too generic, hurt the comps (team decision 2026-11-03)
ALPHA = 0.5                           # share of the TF-IDF score in a facet's blend; fixed, not tuned
TOP_K = 10
MIN_COMPS = 3
PIECE_SEPARATOR = ";"
TOKEN = re.compile(r"[a-z0-9]+")


def similarity_facets(exclude: Sequence[str] = EXCLUDED_FACETS) -> list[str]:
    """The facets in the similarity: every facet in facets.py except `exclude`."""
    return [f.name for f in fc.FACETS if f.name not in exclude]


def facet_texts(facets: pd.DataFrame, names: Sequence[str] | None = None,
                none_as_missing: bool = True) -> pd.DataFrame:
    """One row per company (its first business profile, indexed by
    IQ_COMPANY_ID), one column per facet: the value text, or None where the
    facet is unknown, empty or (with `none_as_missing`) not applicable. With
    `none_as_missing=False`, not applicable is the text "none", as in
    candidates.facet_texts."""
    names = list(names) if names is not None else similarity_facets()
    b1 = facets[facets["business_id"] == "B1"].set_index("IQ_COMPANY_ID")
    out = {}
    for name in names:
        status = b1[f"{name}_status"]
        text = b1[name].fillna("").astype(str).str.strip()
        text = text.where(status != "not_applicable", None if none_as_missing else cd.NOT_APPLICABLE_TEXT)
        text = text.where((status != "unknown") & (text.fillna("") != ""), None)
        out[name] = text.astype(object).where(text.notna(), None)
    return pd.DataFrame(out)


# ---------------------------------------------------------------- TF-IDF

def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def tfidf(texts: pd.Series) -> tuple[np.ndarray, np.ndarray, pd.Series]:
    """For one facet: each company's TF-IDF vector (unit length; a zero row
    where the facet is missing), its raw information (the summed IDF of its
    distinct words; NaN where missing), and the IDF of every word. IDF is
    BM25's, ln(1 + (N - df + 0.5) / (df + 0.5)), over the N companies that
    have the facet."""
    known = texts.notna().to_numpy()
    words = [tokens(t) if k else [] for t, k in zip(texts.fillna(""), known)]
    vocab = sorted({w for ws in words for w in ws})
    index = {w: j for j, w in enumerate(vocab)}
    tf = np.zeros((len(texts), len(vocab)))
    for i, ws in enumerate(words):
        for w in ws:
            tf[i, index[w]] += 1
    n = int(known.sum())
    df = (tf > 0).sum(axis=0)
    idf = np.log1p((n - df + 0.5) / (df + 0.5))
    X = tf * idf
    norm = np.linalg.norm(X, axis=1, keepdims=True)
    X = np.divide(X, norm, out=np.zeros_like(X), where=norm > 0)
    raw = np.where(known, (tf > 0).astype(float) @ idf, np.nan)
    return X, raw, pd.Series(idf, index=vocab)


def lexical(texts: pd.DataFrame) -> tuple[dict[str, np.ndarray], pd.DataFrame, dict[str, pd.Series]]:
    """Per facet: the TF-IDF cosine matrix (NaN where either company lacks
    the facet); each company's raw information per facet; each facet's IDF."""
    sims, raw, idfs = {}, {}, {}
    for name in texts.columns:
        X, raw[name], idfs[name] = tfidf(texts[name])
        known = texts[name].notna().to_numpy()
        sims[name] = np.where(known[:, None] & known[None, :], X @ X.T, np.nan)
    return sims, pd.DataFrame(raw, index=texts.index), idfs


def information(raw: pd.DataFrame, k: float | None = None) -> tuple[pd.DataFrame, float]:
    """The saturated information score raw / (raw + k), in [0, 1); NaN where
    the facet is missing. `k` defaults to the median raw information over all
    companies and facets, so a typical facet text scores 0.5."""
    k = float(np.nanmedian(raw.to_numpy(dtype=float))) if k is None else float(k)
    return raw / (raw + k), k


# ---------------------------------------------------------------- embeddings

def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_text_cache(path: Path) -> dict[str, np.ndarray]:
    if not Path(path).exists():
        return {}
    with np.load(path) as z:
        return dict(zip(z["keys"].tolist(), z["vectors"]))


def embed_texts(texts: Iterable[str], cache: Path, embed: Callable[[list[str]], np.ndarray] | None = None,
                seed: Mapping[str, np.ndarray] | None = None) -> dict[str, np.ndarray]:
    """A unit vector per distinct text. Vectors are kept in an .npz cache
    keyed by each text's sha256, so a new facet or piece embeds only the new
    texts. `seed` adds known vectors (e.g. step 4's cache) before anything is
    embedded; `embed` defaults to candidates.embed (the local model)."""
    store = load_text_cache(cache)
    size = len(store)
    for text, vector in (seed or {}).items():
        store.setdefault(_key(text), np.asarray(vector, dtype=np.float32))
    wanted = sorted(set(texts))
    todo = [t for t in wanted if _key(t) not in store]
    if todo:
        vectors = (embed or cd.embed)(todo)
        store.update({_key(t): np.asarray(v, dtype=np.float32) for t, v in zip(todo, vectors)})
    if len(store) != size:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        keys = list(store)
        np.savez_compressed(cache, keys=np.array(keys), vectors=np.stack([store[k] for k in keys]))
    return {t: store[_key(t)] for t in wanted}


def embedding_cosines(texts: pd.DataFrame, vectors: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Per facet, the cosine matrix of the whole facet texts (NaN where
    either company lacks the facet)."""
    out = {}
    for name in texts.columns:
        col = texts[name]
        known = col.notna().to_numpy()
        E = np.zeros((len(col), len(next(iter(vectors.values())))), dtype=np.float32)
        if known.any():
            E[known] = np.stack([vectors[t] for t in col[known]])
        out[name] = np.where(known[:, None] & known[None, :], E @ E.T, np.nan)
    return out


def pieces(text: str) -> list[str]:
    """A facet text split at ";" into its pieces (the whole text if it has none)."""
    parts = [p.strip() for p in text.split(PIECE_SEPARATOR)]
    return [p for p in parts if p] or [text.strip()]


def piece_cosines(texts: pd.DataFrame, vectors: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Per facet, the best-match piece score: for companies i and j, the mean
    over i's pieces of the best cosine with any of j's pieces, averaged with
    the same from j's side. Equals the whole-text cosine when both texts are a
    single piece; NaN where either company lacks the facet."""
    out = {}
    for name in texts.columns:
        col = texts[name]
        owner, P = [], []
        for i, text in enumerate(col):
            if text is not None and not (isinstance(text, float) and np.isnan(text)):
                for p in pieces(text):
                    owner.append(i)
                    P.append(vectors[p])
        A = np.full((len(col), len(col)), np.nan)
        if owner:
            owner = np.array(owner)
            P = np.stack(P).astype(np.float32)
            starts = np.flatnonzero(np.r_[True, owner[1:] != owner[:-1]])
            counts = np.diff(np.r_[starts, len(owner)])
            best = np.maximum.reduceat(P @ P.T, starts, axis=1)       # piece x company: best piece of that company
            mean = np.add.reduceat(best, starts, axis=0) / counts[:, None]   # company x company
            who = owner[starts]
            A[np.ix_(who, who)] = mean
        out[name] = (A + A.T) / 2
    return out


def blend(embedding: Mapping[str, np.ndarray], lexical_sims: Mapping[str, np.ndarray],
          alpha: float = ALPHA) -> dict[str, np.ndarray]:
    """Per facet, (1 - alpha) x the embedding score + alpha x the TF-IDF cosine."""
    return {name: (1 - alpha) * E + alpha * lexical_sims[name] for name, E in embedding.items()}


# ---------------------------------------------------------------- combining

def combine(per_facet: Mapping[str, np.ndarray], info: pd.DataFrame | None = None) -> np.ndarray:
    """The combined similarity: the weighted mean of the per-facet scores over
    the facets both companies have (NaN if they share none). Without `info`
    the weights are equal (as in candidates.similarity). With it, a pair's
    weight on a facet is the geometric mean of the two companies' information;
    a facet missing from `info` (e.g. a category matrix) weighs 1."""
    num = den = 0.0
    for name, C in per_facet.items():
        both = ~np.isnan(C)
        if info is not None and name in info:
            v = info[name].fillna(0).to_numpy(dtype=float)
            w = np.sqrt(np.outer(v, v))
        else:
            w = np.ones_like(C)
        w = np.where(both, w, 0.0)
        num = num + w * np.nan_to_num(C)
        den = den + w
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def sharpness(per_facet: Mapping[str, np.ndarray], ids: Sequence[str], pool: Sequence[str],
              k: int = TOP_K) -> pd.DataFrame:
    """Per company and facet: the mean of its k highest scores over the pool
    (itself excluded) minus its mean over the pool, in SDs of its pool scores;
    at least 0. NaN where the company lacks the facet."""
    pos = {x: i for i, x in enumerate(ids)}
    cols = np.array([pos[x] for x in pool])
    own = cols[None, :] == np.arange(len(ids))[:, None]
    out = {}
    for name, C in per_facet.items():
        R = np.where(own, np.nan, C[:, cols])
        n = (~np.isnan(R)).sum(axis=1)
        top = -np.sort(-np.where(np.isnan(R), -np.inf, R), axis=1)[:, :k]
        with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)          # companies without the facet: all-NaN rows
            z =(np.where(np.isinf(top), np.nan, top).mean(axis=1) - np.nanmean(R, axis=1)) / np.nanstd(R, axis=1)
        out[name] = np.where(n > k, np.clip(z, 0, None), np.nan)
    return pd.DataFrame(out, index=list(ids))


def gate(info: pd.DataFrame, sharp: pd.DataFrame) -> pd.DataFrame:
    """Per company, its facet weights: information x sharpness, rescaled to
    sum to 1 over the facets it has (NaN for the others). A company whose
    facets all have sharpness 0 falls back to its information alone."""
    g = info * sharp
    total = g.sum(axis=1, min_count=1)
    flat = ~(total > 0)
    g.loc[flat] = info.loc[flat]
    return g.div(g.sum(axis=1, min_count=1), axis=0)


def gated_similarity(per_facet: Mapping[str, np.ndarray], weights: pd.DataFrame) -> np.ndarray:
    """Row i scores every company from i's side: the mean of the facet scores
    weighted by i's gate, over the facets both have (the weights of facets the
    other company lacks are dropped and the rest rescaled)."""
    num = den = 0.0
    for name, C in per_facet.items():
        w = weights[name].fillna(0).to_numpy(dtype=float)[:, None] if name in weights else 0.0
        both = ~np.isnan(C)
        num = num + np.where(both, w * np.nan_to_num(C), 0.0)
        den = den + np.where(both, w, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def method1_similarity(texts: pd.DataFrame, vectors: Mapping[str, np.ndarray], alpha: float = ALPHA,
                       k: float | None = None) -> tuple[np.ndarray, pd.DataFrame, float]:
    """B3 = method 1, the v1 baseline similarity (decided 2026-11-04): per
    facet 0.5 x embedding cosine + 0.5 x TF-IDF cosine, combined with
    information weights. Returns the similarity matrix (rows and columns in
    the order of `texts`), each company's information per facet, and the
    saturation constant used."""
    lex, raw, _ = lexical(texts)
    info, k = information(raw, k)
    return combine(blend(embedding_cosines(texts, vectors), lex, alpha), info), info, k


# ---------------------------------------------------------------- comps

def mutual_top_k(S: np.ndarray, ids: Sequence[str], targets: Sequence[str], pool: Sequence[str],
                 k: int = TOP_K, min_comps: int = MIN_COMPS) -> pd.DataFrame:
    """For each target, its k most similar pool firms (itself excluded; row
    `target` of S): the one-way list. A comp in it is mutual when the target
    would also be among the comp's k most similar, out of the pool plus the
    target, the comp itself excluded (row `comp` of S). Kept: the mutual comps,
    topped up from the one-way list in rank order to `min_comps`. Columns:
    target, comp, rank (in the one-way list), similarity, mutual, topped_up."""
    pos = {x: i for i, x in enumerate(ids)}
    cols = np.array([pos[x] for x in pool])
    rows = []
    for t in targets:
        i = pos[t]
        cand = cols[cols != i]
        s = S[i, cand]
        cand, s = cand[~np.isnan(s)], s[~np.isnan(s)]
        order = np.argsort(-s, kind="stable")[:k]
        top, top_s = cand[order], s[order]
        mutual = np.zeros(len(top), dtype=bool)
        for j, c in enumerate(top):
            back = S[c, i]
            if np.isnan(back):
                continue
            others = S[c, cols[(cols != c) & (cols != i)]]
            mutual[j] = 1 + int((others[~np.isnan(others)] > back).sum()) <= k
        keep = mutual.copy()
        if keep.sum() < min_comps:
            keep[np.flatnonzero(~keep)[:min_comps - keep.sum()]] = True
        rows.append(pd.DataFrame({"target": t, "comp": [ids[c] for c in top], "rank": np.arange(1, len(top) + 1),
                                  "similarity": top_s, "mutual": mutual, "topped_up": keep & ~mutual})[keep])
    cols_out = ["target", "comp", "rank", "similarity", "mutual", "topped_up"]
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=cols_out)
