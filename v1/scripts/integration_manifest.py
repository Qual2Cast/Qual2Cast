"""Record exact local inputs, outputs and model versions for the v1 study."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from integration_holdout_compare import VARIANTS


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/run_manifest.json"
PROFILE_DIRS = (
    "facets_codex_gpt61sol/profiles", "facets_source_gpt61sol/profiles",
    "sector_facets_codex_gpt61sol/profiles", "industry_facets_codex_gpt61sol/profiles",
)
FILES = [
    "data-local/snapshots/company_list_v3_websites_fixed.csv",
    "outputs-local/v1/split/20261027T204930Z/split.csv",
    "outputs-local/v1/universe/20261025T060358Z/financials.csv",
    "outputs-local/v1/integration/review/pairs.csv",
    "outputs-local/v1/golden_set/labels/reviewer_labels_20261028.json",
    "outputs-local/v1/integration/sources/facets_sonnet_corrected.csv",
    "outputs-local/v1/facets_codex_gpt61sol/tables/facets.csv",
    "outputs-local/v1/facets_source_gpt61sol/tables/facets.csv",
    "outputs-local/v1/sector_facets_codex_gpt61sol/tables/sector_facets.csv",
    "outputs-local/v1/industry_facets_codex_gpt61sol/tables/industry_facets_long.csv",
    "outputs-local/v1/integration/yifan_facets/facets.csv",
    "outputs-local/v1/integration/embedding_audit.json",
    "outputs-local/v1/integration/embedding_audit_baseline.json",
    "outputs-local/v1/integration/fields/summary.json",
    "outputs-local/v1/integration/candidate_methods/reviewed_metrics.csv",
    "outputs-local/v1/integration/candidate_methods/rankings.csv.gz",
    "outputs-local/v1/integration/candidate_methods/selected_peers.csv",
    "outputs-local/v1/integration/thresholds/run.json",
    "outputs-local/v1/integration/thresholds/reviewer_crossfit.csv",
    "outputs-local/v1/integration/thresholds/holdout_selected_peers.csv",
    "outputs-local/v1/integration/thresholds/valuation_summary.csv",
    "outputs-local/v1/integration/thresholds/paired_comparison.csv",
    "outputs-local/v1/integration/thresholds/target_errors.csv",
    "outputs-local/v1/integration/candidate_methods_gpt/reviewed_metrics.csv",
    "outputs-local/v1/integration/candidate_methods_gpt/rankings.csv.gz",
    "outputs-local/v1/integration/candidate_methods_gpt/selected_peers.csv",
    "outputs-local/v1/integration/candidate_methods_cited/reviewed_metrics.csv",
    "outputs-local/v1/integration/candidate_methods_cited/valuation_summary.csv",
    "outputs-local/v1/integration/candidate_methods_cited/rankings.csv.gz",
    "outputs-local/v1/integration/candidate_methods_cited/selected_peers.csv",
    "outputs-local/v1/integration/reviewed_rank_metrics.csv",
    "outputs-local/v1/integration/retrieval_compatibility.csv",
    "outputs-local/v1/integration/retrieval_compatibility.json",
    "outputs-local/v1/integration/golden_method_metrics.csv",
    "outputs-local/v1/integration/golden_target_metrics.csv",
    "outputs-local/v1/integration/golden_method_run.json",
    "outputs-local/v1/integration/golden_routes/metrics.csv",
    "outputs-local/v1/integration/golden_routes/judge.csv",
    "outputs-local/v1/integration/golden_routes/direct.csv",
    "outputs-local/v1/integration/golden_routes/run.json",
    "outputs-local/v1/integration/retrieval_paired/comparison.csv",
    "outputs-local/v1/integration/gpt_candidates/reviewed_metrics.csv",
    "outputs-local/v1/integration/gpt_candidates/valuation_summary.csv",
    "outputs-local/v1/integration/gpt_candidates/paired_vs_general.csv",
    "outputs-local/v1/integration/claim_check/verdicts.csv",
    "outputs-local/v1/integration/claim_check_cited/verdicts.csv",
    "outputs-local/v1/integration/gpt_scope_eval/summary.json",
    "outputs-local/v1/integration/gpt_scope_eval/evidence_overlap.csv",
    "outputs-local/v1/integration/gpt_scope_alignment/alignment.csv",
    "outputs-local/v1/integration/gpt_scope_alignment/specificity.csv",
    "outputs-local/v1/integration/gpt_scope_alignment/run.json",
    "outputs-local/v1/integration/gpt_scope_alignment/source_exceptions.csv",
    "outputs-local/v1/integration/gpt_scope_alignment/source_exceptions_run.json",
    "outputs-local/v1/integration/gpt_scope_alignment/sensitivity/overrides.csv",
    "outputs-local/v1/integration/gpt_scope_alignment/sensitivity/comparison.csv",
    "outputs-local/v1/integration/gpt_scope_alignment/sensitivity/paired.csv",
    "outputs-local/v1/integration/gpt_scope_alignment/sensitivity/run.json",
    "outputs-local/v1/integration/gpt_scope_alignment/sensitivity/sonnet_source_exceptions.csv",
    "outputs-local/v1/integration/gpt_scope_alignment/sensitivity/gpt_source_exception.csv",
    "outputs-local/v1/integration/source_reviewed_default/facets.csv",
    "outputs-local/v1/integration/source_reviewed_default/changes.csv",
    "outputs-local/v1/integration/source_reviewed_default/run.json",
    "outputs-local/v1/integration/source_reviewed_default/all_targets_top10.csv",
    "outputs-local/v1/integration/source_reviewed_default/report_index_run.json",
    "outputs-local/v1/integration/source_reviewed_default/scope_comparison.json",
    "outputs-local/v1/integration/company_reports/IQ168154_source_reviewed.json",
    "outputs-local/v1/integration/source_facet_eval/reviewed_metrics.csv",
    "outputs-local/v1/integration/source_facet_eval/paired_comparison.csv",
    "outputs-local/v1/integration/source_facet_eval/target_errors.csv",
    "outputs-local/v1/integration/yifan_eval/reviewed_metrics.csv",
    "outputs-local/v1/integration/judge_gpt61sol/eval_293/summary.json",
    "outputs-local/v1/integration/holdout_routes/control_sonnet/evaluation/summary.csv",
    "outputs-local/v1/integration/holdout_routes/gpt_general/evaluation/summary.csv",
    "outputs-local/v1/integration/holdout_routes/gpt_general/evaluation/target_results.csv",
    "outputs-local/v1/integration/holdout_routes/gpt_all/evaluation/summary.csv",
    "outputs-local/v1/integration/holdout_routes/condition_comparison.csv",
    "outputs-local/v1/integration/factors/method_results.csv",
    "outputs-local/v1/integration/factors/target_results.csv",
    "outputs-local/v1/integration/factors_by_facet/comparison.csv",
    "outputs-local/v1/integration/factors_by_facet/run.json",
    "outputs-local/v1/integration/regression/summary.csv",
    "outputs-local/v1/integration/growth_llm/holdout_c_metrics.csv",
    "outputs-local/v1/integration/growth_llm/holdout_c_events.json",
    "outputs-local/v1/integration/expanded_pool/tfidf/summary.json",
    "outputs-local/v1/integration/expanded_pool/mpnet/summary.json",
    "outputs-local/v1/integration/facet_quality/coverage.csv",
    "outputs-local/v1/integration/judge_gpt61sol/eval_293/all_pairs.csv",
    "outputs-local/v1/integration/judge_gpt61sol/eval_293/selection_metrics.csv",
    "outputs-local/v1/integration/judge_gpt61sol/eval_293/selection_valuation.csv",
    "outputs-local/v1/integration/judge_gpt61sol/eval_293/selection_paired.csv",
    "outputs-local/v1/integration/judge_gpt61sol/eval_293/selection_target_errors.csv",
    "outputs-local/v1/integration/error_diagnosis/summary.json",
    "outputs-local/v1/integration/error_diagnosis/stage_diagnostics.csv",
    "outputs-local/v1/integration/growth_llm/holdout_c_features.csv",
    "outputs-local/v1/integration/growth_outcomes/annual_revenue.csv",
    "outputs-local/v1/integration/growth_outcomes/coverage.csv",
    "outputs-local/v1/integration/growth_outcomes/outcomes_2022.csv",
    "outputs-local/v1/integration/growth_outcomes/eligible_outcomes_2022.csv",
    "outputs-local/v1/integration/growth_outcomes/summary.json",
    "outputs-local/v1/model_selection/2026-11-05T015952Z/model_agreement.csv",
    "outputs-local/v1/model_selection/2026-11-05T015952Z/golden_majority.csv",
    "outputs-local/v1/agent_loop/gold_05b_web/eval/agreement_human.csv",
    "outputs-local/v1/holdout_completion/evaluation/source_scope_sensitivity/sensitivity.csv",
    "outputs-local/v1/integration/experiment_matrix.csv",
    "outputs-local/v1/integration/validation.json",
    "v1/scripts/facets.py",
    "v1/scripts/facet_weighting.py",
    "v1/scripts/cosine_then_llm.py",
    "v1/scripts/agent_loop.py",
    "v1/scripts/holdout_batched_routes.py",
    "v1/scripts/holdout_llm_routes.py",
    "v1/scripts/cli_models.py",
    "v1/scripts/candidates.py",
    "v1/scripts/facet_eval.py",
    "v1/scripts/method1_candidates.py",
    "v1/scripts/b3_facet_add_drop.py",
    "v1/scripts/sector_facet_candidates.py",
    "v1/scripts/integration_web_evidence.py",
    "v1/scripts/integration_claim_check.py",
    "v1/scripts/integration_gpt_scope_eval.py",
    "v1/scripts/integration_source_facets.py",
    "v1/scripts/integration_yifan_facets.py",
    "v1/scripts/integration_gpt_candidates.py",
    "v1/scripts/integration_retrieval_paired.py",
    "v1/scripts/integration_reviewed_ranks.py",
    "v1/scripts/integration_holdout_eval.py",
    "v1/scripts/integration_judge_eval.py",
    "v1/scripts/integration_growth_llm.py",
    "v1/scripts/integration_notebook.py",
    "v1/scripts/integration_pipeline.py",
    "v1/scripts/integration_experiment_matrix.py",
    "v1/scripts/source_scope_sensitivity.py",
    "v1/notebooks/comps_and_valuation.ipynb",
]
for name in ("control_sonnet", "source_reviewed_default", "gpt_general", "gpt_all", *VARIANTS):
    FILES.extend(f"outputs-local/v1/integration/holdout_routes/{name}/{file}"
                 for file in (
                     "llm_run.json", "direct.csv", "judge.csv",
                     "evaluation/run.json", "evaluation/judge_kept.csv",
                     "evaluation/llm_then_b3_peers.csv",
                     "evaluation/summary.csv", "evaluation/target_results.csv",
                     "evaluation/paired_common.csv",
                 ))
FILES.extend(f"outputs-local/v1/integration/holdout_routes/gpt_scope_exception/{file}"
             for file in ("llm_run.json", "direct.csv", "judge.csv", "answer_issues.csv",
                          "evaluation/run.json", "evaluation/summary.csv",
                          "evaluation/target_results.csv", "evaluation/judge_kept.csv",
                          "evaluation/llm_then_b3_peers.csv", "evaluation/paired_common.csv"))
FILES.extend(f"outputs-local/v1/integration/gpt_scope_alignment/sensitivity/{name}/{file}"
             for name in ("sonnet_source_exceptions", "gpt_source_exception")
             for file in ("run.json", "candidates.csv", "ranking.csv.gz"))
FILES.extend(f"outputs-local/v1/integration/source_reviewed_default/candidates/{file}"
             for file in ("run.json", "candidates.csv", "ranking.csv.gz", "top10.csv"))
FILES.extend(f"outputs-local/v1/integration/source_reviewed_default/retrieval/{file}"
             for file in ("run.json", "rankings.csv.gz", "reviewed_metrics.csv",
                          "selected_peers.csv", "valuation_summary.csv"))
FILES.extend(f"outputs-local/v1/integration/source_reviewed_default/factors/{file}"
             for file in ("run.json", "method_results.csv", "target_results.csv",
                          "selected_peers.csv"))
FILES.extend(f"outputs-local/v1/integration/source_reviewed_default/golden/{file}"
             for file in ("run.json", "metrics.csv", "target_metrics.csv"))
FILES.extend(f"outputs-local/v1/integration/source_reviewed_default/error_diagnosis/{file}"
             for file in ("summary.json", "stage_diagnostics.csv",
                          "holdout_target_comparison.csv", "peer_grade_disagreements.csv"))
for name in ("gpt_general", *VARIANTS):
    candidate = "gpt_plus_all_additions" if name == "gpt_all_retrieval" else name
    FILES.extend(f"outputs-local/v1/integration/gpt_candidates/{candidate}/{file}"
                 for file in ("run.json", "candidates.csv", "ranking.csv.gz",
                              "all_targets_top10.csv"))
for name in ("sonnet_control", "gpt_general", *("gpt_plus_all_additions"
             if variant == "gpt_all_retrieval" else variant for variant in VARIANTS)):
    FILES.extend(f"outputs-local/v1/integration/factors_by_facet/{name}/{file}"
                 for file in ("run.json", "method_results.csv", "target_results.csv",
                              "selected_peers.csv"))
for name in ("sonnet_dated", "gpt_general", "sonnet_source_exceptions", "gpt_source_exception"):
    FILES.extend(f"outputs-local/v1/integration/gpt_scope_alignment/sensitivity/{name}/{file}"
                 for file in ("selected_peers.csv", "target_errors.csv"))
CORE_CODE = [
    "v1/scripts/fill_facets.py", "v1/scripts/fill_sector_facets.py",
    "v1/scripts/fill_industry_facets.py", "v1/scripts/sector_facets.py",
    "v1/scripts/industry_facets.py", "v1/scripts/direct_llm.py",
    "v1/scripts/llm_then_cosine.py", "v1/scripts/valuation.py",
    "v1/scripts/verification/retrieve.py",
    "v1/scripts/verification/verify_with_evidence.py",
    "pre-v0/pipeline/config.py", "pre-v0/matching/factors.py",
    "pre-v0/valuation/aggregators.py", "pre-v0/growth_signals/stage.py",
    "pre-v0/growth_signals/build_features.py",
    "pre-v0/growth_signals/build_outcomes.py",
    "pre-v0/growth_signals/edgar_revenue.py",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    files = []
    integration_code = [path.relative_to(ROOT).as_posix()
                        for path in (ROOT / "v1/scripts").glob("integration_*.py")]
    profiles = [path.relative_to(ROOT).as_posix()
                for directory in PROFILE_DIRS
                for path in (V1 / directory).glob("*.json")]
    judge_records = [path.relative_to(ROOT).as_posix() for path in
                     (V1 / "integration/judge_gpt61sol/pairs").glob("*/result.json")]
    call_records = [path.relative_to(ROOT).as_posix()
                    for folder in (V1 / "integration/golden_routes/calls",
                                   V1 / "integration/gpt_scope_alignment/calls",
                                   V1 / "integration/holdout_routes/source_reviewed_default/calls")
                    for path in folder.rglob("*") if path.name in
                    {"run.json", "response.json", "prompt.txt", "schema.json"}]
    if len(profiles) != 4 * 533 or len(judge_records) != 293:
        raise ValueError("Model profile or judge decision records are incomplete")
    for name in sorted(set(FILES + CORE_CODE + integration_code + profiles + judge_records + call_records)):
        path = ROOT / name
        if not path.exists():
            raise FileNotFoundError(path)
        files.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    runs = {}
    for name in (
        "facets_codex_gpt61sol/run.json", "facets_source_gpt61sol/run.json",
        "integration/yifan_facets/run.json", "integration/gpt_candidates/run.json",
        "integration/source_facet_eval/run.json", "integration/yifan_eval/run.json",
        "integration/holdout_routes/control_sonnet/llm_run.json",
        "integration/holdout_routes/source_reviewed_default/llm_run.json",
        "integration/holdout_routes/gpt_general/llm_run.json",
        "integration/holdout_routes/gpt_all/llm_run.json",
        "integration/holdout_routes/gpt_scope_exception/llm_run.json",
        *(f"integration/holdout_routes/{variant}/llm_run.json" for variant in VARIANTS),
    ):
        path = V1 / name
        if path.exists():
            runs[name] = json.loads(path.read_text(encoding="utf-8"))
    record = {"input_and_output_files": files, "model_runs": runs,
              "status": "local extension on an existing PR branch; not pushed",
              "evaluation_limit": "533 public-as-private firms; 160 development valuation targets",
              "unavailable_inputs": {
                  "private_company_outcomes": "No private target outcomes in the frozen local data",
                  "independent_final_holdout": "The 160 public targets informed model development",
                  "historical_growth_features": "2026-captured event pages cannot form a 2022 ex-ante predictor panel",
                  "reviewer_consensus_293": "The accessible 293-pair sheet contains one completed reviewer column",
              }}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Recorded {len(files)} exact files")


if __name__ == "__main__":
    main()
