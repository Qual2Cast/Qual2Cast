"""Pure descriptive comparisons and review validation; no file or outcome reads."""
from __future__ import annotations

import math
import statistics
from urllib.parse import urlparse

VERSION = "descriptive-configurations-and-independent-review-v1-2026-10-18"


def finite(value):
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def truth(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None


def _metric(rows, key):
    return {str(row["target_id"]): float(row[key]) for row in rows
            if finite(row.get(key)) and float(row[key]) >= 0}


def _stat(values, function):
    values = list(values)
    return float(function(values)) if values else None


def summarize_configuration(rows, baseline_rows, *, fresh_ids):
    """Show own coverage and common-target paired errors without significance tests."""
    fresh = list(map(str, fresh_ids))
    if len(fresh) != len(set(fresh)):
        raise ValueError("duplicate_fresh_target")
    allowed = set(fresh)
    rows = [row for row in rows if str(row["target_id"]) in allowed]
    baseline_rows = [row for row in baseline_rows if str(row["target_id"]) in allowed]
    for records in (rows, baseline_rows):
        if len(records) != len({str(row["target_id"]) for row in records}):
            raise ValueError("duplicate_target_within_configuration")
    a, b = _metric(rows, "snapshot_ape"), _metric(baseline_rows, "snapshot_ape")
    logs = _metric(rows, "snapshot_absolute_log_error")
    common = sorted(set(a) & set(b))
    differences = [a[cid] - b[cid] for cid in common]
    guards = [truth(row.get("evidence_guard_accepted")) for row in rows]
    strict_available = sum(finite(row.get("strict_estimate_multiple")) for row in rows)
    return {
        "expected_fresh_targets": len(fresh), "present_target_rows": len(rows),
        "missing_target_rows": len(fresh) - len(rows),
        "own_available_targets": len(a), "own_available_target_ids": sorted(a),
        "own_unavailable_error_targets": len(fresh) - len(a),
        "own_error_coverage": len(a) / len(fresh) if fresh else None,
        "own_median_ape": _stat(a.values(), statistics.median),
        "own_mean_ape": _stat(a.values(), statistics.mean),
        "own_median_absolute_log_error": _stat(logs.values(), statistics.median),
        "own_log_error_count": len(logs),
        "baseline_own_available_targets": len(b),
        "common_paired_targets": len(common), "common_paired_target_ids": common,
        "method_median_ape_common": _stat((a[cid] for cid in common), statistics.median),
        "baseline_median_ape_common": _stat((b[cid] for cid in common), statistics.median),
        "median_paired_ape_difference": _stat(differences, statistics.median),
        "mean_paired_ape_difference": _stat(differences, statistics.mean),
        "method_lower_error_count_common": sum(value < 0 for value in differences),
        "method_equal_error_count_common": sum(value == 0 for value in differences),
        "evidence_guard_accepted_targets": sum(value is True for value in guards),
        "evidence_guard_rejected_targets": sum(value is False for value in guards),
        "evidence_guard_unknown_targets": sum(value is None for value in guards),
        "strict_indication_available_targets": strict_available,
        "strict_indication_withheld_targets": sum(row.get("strict_indication_status") == "withheld" for row in rows),
        "missing_exploratory_estimate_targets": sum(not finite(row.get("estimate_multiple")) for row in rows),
        "evaluation_scope": "descriptive_undated_snapshot_proxy_no_pvalues_no_model_selection",
        "original_fresh_subset_status": "source_inspected_exploratory_development_not_independent_holdout",
    }


def leave_one_target_out(rows, baseline_rows, *, fresh_ids):
    """Delete each target from descriptive summaries; this does NOT retrain models."""
    ids = list(map(str, fresh_ids))
    return [{"excluded_target_id": cid,
             **summarize_configuration(rows, baseline_rows, fresh_ids=[value for value in ids if value != cid]),
             "sensitivity_scope": "descriptive_target_deletion_not_cross_validation_or_retraining"}
            for cid in ids]


def parse_grade(value):
    if value is None or (isinstance(value, str) and value.strip().upper() in ("", "U", "UNKNOWN", "UNJUDGED")):
        return None
    if isinstance(value, bool):
        raise ValueError("grade_must_be_0_1_2_3_or_U")
    if isinstance(value, int) and value in range(4):
        return value
    if isinstance(value, str) and value.strip() in ("0", "1", "2", "3"):
        return int(value.strip())
    raise ValueError("grade_must_be_0_1_2_3_or_U")


def validate_reviews(records, *, actor_type, allowed_pair_ids=None):
    """Validate submitted reviews; blank template rows stay pending, U is unknown.

    Named humans must attest independent initial review. AI submissions are
    accepted only through the separate AI namespace and never become human truth.
    """
    if actor_type not in ("human", "ai"):
        raise ValueError("actor_type_must_be_human_or_ai")
    allowed = set(map(str, allowed_pair_ids)) if allowed_pair_ids is not None else None
    normalized, seen = [], set()
    for record in records:
        row = dict(record)
        pair = str(row.get("pair_id", "")).strip()
        if not pair or (allowed is not None and pair not in allowed):
            raise ValueError("unknown_review_pair")
        if row.get("actor_type") != actor_type:
            raise ValueError("human_and_AI_review_namespaces_must_remain_separate")
        raw_grade = row.get("grade", row.get("whole_company_grade"))
        pending = raw_grade is None or (isinstance(raw_grade, str) and not raw_grade.strip())
        name = str(row.get("reviewer_name", "")).strip()
        grade = parse_grade(raw_grade)
        if not pending:
            if not name:
                raise ValueError("submitted_review_requires_actual_reviewer_name")
            if actor_type == "human" and truth(row.get("independent_review")) is not True:
                raise ValueError("human_review_requires_independence_attestation")
            if not str(row.get("reason", "")).strip():
                raise ValueError("submitted_review_requires_reason_including_U")
            if grade is not None:
                urls = row.get("source_urls_checked", [])
                if isinstance(urls, str):
                    urls = [url.strip() for url in urls.replace("\n", "|").split("|") if url.strip()]
                if not isinstance(urls, list) or not urls or any(
                    not isinstance(url, str) or urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc
                    for url in urls
                ):
                    raise ValueError("known_grade_requires_source_urls")
                if not str(row.get("material_unmatched_businesses", "")).strip():
                    raise ValueError("known_grade_requires_explicit_unmatched_business_account")
                row["source_urls_checked"] = urls
        key = (pair, name or str(row.get("reviewer_slot", "")))
        if key in seen:
            raise ValueError("duplicate_pair_reviewer")
        seen.add(key)
        row.update(pair_id=pair, reviewer_name=name, grade=grade, pending=pending, human_truth_claimed=False,
                   review_status="pending" if pending else "unknown" if grade is None else "submitted_unadjudicated")
        normalized.append(row)
    return normalized


def weighted_cohen_kappa(records, *, reviewer_names, expected_pair_ids=None, weighting="quadratic"):
    """Use separate reviewer marginals and jointly known grades; U is not grade 0."""
    reviewer_names = [str(name).strip() for name in reviewer_names]
    if len(reviewer_names) != 2 or len(set(reviewer_names)) != 2 or not all(reviewer_names):
        raise ValueError("two_distinct_actual_reviewer_names_required")
    if weighting not in ("linear", "quadratic"):
        raise ValueError("unknown_kappa_weighting")
    normalized = validate_reviews(records, actor_type="human", allowed_pair_ids=expected_pair_ids)
    unexpected = {row.get("reviewer_name") for row in normalized if not row["pending"]} - set(reviewer_names)
    if unexpected:
        raise ValueError("reviewer_not_in_declared_roster")
    maps = [{row["pair_id"]: row["grade"] for row in normalized
             if row.get("reviewer_name") == name and not row["pending"]} for name in reviewer_names]
    pool = sorted(set(map(str, expected_pair_ids)) if expected_pair_ids is not None else set(maps[0]) | set(maps[1]))
    joint = [pair for pair in pool if maps[0].get(pair) is not None and maps[1].get(pair) is not None]
    matrix = [[0 for _ in range(4)] for _ in range(4)]
    for pair in joint:
        matrix[maps[0][pair]][maps[1][pair]] += 1
    n = len(joint)
    result = {"reviewer_names": list(reviewer_names), "weighting": weighting, "jointly_known_count": n,
              "expected_pair_count": len(pool), "joint_coverage": n / len(pool) if pool else None,
              "reviewer_known_counts": [sum(value is not None for value in mapping.values()) for mapping in maps],
              "unknown_or_unsubmitted_pair_count": len(pool)-n, "confusion_matrix_0_to_3": matrix,
              "kappa": None, "agreement_is_not_accuracy": True,
              "chance_model": "Cohen_separate_reviewer_marginals",
              "excluded_unknown_pair_ids": [pair for pair in pool if pair not in set(joint)]}
    if not n:
        return {**result, "status": "unavailable_no_jointly_known_grades"}
    exponent = 2 if weighting == "quadratic" else 1
    weights = [[(abs(i-j)/3)**exponent for j in range(4)] for i in range(4)]
    marginal_a = [sum(row)/n for row in matrix]
    marginal_b = [sum(matrix[i][j] for i in range(4))/n for j in range(4)]
    observed = sum(weights[i][j]*matrix[i][j]/n for i in range(4) for j in range(4))
    expected = sum(weights[i][j]*marginal_a[i]*marginal_b[j] for i in range(4) for j in range(4))
    result.update(observed_weighted_disagreement=observed, expected_weighted_disagreement=expected,
                  exact_agreement=sum(matrix[i][i] for i in range(4))/n)
    if expected == 0:
        return {**result, "status": "unavailable_degenerate_marginals"}
    return {**result, "kappa": 1-observed/expected, "status": "available_descriptive_only"}
