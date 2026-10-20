"""Abstention must not change the target population in a paired error comparison."""

import numpy as np
import pandas as pd
from pipeline.compare import paired_comparisons
from pipeline.stages import PipelineConfig


def test_paired_error_uses_the_intersection_not_different_survivors():
    base = PipelineConfig(
        matching_method="rrf",
        business_review_method="llm_staged",
        factor_method="business_only",
        valuation_method="median",
    )
    rows = []
    for method, estimates in [("rrf", [10, 20, np.nan]), ("tfidf", [np.nan, 15, 100])]:
        for company, estimate in zip(["A", "B", "C"], estimates):
            rows.append(
                {
                    **base.to_dict(),
                    "matching_method": method,
                    "company": company,
                    "estimate": estimate,
                    "observed_multiple": 10,
                }
            )
    result = paired_comparisons(pd.DataFrame(rows), base).set_index("matching_method")
    assert result.loc["tfidf", "common_companies"] == "B"
    assert result.loc["tfidf", "common_scored"] == 1
    assert result.loc["tfidf", "mean_paired_ape_change_pp"] == -50
    assert result.loc["rrf", "mean_paired_ape_change_pp"] == 0
