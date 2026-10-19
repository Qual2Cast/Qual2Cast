"""Build descriptive tables only after frozen evaluation and direct models finish.

This does not load the company financial snapshot, fit models, change rankings,
select a winning method, invent grades, or run evaluation. Main reads completed
evaluation outputs, so invoke only after the experiment owner authorizes it.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modular_validation.evaluation import common_pool_metrics, verify_experiment_seal
from modular_validation.experiment_comparison import (
    VERSION, finite, leave_one_target_out, summarize_configuration,
    validate_reviews, weighted_cohen_kappa,
)

OUT = Path(os.environ.get("QUAL2CAST_EXPERIMENT_DIR") or "outputs-local/modular-validation")
OUT = (OUT if OUT.is_absolute() else ROOT / OUT).resolve()
PARAMETERS = OUT / "parameters.json" if (OUT / "parameters.json").exists() else ROOT / "config/modular_validation_parameters.json"
BASELINE = "team_mpnet_cosine"
MODULE_FIELDS = ("acquisition", "representation", "similarity", "factor_family", "candidate_policy", "information_regime")
AGGREGATIONS = ("median", "harmonic", "weighted")
AGG_ALIASES = {"positive_harmonic": "harmonic", "positive_harmonic_mean": "harmonic",
               "reciprocal_rank_weighted_mean": "weighted", "nonnegative_rank_weighted_mean": "weighted"}
SOURCES = [
    "https://nlp.stanford.edu/IR-book/html/htmledition/assessing-relevance-1.html",
    "https://www.itl.nist.gov/div898/handbook/pri/section3/pri334.htm",
    "https://www.jmlr.org/papers/v11/cawley10a.html",
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def save_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, allow_nan=False)
                             if isinstance(value, (dict, list, tuple)) else value
                             for key, value in row.items()})


def configuration_id(method, k, aggregation):
    return f"{method}__k{k}__{aggregation}"


def method_metadata(method, factor_metadata=None):
    """Describe implemented modules; missing provenance is explicit, not guessed."""
    result = {key: "unavailable_metadata" for key in MODULE_FIELDS}
    result.update(metadata_status="unavailable", metadata_source="not_provided")
    representations = {
        "team_tfidf": ("team_clean_text_TFIDF", "cosine", "all_website_terms"),
        "team_lsa": ("team_clean_text_TFIDF_150D_LSA", "cosine", "all_website_terms"),
        "team_mpnet_cosine": ("MPNet_normalized_mean_200_word_chunks", "cosine", "all_website_text"),
        "team_equal_z_ensemble": ("TFIDF_LSA_MPNet", "equal_mean_zscored_cosines", "all_website_text"),
        "doc2vec_dbow_cosine": ("Doc2Vec_DBOW", "cosine", "all_website_text"),
        "mpnet_page_balanced": ("MPNet_equal_page_mean", "cosine", "all_captured_pages"),
        "mpnet_home_only": ("MPNet_home_page_only", "cosine", "home_page_text_ablation"),
        "mpnet_conservative_cleaning": ("MPNet_conservative_cleaning", "cosine", "all_captured_text"),
        "financial_rank_adapted": ("percentile_ranks", "mean_absolute_rank_difference", "revenue_margin_debt_to_revenue"),
        "mpnet_financial_rrf": ("dense_and_financial_rankings", "equal_RRF_constant60", "website_revenue_margin_debt_to_revenue"),
        "same_sic4_mpnet": ("MPNet_normalized_mean_200_word_chunks", "cosine", "website_and_SIC4"),
        "same_sic4_financial": ("percentile_ranks", "mean_absolute_rank_difference", "revenue_margin_debt_to_revenue_and_SIC4"),
        "same_sic4_id_baseline": ("SIC4_and_stable_ID", "stable_ID_order", "SIC4_only"),
        "profile_activity_centroid": ("MPNet_mean_supported_activities", "cosine", "all_extracted_supported_activities"),
        "balanced_activity_ot": ("MPNet_supported_activities_uniform_mass", "balanced_exact_EMD_1minus_cosine", "all_extracted_supported_activities"),
        "unbalanced_activity_ot": ("MPNet_supported_activities_uniform_mass", "unbalanced_KL_OT_rho1", "all_extracted_supported_activities"),
        "unbalanced_ot_rho_0.25": ("MPNet_supported_activities_uniform_mass", "unbalanced_KL_OT_rho0.25", "all_extracted_supported_activities"),
        "unbalanced_ot_rho_4.0": ("MPNet_supported_activities_uniform_mass", "unbalanced_KL_OT_rho4", "all_extracted_supported_activities"),
        "sector_activity_profile": ("source_supported_sector_facets", "equal_known_facet_cosine", "sector_product_customer_role_stage_facets"),
        "local_llm_derived_activity_ledger": ("source_supported_whole_company_activity_profiles", "local_LLM_provisional_grade_derived_ledger", "all_activities_with_deterministic_unmatched_complement"),
        "source_grounded_local_llm_rerank": ("source_supported_whole_company_activity_profiles", "local_LLM_provisional_ordinal_rerank", "known_matched_unmatched_activities"),
    }
    if method in representations:
        representation, similarity, factor = representations[method]
        financial = "financial" in method
        profile = method in {"profile_activity_centroid", "balanced_activity_ot", "unbalanced_activity_ot",
                             "unbalanced_ot_rho_0.25", "unbalanced_ot_rho_4.0", "sector_activity_profile", "source_grounded_local_llm_rerank", "local_llm_derived_activity_ledger"}
        result.update(acquisition="frozen_team_website_snapshot" + ("_plus_supplied_financials" if financial else ""),
                      representation=representation, similarity=similarity, factor_family=factor,
                      candidate_policy="same_SIC4_in_common_pilot" if method.startswith("same_sic4") or method == "sector_activity_profile"
                      else "multi_retriever_shortlist_within_common_pilot" if method in {"source_grounded_local_llm_rerank","local_llm_derived_activity_ledger"}
                      else "common_pilot_excluding_self",
                      information_regime="mentor_permitted_financial_augmentation" if financial else "website_and_local_source_constrained_extraction" if profile else "website_or_SIC_control",
                      metadata_status="documented_in_frozen_runner_sources", metadata_source="scripts/run_modular_validation.py_and_profile_and_LLM_runners")
    supplied = (factor_metadata or {}).get(method)
    if supplied:
        result.update({key: supplied.get(key, result[key]) for key in MODULE_FIELDS})
        result.update(metadata_status="factor_runner_metadata", metadata_source="factors/method_metadata.json")
        result["factor_method_details"] = supplied
    purely_financial = method.startswith("financial_") or method == "same_sic4_financial"
    result["cleaning"] = "not_applicable_to_financial_features" if purely_financial else "not_applicable_to_SIC_ID_control" if method == "same_sic4_id_baseline" else "conservative_restore_scope_with_name_masking" if method == "mpnet_conservative_cleaning" else "frozen_team_cleaning_and_name_masking_or_supported_activity_sources_see_runner"
    result["source_family"] = supplied.get("source_family", "frozen_implementation_and_method_research") if supplied else "frozen_implementation_and_method_research"
    return result


RUBRIC = """Independent whole-company comparability review

