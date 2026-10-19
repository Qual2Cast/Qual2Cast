"""Behavioral checks independent of company labels and GPU availability."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile

import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modular_validation import features
from modular_validation.features import _unit, build_activity_embeddings, build_features
from modular_validation.local_llm import _parse


class FeatureContracts(unittest.TestCase):
    def test_missing_representation_is_unknown_not_zero_similarity(self):
        result = _unit([[3., 4.], [0., 0.], [np.nan, 1.]])
        np.testing.assert_allclose(result[0], [.6, .8])
        self.assertTrue(np.isnan(result[1:]).all())

    def test_activity_adapter_preserves_all_accepted_businesses_and_unknown_rows(self):
        corpus = SimpleNamespace(universe=pd.DataFrame({"IQ_COMPANY_ID": ["A", "B"]}),
                                 provenance={"snapshot": "synthetic"})
        profiles = {"A": {"known_activities": [
            {"activity": "payments", "role": "software_provider", "facets": {}},
            {"activity": "fleet", "role": "service_provider", "facets": {}},
            {"activity": "benefits", "role": "software_provider", "facets": {}}
        ], "status": "model_extracted_unreviewed"}}
        def fake_encode(texts):
            return np.eye(768)[:len(texts)], {"synthetic": True}
        with tempfile.TemporaryDirectory() as tmp, patch("modular_validation.features._encode_groups", fake_encode):
            out = build_activity_embeddings(corpus, tmp, profiles)
            self.assertEqual(list(out), ["A", "B"])
            self.assertEqual(out["A"]["matrix"].shape, (3, 768))
            self.assertEqual(out["B"]["matrix"].shape, (0, 768))
            self.assertFalse(out["A"]["metadata"]["scope_complete"])
            self.assertFalse(out["A"]["metadata"]["human_reviewed"])

    def test_partial_json_cannot_be_accepted_as_a_complete_profile(self):
        with self.assertRaises(ValueError):
            _parse('{"activities":[{"activity":"fleet"}')
        self.assertEqual(_parse('{"activities":[],"scope_notes":"unknown"}')["activities"], [])

    def test_unknown_role_does_not_become_matching_text(self):
        corpus = SimpleNamespace(universe=pd.DataFrame({"IQ_COMPANY_ID": ["A"]}),
                                 provenance={"snapshot": "synthetic"})
        profiles = {"A": {"known_activities": [{"activity": "Fleet services", "role": "unknown",
                                                "facets": {"customer": "unknown"}}]}}
        captured = []
        def fake_encode(texts):
            captured.extend(texts)
            return np.eye(768)[:len(texts)], {"synthetic": True}
        with tempfile.TemporaryDirectory() as tmp, patch("modular_validation.features._encode_groups", fake_encode):
            build_activity_embeddings(corpus, tmp, profiles)
        self.assertEqual(captured, ["Fleet services"])

    def test_full_and_subset_lexical_models_do_not_share_row_cache(self):
        def model(universe, *_):
            return SimpleNamespace(X_tfidf=sparse.csr_matrix(np.ones((len(universe), 2))),
                                   X_lsa=np.ones((len(universe), 2)), vocab=["x", "y"])
        def corpus(ids):
            return SimpleNamespace(universe=pd.DataFrame({"IQ_COMPANY_ID": ids,
                                   "clean_text": ["evidence " + cid for cid in ids]}),
                                   provenance={"page_text_digest": "same raw full corpus"},
                                   team_baseline=SimpleNamespace(Model=model))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(features._TEAM_MODEL, {}, clear=True):
            full = build_features(corpus(["A", "B", "C"]), tmp, "team_tfidf")
            subset = build_features(corpus(["B", "C"]), tmp, "team_tfidf")
            self.assertEqual(full["matrix"].shape[0], 3)
            self.assertEqual(subset["matrix"].shape[0], 2)
            self.assertEqual(subset["ids"], ["B", "C"])

    def test_activity_cache_does_not_reassign_vectors_when_row_order_changes(self):
        profiles = {cid: {"known_activities": [{"activity": cid, "facets": {}}]}
                    for cid in ["A", "B"]}
        def corpus(ids):
            return SimpleNamespace(universe=pd.DataFrame({"IQ_COMPANY_ID": ids}), provenance={})
        def encode(texts):
            result = np.zeros((len(texts), 768))
            for i, text in enumerate(texts):
                result[i, 0 if text == "A" else 1] = 1
            return result, {"synthetic": True}
        with tempfile.TemporaryDirectory() as tmp, patch("modular_validation.features._encode_groups", encode):
            first = build_activity_embeddings(corpus(["A", "B"]), tmp, profiles)
            reversed_order = build_activity_embeddings(corpus(["B", "A"]), tmp, profiles)
            np.testing.assert_array_equal(first["A"]["matrix"], reversed_order["A"]["matrix"])
            np.testing.assert_array_equal(first["B"]["matrix"], reversed_order["B"]["matrix"])


if __name__ == "__main__":
    unittest.main()
