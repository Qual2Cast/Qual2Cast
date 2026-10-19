"""Outcome-blind technical retry eligibility; never relevance-based selection."""
from copy import deepcopy


def technical_retry_reason(record):
    generation = record.get("generation", {})
    if generation.get("input_truncated", False):
        return None
    if generation.get("output_hit_limit", False):
        return "output_token_limit"
    if record.get("raw_model_object") is None and record.get("errors"):
        return "invalid_json_or_top_level_schema"
    return None


def validate_repair_config(first_pass, repair):
    """Only the predeclared output budget may change in a technical repair."""
    expected = deepcopy(first_pass)
    if expected.get("max_new_tokens") != 2048:
        raise ValueError("Expected a 2048-token first pass")
    expected["max_new_tokens"] = 4096
    if repair != expected:
        raise ValueError("Repair must preserve prompt, model, full sources and all settings except output budget 2048->4096")


def select_technical_repairs(first_pass_records, repair_records=None):
    """Choose by the predeclared technical trigger, never by apparent quality."""
    reasons = {cid: reason for cid, record in first_pass_records.items()
               if (reason := technical_retry_reason(record)) is not None}
    if repair_records is not None and set(repair_records) != set(reasons):
        raise ValueError("Repair records must cover every and only technical-trigger company")
    selected, lineage = {}, {}
    for cid, original in first_pass_records.items():
        use_repair = repair_records is not None and cid in reasons
        selected[cid] = repair_records[cid] if use_repair else original
        lineage[cid] = {"selection": "technical_retry" if use_repair else "first_pass",
                        "technical_trigger": reasons.get(cid),
                        "first_pass_status": original.get("status"),
                        "retry_status": repair_records[cid].get("status") if use_repair else None,
                        "selection_uses_relevance_or_valuation": False}
    return selected, lineage
