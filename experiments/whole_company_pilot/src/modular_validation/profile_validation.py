"""Schema and source-span checks, explicitly not semantic human validation."""
from __future__ import annotations
import copy
import hashlib
import json

VERSION = "literal-schema-scope-preserving-v2-2026-10-18"
ROLES = {"producer", "software_provider", "service_provider", "distributor",
         "marketplace", "owner_operator", "unknown"}
UNKNOWN = {"", "unknown", "not stated", "not specified", "none", "n/a"}


def normalize(text):
    return " ".join(text.split()).casefold()


def validate_record(record, sources):
    """Preserve raw generation; correct schema/dedup without inventing evidence."""
    result = copy.deepcopy(record)
    accepted, rejected, field_issues = [], [], []
    seen = {}
    parsed = record.get("raw_model_object")
    activities = parsed.get("activities", []) if isinstance(parsed, dict) else []
    if not isinstance(activities, list):
        activities = []
        field_issues.append({"field": "activities", "issue": "not_a_list"})
    for index, item in enumerate(activities):
        if not isinstance(item, dict):
            rejected.append({"item_index": index, "reason": "not_an_object"})
            continue
        source, quote, activity = item.get("source_id"), item.get("quote"), item.get("activity")
        reason = ("unknown_source" if not isinstance(source, str) or source not in sources else
                  "short_or_missing_quote" if not isinstance(quote, str) or len(quote.split()) < 4 else
                  "quote_not_in_source" if normalize(quote) not in normalize(sources[source]) else
                  "missing_activity" if not isinstance(activity, str) or not activity.strip() else None)
        if reason:
            rejected.append({"item_index": index, "raw_item": item, "reason": reason})
            continue
        role = item.get("role", "unknown")
        if not isinstance(role, str) or role not in ROLES:
            field_issues.append({"item_index": index, "field": "role", "issue": "unrecognized_role_set_unknown"})
            role = "unknown"
        facets = item.get("facets", {})
        if not isinstance(facets, dict):
            field_issues.append({"item_index": index, "field": "facets", "issue": "not_a_dict_set_unknown"})
            facets = {}
        clean_facets = {}
        for key, value in facets.items():
            if not isinstance(key, str) or not isinstance(value, str):
                field_issues.append({"item_index": index, "field": str(key), "issue": "nonstring_facet_omitted"})
            elif normalize(value) not in UNKNOWN:
                clean_facets[key] = value.strip()
        # Different business contexts/facets must never disappear merely because
        # the model reused a short product label and operating-role label.
        signature = (normalize(activity), role,
                     tuple(sorted((normalize(k), normalize(v)) for k, v in clean_facets.items())))
        if signature in seen:
            previous = accepted[seen[signature]]
            additional = {"source_id": source, "quote": quote}
            primary = {"source_id": previous["source_id"], "quote": previous["quote"]}
            if additional != primary and additional not in previous["additional_evidence"]:
                previous["additional_evidence"].append(additional)
            continue
        seen[signature] = len(accepted)
        accepted.append({"activity": activity.strip(), "role": role, "facets": clean_facets,
                         "source_id": source, "quote": quote,
                         "additional_evidence": [], "source_support": "normalized_literal_quote_present",
                         "semantic_role_human_verified": False})
    result["original_extraction_activity_count"] = len(record.get("known_activities", []))
    result["known_activities"] = accepted
    result["rejected_activities"] = rejected
    result["schema_field_issues"] = field_issues
    result["validation_version"] = VERSION
    result["validation_source_digest"] = hashlib.sha256(
        json.dumps(sources, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    generation = record.get("generation", {})
    result["status"] = ("truncated_incomplete" if generation.get("input_truncated") or generation.get("output_hit_limit") else
                        "model_extracted_unreviewed" if accepted else "unknown_or_invalid")
    result["scope_complete"] = False
    result["human_scope_reviewed"] = False
    result["human_truth"] = False
    return result
