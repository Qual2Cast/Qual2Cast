"""Synthetic-only comparison/review tests: no company files or outcomes read."""
from pathlib import Path
import importlib.util
import csv
import json

import pytest

from modular_validation.experiment_comparison import (
    finite, leave_one_target_out, parse_grade, summarize_configuration,
    validate_reviews, weighted_cohen_kappa,
)


def value(cid, ape, **extras):
    return {"target_id": cid, "snapshot_ape": ape, "snapshot_absolute_log_error": ape,
            "estimate_multiple": 10 if ape is not None else None, **extras}


def review(pair, name, grade, **extras):
    return {"pair_id": pair, "reviewer_name": name, "actor_type": "human", "grade": grade,
            "independent_review": True, "source_urls_checked": "https://example.com/business",
            "material_unmatched_businesses": "Synthetic activity difference recorded.",
            "reason": "Synthetic test fixture, not an actual company judgment.", **extras}


def test_own_coverage_is_distinct_from_same_target_paired_error():
    method = [value("a", .1), value("b", None), value("c", .3)]
    baseline = [value("a", .2), value("b", .1), value("c", None)]
    result = summarize_configuration(method, baseline, fresh_ids=["a", "b", "c", "d"])
    assert result["own_median_ape"] == pytest.approx(.2)
    assert result["own_available_targets"] == 2
    assert result["own_unavailable_error_targets"] == 2
    assert result["own_error_coverage"] == .5
    assert result["common_paired_target_ids"] == ["a"]
    assert result["method_median_ape_common"] == .1
    assert result["baseline_median_ape_common"] == .2
    assert result["median_paired_ape_difference"] == -.1
    assert result["missing_target_rows"] == 1


def test_nonfinite_metrics_and_development_are_excluded_not_imputed():
    rows = [value("a", "nan"), value("b", float("inf")), value("dev", .001)]
    result = summarize_configuration(rows, [], fresh_ids=["a", "b"])
    assert result["own_available_targets"] == 0
    assert result["own_median_ape"] is None
    assert result["common_paired_targets"] == 0
    assert not finite("") and not finite(None) and not finite("nan")


def test_evidence_guard_and_strict_indication_are_separate():
    rows = [value("a", .1, evidence_guard_accepted="True", strict_indication_status="withheld"),
            value("b", .2, evidence_guard_accepted=False, strict_indication_status="withheld"),
            value("c", .3)]
    result = summarize_configuration(rows, rows, fresh_ids=["a", "b", "c"])
    assert result["evidence_guard_accepted_targets"] == 1
    assert result["evidence_guard_rejected_targets"] == 1
    assert result["evidence_guard_unknown_targets"] == 1
    assert result["strict_indication_available_targets"] == 0
    assert result["strict_indication_withheld_targets"] == 2
    assert result["own_available_targets"] == 3


def test_deletion_sensitivity_recomputes_coverage_and_is_not_refit():
    rows = [value("a", .1), value("b", .5), value("c", None)]
    results = leave_one_target_out(rows, rows, fresh_ids=["a", "b", "c"])
    assert len(results) == 3
    assert results[0]["own_median_ape"] == .5
    assert results[2]["own_error_coverage"] == 1
    assert all("not_cross_validation" in row["sensitivity_scope"] for row in results)


def test_duplicate_targets_are_rejected():
    with pytest.raises(ValueError, match="duplicate_target"):
        summarize_configuration([value("a", .1), value("a", .2)], [], fresh_ids=["a"])
    with pytest.raises(ValueError, match="duplicate_fresh"):
        summarize_configuration([], [], fresh_ids=["a", "a"])


@pytest.mark.parametrize("grade", ["U", "UNKNOWN", "UNJUDGED", None, ""])
def test_unknown_grade_never_equals_zero(grade):
    assert parse_grade(grade) is None
    assert parse_grade("0") == 0


@pytest.mark.parametrize("grade", [True, -1, 4, 2.0, "2.5", "irrelevant"])
def test_grade_scale_rejects_invalid_values(grade):
    with pytest.raises(ValueError):
        parse_grade(grade)


def test_submission_validation_names_sources_independence_and_namespaces():
    cases = [({"reviewer_name": ""}, "actual_reviewer"),
             ({"independent_review": False}, "independence"),
             ({"source_urls_checked": "file:///test"}, "source_urls"),
             ({"material_unmatched_businesses": ""}, "unmatched_business"),
             ({"reason": ""}, "reason"),
             ({"actor_type": "ai"}, "namespaces")]
    for changes, expected in cases:
        with pytest.raises(ValueError, match=expected):
            validate_reviews([review("p", "Reviewer A", 2, **changes)], actor_type="human")
    row = validate_reviews([review(" p ", " Reviewer A ", "U", source_urls_checked="")], actor_type="human")[0]
    assert row["pair_id"] == "p" and row["reviewer_name"] == "Reviewer A"
    assert row["review_status"] == "unknown" and row["grade"] is None


