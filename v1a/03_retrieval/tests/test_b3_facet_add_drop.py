"""Checks for the B3 facet evaluation's label and bundle handling."""

import numpy as np
import pandas as pd

import b3_facet_add_drop as review


def test_unlabeled_selected_pair_is_not_a_bad_comp():
    ids = ["target", "good", "bad", "unlabeled"]
    similarity = np.array([
        [1.0, .9, .4, .8],
        [.9, 1.0, .2, .1],
        [.4, .2, 1.0, .3],
        [.8, .1, .3, 1.0],
    ])
    labels = {"human_majority": pd.DataFrame({
        "target": ["target", "target"], "comp": ["good", "bad"], "grade": [2, 0]
    })}
    rows, per_target, selected = review.score_variant("test", similarity, ids, ids, labels)
    assert rows[0]["good_recall"] == 1
    assert rows[0]["labeled_bad_selected"] == 1  # top-up to three includes bad
    assert rows[0]["labeled_selected"] == 2
    assert rows[0]["selected_on_labeled_targets"] == 3
    assert len(per_target) == 1 and len(selected[selected.target == "target"]) == 3


def test_industry_bundle_is_missing_between_sic2_groups():
    ids = ["a", "b", "c"]
    industry = pd.DataFrame({
        "IQ_COMPANY_ID": ids, "sic2": ["73", "73", "58"],
        "facet": ["product", "product", "service"],
        "status": ["stated"] * 3, "value": ["payroll", "payroll", "restaurant"],
    })
    vectors = {"payroll": np.array([1.0, 0.0]), "restaurant": np.array([0.0, 1.0])}
    matrix = review.industry_matrix(industry, ids, vectors)
    assert np.isfinite(matrix[0, 1])
    assert np.isnan(matrix[0, 2]) and np.isnan(matrix[1, 2])
