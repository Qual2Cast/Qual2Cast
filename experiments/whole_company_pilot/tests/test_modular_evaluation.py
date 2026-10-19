"""Synthetic safeguards for incomplete judgments and fixed-peer comparisons."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.modular_validation import evaluation


class EvaluationInvariants(unittest.TestCase):
    def test_experiment_seal_requires_every_code_and_parameter_proof(self):
        proof = {"ranking_inputs": {"synthetic.csv": "a"}, "design_sha256": "b",
                 "parameter_sha256": "c", "evaluation_script_sha256": "d",
                 "direct_valuation_script_sha256": "e", "module_sha256": {"synthetic.py": "f"}}
        self.assertTrue(evaluation.verify_experiment_seal(proof, dict(proof))["verified"])
        for field in proof:
            with self.subTest(field=field):
                changed = dict(proof); changed[field] = "changed"
                with self.assertRaisesRegex(RuntimeError, "separate explicit experiment"):
                    evaluation.verify_experiment_seal(proof, changed)
                missing = dict(proof); del missing[field]
                with self.assertRaises(RuntimeError):
                    evaluation.verify_experiment_seal(missing, proof)

    def test_common_pool_ideal_includes_unretrieved_best_peer(self):
        result = evaluation.common_pool_metrics(["b", "c"], {"a": 3, "b": 2, "c": 1}, k=2)
        expected = (3 + 1 / np.log2(3)) / (7 + 3 / np.log2(3))
        self.assertAlmostEqual(result["pooled_ndcg"], expected)
        self.assertLess(result["pooled_ndcg"], 1)
        self.assertEqual(result["precision_at_k"], .5)

    def test_unknown_labels_are_not_false_negatives(self):
        result = evaluation.common_pool_metrics(["a", "b"], {"a": 2, "b": None, "c": 3}, k=2)
        self.assertIsNone(result["precision_at_k"])
        self.assertEqual((result["precision_lower"], result["precision_upper"]), (.5, 1.))
        self.assertIsNone(result["pooled_ndcg"])
        self.assertEqual(result["unknown_top_count"], 1)
        self.assertEqual(result["judgment_coverage_at_k"], .5)
        with self.assertRaises(ValueError):
            evaluation.common_pool_metrics(["new"], {"a": 3}, pool_ids=["a"], k=1)

    def test_known_top_with_unknown_ideal_has_no_point_ndcg(self):
        result = evaluation.common_pool_metrics(["a"], {"a": 1, "b": None}, k=1)
        self.assertIsNotNone(result["dcg"])
        self.assertIsNone(result["ideal_dcg"])
        self.assertIsNone(result["pooled_ndcg"])
        zero = evaluation.common_pool_metrics(["a"], {"a": 0}, k=1)
        self.assertIsNone(zero["pooled_ndcg"])
        self.assertEqual(zero["ndcg_reason"], "no_positive_ideal")

    def test_fixed_denominator_and_rank_integrity(self):
        result = evaluation.common_pool_metrics(["a"], {"a": 3}, k=5)
        self.assertEqual(result["precision_at_k"], .2)
        self.assertEqual(result["missing_output_slots"], 4)
        with self.assertRaises(ValueError):
            evaluation.fixed_peer_sets(["a", "a"])
        with self.assertRaises(ValueError):
            evaluation.ranking_coverage(["outside"], ["a"])

    def test_agreement_and_proxy_are_distinct_from_accuracy(self):
        agreement = evaluation.ranking_agreement(["a", "b", "c"], ["c", "b", "a"], k=2)
        self.assertEqual(agreement["overlap_fraction_of_k"], .5)
        self.assertEqual(agreement["spearman_common_rank"], -1.)
        proxy = evaluation.ranking_proxy_diagnostics(["a", "b", "c"],
                    text_lengths={"a": 10, "b": 20, "c": 30},
                    candidate_sic={"a": "7370", "b": "2834", "c": None},
                    target_sic="7370", scores={"a": 3, "b": 2, "c": 1}, k=3)
        self.assertEqual(proxy["same_sic_fraction_known"], .5)
        self.assertAlmostEqual(proxy["sic_coverage_at_k"], 2 / 3)
        self.assertEqual(proxy["rank_length_spearman"], 1.)
        self.assertEqual(proxy["score_length_spearman"], -1.)

    def test_evidence_guard_does_not_refill_or_invent_relevance(self):
        ranking = ["a", "b", "c", "d", "e", "f"]
        support = {value: True for value in ranking}
        support["e"] = None
        result = evaluation.evidence_coverage_abstention(ranking, support, target_supported=True)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["selected_ids"], ranking[:5])
        self.assertEqual(result["accepted_ids"], [])
        self.assertEqual(result["reasons"], [{"entity": "e", "reason": "unknown_activity_support"}])
        support["e"] = True
        self.assertTrue(evaluation.evidence_coverage_abstention(ranking, support, target_supported=True)["accepted"])
        self.assertFalse(evaluation.evidence_coverage_abstention(ranking[:3], support, target_supported=True)["accepted"])

    def test_aggregation_common_rows_original_rank_weights_and_minimum(self):
        result = evaluation.fixed_peer_aggregations(["a", "b", "c", "d"],
                    {"a": 8., "b": None, "c": 12., "d": 16.}, minimum_valid_peers=3)
        self.assertEqual(result["valid_ids"], ["a", "c", "d"])
        for aggregation in result["aggregations"].values():
            self.assertEqual(aggregation["valid_ids"], ["a", "c", "d"])
        expected = (8 + 12 / 3 + 16 / 4) / (1 + 1 / 3 + 1 / 4)
        self.assertAlmostEqual(result["aggregations"]["reciprocal_rank_weighted_mean"]["estimate"], expected)
        self.assertEqual(result["aggregations"]["median"]["estimate"], 12.)
        too_few = evaluation.fixed_peer_aggregations(["a", "b"], {"a": 8., "b": 12.})
        self.assertFalse(too_few["eligible"])
        self.assertTrue(all(value["estimate"] is None for value in too_few["aggregations"].values()))

    def test_historic_labels_cannot_be_reported_as_fresh(self):
        with self.assertRaises(ValueError):
            evaluation.historical_development_metrics(["a"], {"a": 1}, target_id="PCTY",
                  label_source="synthetic_fixture", target_is_development=False, k=1)
        result = evaluation.historical_development_metrics(["a"], {"a": 1}, target_id="PCTY",
                  label_source="synthetic_fixture", target_is_development=True, k=1)
        self.assertFalse(result["fresh_validation"])
        self.assertFalse(result["independent_human_truth_claimed"])

    def test_strict_indication_withholds_unknown_alignment_without_changing_proxy(self):
        evidence = {value: True for value in "abcde"}
        guard = evaluation.evidence_coverage_abstention(list("abcde"), evidence, target_supported=True)
        proxy = 12.
        result = evaluation.strict_valuation_indication(guard, estimate_multiple=proxy,
                 target_ebitda=5., valid_peer_count=5)
        self.assertIsNone(result["strict_estimate_multiple"])
        self.assertIsNone(result["strict_estimated_ev_supplied_millions"])
        self.assertEqual(result["strict_indication_reasons"], ["financial_dates_and_definitions_unconfirmed"])
        self.assertEqual(proxy, 12.)

    def test_strict_indication_checks_original_full_k_without_refill(self):
        evidence = {value: True for value in "abcdef"}; evidence["e"] = None
        guard = evaluation.evidence_coverage_abstention(list("abcdef"), evidence, target_supported=True, k=5)
        result = evaluation.strict_valuation_indication(guard, estimate_multiple=12.,
                 target_ebitda=5., valid_peer_count=4, dates_and_definitions_confirmed=True)
        self.assertIsNone(result["strict_estimate_multiple"])
        self.assertEqual(guard["selected_ids"], list("abcde"))
        self.assertIn("target_or_original_peer_evidence_guard_failed", result["strict_indication_reasons"])
        short = evaluation.evidence_coverage_abstention(list("abc"), evidence, target_supported=True, k=5)
        self.assertFalse(short["accepted"])

    def test_strict_indication_minimum_and_positive_financial_inputs(self):
        guard = {"accepted": True}
        result = evaluation.strict_valuation_indication(guard, estimate_multiple=12.,
                 target_ebitda=5., valid_peer_count=3, dates_and_definitions_confirmed=True)
        self.assertEqual(result["strict_estimated_ev_supplied_millions"], 60.)
        self.assertEqual(result["strict_indication_status"], "eligible_unreviewed")
        for estimate, ebitda, count in [(None, 5., 3), (12., 0., 3), (12., 5., 2)]:
            with self.subTest(estimate=estimate, ebitda=ebitda, count=count):
                result = evaluation.strict_valuation_indication(guard, estimate_multiple=estimate,
                         target_ebitda=ebitda, valid_peer_count=count, dates_and_definitions_confirmed=True)
                self.assertIsNone(result["strict_estimated_ev_supplied_millions"])


if __name__ == "__main__":
    unittest.main()
