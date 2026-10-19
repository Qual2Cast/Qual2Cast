from modular_validation.evidence_policy import profile_eligibility


def test_truncation_overrides_present_activity():
    p = {"known_activities": [{"activity": "software"}], "generation": {"input_truncated": True}}
    assert profile_eligibility(p) == (False, "explicitly_truncated_profile")
    p["generation"] = {"output_hit_limit": True}
    assert not profile_eligibility(p)[0]


def test_missing_is_unknown_and_supported_is_not_approval():
    assert not profile_eligibility({})[0]
    assert profile_eligibility({"known_activities": [{"activity": "software"}]}) == (True, "supported_unreviewed_activity_evidence")
