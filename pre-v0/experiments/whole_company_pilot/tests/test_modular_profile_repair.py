import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modular_validation.profile_repair import technical_retry_reason, validate_repair_config, select_technical_repairs


class TechnicalRepairs(unittest.TestCase):
    def test_only_technical_output_failure_qualifies(self):
        self.assertEqual(technical_retry_reason({"generation": {"output_hit_limit": True}}),
                         "output_token_limit")
        self.assertEqual(technical_retry_reason({"raw_model_object": None, "errors": ["invalid JSON"]}),
                         "invalid_json_or_top_level_schema")
        self.assertIsNone(technical_retry_reason({"raw_model_object": {"activities": []},
                         "known_activities": [], "errors": []}))
        self.assertIsNone(technical_retry_reason({"generation": {"input_truncated": True,
                         "output_hit_limit": True}, "raw_model_object": None, "errors": ["JSON"]}))

    def test_no_hidden_prompt_model_or_source_change(self):
        original = {"max_new_tokens": 2048, "model": "same", "prompt": "same", "sources": "all"}
        repaired = {**original, "max_new_tokens": 4096}
        validate_repair_config(original, repaired)
        for key in ["model", "prompt", "sources"]:
            with self.assertRaises(ValueError):
                validate_repair_config(original, {**repaired, key: "changed"})

    def test_repairs_are_uniform_and_never_chosen_by_better_result(self):
        first = {"A": {"generation": {"output_hit_limit": True}, "status": "truncated_incomplete"},
                 "B": {"raw_model_object": None, "errors": ["JSON"], "status": "unknown_or_invalid"},
                 "C": {"raw_model_object": {"activities": []}, "errors": []}}
        with self.assertRaises(ValueError):
            select_technical_repairs(first, {"A": {}})
        with self.assertRaises(ValueError):
            select_technical_repairs(first, {"A": {}, "B": {}, "C": {}})
        retry = {"A": {"status": "unknown_or_invalid"}, "B": {"status": "truncated_incomplete"}}
        selected, lineage = select_technical_repairs(first, retry)
        self.assertIs(selected["A"], retry["A"])
        self.assertIs(selected["B"], retry["B"])
        self.assertIs(selected["C"], first["C"])
        self.assertEqual(lineage["A"]["selection"], "technical_retry")
        self.assertFalse(lineage["A"]["selection_uses_relevance_or_valuation"])


if __name__ == "__main__":
    unittest.main()
