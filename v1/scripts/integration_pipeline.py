"""Run the local v1 integration in the order used by the results notebook."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from integration_holdout_compare import VARIANTS


ROOT = Path(__file__).resolve().parents[2]
I = "outputs-local/v1/integration"
V = "outputs-local/v1"


STAGES: list[tuple[str, str, tuple[str, ...]]] = [
    ("scope_sources", "integration_sources.py", ()),
    ("field_alignment", "integration_fields.py", ()),
    ("review_labels", "integration_review.py", ()),
    ("kethan_diagnostics", "error_analysis.py", ()),
    ("scope_evaluation", "integration_scope_eval.py", ()),
    ("saved_facet_pairs", "integration_facet_293.py", ()),
    ("saved_facet_valuation", "integration_facet_valuation.py", ()),
    ("barbara_catalog", "integration_barbara.py", ("--workers", "2")),
    ("barbara_published_matches", "integration_barbara_matches.py", ()),
    ("expanded_tfidf", "integration_expanded.py", ("--method", "tfidf")),
    ("expanded_mpnet", "integration_expanded.py", ("--method", "mpnet")),
    ("sonnet_retrieval", "integration_candidate_methods.py", ()),
    ("calibrated_threshold", "integration_thresholds.py", ()),
    ("gpt_general", "fill_facets.py", ("--out", f"{V}/facets_codex_gpt61sol",
                                       "--backend", "codex", "--model", "gpt-6.1-sol",
                                       "--workers", "2")),
    ("gpt_sector", "fill_sector_facets.py", ("--out", f"{V}/sector_facets_codex_gpt61sol",
                                              "--include-holdout", "--backend", "codex",
                                              "--model", "gpt-6.1-sol", "--workers", "2")),
    ("gpt_sic2", "fill_industry_facets.py", ("--out", f"{V}/industry_facets_codex_gpt61sol",
                                                "--backend", "codex", "--model", "gpt-6.1-sol",
                                                "--workers", "2")),
    ("web_evidence", "integration_web_evidence.py", ()),
    ("gpt_cited", "integration_source_facets.py", ("--workers", "2")),
    ("gpt_cited_claim_check", "integration_claim_check.py",
     ("--facets", f"{V}/facets_source_gpt61sol/tables/facets.csv",
      "--out", f"{I}/claim_check_cited")),
    ("yifan_fields", "integration_yifan_facets.py", ("--workers", "2")),
    ("embedding_audit", "integration_embedding_audit.py", ()),
    ("gpt_scope_check", "integration_gpt_scope_eval.py", ()),
    ("gpt_scope_alignment", "integration_gpt_scope_alignment.py", ()),
    ("scope_source_review", "integration_scope_source_review.py", ()),
    ("scope_exception_sensitivity", "integration_scope_exception_sensitivity.py", ()),
    ("source_reviewed_default", "integration_default_scope.py", ()),
    ("source_reviewed_candidates", "integration_default_candidates.py", ()),
    ("source_reviewed_scope_comparison", "integration_default_scope_compare.py", ()),
    ("source_reviewed_retrieval", "integration_candidate_methods.py",
     ("--facets", f"{I}/source_reviewed_default/facets.csv",
      "--out", f"{I}/source_reviewed_default/retrieval",
      "--facet-label", "Source-reviewed Sonnet default")),
    ("source_reviewed_report_index", "integration_default_report_index.py", ()),
    ("source_reviewed_golden", "integration_default_golden_eval.py", ()),
    ("gpt_claim_check", "integration_claim_check.py", ()),
    ("facet_coverage", "integration_facet_quality.py", ()),
    ("gpt_retrieval", "integration_candidate_methods.py",
     ("--facets", f"{V}/facets_codex_gpt61sol/tables/facets.csv",
      "--out", f"{I}/candidate_methods_gpt", "--facet-label", "GPT-6.1 Sol general")),
    ("retrieval_paired", "integration_retrieval_paired.py", ()),
    ("gpt_facet_variants", "integration_gpt_candidates.py", ()),
    ("cited_facet_evaluation", "integration_source_facet_eval.py", ()),
    ("cited_retrieval", "integration_candidate_methods.py",
     ("--facets", f"{V}/facets_source_gpt61sol/tables/facets.csv",
      "--out", f"{I}/candidate_methods_cited", "--facet-label", "GPT-6.1 Sol source-cited")),
    ("reviewed_rank_metrics", "integration_reviewed_ranks.py", ()),
    ("retrieval_compatibility", "integration_retrieval_compatibility.py", ()),
    ("golden_routes", "integration_golden_routes.py", ()),
    ("yifan_facet_evaluation", "integration_yifan_eval.py", ()),
    ("judge_pairs", "integration_judge_input.py", ()),
    ("gpt_source_judge", "agent_loop.py",
     ("--pairs", "selected", "--candidates", f"{I}/judge_input_293",
      "--facets", f"{V}/facets_source_gpt61sol/tables/facets.csv",
      "--backend", "codex", "--model", "gpt-6.1-sol",
      "--search", "codex", "--search-model", "gpt-6.1-sol",
      "--workers", "2", "--out", f"{I}/judge_gpt61sol")),
    ("judge_evaluation", "integration_judge_eval.py",
     ("--run", f"{I}/judge_gpt61sol")),
    ("judge_selection", "integration_judge_selection.py", ()),
]

for name, candidate, general, sector, industry in (
    ("control_sonnet", "gpt_general", f"{I}/sources/facets_sonnet_corrected.csv", None, None),
    ("gpt_general", "gpt_general", f"{V}/facets_codex_gpt61sol/tables/facets.csv", None, None),
    ("gpt_all", "gpt_plus_all_additions", f"{V}/facets_codex_gpt61sol/tables/facets.csv",
     f"{V}/sector_facets_codex_gpt61sol/tables/sector_facets.csv",
     f"{V}/industry_facets_codex_gpt61sol/tables/industry_facets_long.csv"),
):
    candidates = f"{I}/gpt_candidates/{candidate}"
    output = f"{I}/holdout_routes/{name}"
    args = ["--candidates-run", candidates, "--out", output,
            "--general-facets", general, "--candidate-rule", "selected",
            "--prompt-version", "current", "--model", "gpt-6.1-sol", "--workers", "2"]
    if sector:
        args.extend(("--sector-facets", sector))
    if industry:
        args.extend(("--industry-facets", industry))
    STAGES.append((f"{name}_llm", "holdout_batched_routes.py", tuple(args)))
    STAGES.append((f"{name}_valuation", "integration_holdout_eval.py",
                   ("--candidates", candidates, "--llm", output,
                    "--out", f"{output}/evaluation")))

STAGES.append(("gpt_scope_exception_llm", "holdout_batched_routes.py",
               ("--candidates-run", f"{I}/gpt_scope_alignment/sensitivity/gpt_source_exception",
                "--out", f"{I}/holdout_routes/gpt_scope_exception",
                "--general-facets", f"{I}/gpt_scope_alignment/sensitivity/gpt_source_exception.csv",
                "--candidate-rule", "selected", "--prompt-version", "current",
                "--model", "gpt-6.1-sol", "--workers", "2")))
STAGES.append(("gpt_scope_exception_valuation", "integration_holdout_eval.py",
               ("--candidates", f"{I}/gpt_scope_alignment/sensitivity/gpt_source_exception",
                "--llm", f"{I}/holdout_routes/gpt_scope_exception",
                "--out", f"{I}/holdout_routes/gpt_scope_exception/evaluation")))

STAGES.append(("source_reviewed_default_llm", "holdout_batched_routes.py",
               ("--candidates-run", f"{I}/source_reviewed_default/candidates",
                "--out", f"{I}/holdout_routes/source_reviewed_default",
                "--general-facets", f"{I}/source_reviewed_default/facets.csv",
                "--candidate-rule", "selected", "--prompt-version", "current",
                "--model", "gpt-6.1-sol", "--workers", "4")))
STAGES.append(("source_reviewed_default_valuation", "integration_holdout_eval.py",
               ("--candidates", f"{I}/source_reviewed_default/candidates",
                "--llm", f"{I}/holdout_routes/source_reviewed_default",
                "--out", f"{I}/holdout_routes/source_reviewed_default/evaluation")))

for candidate in (
    "gpt_plus_ff49", "gpt_plus_sic4", "gpt_plus_fiona_sub-sector",
    "gpt_plus_fiona_categories", "gpt_plus_barbara_sic2_facets",
    "gpt_plus_all_additions", "gpt_all_except_ff49", "gpt_all_except_sic4",
    "gpt_all_except_fiona_sub-sector", "gpt_all_except_fiona_categories",
    "gpt_all_except_barbara_sic2_facets",
):
    name = "gpt_all_retrieval" if candidate == "gpt_plus_all_additions" else candidate
    candidates = f"{I}/gpt_candidates/{candidate}"
    output = f"{I}/holdout_routes/{name}"
    STAGES.append((f"{name}_llm", "holdout_batched_routes.py",
                   ("--candidates-run", candidates, "--out", output,
                    "--general-facets", f"{V}/facets_codex_gpt61sol/tables/facets.csv",
                    "--candidate-rule", "selected", "--prompt-version", "current",
                    "--model", "gpt-6.1-sol", "--workers", "4",
                    "--reuse-direct-from", f"{I}/holdout_routes/gpt_general")))
    STAGES.append((f"{name}_valuation", "integration_holdout_eval.py",
                   ("--candidates", candidates, "--llm", output,
                    "--out", f"{output}/evaluation")))

STAGES += [
    ("facet_condition_comparison", "integration_holdout_compare.py", ()),
    ("factor_sets", "integration_factors.py", ()),
    ("source_reviewed_default_factors", "integration_factors.py",
     ("--shortlist", f"{I}/source_reviewed_default/candidates/top10.csv",
      "--out", f"{I}/source_reviewed_default/factors",
      "--source-label", "Source-reviewed Sonnet default B3 top ten")),
    ("industry_regression", "integration_regression.py", ()),
    ("growth_rules", "integration_growth.py", ()),
    ("growth_llm", "integration_growth_llm.py",
     ("--set", "holdout_c", "--model", "gpt-6.1-sol")),
    ("growth_outcomes", "integration_growth_outcomes.py", ()),
    ("company_example", "integration_company_report.py",
     ("aarcorp.com", "--method", "source_reviewed")),
    ("error_diagnosis", "integration_error_diagnosis.py", ()),
    ("experiment_matrix", "integration_experiment_matrix.py", ()),
    ("notebook_build", "integration_notebook.py", ()),
    ("notebook_execute", "integration_execute_notebook.py", ()),
    ("validate", "integration_validate.py", ()),
    ("manifest", "integration_manifest.py", ()),
]

factor_names = ("gpt_general", *("gpt_plus_all_additions" if name == "gpt_all_retrieval"
                                 else name for name in VARIANTS))
factor_stages = [
    (f"factor_{name}", "integration_factors.py",
     ("--shortlist", f"{I}/gpt_candidates/{name}/all_targets_top10.csv",
      "--out", f"{I}/factors_by_facet/{name}",
      "--source-label", f"{name} B3 top ten"))
    for name in factor_names
]
factor_stages.append(("factor_cross", "integration_factor_cross.py", ()))
factor_position = next(i for i, stage in enumerate(STAGES) if stage[0] == "industry_regression")
STAGES[factor_position:factor_position] = factor_stages


def command(stage: tuple[str, str, tuple[str, ...]]) -> list[str]:
    _, script, args = stage
    return [sys.executable, str(ROOT / "v1/scripts" / script), *args]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-stage", choices=[stage[0] for stage in STAGES])
    parser.add_argument("--through-stage", choices=[stage[0] for stage in STAGES])
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    names = [stage[0] for stage in STAGES]
    first = names.index(args.from_stage) if args.from_stage else 0
    last = names.index(args.through_stage) + 1 if args.through_stage else len(STAGES)
    if first >= last:
        raise ValueError("The final stage must follow the starting stage")
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    for name, script, extra in STAGES[first:last]:
        print(f"{name}: {script} {' '.join(extra)}", flush=True)
        if args.execute:
            subprocess.run(command((name, script, extra)), cwd=ROOT,
                           env=environment, check=True)


if __name__ == "__main__":
    main()
