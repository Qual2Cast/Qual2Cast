import unittest
from modular_validation.judgments import validate_judgment, revalidate_judgment_record


class JudgmentTests(unittest.TestCase):
    def base(self):
        return dict(grade=2, scope_adequate=True, matched_activity_ids=[["A0", "B0"]],
                    unmatched_A=["A1"], unmatched_B=[], reason="Synthetic example: one adjacent business.")

    def test_unmatched_division_retained(self):
        self.assertEqual(validate_judgment(self.base(), activities_a=2, activities_b=1)["grade"], 2)

    def test_cherry_picked_division_rejected(self):
        value=self.base(); value["unmatched_A"]=[]
        with self.assertRaisesRegex(ValueError,"unaccounted"):
            validate_judgment(value, activities_a=2, activities_b=1)

    def test_double_assignment_rejected(self):
        value=self.base(); value["unmatched_A"]=["A0","A1"]
        with self.assertRaisesRegex(ValueError,"both_matched"):
            validate_judgment(value, activities_a=2, activities_b=1)

    def test_insufficient_scope_abstains(self):
        value=self.base(); value["scope_adequate"]=False
        self.assertIsNone(validate_judgment(value, activities_a=2, activities_b=1)["grade"])

    def test_boolean_grade_is_not_integer_grade(self):
        value=self.base(); value["grade"]=True
        with self.assertRaisesRegex(ValueError,"integer"):
            validate_judgment(value, activities_a=2, activities_b=1)

    def cached(self):
        return {"grade": 3, "parsed": self.base(),
                "generation": {"input_truncated": False, "output_hit_limit": False}}

    def profiles(self):
        return ({"known_activities": [{"activity": "synthetic A0"}, {"activity": "synthetic A1"}]},
                {"known_activities": [{"activity": "synthetic B0"}]})

    def test_cache_grade_is_rederived_without_mutating_raw(self):
        raw = self.cached(); a, b = self.profiles()
        result = revalidate_judgment_record(raw, profile_a=a, profile_b=b)
        self.assertEqual(result["grade"], 2)
        self.assertEqual(raw["grade"], 3)
        self.assertNotIn("current_validation", raw)
        self.assertFalse(result["current_validation"]["raw_cache_modified"])

    def test_cache_must_account_for_current_activity_inventory(self):
        raw = self.cached(); a, b = self.profiles()
        a["known_activities"].append({"activity": "synthetic extra division"})
        result = revalidate_judgment_record(raw, profile_a=a, profile_b=b)
        self.assertIsNone(result["grade"])
        self.assertEqual(result["error"], "unaccounted_company_activity")

    def test_cache_truncation_or_unknown_metadata_abstains(self):
        a, b = self.profiles()
        for generation in ({"input_truncated": True, "output_hit_limit": False},
                           {"input_truncated": False, "output_hit_limit": True}, {}, None):
            with self.subTest(generation=generation):
                raw = self.cached(); raw["generation"] = generation
                self.assertIsNone(revalidate_judgment_record(raw, profile_a=a, profile_b=b)["grade"])

    def test_cache_current_profile_eligibility_overrides_grade(self):
        raw = self.cached(); a, b = self.profiles()
        b["generation"] = {"input_truncated": True}
        result = revalidate_judgment_record(raw, profile_a=a, profile_b=b)
        self.assertIsNone(result["grade"])
        self.assertEqual(result["error"], "missing_or_explicitly_truncated_company_activity_evidence")

    def test_reversed_cache_uses_presented_activity_order(self):
        raw = self.cached(); a, b = self.profiles()
        raw["parsed"]["unmatched_A"] = []
        raw["parsed"]["unmatched_B"] = ["B1"]
        result = revalidate_judgment_record(raw, profile_a=b, profile_b=a)
        self.assertEqual(result["grade"], 2)
