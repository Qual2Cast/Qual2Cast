"""Validate provisional whole-company comparisons, without assigning truth."""
from __future__ import annotations
import copy

from .evidence_policy import profile_eligibility, VERSION as EVIDENCE_POLICY_VERSION

VERSION = "all-activities-and-cache-revalidation-v2-2026-10-18"


def validate_judgment(parsed, *, activities_a, activities_b):
    """Require all supplied activities to be explicitly accounted for.

    Structural validation cannot establish that the comparison or attribution is
    correct. It prevents the model silently discarding an inconvenient division.
    Multiple matched counterparts are permitted; matched and unmatched sets must
    be disjoint and exhaust the supplied activities in each company.
    """
    if not isinstance(parsed, dict):
        raise ValueError("comparison_must_be_object")
    grade = parsed.get("grade")
    if grade is not None and (type(grade) is not int or grade not in (0, 1, 2, 3)):
        raise ValueError("invalid_integer_grade")
    if not isinstance(parsed.get("scope_adequate"), bool):
        raise ValueError("missing_boolean_scope_adequacy")
    allowed_a = {f"A{i}" for i in range(activities_a)}
    allowed_b = {f"B{i}" for i in range(activities_b)}
    matched = parsed.get("matched_activity_ids")
    if not isinstance(matched, list):
        raise ValueError("missing_matched_activity_ids")
    for pair in matched:
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(v, str) for v in pair):
            raise ValueError("invalid_matched_activity_ids")
        if pair[0] not in allowed_a or pair[1] not in allowed_b:
            raise ValueError("invalid_matched_activity_ids")
    for field, allowed, side in [("unmatched_A", allowed_a, 0), ("unmatched_B", allowed_b, 1)]:
        unmatched = parsed.get(field)
        if not isinstance(unmatched, list) or any(not isinstance(v, str) or v not in allowed for v in unmatched):
            raise ValueError("invalid_unmatched_activity_ids")
        if len(set(unmatched)) != len(unmatched):
            raise ValueError("duplicate_unmatched_activity_ids")
        covered = {pair[side] for pair in matched}
        if covered & set(unmatched):
            raise ValueError("activity_both_matched_and_unmatched")
        if covered | set(unmatched) != allowed:
            raise ValueError("unaccounted_company_activity")
    if grade is not None and grade > 0 and not matched:
        raise ValueError("positive_grade_without_supported_activity_match")
    if not isinstance(parsed.get("reason"), str) or not parsed["reason"].strip():
        raise ValueError("missing_explanation")
    return {"grade": grade if parsed["scope_adequate"] and activities_a and activities_b else None,
            "all_supplied_activities_accounted_for": True,
            "human_truth": False,
            "error": "missing_company_activity_evidence" if not activities_a or not activities_b
            else "model_abstained_insufficient_scope" if not parsed["scope_adequate"] else None}


def revalidate_judgment_record(record, *, profile_a, profile_b):
    """Derive a current grade from raw parsed evidence, never a cached grade.

    This returns a separate normalized record. It does not modify raw cache data
    or establish semantic truth. Unknown generation/truncation metadata abstains.
    Profiles must be passed in the same A/B order as the original model input.
    """
    result = copy.deepcopy(record)
    result["cached_grade_before_revalidation"] = record.get("grade")
    result["grade"] = None
    result["human_truth"] = False
    result["current_validation"] = {
        "validator_version": VERSION,
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "raw_cache_modified": False,
    }
    if not profile_eligibility(profile_a)[0] or not profile_eligibility(profile_b)[0]:
        result["error"] = "missing_or_explicitly_truncated_company_activity_evidence"
        return result
    generation = record.get("generation")
    if not isinstance(generation, dict) or any(
        type(generation.get(flag)) is not bool
        for flag in ("input_truncated", "output_hit_limit")
    ):
        result["error"] = "unknown_generation_truncation_status"
        return result
    if generation["input_truncated"] or generation["output_hit_limit"]:
        result["error"] = "truncated_input_or_output"
        return result
    try:
        check = validate_judgment(
            record.get("parsed"), activities_a=len(profile_a["known_activities"]),
            activities_b=len(profile_b["known_activities"]),
        )
        result["grade"], result["error"] = check["grade"], check["error"]
        result["current_validation"].update(check)
    except (TypeError, ValueError) as exc:
        result["error"] = str(exc)
    return result
