"""Pre-outcome evidence eligibility; support is not semantic validation."""

VERSION = "activity-support-and-truncation-v1-2026-10-18"


def profile_eligibility(record):
    """Do not silently score an explicitly truncated company as a whole business."""
    if not isinstance(record, dict):
        return False, "missing_profile"
    generation = record.get("generation") or {}
    if generation.get("input_truncated") or generation.get("output_hit_limit") or record.get("status") == "truncated_incomplete":
        return False, "explicitly_truncated_profile"
    if not record.get("known_activities"):
        return False, "missing_supported_activities"
    return True, "supported_unreviewed_activity_evidence"
