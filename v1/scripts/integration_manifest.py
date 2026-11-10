"""Record exact local inputs, outputs and model versions for the v1 study."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


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
    "outputs-local/v1/integration/thresholds/run.json",
    "outputs-local/v1/integration/thresholds/reviewer_crossfit.csv",
    "outputs-local/v1/integration/thresholds/holdout_selected_peers.csv",
    "outputs-local/v1/integration/thresholds/valuation_summary.csv",
    "outputs-local/v1/integration/thresholds/paired_comparison.csv",
    "outputs-local/v1/integration/thresholds/target_errors.csv",
    "outputs-local/v1/integration/candidate_methods_gpt/reviewed_metrics.csv",
    "outputs-local/v1/integration/candidate_methods_gpt/rankings.csv.gz",
    "outputs-local/v1/integration/candidate_methods_cited/reviewed_metrics.csv",
    "outputs-local/v1/integration/candidate_methods_cited/valuation_summary.csv",
    "outputs-local/v1/integration/candidate_methods_cited/rankings.csv.gz",
    "outputs-local/v1/integration/reviewed_rank_metrics.csv",
    "outputs-local/v1/integration/retrieval_paired/comparison.csv",
    "outputs-local/v1/integration/gpt_candidates/reviewed_metrics.csv",
    "outputs-local/v1/integration/gpt_candidates/valuation_summary.csv",
    "outputs-local/v1/integration/gpt_candidates/paired_vs_general.csv",
    "outputs-local/v1/integration/claim_check/verdicts.csv",
    "outputs-local/v1/integration/claim_check_cited/verdicts.csv",
    "outputs-local/v1/integration/gpt_scope_eval/summary.json",
    "outputs-local/v1/integration/gpt_scope_eval/evidence_overlap.csv",
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
    "v1/notebooks/comps_and_valuation.ipynb",
]
CORE_CODE = [
    "v1/scripts/fill_facets.py", "v1/scripts/fill_sector_facets.py",
    "v1/scripts/fill_industry_facets.py", "v1/scripts/sector_facets.py",
    "v1/scripts/industry_facets.py", "v1/scripts/direct_llm.py",
    "v1/scripts/llm_then_cosine.py", "v1/scripts/valuation.py",
    "v1/scripts/verification/retrieve.py",
    "v1/scripts/verification/verify_with_evidence.py",
    "pre-v0/pipeline/config.py", "pre-v0/matching/factors.py",
    "pre-v0/valuation/aggregators.py", "pre-v0/growth_signals/stage.py",
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
    if len(profiles) != 4 * 533 or len(judge_records) != 293:
        raise ValueError("Model profile or judge decision records are incomplete")
    for name in sorted(set(FILES + CORE_CODE + integration_code + profiles + judge_records)):
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
        "integration/holdout_routes/gpt_general/llm_run.json",
        "integration/holdout_routes/gpt_all/llm_run.json",
    ):
        path = V1 / name
        if path.exists():
            runs[name] = json.loads(path.read_text(encoding="utf-8"))
    record = {"input_and_output_files": files, "model_runs": runs,
              "status": "local study; no cloud upload",
              "evaluation_limit": "533 public-as-private firms; 160 development valuation targets",
              "unavailable_inputs": {
                  "private_company_outcomes": "No private target outcomes in the frozen local data",
                  "independent_final_holdout": "The 160 public targets informed model development",
                  "growth_outcomes": "No dated annual-revenue history in the local snapshot",
                  "reviewer_consensus_293": "The accessible 293-pair sheet contains one completed reviewer column",
              }}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Recorded {len(files)} exact files")


if __name__ == "__main__":
    main()
