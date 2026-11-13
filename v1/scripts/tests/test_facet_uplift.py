"""Statistical plumbing checks, independent of saved company data and model APIs."""
import numpy as np
import pandas as pd

from facet_uplift import (arm_support, estimate_fold, group_splits,
                          summarize, treatment)


def test_outer_and_inner_groups_are_disjoint_and_cover_each_row():
    groups = np.repeat([f"target{i}" for i in range(45)], 7)
    held_rows = []
    for train, test in group_splits(groups):
        assert not set(groups[train]) & set(groups[test])
        held_rows.extend(test)
        for inner_train, inner_valid in group_splits(groups[train], 3):
            assert not set(groups[train][inner_train]) & set(groups[train][inner_valid])
            assert not set(groups[test]) & set(groups[train][inner_train])
    assert sorted(held_rows) == list(range(len(groups)))


def test_thresholds_use_only_train_and_unknown_never_becomes_control():
    scores = np.array([0., .2, .4, .6, .8, 1.])
    a, low, high = treatment(scores, np.array([np.nan, .1, .9]), "b3", "primary")
    b, low2, high2 = treatment(scores, np.array([np.nan, -100., 100.]), "b3", "primary")
    assert low == high == low2 == high2 == .5
    assert np.isnan(a[0]) and np.isnan(b[0])
    assert list(a[1:]) == [0, 1]
    extreme, _, _ = treatment(scores, np.array([.1, .5, .9]), "b3", "extreme")
    assert extreme[0] == 0 and np.isnan(extreme[1]) and extreme[2] == 1


def test_agent_evidenced_zero_and_unknown_are_distinct():
    values = np.array([np.nan, 0, 25, 50, 75, 100])
    primary, _, _ = treatment(values, values, "agent", "primary")
    strict, _, _ = treatment(values, values, "agent", "extreme")
    assert np.isnan(primary[0]) and primary[1] == 0
    assert primary[3] == 0 and np.isnan(strict[3])
    assert list(primary[4:]) == [1, 1]
    assert not arm_support(np.ones(100), np.repeat(np.arange(10), 10))


def test_xlearner_recovers_positive_effect_on_randomized_synthetic_data():
    rng = np.random.default_rng(12)
    n = 4000
    groups = np.repeat(np.arange(80), 50)
    t = rng.integers(0, 2, n)
    y = rng.binomial(1, .2 + .4*t)
    x = np.zeros((n, 2))
    tau, e, m0, m1, probability = estimate_fold(x, y, t, groups, x[:20], t[:20])
    assert np.all((tau > .30) & (tau < .50))
    assert np.all((e > .4) & (e < .6))
    assert np.all(m1 > m0)
    assert np.all((probability >= 0) & (probability <= 1))


def test_unsupported_facets_remain_in_summary():
    diagnostics = pd.DataFrame([dict(source="agent", facet="missing", rule="primary",
                                    fold=i, status="insufficient_support") for i in range(5)])
    summary, bins = summarize(pd.DataFrame(), diagnostics, 20)
    assert summary.iloc[0].predicted_pairs == 0
    assert summary.iloc[0].status == "partial_or_unsupported"
    assert bins.empty


def test_rating_outcome_recovers_known_effect_in_rating_points():
    rng = np.random.default_rng(12)
    n = 4000
    groups = np.repeat(np.arange(80), 50)
    t = rng.integers(0, 2, n)
    # Expected rating 0.4 under control, 1.0 under treatment: +0.6 points.
    y = rng.binomial(2, .2 + .3*t)
    x = np.zeros((n, 2))
    tau, e, m0, m1, response = estimate_fold(x, y, t, groups, x[:20], t[:20], "rating")
    assert np.all((tau > .45) & (tau < .75))
    assert np.all((response >= 0) & (response <= 2))
    assert np.all(m1 > m0)


def test_rating_diagnostics_use_rating_metrics_and_two_point_effect_bound():
    effects = pd.DataFrame({"source": ["b3"]*6, "facet": ["products"]*6,
        "rule": ["primary"]*6, "target": ["a","a","b","b","c","c"],
        "outcome_value": [0,1,2,0,1,2], "predicted_outcome": [.2,.9,1.6,.3,1.2,1.7],
        "baseline_outcome": [1.]*6, "uplift": [.2,.3,.4,.5,1.2,2.1],
        "overlap": [True]*6, "dr_pseudo_effect": [.2]*6})
    diagnostics = pd.DataFrame([dict(source="b3", facet="products", rule="primary",
                                    fold=i, status="ok") for i in range(5)])
    result, _ = summarize(effects, diagnostics, 20, "rating")
    assert result.iloc[0].outside_rating_effect_range == 1
    assert result.iloc[0].mae < result.iloc[0].baseline_mae
    assert "brier" not in result and "response_auc" not in result
