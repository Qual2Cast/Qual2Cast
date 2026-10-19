import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modular_validation.profile_validation import validate_record


class ProfileValidation(unittest.TestCase):
    def record(self, activities):
        return {"raw_model_object": {"activities": activities}, "known_activities": [],
                "generation": {}, "human_truth": False}

    def item(self, **updates):
        return {"activity": "Software", "role": "software_provider", "facets": {},
                "source_id": "P1", "quote": "Software for fleet and healthcare businesses", **updates}

    def test_distinct_facets_preserve_business_scope_and_exact_duplicates_consolidate(self):
        first = self.item(facets={"customer": "fleet operators"})
        second = self.item(facets={"customer": "healthcare businesses"})
        original = self.record([first, second, dict(first)])
        out = validate_record(original, {"P1": first["quote"]})
        self.assertEqual(len(out["known_activities"]), 2)
        self.assertEqual(out["known_activities"][0]["additional_evidence"], [])
        self.assertEqual(original["known_activities"], [])
        self.assertFalse(out["human_scope_reviewed"])

    def test_missing_quote_rejected_and_nonstring_facets_not_coerced_to_facts(self):
        good = self.item(facets={"customer": ["invented list"], "revenue_model": "unknown", "product_function": "fleet operations"})
        bad = self.item(quote="Unseen source quotation goes here")
        out = validate_record(self.record([good, bad]), {"P1": good["quote"]})
        self.assertEqual(len(out["known_activities"]), 1)
        self.assertEqual(out["known_activities"][0]["facets"], {"product_function": "fleet operations"})
        self.assertEqual(out["rejected_activities"][0]["reason"], "quote_not_in_source")


if __name__ == "__main__":
    unittest.main()