Purpose: assess business comparability for explaining a proposed peer set. This
does not approve a valuation multiple, investment, forecast, or causal model.

Two actual named reviewers independently complete their separate CSVs. Names
are initially blank, not fictional. Each reviewer sees company names, official
source URLs, full available business evidence and the same rubric. Method,
rank, similarity score, valuation estimate and outcome must remain hidden.
Do not open the configuration/error tables or the other reviewer's responses
before submitting an initial review. Preserve original reviews; adjudicate
disagreements separately, with a new reason and without replacing the originals.

Grade 3: strong whole-company business comparability. The principal supported
activities, operating role, customers and product/commercialization setting
align; remaining material differences are explicitly described.
Grade 2: plausible business comparable with material differences. Describe all
matched and unmatched activities and why the company could still inform review.
Grade 1: partial activity/product overlap with important whole-company mismatch;
insufficient as a strong company comparable without a specific justification.
Grade 0: sources support a fundamental business mismatch, even if vocabulary or
industry labels overlap. This is an observed mismatch, not missing information.
U: evidence is insufficient, outdated, conflicting or does not support a
whole-company assessment. U remains unknown and never becomes grade zero.
Blank grade: review not yet submitted. U: reviewed but still unknown.

For every submitted review record your actual name, independent_review=true,
and reason. For grades 0-3, cite the HTTP(S) URLs checked and account explicitly
for material_unmatched_businesses (state 'none identified in checked evidence'
only when that is supported). Include supported activities, unknown scope and
source access dates where possible. Weighting a business by revenue requires
validated business weights; product list length is not a revenue weight. Do not
discard a subsidiary/activity simply to improve the match. Missing disclosure
does not establish that a company lacks an activity. An activity extraction is
provisional until checked against its source, and source support does not prove
complete coverage or historical truth. Current pages must be marked current,
not silently treated as the archived snapshot.

