"""Tests for facet_weighting.py (method 1 and method 2 similarity). Synthetic
data and a hashing stand-in for the embedding model: no model is loaded."""

import hashlib

import numpy as np
import pandas as pd
import pytest

import candidates as cd
import facet_weighting as fw
import facets as fc


def fake_embed(texts):
    """A unit bag-of-words vector per text (hashed words), so texts sharing
    words have a positive cosine."""
    out = np.zeros((len(texts), 64), dtype=np.float32)
    for i, t in enumerate(texts):
        for w in fw.tokens(t):
            out[i, int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
    norm = np.linalg.norm(out, axis=1, keepdims=True)
    return np.divide(out, norm, out=np.zeros_like(out), where=norm > 0)


def facet_rows(values: dict[str, list], status: dict[str, list] | None = None) -> pd.DataFrame:
    n = len(next(iter(values.values())))
    d = {"IQ_COMPANY_ID": [f"C{i}" for i in range(n)], "business_id": ["B1"] * n}
    for name, v in values.items():
        d[name] = v
        d[f"{name}_status"] = (status or {}).get(name, ["ok"] * n)
    return pd.DataFrame(d)


def test_similarity_facets_leave_out_company_size():
    names = fw.similarity_facets()
    assert "company_size" not in names
    assert names == [f.name for f in fc.FACETS if f.name != "company_size"]


def test_facet_texts_none_unknown_and_empty():
    rows = facet_rows({"primary_products": ["pumps; valves", "", "x", "y"]},
                      {"primary_products": ["ok", "ok", "not_applicable", "unknown"]})
    t = fw.facet_texts(rows, ["primary_products"])
    assert t["primary_products"].tolist() == ["pumps; valves", None, None, None]
    old = fw.facet_texts(rows, ["primary_products"], none_as_missing=False)
    assert old["primary_products"].tolist() == ["pumps; valves", None, cd.NOT_APPLICABLE_TEXT, None]


def test_tfidf_discounts_shared_words_and_skips_missing():
    texts = pd.Series(["B2B: hospitals", "B2B: dialysis clinics", "B2B: dialysis centers", "B2B: banks", None])
    X, raw, idf = fw.tfidf(texts)
    assert idf["b2b"] < idf["dialysis"] < idf["banks"]
    assert np.isnan(raw[4]) and not np.isnan(raw[:4]).any()
    assert np.allclose(np.linalg.norm(X[:4], axis=1), 1) and not X[4].any()
    sims, raw_df, _ = fw.lexical(pd.DataFrame({"f": texts}))
    C = sims["f"]
    assert C[1, 2] > C[0, 1] > 0          # shared "dialysis" beats shared "b2b"
    assert np.isnan(C[4]).all()


def test_information_saturates_at_the_median():
    raw = pd.DataFrame({"a": [1.0, 2.0, 4.0], "b": [2.0, np.nan, 8.0]})
    info, k = fw.information(raw)
    assert k == 2.0
    assert info.loc[1, "a"] == 0.5 and np.isnan(info.loc[1, "b"])
    assert (info.fillna(0).to_numpy() < 1).all()
    assert info.loc[2, "b"] > info.loc[2, "a"] > info.loc[0, "a"]


def test_combine_without_info_matches_step4_similarity():
    rng = np.random.default_rng(0)
    E = {n: rng.normal(size=(6, 8)) for n in ("a", "b", "c")}
    E = {n: v / np.linalg.norm(v, axis=1, keepdims=True) for n, v in E.items()}
    E["b"][2] = 0                       # unknown facet
    S, per_facet = cd.similarity(E)
    assert np.allclose(fw.combine(per_facet), S, equal_nan=True)


def test_combine_weights_by_information():
    C1 = np.array([[1.0, 0.9], [0.9, 1.0]])
    C2 = np.array([[1.0, 0.1], [0.1, 1.0]])
    info = pd.DataFrame({"a": [1.0, 1.0], "b": [0.0, 0.5]})
    S = fw.combine({"a": C1, "b": C2}, info)
    assert S[0, 1] == pytest.approx(0.9)          # facet b weighs 0 for company 0
    S2 = fw.combine({"a": C1, "b": C2}, pd.DataFrame({"a": [1.0, 1.0], "b": [1.0, 1.0]}))
    assert S2[0, 1] == pytest.approx(0.5)


def test_pieces_and_best_match():
    assert fw.pieces("OEM: pumps; distributor: parts; ") == ["OEM: pumps", "distributor: parts"]
    assert fw.pieces("one piece") == ["one piece"]
    texts = pd.DataFrame({"f": ["aircraft repair; military shelters", "aircraft repair", "bank loans", None]})
    all_pieces = sorted({p for x in texts["f"].dropna() for p in fw.pieces(x)})
    vectors = dict(zip(all_pieces, fake_embed(all_pieces)))
    whole = fw.embedding_cosines(texts.iloc[1:3], vectors)
    P = fw.piece_cosines(texts, vectors)
    assert P["f"][1, 2] == pytest.approx(whole["f"][0, 1], abs=1e-6)   # single pieces: the whole cosine
    assert P["f"][0, 1] > 0.5                       # the shared piece matches exactly from company 1's side
    assert np.allclose(P["f"], P["f"].T, equal_nan=True)
    assert np.isnan(P["f"][3]).all()


def test_embed_texts_caches_by_text(tmp_path):
    calls = []

    def embed(texts):
        calls.append(list(texts))
        return fake_embed(texts)

    cache = tmp_path / "texts.npz"
    first = fw.embed_texts(["a b", "c"], cache, embed)
    again = fw.embed_texts(["c", "a b"], cache, embed)
    assert len(calls) == 1 and all(np.allclose(first[t], again[t]) for t in first)
    fw.embed_texts(["c", "new text"], cache, embed)
    assert calls[-1] == ["new text"]
    seeded = fw.embed_texts(["s"], tmp_path / "other.npz", embed, seed={"s": np.ones(64)})
    assert calls[-1] == ["new text"] and seeded["s"].sum() == 64


def test_sharpness_and_gate():
    n = 100
    rng = np.random.default_rng(1)
    flat = rng.uniform(0.4, 0.5, (n, n))
    clustered = flat.copy()
    clustered[0, 1:11] = 0.95                   # company 0 has ten clear neighbours on this facet
    per_facet = {"flat": flat, "clustered": clustered}
    ids = [f"C{i}" for i in range(n)]
    sharp = fw.sharpness(per_facet, ids, ids, k=10)
    assert sharp.loc["C0", "clustered"] > sharp.loc["C0", "flat"] + 0.5
    info = pd.DataFrame({"flat": 0.5, "clustered": 0.5}, index=ids)
    info.loc["C3", "flat"] = np.nan
    g = fw.gate(info, sharp)
    assert np.allclose(g.sum(axis=1), 1)
    assert g.loc["C0", "clustered"] > g.loc["C0", "flat"]
    assert np.isnan(g.loc["C3", "flat"]) and g.loc["C3", "clustered"] == pytest.approx(1)


def test_gated_similarity_scores_from_each_side():
    a = np.array([[1, 0.9, 0.1], [0.9, 1, 0.1], [0.1, 0.1, 1.0]])
    b = np.array([[1, 0.1, 0.9], [0.1, 1, 0.1], [0.9, 0.1, 1.0]])
    w = pd.DataFrame({"a": [1.0, 0.0, 0.5], "b": [0.0, 1.0, 0.5]})
    S = fw.gated_similarity({"a": a, "b": b}, w)
    assert S[0, 1] == pytest.approx(0.9) and S[1, 0] == pytest.approx(0.1)


def test_mutual_top_k_keeps_mutual_and_tops_up():
    ids = ["T", "A", "B", "C", "D", "H"]
    S = np.full((6, 6), 0.1)
    np.fill_diagonal(S, 1)
    S[0, 1:5] = [0.9, 0.8, 0.7, 0.6]           # T's list: A B C D
    S[1, 0] = 0.9                              # A ranks T first
    S[2, 0] = 0.05                             # B ranks T last
    S[2, 3] = S[2, 4] = 0.5
    S[3, 0] = 0.8
    S[4, 0] = 0.05
    S[4, 1] = S[4, 2] = 0.5
    out = fw.mutual_top_k(S, ids, ["T"], ids[:5], k=2, min_comps=1)
    assert out["comp"].tolist() == ["A"] and out["mutual"].all()
    topped = fw.mutual_top_k(S, ids, ["T"], ids[:5], k=2, min_comps=2)
    assert topped["comp"].tolist() == ["A", "B"] and topped["topped_up"].tolist() == [False, True]
    assert len(fw.mutual_top_k(S, ids, ["T"], ids[:5], k=4, min_comps=0)) <= 4
    # a holdout target (not in the pool) enters each comp's list beside the pool
    S[5, :5] = [0.1, 0.95, 0.9, 0.1, 0.1]
    S[1, 5] = 0.99
    hold = fw.mutual_top_k(S, ids, ["H"], ids[:5], k=2, min_comps=0)
    assert hold["comp"].tolist() == ["A"]


def test_a_new_facet_flows_through(monkeypatch):
    extra = fc.Facet("ownership", "Ownership", "Who owns it", "family-controlled")
    monkeypatch.setattr(fc, "FACETS", [*fc.FACETS, extra])
    names = fw.similarity_facets()
    assert names[-1] == "ownership" and len(names) == len(fc.FACETS) - 1
    rng = np.random.default_rng(2)
    words = ["pumps", "valves", "banks", "loans", "aircraft", "repair", "restaurants", "software"]
    n = 25
    values = {name: [" ".join(rng.choice(words, 3)) + "; " + str(rng.choice(words)) for _ in range(n)] for name in names}
    rows = facet_rows(values)
    texts = fw.facet_texts(rows, names)
    lex, raw, _ = fw.lexical(texts)
    info, _ = fw.information(raw)
    all_texts = {t for c in texts for x in texts[c].dropna() for t in [x, *fw.pieces(x)]}
    vectors = {t: v for t, v in zip(sorted(all_texts), fake_embed(sorted(all_texts)))}
    per_facet = fw.blend(fw.piece_cosines(texts, vectors), lex)
    ids = list(texts.index)
    S1 = fw.combine(fw.blend(fw.embedding_cosines(texts, vectors), lex), info)
    g = fw.gate(info, fw.sharpness(per_facet, ids, ids, k=5))
    S2 = fw.gated_similarity(per_facet, g)
    assert "ownership" in g.columns and np.allclose(g.sum(axis=1), 1)
    for S in (S1, S2):
        comps = fw.mutual_top_k(S, ids, ids, ids, k=5, min_comps=2)
        assert comps.groupby("target").size().between(2, 5).all()


def test_method1_similarity_is_the_b3_recipe():
    texts = pd.DataFrame({"a": ["B2B: dialysis clinics", "B2B: dialysis centers", "B2B: banks", None],
                          "b": ["pumps; valves", "valves", "loans", "pumps"]})
    all_texts = sorted({t for c in texts for t in texts[c].dropna()})
    vectors = dict(zip(all_texts, fake_embed(all_texts)))
    S, info, k = fw.method1_similarity(texts, vectors)
    lex, raw, _ = fw.lexical(texts)
    info2, k2 = fw.information(raw)
    expected = fw.combine(fw.blend(fw.embedding_cosines(texts, vectors), lex, fw.ALPHA), info2)
    assert k == k2 and np.allclose(S, expected, equal_nan=True)
    assert S[0, 1] > S[0, 2]                     # shared "dialysis" beats shared boilerplate
