"""Checks that the frozen human review and route pool align."""

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd

import reviewer_gold_eval as review


class ReviewerEvaluationTests(unittest.TestCase):
    def test_saved_sheet_and_four_routes_cover_the_same_36_pairs(self):
        labels, _ = review.load_snapshot(review.LABELS)
        pool = pd.read_csv(review.POOL, dtype={"target_id": str, "comp_id": str})
        review.validate(labels, pool)
        routes = review.routes_from_pool(pool)
        self.assertEqual(len(labels), 36)
        self.assertEqual(len(routes), 4)
        metrics = review.evaluate_reviewers(labels, routes)
        self.assertEqual(len(metrics), 3 * 4 * 3)  # reviewers × routes × two targets plus mean

    def test_disagreement_is_not_erased_by_a_consensus_score(self):
        labels, _ = review.load_snapshot(review.LABELS)
        pairs, agreement = review.agreement(labels)
        self.assertEqual(int(pairs["unanimous"].sum()), 11)
        self.assertEqual(int((~pairs["unanimous"]).sum()), 25)
        self.assertEqual(agreement["exact_agreement"].tolist(), [12, 12, 30])

    def test_facet_exports_keep_reviewers_and_exclude_three_way_ties(self):
        labels, _ = review.load_snapshot(review.LABELS)
        with TemporaryDirectory() as folder:
            output = Path(folder)
            counts = review.export_facet_labels(labels, output)
            self.assertEqual(counts, {"riya": 36, "barbara": 36,
                                      "matthew": 36, "majority": 32,
                                      "no_majority": 4})
            majority = pd.read_csv(output / "facet_labels_majority.csv")
            unresolved = pd.read_csv(output / "facet_labels_no_majority.csv")
            majority_pairs = set(zip(majority["target_iq_id"], majority["comp_iq_id"]))
            unresolved_pairs = set(zip(unresolved["target_id"], unresolved["comp_id"]))
            self.assertTrue(majority_pairs.isdisjoint(unresolved_pairs))


if __name__ == "__main__":
    unittest.main()