The review pool is the common union of methods' top ten plus seeded random
controls, not an exhaustive universe or random representative accuracy sample.
Precision@k uses grade >=2 for this declared rubric and fixed k. Unknown grades
withhold point precision where needed; common-pool nDCG needs a known common
ideal and cannot imply full-universe recall. Agreement uses separately named
human raters, quadratic weighted Cohen kappa (separate marginal distributions),
raw agreement and coverage; unknown pairs are excluded and counted, not zeroed.
No universal kappa pass mark is imposed. Agreement is not correctness. The IR
text's pooled-marginal worked kappa example is not our separate-marginal formula.

AI/source challenge audits, local LLM ranking grades, independent human reviews,
and financial snapshot errors are distinct evidence layers. AI assessments must
use actor_type=ai and cannot be imported as human truth. Challenge cases selected
for known mismatches are purposive diagnostics, not representative accuracy.

Sources:
https://nlp.stanford.edu/IR-book/html/htmledition/assessing-relevance-1.html
https://www.jmlr.org/papers/v11/cawley10a.html
https://www.itl.nist.gov/div898/handbook/pri/section3/pri334.htm
"""


def prepare_reviews(destination, pool, names):
    fields = ["pair_id", "target_id", "candidate_id", "target", "candidate", "target_url", "candidate_url",
              "reviewer_slot", "reviewer_name", "actor_type", "independent_review", "grade",
              "source_urls_checked", "source_access_dates", "supported_activities", "material_unmatched_businesses",
              "unknown_scope", "reason"]
    pair_ids = [row["pair_id"] for row in pool]
    if len(pair_ids) != len(set(pair_ids)):
        raise ValueError("duplicate_blinded_pool_pair")
    actual = []
    for index, name in enumerate(names, 1):
        path = destination / f"reviewer_{index}_template.csv"
        if not path.exists():
            rows = [{**{key: row.get(key, "") for key in fields}, "reviewer_slot": f"reviewer_{index}",
                     "reviewer_name": name, "actor_type": "human", "grade": "", "independent_review": ""} for row in pool]
            random.Random(4511 + index).shuffle(rows)
            save_csv(path, rows, fields)
        rows = read_csv(path)
        if set(row["pair_id"] for row in rows) != set(pair_ids):
            raise ValueError("existing_review_template_pool_changed_preserve_and_version_reviews")
        actual.extend(rows)
    (destination / "HUMAN_REVIEW_RUBRIC.txt").write_text(RUBRIC, encoding="utf-8")
    roster_path = destination / "reviewer_roster.json"
    if not roster_path.exists():
        save_json(roster_path, {"reviewer_names": names, "names_are_actual_not_fabricated": True,
                               "independent_initial_reviews_required": True})
    declared = read_json(roster_path)["reviewer_names"]
    normalized = validate_reviews(actual, actor_type="human", allowed_pair_ids=pair_ids)
    known_names = {row["reviewer_name"] for row in normalized if not row["pending"]}
    if known_names - set(declared):
        raise ValueError("submitted_name_not_in_roster_update_actual_roster_before_analysis")
    ready = len(declared) == 2 and all(declared) and len(set(declared)) == 2
    agreement = weighted_cohen_kappa(actual, reviewer_names=declared, expected_pair_ids=pair_ids) if ready else {
        "status": "awaiting_two_actual_named_independent_reviewers", "kappa": None,
        "expected_pair_count": len(pair_ids), "jointly_known_count": 0, "joint_coverage": 0.0,
        "agreement_is_not_accuracy": True}
    save_json(destination / "human_agreement.json", agreement)
    save_json(destination / "review_validation.json", {"human_review_records": len(normalized),
        "pending": sum(row["pending"] for row in normalized),
        "submitted_unknown": sum(not row["pending"] and row["grade"] is None for row in normalized),
        "known_unadjudicated": sum(row["grade"] is not None for row in normalized),
        "actual_declared_reviewer_names": declared, "templates_preserved_on_rerun": True})
    ai_path = destination / "ai_reviews.json"
    ai = validate_reviews(read_json(ai_path), actor_type="ai", allowed_pair_ids=pair_ids) if ai_path.exists() else []
    save_json(destination / "ai_review_validation.json", {"status": "provided_separate_AI_reviews" if ai else "planned_no_AI_grades_supplied",
        "records": len(ai), "known_grades": sum(row["grade"] is not None for row in ai),
        "independent_human_truth": False,
        "distinction": "AI review entries are separate from generating LLM ranking grades, qualitative agent challenges, and human reviews"})
    return normalized, ai, agreement


def review_metrics(records, pool, rankings, methods, ks, *, actor_type):
    submitted_names = sorted({row["reviewer_name"] for row in records if not row["pending"]})
    rows = []
    for name in submitted_names:
        by_pair = {row["pair_id"]: row["grade"] for row in records if row["reviewer_name"] == name}
        for cid in sorted({row["target_id"] for row in pool}):
            target_pool = [row for row in pool if row["target_id"] == cid]
            labels = {row["candidate_id"]: by_pair.get(row["pair_id"]) for row in target_pool}
            for method in methods:
                rank = [row for row in rankings if row["target_id"] == cid and row["method"] == method and finite(row.get("rank"))]
                rank.sort(key=lambda row: float(row["rank"]))
                for k in ks:
                    rows.append({"reviewer_name": name, "actor_type": actor_type, "target_id": cid, "method": method,
                                 **common_pool_metrics([row["candidate_id"] for row in rank], labels, pool_ids=list(labels), k=k),
                                 "independent_human_truth": False, "adjudication_status": "not_adjudicated"})
    return rows


def configuration_review_summary(metrics, method, k, fresh_ids):
    """Keep each assessor separate; do not silently average human judgments."""
    names = sorted({row["reviewer_name"] for row in metrics})
    summaries = {}
    for name in names:
        selected = [row for row in metrics if row["reviewer_name"] == name and row["method"] == method
                    and row["k"] == k and row["target_id"] in fresh_ids]
        summaries[name] = {"expected_target_count": len(fresh_ids), "present_target_count": len(selected),
            "judged_top_slots": sum(row["judged_top_count"] for row in selected),
            "expected_top_slots": len(fresh_ids) * k,
            "judgment_coverage_at_k": sum(row["judged_top_count"] for row in selected) / (len(fresh_ids) * k),
            "point_precision_available_targets": sum(row["precision_at_k"] is not None for row in selected),
            "point_pooled_ndcg_available_targets": sum(row["pooled_ndcg"] is not None for row in selected),
            "adjudicated": False, "unknown_labels_not_zero": True}
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer-1-name", default="")
    parser.add_argument("--reviewer-2-name", default="")
    args = parser.parse_args()
    evaluation = OUT / "evaluation"
    required = [evaluation / name for name in ("evaluation_status.json", "valuation_results.csv", "all_rankings.csv",
        "all_rankings_freeze.json", "direct_valuation_manifest.json", "direct_valuation_results.csv", "blind_human_review.csv")]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("Complete and authorize evaluation/direct model runs before comparison: " + ", ".join(missing))
    # Verify executable inputs BEFORE opening any outcome result file.
    frozen = read_json(evaluation / "all_rankings_freeze.json")
    current = {"ranking_inputs": {rel: digest(OUT / rel) for rel in frozen["ranking_inputs"]},
               "design_sha256": digest(OUT / "design_freeze.json"), "parameter_sha256": digest(PARAMETERS),
               "evaluation_script_sha256": digest(ROOT / "scripts/evaluate_modular_validation.py"),
               "direct_valuation_script_sha256": digest(ROOT / "scripts/run_direct_valuation.py"),
               "module_sha256": {p.name: digest(p) for p in sorted((ROOT / "src/modular_validation").glob("*.py"))}}
    proof = verify_experiment_seal(frozen, current)
    status = read_json(evaluation / "evaluation_status.json")
    direct_manifest = read_json(evaluation / "direct_valuation_manifest.json")
    if not status.get("completed_at_utc") or not direct_manifest.get("parameters_frozen_before_outcome_access"):
        raise RuntimeError("Evaluation/direct completion provenance is missing")
    verify_experiment_seal(direct_manifest["verified_digests"], current)
    design, parameters = read_json(OUT / "design_freeze.json"), read_json(PARAMETERS)
    target_info = {row["IQ_COMPANY_ID"]: row for row in design["targets"]}
    fresh = [cid for cid, row in target_info.items() if row["role"] == "fresh_pilot"]
    if len(fresh) != 9:
        raise ValueError("this_report_requires_the_frozen_nine_fresh_targets")
    values, rankings = read_csv(evaluation / "valuation_results.csv"), read_csv(evaluation / "all_rankings.csv")
    if any(row["target_id"] not in target_info or row["role"] != target_info[row["target_id"]]["role"] for row in values):
        raise ValueError("evaluation_targets_or_roles_differ_from_design")
    methods = sorted(set(design.get("methods_predeclared", [])) | {row["method"] for row in rankings} | {row["method"] for row in values})
    ks = sorted({int(parameters["peer_policies"]["required_k"]), *map(int, parameters["peer_policies"]["sensitivity_k"])})
    groups = {}
    for row in values:
        agg = AGG_ALIASES.get(row["aggregation"], row["aggregation"])
        if int(row["k"]) not in ks or agg not in AGGREGATIONS:
            raise ValueError("unexpected_k_or_aggregation_not_in_frozen_compatible_cross")
        groups.setdefault((row["method"], int(row["k"]), agg), []).append(row)
    if any(len(rows) != len({row["target_id"] for row in rows}) for rows in groups.values()):
        raise ValueError("duplicate_configuration_target_rows_including_development")
    destination = OUT / "comparison"
    destination.mkdir(exist_ok=True)
    metadata_path = OUT / "factors/method_metadata.json"
    metadata = read_json(metadata_path) if metadata_path.exists() else {}
    if "methods" in metadata:
        metadata = metadata["methods"]
    if isinstance(metadata, list):
        metadata = {row["method"]: row for row in metadata}
    pool = read_csv(evaluation / "blind_human_review.csv")
    human, ai, agreement = prepare_reviews(destination, pool, [args.reviewer_1_name.strip(), args.reviewer_2_name.strip()])
    human_metrics = review_metrics(human, pool, rankings, methods, ks, actor_type="human")
    ai_metrics = review_metrics(ai, pool, rankings, methods, ks, actor_type="ai")
    save_csv(destination / "human_ranking_metrics.csv", human_metrics, fields=None if human_metrics else ["actor_type", "reviewer_name", "target_id", "method", "k", "status"])
    save_csv(destination / "ai_ranking_metrics.csv", ai_metrics, fields=None if ai_metrics else ["actor_type", "reviewer_name", "target_id", "method", "k", "status"])
    config_rows, sensitivity, target_rows = [], [], []
    for method in methods:
        for k in ks:
            for aggregation in AGGREGATIONS:
                rows, baseline = groups.get((method, k, aggregation), []), groups.get((BASELINE, k, aggregation), [])
                config = {"configuration_id": configuration_id(method, k, aggregation), "method": method, "k": k,
                          "aggregation": aggregation, **method_metadata(method, metadata),
                          "evidence_policy": "unguarded_snapshot_experiment_plus_separate_strict_guard_no_refill",
                          "configuration_status": "observed" if rows else "declared_but_no_results",
                          "baseline_configuration_id": configuration_id(BASELINE, k, aggregation),
                          "business_grade_source": "independent_human_unadjudicated_if_supplied",
                          "human_known_grades_all_pool": sum(row["grade"] is not None for row in human),
                          "human_judgment_coverage_by_reviewer": configuration_review_summary(human_metrics, method, k, fresh),
                          "AI_review_stage": "separate_provisional_not_human_truth",
                          "AI_judgment_coverage_by_assessor": configuration_review_summary(ai_metrics, method, k, fresh),
                          "candidate_universe": design.get("scope", parameters.get("candidate_universe")),
                          "compute_provenance": "evaluation/all_rankings_freeze.json",
                          "limitations": "two_sector_nine_fresh_plus_development; undated_snapshot; no_winner_selection; dependent_methods"}
                config_rows.append({**config, **summarize_configuration(rows, baseline, fresh_ids=fresh)})
                sensitivity.extend({**config, **item} for item in leave_one_target_out(rows, baseline, fresh_ids=fresh))
                by_target = {row["target_id"]: row for row in rows}
                base_target = {row["target_id"]: row for row in baseline}
                for cid, target in target_info.items():
                    row, base = by_target.get(cid, {}), base_target.get(cid, {})
                    paired = finite(row.get("snapshot_ape")) and finite(base.get("snapshot_ape"))
                    target_rows.append({"configuration_id": config["configuration_id"], "method": method, "k": k, "aggregation": aggregation,
                        "target_id": cid, "target_ticker": target["target_ciq_ticker"], "role": target["role"],
                        **{key: row.get(key) for key in ("estimate_multiple", "snapshot_ape", "snapshot_absolute_log_error", "snapshot_signed_error",
                            "valuation_status", "reason", "selected_peers", "valid_peers", "effective_peers", "valid_peer_ids",
                            "evidence_guard_accepted", "evidence_guard_reasons", "strict_indication_status", "strict_indication_reasons")},
                        "result_row_status": "present" if row else "missing_configuration_target",
                        "paired_with_baseline": paired, "baseline_snapshot_ape": base.get("snapshot_ape"),
                        "paired_ape_difference": float(row["snapshot_ape"]) - float(base["snapshot_ape"]) if paired else None})
    save_csv(destination / "configuration_results.csv", config_rows)
    save_csv(destination / "configuration_target_errors.csv", target_rows)
    save_csv(destination / "leave_one_target_out.csv", sensitivity)
    direct_values = read_csv(evaluation / "direct_valuation_results.csv")
    if any(row["target_id"] not in target_info or row["role"] != target_info[row["target_id"]]["role"] for row in direct_values):
        raise ValueError("direct_evaluation_targets_or_roles_differ_from_design")
    direct_rows, direct_sensitivity = [], []
    direct_groups = {}
    for row in direct_values:
        direct_groups.setdefault((row["model"], row["information"]), []).append({**row, "estimate_multiple": row.get("prediction")})
    for model in ("ridge", "hist_gradient_boosting"):
        for information in ("financial_only", "financial_plus_website"):
            rows = direct_groups.get((model, information), [])
            baseline = groups.get((BASELINE, 5, "median"), [])
            config = {"configuration_id": f"direct__{model}__{information}", "model": model, "information": information,
                      "k": "not_applicable", "aggregation": "not_applicable", "baseline_configuration_id": configuration_id(BASELINE, 5, "median"),
                      "training_universe": direct_manifest["training_universe"],
                      "training_universe_company_count": direct_manifest["training_universe_company_count"],
                      "held_out_group": "all_ten_frozen_targets_excluded_from_training",
                      "business_relevance_validation": False, "strict_indication_policy": "not_implemented_for_direct_prediction_not_approved_valuation"}
            direct_rows.append({**config, **summarize_configuration(rows, baseline, fresh_ids=fresh)})
            direct_sensitivity.extend({**config, **item} for item in leave_one_target_out(rows, baseline, fresh_ids=fresh))
    save_csv(destination / "direct_configuration_results.csv", direct_rows)
    save_csv(destination / "direct_leave_one_target_out.csv", direct_sensitivity)
    save_csv(destination / "direct_target_errors.csv", direct_values)
    challenge_dir = OUT / "agent-assessment"
    challenges = [{"path": str(path.relative_to(OUT)), "sha256": digest(path)} for path in sorted(challenge_dir.glob("*"))
                  if path.is_file() and path.suffix.lower() in (".json", ".csv", ".txt")]
    save_json(destination / "agent_review_stage.json", {"status": "purposive_source_audit_artifacts_available" if challenges else "planned_awaiting_source_audits",
        "artifacts": challenges, "planned_challenges": ["GTII-MAPS", "HRMY-RMD", "PCTY-HURN", "CARG-PAL", "SABR-RAMP"],
        "selection": "purposively_selected_business_role_or_customer_challenges_from_baseline",
        "quantitative_labels_created": False, "representative_accuracy_claimed": False,
        "separate_from": ["human_review", "generating_LLM_rerank_scores", "snapshot_valuation_error"],
        "meaning": "Check source support, unmatched activities, role/customer differences and each method's retention of these pairs; not hard gold or random accuracy sample"})
    (destination / "COMPARISON_README.txt").write_text(
        "Compatible configuration comparison\n\n"
        "Read own coverage and common-paired errors together. The common paired set is recomputed for each method against the dense baseline at the SAME k and aggregation. "
        "Direct models use the declared dense k=5 median baseline separately. The nine originally fresh targets exclude PCTY. Frozen role labels are preserved for traceability; after source-informed design, all ten are exploratory development and no longer an independent holdout. Per-target files retain all ten with roles. "
        "Leave-one-target-out tables delete one target from descriptive summaries; they do not refit models and are not cross-validation. "
        "This is the full compatible method x peer-count x aggregation menu, plus separate direct-model information blocks. Methods are dependent bundles, not orthogonal factorial factors. "
        "No p-values, optimal weights, winner selection or historical forecasting claim are produced. Missing configurations remain visible. "
        "All estimates are undated snapshot diagnostics. Evidence support alone does not establish comparable-company relevance; strict guard counts and date/definition withholding remain visible.\n\n"
        "Human templates hide methods/ranks/scores/outcomes, preserve independent originals, and require actual names. Set actual names in reviewer_roster.json and each submitted CSV; CLI names apply only at first creation. Unknown is U, never zero. "
        "Human and AI metrics have separate files. No labels are fabricated. Source challenge cases are purposive qualitative diagnostics, not representative accuracy.\n\n"
        + "\n".join(SOURCES), encoding="utf-8")
    input_paths = required + [OUT / "design_freeze.json", PARAMETERS]
    if metadata_path.exists():
        input_paths.append(metadata_path)
    save_json(destination / "comparison_status.json", {"completed_at_utc": datetime.now(timezone.utc).isoformat(), "helper_version": VERSION,
        "experiment_dir": str(OUT), "script_sha256": digest(__file__), "helper_sha256": digest(ROOT / "src/modular_validation/experiment_comparison.py"),
        "freeze_verification": proof, "input_sha256": {str(path): digest(path) for path in input_paths},
        "method_count": len(methods), "k_values": ks, "aggregations": AGGREGATIONS, "configuration_rows": len(config_rows),
        "direct_configuration_rows": len(direct_rows), "fresh_target_count": len(fresh),
        "development_targets": [cid for cid, target in target_info.items() if target["role"] != "fresh_pilot"],
        "human_agreement_status": agreement["status"], "winner_selected": False, "pvalues_computed": False,
        "factorial_design_claim": "enumerated_compatible_cross_not_orthogonal_or_fractional_factorial",
        "sources": SOURCES})
    print("COMPARISON_COMPLETE", len(config_rows), "peer configurations;", len(direct_rows), "direct configurations")


if __name__ == "__main__":
    main()
