"""Offline checks for filter_comparison.py (toy data, no saved runs)."""

import pandas as pd
import pytest

import filter_comparison as fc


def toy() -> pd.DataFrame:
    return pd.DataFrame({
        "target_id": ["A", "A", "A", "B", "B", "B"],
        "rank": [1, 2, 8, 1, 2, 9],
        "similarity": [0.5, 0.4, 0.3, 0.5, 0.4, 0.3],
        "selector_keep": [1, 0, 0, 1, 0, 0],
        "agent_grade": [2, 1, None, 1, 0, 1],
        "score_barbara": [2, 1, 0, 1, 0, 0],
    })


def test_scores_counts_and_rates():
    r = fc.scores(pd.Series([True, True, False, False]), pd.Series([True, False, True, False]))
    assert (r["kept"], r["true_kept"], r["false_kept"], r["missed"]) == (2, 1, 1, 1)
    assert r["precision"] == r["recall"] == 0.5
    assert r["kappa"] == pytest.approx(0.0)


def test_null_agent_grade_is_not_kept():
    f = fc.filters(toy(), k=7)
    assert f["agent grade >= 1"].tolist() == [True, True, False, True, False, True]
    assert f["agent grade 2"].sum() == 1
    assert f["B3 top 7"].tolist() == [True, True, False, True, True, False]
    assert f["agent >= 1 OR selector"].sum() == 4


def test_agent_filter_against_peer_labels():
    d = toy()
    r = fc.scores(fc.filters(d)["agent grade >= 1"], d["score_barbara"] >= 1)
    assert r["precision"] == pytest.approx(3 / 4) and r["recall"] == pytest.approx(1.0)


def test_bootstrap_resamples_whole_targets():
    d = toy()
    kept, truth = d["score_barbara"] >= 1, d["score_barbara"] >= 1
    ci = fc.bootstrap(d, kept, truth)
    assert ci["precision_lo"] == ci["precision_hi"] == 1.0
