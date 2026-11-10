"""Check the completed local study before recording its file manifest."""

from __future__ import annotations

import json
from pathlib import Path

import nbformat
import pandas as pd

import facets as fc
from integration_notebook import NOTEBOOK, TAG


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
    ranked_review = table(I / "reviewed_rank_metrics.csv")
    assert len(ranked_review) == 60
    assert ranked_review.groupby("facet_source")["method"].nunique().to_dict() == retrieval
    assert ranked_review["labeled_precision_at_3"].dropna().between(0, 1).all()
    assert ranked_review["labeled_ndcg_at_3"].dropna().between(0, 1).all()
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
    for name in ("control_sonnet", "gpt_general", "gpt_all"):
        run = json.loads((I / "holdout_routes" / name / "llm_run.json").read_text(encoding="utf-8"))
        values = table(I / "holdout_routes" / name / "evaluation/summary.csv")
        assert run["model"] == "gpt-6.1-sol" and run["complete"]
        assert run["targets_done"] == run["holdout_total"] == 160
        assert run["answer_issues"] == 0 and len(values) == 6
        routes[name] = len(values)
    matrix = table(I / "experiment_matrix.csv")
    assert not matrix.duplicated(["stage", "configuration"]).any()
    assert matrix["stage"].nunique() >= 10
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    added = [cell for cell in notebook.cells if TAG in cell.metadata.get("tags", [])]
    assert len(notebook.cells) > 65 and len(added) == len(notebook.cells) - 65
    assert all(cell.execution_count is not None and
               not any(item.output_type == "error" for item in cell.outputs)
               for cell in added if cell.cell_type == "code")
    report = {"status": "passed", "company_count": 533, "training": 373, "development_targets": 160,
              "facets": facets, "cited_fields": len(filled), "embedding_cache": audit["status"],
              "retrieval_methods": retrieval,
              "claim_checks": claims, "reviewed_pairs_judged": len(judge),
              "holdout_route_rows": routes, "experiment_rows": len(matrix),
              "notebook_cells": len(notebook.cells), "executed_integration_cells":
              sum(cell.cell_type == "code" for cell in added)}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
