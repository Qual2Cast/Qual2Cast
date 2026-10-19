"""Synthetic invariants only: these tests cannot establish company relevance."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

MODULE_PATH = Path(__file__).resolve().parents[1] / "src/modular_validation/numeric.py"
SPEC = importlib.util.spec_from_file_location("modular_numeric_under_test", MODULE_PATH)
numeric = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(numeric)


class NumericInvariants(unittest.TestCase):
    def test_cosine_geometry_and_unknown_rows(self):
        result = numeric.cosine_scores([1., 0.], [[1., 0.], [-1., 0.], [0., 0.], [np.nan, 1.]])
        self.assertEqual(result["scores"], [1., -1., None, None])
        self.assertEqual(numeric.cosine_scores([0., 0.], [[1., 0.]])["scores"], [None])
        huge = numeric.cosine_scores([1e308, 1e308], [[1e308, 1e308]])
        self.assertAlmostEqual(huge["scores"][0], 1)

    def test_exact_transport_matches_analytic_plan(self):
        # Target has only one activity, so both prescribed source masses must move.
        result = numeric.balanced_ot([[0.], [2.]], [.25, .75], [1.])
        self.assertEqual(result["status"], "ok")
        np.testing.assert_allclose(result["plan"], [[.25], [.75]])
        self.assertAlmostEqual(result["distance"], 1.5)
        self.assertAlmostEqual(result["source_l1_deviation"], 0)
        unequal = numeric.balanced_ot([[1.]], [1.], [2.])
        self.assertIsNone(unequal["distance"])
        self.assertEqual(unequal["reason"], "unequal_total_mass")

    def test_uot_one_cell_solution_and_mass_penalties(self):
        # Analytic minimizer: p=exp(-cost/(reg+rho_source+rho_target)).
        cost, reg, rho = 2., .2, .5
        result = numeric.unbalanced_ot([[cost]], [1.], [1.], reg=reg, reg_m=rho)
        p = np.exp(-cost / (reg + 2 * rho))
        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(result["plan"][0][0], p, places=7)
        self.assertAlmostEqual(result["full_objective"], (reg + 2 * rho) * (1 - p), places=7)
        self.assertAlmostEqual(sum(result["objective_terms"].values()), result["full_objective"])
        self.assertAlmostEqual(result["source_deficit"][0], 1 - p, places=7)
        self.assertGreater(result["full_objective"], result["linear_cost"])
        self.assertGreater(abs(result["full_objective"] - result["library_reported_total_cost"]), .1)
        padded = numeric.unbalanced_ot([[cost], [999.]], [1., 0.], [1.], reg=reg, reg_m=rho)
        self.assertEqual(padded["plan"][1], [0.])
        self.assertAlmostEqual(padded["full_objective"], result["full_objective"])

    def test_unknown_and_unconverged_transport_are_not_zero(self):
        self.assertIsNone(numeric.balanced_ot([[np.nan]], [1.], [1.])["distance"])
        result = numeric.unbalanced_ot([[2.]], [1.], [1.], reg=.2, reg_m=.5, max_iterations=1)
        self.assertEqual(result["status"], "solver_failed")
        self.assertIsNone(result["distance"])
        self.assertTrue(np.isfinite(result["full_objective"]))

    def test_sard_monotone_transform_and_missing_policy(self):
        query = [2., 20.]
        candidates = [[2., 20.], [4., 40.], [np.nan, 20.]]
        a = numeric.sard_rank_distances(query, candidates, feature_names=["x", "y"])
        b = numeric.sard_rank_distances(np.log(query), np.log(candidates), feature_names=["x", "y"])
        self.assertEqual(a["distances"], b["distances"])
        self.assertEqual(a["distances"][0], 0)
        self.assertGreater(a["distances"][1], 0)
        self.assertIsNone(a["distances"][2])
        partial = numeric.sard_rank_distances(query, candidates, feature_names=["x", "y"], min_features=1)
        self.assertEqual(partial["candidate_metadata"][2]["missing_features"], ["x"])
        self.assertEqual(partial["missingness_policy"], "partial_weight_rescaled_explicit_adaptation")

    def test_hybrid_orientation_unknowns_and_no_information(self):
        result = numeric.hybrid_zscore({"similarity": [1., 2., np.nan], "distance": [3., 2., 1.]},
                    weights={"similarity": 1., "distance": 1.},
                    directions={"similarity": "higher", "distance": "lower"})
        self.assertGreater(result["scores"][1], result["scores"][0])
        self.assertIsNone(result["scores"][2])
        constant = numeric.hybrid_zscore({"a": [2., 2.]}, weights={"a": 1}, directions={"a": "higher"})
        self.assertEqual(constant["scores"], [None, None])

    def test_percentile_ranks_and_rrf_use_frozen_conventions(self):
        ranks = numeric.sard_rank_distances([2.], [[1.], [3.], [4.]],
                    feature_names=["x"], rank_scale="percentile", aggregation="mean")
        np.testing.assert_allclose(ranks["distances"], [.25, .25, .5])
        fusion = numeric.reciprocal_rank_fusion({"a": ["x", "y", "z"], "b": ["y", "x"]},
                    weights={"a": .5, "b": .5}, constant=60)
        self.assertAlmostEqual(fusion["scores"][0], fusion["scores"][1])
        self.assertIsNone(fusion["scores"][2])
        self.assertEqual(fusion["missing_components"][2], ["b"])

    def test_fixed_row_aggregators_and_exclusion_ids(self):
        ids, values = ["a", "b", "c", "d", "e"], [4., 12., np.nan, -2., 0.]
        median = numeric.aggregate_multiples(ids, values)
        harmonic = numeric.aggregate_multiples(ids, values, method="harmonic")
        weighted = numeric.aggregate_multiples(ids, values, method="weighted", weights=[1, 3, 1, 1, 1])
        self.assertEqual(median["valid_ids"], ["a", "b"])
        self.assertEqual(harmonic["valid_ids"], median["valid_ids"])
        self.assertEqual(weighted["valid_ids"], median["valid_ids"])
        self.assertEqual(median["estimate"], 8)
        self.assertEqual(harmonic["estimate"], 6)
        self.assertEqual(weighted["estimate"], 10)
        self.assertEqual([entry["peer_id"] for entry in median["excluded"]], ["c", "d", "e"])
        self.assertEqual(numeric.aggregate_multiples(["a", "b"], [1e308, 1e308])["estimate"], 1e308)
        self.assertIsNone(numeric.aggregate_multiples(["a"], [0.])["estimate"])
        with self.assertRaises(ValueError):
            numeric.aggregate_multiples(["a"], [5.], method="weighted", weights=[-1.])


if __name__ == "__main__":
    unittest.main()