def test_pending_templates_and_submitted_unknown_are_different():
    rows = [{"pair_id": "p", "actor_type": "human", "reviewer_slot": "1", "grade": ""},
            review("p", "Reviewer A", "U")]
    result = validate_reviews(rows, actor_type="human", allowed_pair_ids=["p"])
    assert result[0]["pending"] and not result[1]["pending"]
    assert result[0]["grade"] is None and result[1]["grade"] is None
    with pytest.raises(ValueError, match="unknown_review_pair"):
        validate_reviews([review("q", "Reviewer A", 2)], actor_type="human", allowed_pair_ids=["p"])
    with pytest.raises(ValueError, match="duplicate_pair"):
        validate_reviews([review("p", "Reviewer A", 2)] * 2, actor_type="human")


def test_weighted_kappa_matches_reference_for_ordinal_synthetic_labels():
    from sklearn.metrics import cohen_kappa_score
    a, b = [0, 1, 2, 3, 0, 3], [0, 2, 2, 3, 1, 1]
    rows = [review(str(i), name, grade) for name, grades in [("A", a), ("B", b)] for i, grade in enumerate(grades)]
    for weighting in ["linear", "quadratic"]:
        result = weighted_cohen_kappa(rows, reviewer_names=["A", "B"], weighting=weighting)
        assert result["kappa"] == pytest.approx(cohen_kappa_score(a, b, labels=[0, 1, 2, 3], weights=weighting))
        assert result["exact_agreement"] == .5
        assert result["agreement_is_not_accuracy"]


def test_kappa_excludes_U_and_reports_coverage_and_degenerate_cases():
    rows = [review("a", "A", 0), review("a", "B", 0),
            review("b", "A", 3), review("b", "B", 3),
            review("c", "A", "U"), review("c", "B", 0)]
    result = weighted_cohen_kappa(rows, reviewer_names=["A", "B"], expected_pair_ids=["a", "b", "c", "d"])
    assert result["kappa"] == 1
    assert result["jointly_known_count"] == 2 and result["joint_coverage"] == .5
    assert result["excluded_unknown_pair_ids"] == ["c", "d"]
    constant = weighted_cohen_kappa(rows[:2], reviewer_names=["A", "B"])
    assert constant["kappa"] is None and constant["status"] == "unavailable_degenerate_marginals"
    unknown = weighted_cohen_kappa([], reviewer_names=["A", "B"], expected_pair_ids=["a"])
    assert unknown["kappa"] is None and unknown["jointly_known_count"] == 0


def builder():
    path = Path(__file__).resolve().parents[1] / "scripts/build_experiment_comparison.py"
    spec = importlib.util.spec_from_file_location("synthetic_comparison_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Main is guarded; no outcome files read.
    return module


def test_review_templates_are_blinded_and_preserved(tmp_path):
    script = builder()
    pool = [{"pair_id": "p", "target_id": "synthetic_a", "candidate_id": "synthetic_b", "target": "A", "candidate": "B",
             "target_url": "https://example.com/a", "candidate_url": "https://example.com/b",
             "method": "DO_NOT_LEAK", "score": "DO_NOT_LEAK", "observed_multiple": "DO_NOT_LEAK"}]
    human, ai, agreement = script.prepare_reviews(tmp_path, pool, ["", ""])
    assert len(human) == 2 and ai == []
    assert agreement["kappa"] is None
    first = tmp_path / "reviewer_1_template.csv"
    before = first.read_bytes()
    assert b"DO_NOT_LEAK" not in before
    assert all(row["reviewer_name"] == "" and row["grade"] is None for row in human)
    script.prepare_reviews(tmp_path, pool, ["", ""])
    assert first.read_bytes() == before
    with pytest.raises(ValueError, match="pool_changed"):
        script.prepare_reviews(tmp_path, [{**pool[0], "pair_id": "different"}], ["", ""])


def test_method_metadata_preserves_explicit_factor_details_and_unknowns():
    script = builder()
    assert script.method_metadata("new_unknown_method")["metadata_status"] == "unavailable"
    metadata = {"new_method": {"factor_family": ["size"], "acquisition": "synthetic_source"}}
    result = script.method_metadata("new_method", metadata)
    assert result["factor_family"] == ["size"] and result["similarity"] == "unavailable_metadata"


def test_review_metrics_do_not_turn_AI_into_human_or_unknown_into_bad(tmp_path):
    script = builder()
    pool = [{"pair_id": "p", "target_id": "t", "candidate_id": "a"},
            {"pair_id": "q", "target_id": "t", "candidate_id": "b"}]
    records = validate_reviews([review("p", "Agent", 3, actor_type="ai"),
                                review("q", "Agent", "U", actor_type="ai")], actor_type="ai")
    ranks = [{"target_id": "t", "candidate_id": "a", "method": "synthetic", "rank": "1"},
             {"target_id": "t", "candidate_id": "b", "method": "synthetic", "rank": "2"}]
    result = script.review_metrics(records, pool, ranks, ["synthetic"], [2], actor_type="ai")[0]
    assert result["actor_type"] == "ai" and not result["independent_human_truth"]
    assert result["precision_at_k"] is None and result["pooled_ndcg"] is None
    assert result["precision_lower"] == .5 and result["precision_upper"] == 1
    summary = script.configuration_review_summary([result], "synthetic", 2, ["t", "missing"])
    assert summary["Agent"]["judgment_coverage_at_k"] == .25
    assert summary["Agent"]["point_precision_available_targets"] == 0
    assert script.configuration_review_summary([], "synthetic", 2, ["t"]) == {}
