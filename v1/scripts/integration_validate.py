"""Check the completed local study before recording its file manifest."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import nbformat
import pandas as pd

import facets as fc
from integration_holdout_compare import VARIANTS
from integration_notebook import NOTEBOOK, TAG
from integration_reviewed_ranks import checked_sources


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
I = V1 / "integration"
OUT = I / "validation.json"


def table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, dtype={"IQ_COMPANY_ID": str, "target": str, "comp": str})


def main() -> None:
    split = table(V1 / "split/20261027T204930Z/split.csv")
    assert (len(split), split["IQ_COMPANY_ID"].nunique()) == (533, 533)
    assert split["sample"].value_counts().to_dict() == {"training": 373, "holdout": 160}
    facets = {}
    for name, path in (
        ("general", V1 / "facets_codex_gpt61sol/tables/facets.csv"),
        ("source_cited", V1 / "facets_source_gpt61sol/tables/facets.csv"),
    ):
        data = table(path)
        assert len(data) == 533 and data["IQ_COMPANY_ID"].is_unique
        assert set(data["IQ_COMPANY_ID"]) == set(split["IQ_COMPANY_ID"])
        assert data["llm_status"].eq("ok").all()
        assert data["prompt_version"].eq(fc.PROMPT_VERSION).all()
        facets[name] = len(data)
    cited_profiles = [json.loads(path.read_text(encoding="utf-8"))
                      for path in (V1 / "facets_source_gpt61sol/profiles").glob("*.json")]
    assert len(cited_profiles) == 533
    assert {profile["IQ_COMPANY_ID"] for profile in cited_profiles} == set(split["IQ_COMPANY_ID"])
    assert all(profile["model"] == "gpt-6.1-sol" and
               len(profile["businesses"]) == 1 and
               profile["businesses"][0]["business_id"] == "B1"
               for profile in cited_profiles)
    filled = [facet for profile in cited_profiles
              for facet in profile["businesses"][0]["facets"].values()
              if facet["status"] == "filled"]
    assert all(any(quote.get("quote_found") and quote.get("url")
                   for quote in facet["quotes"]) for facet in filled)
    sector = table(V1 / "sector_facets_codex_gpt61sol/tables/sector_facets.csv")
    industry = table(V1 / "industry_facets_codex_gpt61sol/tables/industry_facets_long.csv")
    yifan = table(I / "yifan_facets/facets.csv")
    assert sector["IQ_COMPANY_ID"].nunique() == 533 and sector["llm_status"].eq("ok").all()
    assert sector["model"].eq("gpt-6.1-sol").all()
    assert industry["IQ_COMPANY_ID"].nunique() == 533 and industry["model"].eq("gpt-6.1-sol").all()
    assert yifan["IQ_COMPANY_ID"].nunique() == 533 and yifan["llm_status"].eq("ok").all()
    yifan_run = json.loads((I / "yifan_facets/run.json").read_text(encoding="utf-8"))
    assert yifan_run["model"] == "gpt-6.1-sol" and yifan_run["companies"] == 533
    audit = json.loads((I / "embedding_audit.json").read_text(encoding="utf-8"))
    assert audit["status"] == "compatible" and audit["b0_caches_checked"] == 3
    assert audit["reused_texts_checked"] == audit["unique_texts"]
    retrieval = {}
    for name in ("candidate_methods", "candidate_methods_gpt", "candidate_methods_cited"):
        run = json.loads((I / name / "run.json").read_text(encoding="utf-8"))
        metrics = table(I / name / "reviewed_metrics.csv")
        values = table(I / name / "valuation_summary.csv")
        assert (run["company_count"], run["pool"], run["valuation_targets"],
                run["method_count"]) == (533, 373, 160, 20)
        assert len(metrics) == 20 and metrics["method"].is_unique
        assert len(values) == 21 and values["comp rule"].is_unique
        retrieval[name] = len(metrics)
    default_run = json.loads((I / "source_reviewed_default/run.json").read_text(encoding="utf-8"))
    default_facets = I / "source_reviewed_default/facets.csv"
    default_data = table(default_facets)
    assert len(default_data) == 533 and default_data["IQ_COMPANY_ID"].is_unique
    assert set(default_data["IQ_COMPANY_ID"]) == set(split["IQ_COMPANY_ID"])
    assert default_run["reviewed_fields"] == 10 and default_run["company_count"] == 533
    assert default_run["regression_categories_unchanged"]
    assert default_run["facets_sha256"] == hashlib.sha256(default_facets.read_bytes()).hexdigest()
    default_changes = table(I / "source_reviewed_default/changes.csv")
    assert len(default_changes) == 10 and set(default_changes["ticker"]) == {
        "HLTC", "ENSG", "SKIL"}
    assert default_changes["primary_source"].notna().all()
    default_b3 = json.loads((I / "source_reviewed_default/candidates/run.json").read_text(
        encoding="utf-8"))
    assert default_b3["facet_sha256"] == default_run["facets_sha256"]
    assert default_b3["targets"] == 160 and default_b3["pool"] == 373
    default_scope_comparison = json.loads((I / "source_reviewed_default/scope_comparison.json")
                                          .read_text(encoding="utf-8"))
    assert default_scope_comparison["targets"] == 160
    assert default_scope_comparison["changed_peer_lists"] == 1
    default_retrieval = json.loads((I / "source_reviewed_default/retrieval/run.json").read_text(
        encoding="utf-8"))
    assert default_retrieval["method_count"] == 20
    assert default_retrieval["facet_sha256"] == default_run["facets_sha256"]
    assert len(table(I / "source_reviewed_default/retrieval/reviewed_metrics.csv")) == 20
    default_selected = table(I / "source_reviewed_default/candidates/selected_peers.csv")
    retrieval_selected = table(I / "source_reviewed_default/retrieval/selected_peers.csv")
    retrieval_selected = retrieval_selected.loc[
        retrieval_selected["method"].eq("B3 embedding plus TF-IDF") &
        retrieval_selected["target"].isin(set(split.loc[split["sample"].eq("holdout"),
                                                  "IQ_COMPANY_ID"]))]
    assert set(map(tuple, default_selected[["target", "comp"]].itertuples(index=False, name=None))) == set(
        map(tuple, retrieval_selected[["target", "comp"]].itertuples(index=False, name=None)))
    default_index = table(I / "source_reviewed_default/all_targets_top10.csv")
    assert len(default_index) == 5330 and default_index.groupby("target").size().eq(10).all()
    assert set(default_index["target"]) == set(split["IQ_COMPANY_ID"])
    default_gold = table(I / "source_reviewed_default/golden/metrics.csv")
    assert len(default_gold) == 20 * 6
    assert default_gold.groupby("label_source").size().eq(20).all()
    ranked_review = table(I / "reviewed_rank_metrics.csv")
    assert len(ranked_review) == 60
    assert ranked_review.groupby("facet_source")["method"].nunique().to_dict() == retrieval
    assert ranked_review["labeled_precision_at_3"].dropna().between(0, 1).all()
    assert ranked_review["labeled_ndcg_at_3"].dropna().between(0, 1).all()
    compatible = table(I / "retrieval_compatibility.csv")
    assert len(compatible) == 20 and compatible["method"].is_unique
    assert compatible["common_field_source_runs"].eq(4).all()
    assert compatible["specialized_facet_conditions"].sum() == 12
    checked_sources()
    golden = table(I / "golden_method_metrics.csv")
    golden_run = json.loads((I / "golden_method_run.json").read_text(encoding="utf-8"))
    assert golden_run["methods"] == 72 and golden_run["company_count"] == 533
    assert golden_run["label_counts"] == {
        "human_majority": 32, "human_unanimous": 11,
        "human_riya": 36, "human_barbara": 36, "human_matthew": 36,
        "barbara_293": 293,
    }
    assert len(golden) == 72 * 6
    assert golden.groupby("label_source")[["facet_source", "method"]].size().eq(72).all()
    assert golden["pairwise_top10_accuracy"].dropna().between(0, 1).all()
    assert golden.loc[golden["label_source"].eq("human_majority"), "good_total"].eq(11).all()
    route_gold = table(I / "golden_routes/metrics.csv")
    route_run = json.loads((I / "golden_routes/run.json").read_text(encoding="utf-8"))
    assert len(route_gold) == 12 * 4 * 5
    assert route_gold.groupby("label_source").size().eq(12 * 4).all()
    assert route_gold["labeled_targets"].eq(2).all()
    assert route_run["model"] == "gpt-6.1-sol" and len(route_run["targets"]) == 2
    assert len(table(I / "golden_routes/judge.csv")) >= 20
    assert len(table(I / "golden_routes/direct.csv")) > 0
    for kind in ("judge", "direct"):
        for target in route_run["targets"]:
            call = json.loads((I / "golden_routes/calls" / kind / target / "run.json")
                              .read_text(encoding="utf-8"))
            assert call["model"] == "gpt-6.1-sol" and call["status"] == "ok"
            assert len(call["fingerprint"]) == 64
    alignment = table(I / "gpt_scope_alignment/alignment.csv")
    specificity = table(I / "gpt_scope_alignment/specificity.csv")
    alignment_run = json.loads((I / "gpt_scope_alignment/run.json").read_text(encoding="utf-8"))
    assert len(alignment) == len(specificity) == alignment_run["corrected_fields"] == 116
    assert alignment["IQ_COMPANY_ID"].nunique() == alignment_run["companies"] == 42
    assert alignment["status"].isin(["aligned", "outdated", "uncertain"]).all()
    assert specificity["general"].dropna().isin(
        ["specific_outdated", "not_specific", "unclear"]).all()
    assert specificity["general"].eq("specific_outdated").sum() == alignment_run[
        "strict_general_counts"].get("specific_outdated", 0)
    exceptions = table(I / "gpt_scope_alignment/source_exceptions.csv")
    assert set(exceptions["ticker"]) == {"HLTC", "ENSG", "TKR", "SKIL"}
    assert exceptions["company_id"].is_unique
    sensitivity = table(I / "gpt_scope_alignment/sensitivity/comparison.csv")
    assert set(sensitivity["variant"]) == {
        "Sonnet dated", "Sonnet source exceptions", "GPT general", "GPT source exception"}
    assert sensitivity["good_total"].eq(11).all()
    scope_pair = table(I / "gpt_scope_alignment/sensitivity/paired.csv")
    assert len(scope_pair) == 2 and scope_pair["targets"].eq(160).all()
    overrides = table(I / "gpt_scope_alignment/sensitivity/overrides.csv")
    assert len(overrides) == 8 and not overrides.duplicated(
        ["variant", "IQ_COMPANY_ID", "facet"]).any()
    for name in ("sonnet_source_exceptions", "gpt_source_exception"):
        scoped = table(I / "gpt_scope_alignment/sensitivity" / f"{name}.csv")
        candidates = table(I / "gpt_scope_alignment/sensitivity" / name / "candidates.csv")
        assert len(scoped) == 533 and scoped["IQ_COMPANY_ID"].is_unique
        assert candidates["target"].nunique() == 160
        assert candidates["comp"].isin(split.loc[split["sample"].eq("training"),
                                             "IQ_COMPANY_ID"]).all()
    cutoff = json.loads((I / "thresholds/run.json").read_text(encoding="utf-8"))
    crossfit = table(I / "thresholds/reviewer_crossfit.csv")
    selected = table(I / "thresholds/holdout_selected_peers.csv")
    assert (cutoff["reviewed_pairs"], cutoff["reviewer_targets"],
            cutoff["candidate_pool"], cutoff["development_targets"]) == (293, 45, 373, 160)
    assert len(crossfit) == 293 and crossfit["target"].nunique() == 45
    assert set(selected["target"]).issubset(set(split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"]))
    assert set(selected["comp"]).issubset(set(split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"]))
    claims = {}
    for name in ("claim_check", "claim_check_cited"):
        audit_table = table(I / name / "audit.csv")
        checks = table(I / name / "verdicts.csv")
        assert len(audit_table) == 40 and audit_table["status"].eq("ok").all()
        assert len(checks) == 480 and checks.groupby("IQ_COMPANY_ID").size().eq(12).all()
        claims[name] = len(checks)
    judge = table(I / "judge_gpt61sol/verdicts.csv")
    assert len(judge) == 293 and not judge.duplicated(["target", "comp"]).any()
    assert judge["status"].eq("ok").all()
    assert judge["score"].dropna().isin([0, 1, 2]).all()
    judge_config = json.loads((I / "judge_gpt61sol/config.json").read_text(encoding="utf-8"))
    assert judge_config["model"] == judge_config["search_model"] == "gpt-6.1-sol"
    assert judge_config["backend"] == judge_config["search"] == "codex"
    records = [json.loads(path.read_text(encoding="utf-8"))
               for path in (I / "judge_gpt61sol/pairs").glob("*/result.json")]
    assert len(records) == 293 and all(record.get("fingerprint") and
                                       record["row"]["status"] == "ok" for record in records)
    routes = {}
    for name in ("control_sonnet", "source_reviewed_default", "gpt_general", "gpt_all", *VARIANTS,
                 "gpt_scope_exception"):
        run = json.loads((I / "holdout_routes" / name / "llm_run.json").read_text(encoding="utf-8"))
        values = table(I / "holdout_routes" / name / "evaluation/summary.csv")
        targets = table(I / "holdout_routes" / name / "evaluation/target_results.csv")
        assert run["model"] == "gpt-6.1-sol" and run["complete"]
        assert run["targets_done"] == run["holdout_total"] == 160
        assert run["answer_issues"] == 0 and len(values) == 6
        assert len(targets) == 960 and targets["target"].nunique() == 160
        assert not targets.duplicated(["method", "target"]).any()
        assert targets.groupby("method")["error %"].count().to_dict() == dict(
            zip(values["comp rule"], values["targets"]))
        if name in VARIANTS:
            assert Path(run["direct_reused_from"]).parts[-2:] == (
                "holdout_routes", "gpt_general")
            reused = list((I / "holdout_routes" / name / "calls/batch_direct").glob(
                "*/reused_from.txt"))
            assert len(reused) == 20
        routes[name] = len(values)
    features = table(I / "growth_llm/holdout_c_features.csv")
    assert features.groupby("method")["IQ_COMPANY_ID"].nunique().to_dict() == {
        "rules": 10, "llm": 10, "hybrid": 10}
    assert features["cutoff_date"].eq("2026-10-19").all()
    outcomes = table(I / "growth_outcomes/outcomes_2022.csv")
    revenue_coverage = table(I / "growth_outcomes/coverage.csv")
    outcome_run = json.loads((I / "growth_outcomes/summary.json").read_text(encoding="utf-8"))
    assert len(revenue_coverage) == outcome_run["snapshot_companies"] == 560
    assert revenue_coverage["IQ_COMPANY_ID"].is_unique
    assert revenue_coverage["status"].eq("ok").sum() == (
        outcome_run["companies_with_annual_revenue"])
    assert outcome_run["cutoff_fiscal_year"] == 2022
    assert len(outcomes) == outcome_run["companies_with_cutoff_revenue"]
    assert outcomes["IQ_COMPANY_ID"].is_unique
    assert outcomes["cutoff_fiscal_year"].eq(2022).all()
    eligible_outcomes = table(I / "growth_outcomes/eligible_outcomes_2022.csv")
    assert len(eligible_outcomes) == outcome_run["eligible_companies_with_cutoff_revenue"]
    assert set(eligible_outcomes["IQ_COMPANY_ID"]).issubset(set(split["IQ_COMPANY_ID"]))
    for years in (1, 2, 3):
        assert outcomes[f"revenue_growth_{years}y"].notna().sum() == (
            outcome_run["outcome_counts"][f"{years}y"])
        assert eligible_outcomes[f"revenue_growth_{years}y"].notna().sum() == (
            outcome_run["eligible_outcome_counts"][f"{years}y"])
    factor_cross = table(I / "factors_by_facet/comparison.csv")
    factor_run = json.loads((I / "factors_by_facet/run.json").read_text(encoding="utf-8"))
    assert len(factor_cross) == factor_run["rows"] == 12 * 8 * 3 * 6
    assert factor_run["sonnet_control_reproduced"]
    assert factor_cross["facet_condition"].nunique() == 12
    assert factor_cross["factor_set"].nunique() == 8
    assert factor_cross["peer_budget"].nunique() == 3
    assert factor_cross["aggregation"].nunique() == 6
    default_factors = table(I / "source_reviewed_default/factors/method_results.csv")
    assert len(default_factors) == 8 * 3 * 6
    assert default_factors["coverage"].le(160).all()
    matrix = table(I / "experiment_matrix.csv")
    assert not matrix.duplicated(["stage", "configuration"]).any()
    assert matrix["stage"].nunique() >= 10
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    added = [cell for cell in notebook.cells if TAG in cell.metadata.get("tags", [])]
    assert len(notebook.cells) > 65 and len(added) == len(notebook.cells) - 65
    assert all(cell.execution_count is not None and
               not any(item.output_type == "error" for item in cell.outputs)
               for cell in added if cell.cell_type == "code")
    report = {"status": "passed", "check_scope": "saved-stage integrity and source-reviewed default rerun",
              "three_requested_checks_executed": True,
              "scope_exceptions_applied_to_default": True,
              "integration_default_complete": True,
              "full_plan_complete": False, "company_count": 533,
              "training": 373, "development_targets": 160,
              "facets": facets, "cited_fields": len(filled), "embedding_cache": audit["status"],
              "retrieval_methods": retrieval,
              "golden_method_rows": len(golden),
              "golden_route_rows": len(route_gold),
              "scope_alignment": alignment_run["status_counts"],
              "scope_specific_outdated": alignment_run["strict_general_counts"].get(
                  "specific_outdated", 0),
              "source_review_cases": len(exceptions),
              "source_conflicts": int(exceptions["decision"].eq(
                  "retain_current_business").sum()),
              "source_exception_sensitivity": len(sensitivity),
              "claim_checks": claims, "reviewed_pairs_judged": len(judge),
              "holdout_route_rows": routes, "experiment_rows": len(matrix),
              "growth_feature_rows": len(features), "growth_outcomes": len(outcomes),
              "facet_factor_rows": len(factor_cross),
              "notebook_cells": len(notebook.cells), "executed_integration_cells":
              sum(cell.cell_type == "code" for cell in added)}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
