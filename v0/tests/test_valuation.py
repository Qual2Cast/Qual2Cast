"""Tests for the step 7 estimate and the evaluation (valuation.py)."""

import numpy as np
import pandas as pd
import pytest

import valuation as vl

MULTIPLES = pd.Series({"t": 10.0, "a": 8.0, "b": 12.0, "c": 20.0, "u": np.nan})


def test_weighted_mean_and_median():
    pairs = pd.DataFrame({"target": ["t"] * 3, "comp": ["a", "b", "c"], "similarity": [0.5, 0.25, 0.25]})
    mean = vl.estimate(pairs, MULTIPLES, weight="similarity")
    assert mean.loc["t", "estimate"] == pytest.approx(0.5 * 8 + 0.25 * 12 + 0.25 * 20)
    assert vl.estimate(pairs, MULTIPLES).loc["t", "estimate"] == pytest.approx(40 / 3)
    assert vl.estimate(pairs, MULTIPLES, how="median").loc["t", "estimate"] == 12
    assert mean.loc["t", "comps"] == 3


def test_comps_without_a_multiple_are_left_out():
    pairs = pd.DataFrame({"target": ["t", "t"], "comp": ["a", "u"]})
    r = vl.estimate(pairs, MULTIPLES)
    assert r.loc["t", "estimate"] == 8 and r.loc["t", "comps"] == 1
    assert vl.estimate(pd.DataFrame({"target": ["t"], "comp": ["u"]}), MULTIPLES).empty


def test_no_matching_leaves_out_the_target():
    r = vl.no_matching(["t"], ["t", "a", "b", "c"], MULTIPLES)
    assert r.loc["t", "estimate"] == 12 and r.loc["t", "comps"] == 3


def test_summary():
    actual = pd.Series({"t": 10.0, "s": 20.0})
    base = pd.DataFrame({"estimate": [15.0, 15.0], "comps": [3, 3]}, index=["t", "s"])
    good = pd.DataFrame({"estimate": [11.0, 18.0], "comps": [2, 4]}, index=["t", "s"])
    s = vl.summary({"none": base, "good": good}, actual, baseline="none")
    assert s.loc["none", "median abs % error"] == pytest.approx(37.5)    # 50% and 25%
    assert s.loc["good", "median abs % error"] == pytest.approx(10)      # 10% and 10%
    assert s.loc["good", "% within 25%"] == 100
    assert s.loc["good", "% closer than no matching"] == 100
    assert np.isnan(s.loc["none", "Spearman(estimate, actual)"])
