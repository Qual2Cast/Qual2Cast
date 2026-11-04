"""Small checks for the fixed-holdout comparison's two new calculations."""

import numpy as np
import pandas as pd
import unittest

from holdout_evaluation import rerank_without_primary_services, summary_without_scipy


class HoldoutEvaluationTests(unittest.TestCase):
    def test_f3_ablation_reorders_without_changing_candidate_set(self):
        rows = pd.DataFrame({
            "target": ["T"] * 3,
            "comp": ["A", "B", "C"],
            "sim_primary_services": [1.0, 0.0, 0.0],
            **{f"sim_f{i}": [0.2, 0.8, 0.1] for i in range(10)},
        })
        selected = rerank_without_primary_services(rows)
        self.assertEqual(selected.sort_values("rank")["comp"].tolist(), ["B", "A", "C"])
        self.assertEqual(set(selected["comp"]), set(rows["comp"]))
        self.assertTrue(selected["in_top_k"].all())


    def test_spearman_is_pearson_of_ranks_and_summary_keeps_coverage(self):
        actual = pd.Series({"A": 10.0, "B": 20.0, "C": 30.0})
        baseline = pd.DataFrame({"estimate": [20.0] * 3, "comps": [10] * 3}, index=actual.index)
        chosen = pd.DataFrame({"estimate": [9.0, 18.0], "comps": [2, 3]}, index=["A", "B"])
        summary = summary_without_scipy({"baseline": baseline, "chosen": chosen}, actual, "baseline")
        self.assertEqual(summary.loc["chosen", "targets"], 2)
        self.assertTrue(np.isclose(summary.loc["chosen", "Spearman(estimate, actual)"], 1.0))
        self.assertTrue(np.isclose(summary.loc["chosen", "median abs % error"], 10.0))


if __name__ == "__main__":
    unittest.main()
