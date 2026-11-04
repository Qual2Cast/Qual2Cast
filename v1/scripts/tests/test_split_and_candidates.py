"""Tests for the training/holdout split (split.py) and the step 4 candidates
(candidates.py). Synthetic data only: no model is loaded."""

import numpy as np
import pandas as pd
import pytest

import candidates as cd
import split as sp


def strata(n_per: dict[str, int]) -> pd.Series:
    ids, groups = [], []
    for g, n in n_per.items():
        ids += [f"{g}{i:03d}" for i in range(n)]
        groups += [g] * n
    return pd.Series(groups, index=ids)


def test_train_counts_sum_to_rounded_share():
    sizes = pd.Series({"large": 276, "mid-sized": 163, "among the largest": 73, "small": 19, "unknown": 2})
    counts = sp.train_counts(sizes, 0.7)
    assert counts.sum() == round(0.7 * 533)
    assert (counts - sizes * 0.7).abs().max() < 1


def test_split_is_stratified_and_keeps_forced_in_training():
    s = strata({"a": 100, "b": 40, "c": 10})
    forced = ["a000", "b001", "c002"]
    sample = sp.stratified_split(s, 0.7, seed=1, forced_train=forced)
    assert (sample[forced] == "training").all()
    assert (sample == "training").sum() == 105
    per = sample.eq("training").groupby(s).sum()
    assert per.to_dict() == {"a": 70, "b": 28, "c": 7}


def test_split_depends_on_seed_not_order():
    s = strata({"a": 50, "b": 30})
    one = sp.stratified_split(s, seed=3)
    shuffled = s.sample(frac=1, random_state=0)
    assert one.equals(sp.stratified_split(shuffled, seed=3).reindex(one.index))
    assert not one.equals(sp.stratified_split(s, seed=4))


def test_forced_id_must_exist():
    with pytest.raises(ValueError):
        sp.stratified_split(strata({"a": 5}), forced_train=["nope"])


def test_size_strata_blank_is_unknown():
    f = pd.DataFrame({"IQ_COMPANY_ID": ["x", "y"], "business_id": ["B1", "B1"],
                      "company_size_category": ["large", ""]})
    assert sp.size_strata(f).to_dict() == {"x": "large", "y": sp.SIZE_UNKNOWN}


def test_smd_sign_and_zero():
    sample = pd.Series(["training"] * 3 + ["holdout"] * 3)
    assert sp.smd(pd.Series([1.0, 2, 3, 1, 2, 3]), sample) == 0
    assert sp.smd(pd.Series([3.0, 4, 5, 1, 2, 3]), sample) > 0


def test_sic_division():
    assert sp.sic_division("07") == "A Agriculture, Forestry, Fishing"
    assert sp.sic_division("73") == "I Services"


def unit(*rows):
    E = np.array(rows, dtype=np.float32)
    n = np.linalg.norm(E, axis=1, keepdims=True)
    return np.divide(E, n, out=np.zeros_like(E), where=n > 0)


def test_similarity_skips_unknown_facets():
    emb = {"f1": unit([1, 0], [1, 0], [0, 1]),
           "f2": unit([1, 0], [0, 1], [0, 0])}        # company 2 unknown on f2
    S, per = cd.similarity(emb)
    assert S[0, 1] == pytest.approx(0.5)              # mean of 1 and 0
    assert S[0, 2] == pytest.approx(0.0)              # f1 only
    assert np.isnan(per["f2"][0, 2])
    S_w, _ = cd.similarity(emb, {"f1": 3.0, "f2": 1.0})
    assert S_w[0, 1] == pytest.approx(0.75)


def test_rank_candidates_excludes_target_and_respects_pool():
    ids = ["t", "a", "b", "c", "h"]
    S = np.array([[1, .9, .5, .1, .95]] * 5, dtype=float)
    r = cd.rank_candidates(S, ids, targets=["t"], pool=["t", "a", "b", "c"], k=2, z_levels=(1.0,))
    assert list(r["comp"]) == ["a", "b", "c"]          # not itself, not the holdout firm h
    s = np.array([.9, .5, .1])
    assert r["z"].iloc[0] == pytest.approx((.9 - s.mean()) / s.std())
    assert list(r["in_top_k"]) == [True, True, False]
    assert list(r["z_ge_1"]) == [True, False, False]
    assert len(cd.candidates(r, (1.0,))) == 2


def test_facet_texts_marks_not_applicable_and_unknown():
    row = {"IQ_COMPANY_ID": "x", "business_id": "B1"}
    for f in cd.SIMILARITY_FACETS:
        row[f], row[f"{f}_status"] = "text", "filled"
    row["primary_products_status"], row["primary_products"] = "not_applicable", ""
    row["end_markets_status"], row["end_markets"] = "unknown", ""
    t = cd.facet_texts(pd.DataFrame([row]))
    assert "company_size" not in t.columns
    assert t.loc["x", "primary_products"] == cd.NOT_APPLICABLE_TEXT
    assert t.loc["x", "end_markets"] is None
    assert t.loc["x", "offering_description"] == "text"
