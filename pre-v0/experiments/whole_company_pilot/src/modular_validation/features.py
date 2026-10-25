"""Reproducible representations on the current team's fixed eligible universe."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
from pathlib import Path

import numpy as np
from scipy import sparse

MPNET_ID = "sentence-transformers/all-mpnet-base-v2"
MPNET_REVISION = "e8c3b32edf5434bc2275fc9bab85f82640a19130"
_ENCODER = None
_TEAM_MODEL = {}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def _unit(matrix):
    matrix = np.asarray(matrix, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1)
    out = np.full_like(matrix, np.nan)
    valid = np.isfinite(matrix).all(axis=1) & (norms > 0)
    out[valid] = matrix[valid] / norms[valid, None]
    return out


def encoder():
    global _ENCODER
    if _ENCODER is None:
        from huggingface_hub import hf_hub_download
        from sentence_transformers import SentenceTransformer
        # Resolve a required file, not snapshot-wide optional ONNX/OpenVINO assets.
        path = str(Path(hf_hub_download(MPNET_ID, "model.safetensors",
                       revision=MPNET_REVISION, token=False,
                       local_files_only=True)).parent)
        _ENCODER = SentenceTransformer(path, device="cuda", local_files_only=True,
                                       trust_remote_code=False)
    return _ENCODER


def _encode_groups(groups, chunk_words=200):
    """Each group is one retained text unit; preserve no-evidence rows as NaN."""
    model = encoder()
    chunks, positions = [], []
    for i, text in enumerate(groups):
        words = str(text).split()
        for start in range(0, len(words), chunk_words):
            chunks.append(" ".join(words[start:start + chunk_words]))
            positions.append(i)
    pooled = np.full((len(groups), 768), np.nan, dtype=np.float64)
    if not chunks:
        return pooled, {"chunks": 0, "truncated_chunks": 0}
    counts = [len(model.tokenizer.encode(t, add_special_tokens=True, truncation=False)) for t in chunks]
    vectors = model.encode(chunks, batch_size=32, normalize_embeddings=True,
                           show_progress_bar=False, convert_to_numpy=True)
    sums = np.zeros_like(pooled)
    numbers = np.zeros(len(groups), dtype=int)
    for pos, vector in zip(positions, vectors):
        sums[pos] += vector
        numbers[pos] += 1
    keep = numbers > 0
    pooled[keep] = sums[keep] / numbers[keep, None]
    pooled = _unit(pooled)
    return pooled, {"chunks": len(chunks), "truncated_chunks": sum(n > model.max_seq_length for n in counts),
                    "max_chunk_wordpieces": max(counts), "model_max_wordpieces": model.max_seq_length,
                    "empty_groups": int((~keep).sum())}


def _page_groups(corpus, home_only=False):
    groups, owners = [], []
    allowed = {row.IQ_COMPANY_ID: set(row.clean_sents) for row in corpus.universe.itertuples()}
    for doc in corpus.documents.itertuples():
        if doc.company_id not in allowed or doc.block_page:
            continue
        if home_only and doc.page_id != "P1" and doc.source_category != "home":
            continue
        sents = corpus.team_baseline.to_sentences(doc.text_masked)
        groups.append(" ".join(s for s in sents if s in allowed[doc.company_id]))
        owners.append(doc.company_id)
    return groups, owners


def _conservative_groups(corpus):
    """Stored raw-text filtering ablation, not a reconstructed DOM experiment.

    Financial/public-company removal remains in force. A raw block touched by
    those rules keeps only its strictly cleaned remainder. Other blocks retain
    qualitative scope/history/size text before company-name masking.
    """
    import fetch_and_clean as cleaning
    protected = {"financial_figure", "finance_talk", "scale_figure", "public_company",
                 "ticker_tag", "bare_ticker", "public_phrase"}
    names = {row.IQ_COMPANY_ID: (row.target_company_name, row.target_ciq_website)
             for row in corpus.universe.itertuples()}
    groups, owners = [], []
    for doc in corpus.documents.itertuples():
        if doc.company_id not in names or doc.block_page:
            continue
        kept = []
        for block in doc.text_raw.splitlines():
            strict, removed = cleaning.clean_block_logged(block)
            keep = strict if any(item["reason"] in protected for item in removed) else block
            if keep:
                kept.append(keep)
        name, website = names[doc.company_id]
        masked, _ = corpus.team_baseline.mask("\n".join(kept),
                                              corpus.team_baseline.name_variants(name, website), [])
        groups.append(" ".join(corpus.team_baseline.to_sentences(masked)))
        owners.append(doc.company_id)
    return groups, owners


def build_features(corpus, cache_dir, method_id, parameters=None):
    """Return {ids, matrix, metadata, cache_key}; parameters is the frozen config.

    Row order exactly matches corpus.universe.IQ_COMPANY_ID. Dense rows without
    evidence are NaN, never zero relevance; valid_rows also covers sparse data.
    """
    parameters = parameters or {}
    ids = corpus.universe.IQ_COMPANY_ID.tolist()
    settings = {"method_id": method_id, "parameters": parameters,
                "input_provenance": corpus.provenance, "ids": ids,
                "text_sha256": _hash(corpus.universe.clean_text.tolist()),
                "module_version": "2026-10-18-v1",
                "packages": {p: importlib.metadata.version(p) for p in ["numpy", "scikit-learn", "sentence-transformers", "gensim"]}}
    key = _hash(settings)
    folder = Path(cache_dir) / f"{method_id}_{key[:20]}"
    meta_path = folder / "metadata.json"
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        matrix = sparse.load_npz(folder / "matrix.npz") if metadata["sparse"] else np.load(folder / "matrix.npy", allow_pickle=False)
        return {"ids": ids, "matrix": matrix, "metadata": metadata, "cache_key": key}
    diagnostics = {}
    if method_id in {"team_tfidf", "team_lsa"}:
        base_key = _hash({"page_text_digest": corpus.provenance["page_text_digest"],
                          "ids": ids, "text_sha256": settings["text_sha256"]})
        if base_key not in _TEAM_MODEL:
            _TEAM_MODEL[base_key] = corpus.team_baseline.Model(corpus.universe, False, Path(cache_dir))
        baseline = _TEAM_MODEL[base_key]
        matrix = baseline.X_tfidf if method_id == "team_tfidf" else baseline.X_lsa
        diagnostics = {"frozen_team_baseline": True, "random_state": 0,
                       "vocabulary_size": len(baseline.vocab), "same_source_corpus": True}
    elif method_id == "doc2vec_dbow_cosine":
        from gensim.models.doc2vec import Doc2Vec, TaggedDocument
        config = {"vector_size": 300, "dm": 0, "epochs": 100, "min_count": 2, "seed": 4511, "workers": 1}
        config.update(parameters.get("doc2vec", {}))
        docs = [TaggedDocument(re.findall(r"\b[a-zA-Z][a-zA-Z-]+\b", t.lower()), [cid])
                for cid, t in zip(ids, corpus.universe.clean_text)]
        model = Doc2Vec(**config)
        model.build_vocab(docs)
        model.train(docs, total_examples=len(docs), epochs=config["epochs"])
        matrix = _unit(np.vstack([model.dv[cid] for cid in ids]))
        unavailable = [i for i, d in enumerate(docs) if not any(t in model.wv for t in d.words)]
        matrix[unavailable] = np.nan
        diagnostics = {"training_companies": len(docs), "training_scope": "transductive supplied website corpus; no relevance/outcome labels",
                       "vocabulary_size": len(model.wv), "config": config,
                       "comparability_to_large_corpus_paper": "new smaller-corpus condition"}
    elif method_id == "team_mpnet_cosine":
        matrix, diagnostics = _encode_groups(corpus.universe.clean_text.tolist())
        diagnostics["pooling"] = "normalize each 200-word chunk, mean chunks, normalize company mean"
    elif method_id in {"mpnet_page_balanced", "mpnet_home_only", "mpnet_conservative_cleaning"}:
        groups, owners = (_conservative_groups(corpus) if method_id == "mpnet_conservative_cleaning"
                          else _page_groups(corpus, home_only=method_id == "mpnet_home_only"))
        if method_id == "mpnet_conservative_cleaning":
            by_id = {cid: [] for cid in ids}
            for owner, text in zip(owners, groups):
                by_id[owner].append(text)
            matrix, diagnostics = _encode_groups([" ".join(by_id[cid]) for cid in ids])
            diagnostics["transformation"] = "stored raw blocks with protected finance/public redaction; no raw HTML comparison"
        else:
            page_vectors, diagnostics = _encode_groups(groups)
            owner_index = {cid: i for i, cid in enumerate(ids)}
            accum = np.zeros((len(ids), 768))
            counts = np.zeros(len(ids), dtype=int)
            for owner, vector in zip(owners, page_vectors):
                if np.isfinite(vector).all():
                    i = owner_index[owner]
                    accum[i] += vector
                    counts[i] += 1
            matrix = _unit(accum)
            diagnostics["page_counts"] = counts.tolist()
            diagnostics["pooling"] = "normalize page chunk mean; equal mean over available pages; normalize company mean"
    else:
        raise ValueError(f"Unsupported feature method: {method_id}")
    is_sparse = sparse.issparse(matrix)
    valid = np.asarray(matrix.multiply(matrix).sum(axis=1)).ravel() > 0 if is_sparse else np.isfinite(matrix).all(axis=1)
    metadata = {**settings, "cache_key": key, "sparse": is_sparse,
                "shape": list(matrix.shape), "valid_rows": valid.tolist(),
                "diagnostics": diagnostics, "model_revision": MPNET_REVISION if method_id.startswith(("mpnet", "team_mpnet")) else None}
    folder.mkdir(parents=True, exist_ok=False)
    if is_sparse:
        sparse.save_npz(folder / "matrix.npz", matrix)
    else:
        np.save(folder / "matrix.npy", matrix, allow_pickle=False)
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"ids": ids, "matrix": matrix, "metadata": metadata, "cache_key": key}


def build_activity_embeddings(corpus, cache_dir, profiles, parameters=None):
    """Return activity representations in the supplied corpus scope and order.

    Activity rows preserve every accepted activity. These model-derived profiles
    have only literal quote validation, not human semantic approval. Zero rows
    mean unavailable scope; consumers must not score them as zero similarity.
    """
    ids = corpus.universe.IQ_COMPANY_ID.tolist()
    settings = {"kind": "supported_activity_embeddings_v3_scope_isolation", "revision": MPNET_REVISION,
                "parameters": parameters or {}, "profiles_digest": _hash(profiles),
                "corpus": corpus.provenance, "ids": ids}
    key = _hash(settings)
    path = Path(cache_dir) / f"activities_{key[:20]}"
    texts, positions, accepted = [], [], {}
    for cid in ids:
        activities = profiles.get(cid, {}).get("known_activities", [])
        accepted[cid] = activities
        for activity in activities:
            parts = [str(activity.get("activity", ""))]
            role = str(activity.get("role", "")).strip()
            if role.casefold() not in {"", "unknown", "not stated", "none", "n/a"}:
                parts.append(role)
            parts += [f"{k}: {v}" for k, v in sorted(activity.get("facets", {}).items())
                      if str(v).strip().casefold() not in {"", "unknown", "not stated", "none"}]
            texts.append("; ".join(parts))
            positions.append(cid)
    if (path / "embeddings.npy").exists():
        vectors = np.load(path / "embeddings.npy", allow_pickle=False)
        diagnostics = json.loads((path / "metadata.json").read_text())["diagnostics"]
    else:
        vectors, diagnostics = _encode_groups(texts)
        path.mkdir(parents=True, exist_ok=False)
        np.save(path / "embeddings.npy", vectors, allow_pickle=False)
        (path / "metadata.json").write_text(json.dumps({**settings, "diagnostics": diagnostics}, indent=2), encoding="utf-8")
    by_id = {cid: [] for cid in ids}
    for cid, vector in zip(positions, vectors):
        by_id[cid].append(vector)
    return {cid: {"matrix": np.asarray(by_id[cid]).reshape((-1, 768)),
                  "activities": accepted[cid],
                  "metadata": {"cache_key": key, "profile_status": profiles.get(cid, {}).get("status", "unavailable"),
                               "input_truncated": profiles.get(cid, {}).get("generation", {}).get("input_truncated", False),
                               "output_hit_limit": profiles.get(cid, {}).get("generation", {}).get("output_hit_limit", False),
                               "scope_complete": False, "human_reviewed": False,
                               "mass_policy": "uniform textual activities, not revenue shares"}}
            for cid in ids}
