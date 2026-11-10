"""Index every executed comparable and valuation configuration in one table."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from integration_holdout_compare import VARIANTS


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration"
OUT = BASE / "experiment_matrix.csv"


def add(rows: list[dict], stage: str, table: pd.DataFrame, *, facet: str,
        retrieval: str, selection: str, grading: str, factor: str,
        aggregation: str, method_col: str, error_col: str,
        coverage_col: str = "targets", label_cohort: str =
        "Barbara 293; 160 development valuation targets") -> None:
    for record in table.to_dict("records"):
        rows.append({
            "stage": stage,
            "configuration": record[method_col],
            "facet": facet,
            "retrieval": retrieval,
            "selection": selection,
            "grading": grading,
            "factor": factor,
            "aggregation": aggregation,
            "target_count": record.get(coverage_col),
            "median_absolute_percentage_error": record.get(error_col),
            "label_cohort": label_cohort,
        })


def main() -> None:
    rows: list[dict] = []
    candidate = pd.read_csv(BASE / "candidate_methods/valuation_summary.csv")
    add(rows, "retrieval comparison", candidate, facet="corrected Sonnet general",
        retrieval="varies by configuration", selection="saved route", grading="none",
        factor="business only", aggregation="saved route", method_col="comp rule",
        error_col="median abs % error")
    reviewed_candidate = pd.read_csv(BASE / "source_reviewed_default/retrieval/valuation_summary.csv")
    add(rows, "source-reviewed default retrieval", reviewed_candidate,
        facet="source-reviewed Sonnet general", retrieval="varies by configuration",
        selection="saved route", grading="none", factor="business only",
        aggregation="saved route", method_col="comp rule", error_col="median abs % error")
    gpt_candidate = pd.read_csv(BASE / "candidate_methods_gpt/valuation_summary.csv")
    add(rows, "GPT retrieval comparison", gpt_candidate, facet="GPT general",
        retrieval="varies by configuration", selection="saved route", grading="none",
        factor="business only", aggregation="saved route", method_col="comp rule",
        error_col="median abs % error")
    cited_candidate = pd.read_csv(BASE / "candidate_methods_cited/valuation_summary.csv")
    add(rows, "cited retrieval comparison", cited_candidate, facet="GPT source-cited general",
        retrieval="varies by configuration", selection="saved route", grading="none",
        factor="business only", aggregation="saved route", method_col="comp rule",
        error_col="median abs % error")
    threshold = pd.read_csv(BASE / "thresholds/valuation_summary.csv")
    add(rows, "reviewer-calibrated threshold", threshold, facet="corrected Sonnet general",
        retrieval="B3 fixed training pool", selection="training-label z threshold",
        grading="none", factor="business only", aggregation="similarity-weighted mean",
        method_col="comp rule", error_col="median abs % error",
        label_cohort="Barbara 293 training labels; 160 development valuation targets")

    facet = pd.read_csv(BASE / "facet_valuation/summary.csv")
    facet = facet[facet["variant"].notna() & facet["variant"].ne("No matching")]
    for record in facet.to_dict("records"):
        rows.append({
            "stage": "saved facet ablation", "configuration":
                f"{record['variant']}: {record['rule']}",
            "facet": record["variant"], "retrieval": "B3",
            "selection": record["rule"], "grading": "none", "factor": "business only",
            "aggregation": record["rule"], "target_count": record["targets"],
            "median_absolute_percentage_error": record["median abs % error"],
            "label_cohort": "Barbara 293; 160 development valuation targets",
        })

    for name, path in (
        ("GPT facet comparison", "gpt_candidates/valuation_summary.csv"),
        ("source availability", "source_facet_eval/valuation_summary.csv"),
        ("Orbis qualitative facets", "yifan_eval/valuation_summary.csv"),
    ):
        table = pd.read_csv(BASE / path)
        for record in table.to_dict("records"):
            if record["comp rule"] == "No matching":
                continue
            rows.append({
                "stage": name, "configuration": record["comp rule"],
                "facet": record["comp rule"], "retrieval": "B3",
                "selection": "mutual top 10, top up to 3", "grading": "none",
                "factor": "business only", "aggregation": "similarity-weighted mean",
                "target_count": record["targets"],
                "median_absolute_percentage_error": record["median abs % error"],
                "label_cohort": "Barbara 293; 160 development valuation targets",
            })

    for condition in ("control_sonnet", "source_reviewed_default", "gpt_general", "gpt_all", *VARIANTS,
                      "gpt_scope_exception"):
        table = pd.read_csv(BASE / "holdout_routes" / condition / "evaluation/summary.csv")
        for record in table.to_dict("records"):
            rows.append({
                "stage": "GPT selector routes", "configuration": f"{condition}: {record['comp rule']}",
                "facet": condition, "retrieval": "B3 condition-specific shortlist",
                "selection": record["comp rule"],
                "grading": ("binary LLM" if "then LLM" in record["comp rule"]
                            else "direct LLM" if record["comp rule"].startswith("LLM")
                            else "none"),
                "factor": "business only", "aggregation": "saved route",
                "target_count": record["targets"],
                "median_absolute_percentage_error": record["median abs % error"],
                "label_cohort": "160 development valuation targets",
            })

    judge_value = pd.read_csv(BASE / "judge_gpt61sol/eval_293/selection_valuation.csv")
    judge_peer = pd.read_csv(BASE / "judge_gpt61sol/eval_293/selection_metrics.csv")
    for record in judge_value.to_dict("records"):
        name = record["comp rule"]
        rows.append({
            "stage": "judge selection on reviewed pairs", "configuration": name,
            "facet": "corrected Sonnet B3 rank; GPT source-cited judge context",
            "retrieval": "frozen 293 reviewed B3 pairs",
            "selection": name, "grading": "source-citing 0–2 GPT judge",
            "factor": "business only", "aggregation": "similarity-weighted mean",
            "target_count": record["targets"],
            "median_absolute_percentage_error": record["median abs % error"],
            "label_cohort": "Barbara 293; 45 training targets, reviewed pairs only",
        })

    factors = pd.read_csv(BASE / "factors/method_results.csv")
    for record in factors.to_dict("records"):
        rows.append({
            "stage": "private-supplied factors", "configuration":
                f"{record['factor_set']}: {record['peer_budget']} peers, {record['aggregation']}",
            "facet": "corrected Sonnet general", "retrieval": "B3",
            "selection": f"top {record['peer_budget']} after factor distance",
            "grading": "none", "factor": record["factor_set"],
            "aggregation": record["aggregation"], "target_count": record["coverage"],
            "median_absolute_percentage_error": record["median_ape"],
            "label_cohort": "160 development valuation targets",
        })

    default_factors = pd.read_csv(BASE / "source_reviewed_default/factors/method_results.csv")
    for record in default_factors.to_dict("records"):
        rows.append({
            "stage": "source-reviewed default factors", "configuration":
                f"{record['factor_set']}: {record['peer_budget']} peers, {record['aggregation']}",
            "facet": "source-reviewed Sonnet general", "retrieval": "B3",
            "selection": f"top {record['peer_budget']} after factor distance",
            "grading": "none", "factor": record["factor_set"],
            "aggregation": record["aggregation"], "target_count": record["coverage"],
            "median_absolute_percentage_error": record["median_ape"],
            "label_cohort": "160 development valuation targets",
        })

    factor_cross = pd.read_csv(BASE / "factors_by_facet/comparison.csv")
    for record in factor_cross.to_dict("records"):
        rows.append({
            "stage": "GPT facets with private-supplied factors",
            "configuration": (f"{record['facet_condition']}: {record['factor_set']}: "
                              f"{record['peer_budget']} peers: {record['aggregation']}"),
            "facet": record["facet_condition"], "retrieval": "B3",
            "selection": f"top {record['peer_budget']} after factor distance",
            "grading": "none", "factor": record["factor_set"],
            "aggregation": record["aggregation"], "target_count": record["coverage"],
            "median_absolute_percentage_error": record["median_ape"],
            "label_cohort": "160 development valuation targets",
        })

    regression = pd.read_csv(BASE / "regression/summary.csv")
    add(rows, "FF49 regression", regression, facet="industry and optional qualitative",
        retrieval="not applicable", selection="pooled training firms", grading="none",
        factor="dated public financial fields", aggregation="regression",
        method_col="method", error_col="median_ape",
        label_cohort="160 development valuation targets")
    output = pd.DataFrame(rows)
    if output["stage"].isna().any() or output.duplicated(["stage", "configuration"]).any():
        raise ValueError("Experiment names must uniquely identify executed configurations")
    output["pairwise_accuracy"] = float("nan")
    output["reviewed_good_recall"] = float("nan")
    diagnostics = (
        ("retrieval comparison", "candidate_methods/reviewed_metrics.csv", "method",
         "pairwise accuracy", "good_recall"),
        ("source-reviewed default retrieval", "source_reviewed_default/retrieval/reviewed_metrics.csv", "method",
         "pairwise accuracy", "good_recall"),
        ("GPT retrieval comparison", "candidate_methods_gpt/reviewed_metrics.csv", "method",
         "pairwise accuracy", "good_recall"),
        ("cited retrieval comparison", "candidate_methods_cited/reviewed_metrics.csv", "method",
         "pairwise accuracy", "good_recall"),
        ("saved facet ablation", "facet_293/metrics.csv", "variant",
         "pairwise_accuracy", "good_recall"),
        ("GPT facet comparison", "gpt_candidates/reviewed_metrics.csv", "variant",
         "pairwise_accuracy", "good_recall"),
        ("source availability", "source_facet_eval/reviewed_metrics.csv", "variant",
         "pairwise_accuracy", "good_recall"),
        ("Orbis qualitative facets", "yifan_eval/reviewed_metrics.csv", "variant",
         "pairwise_accuracy", "good_recall"),
    )
    for stage, path, key, accuracy, recall in diagnostics:
        scores = pd.read_csv(BASE / path).drop_duplicates(key).set_index(key)
        mask = output["stage"].eq(stage)
        names = output.loc[mask, "configuration"]
        if stage == "saved facet ablation":
            names = names.str.rsplit(": ", n=1).str[0]
        output.loc[mask, "pairwise_accuracy"] = names.map(scores[accuracy]).to_numpy()
        output.loc[mask, "reviewed_good_recall"] = names.map(scores[recall]).to_numpy()
    mask = output["stage"].eq("judge selection on reviewed pairs")
    output.loc[mask, "reviewed_good_recall"] = output.loc[mask, "configuration"].map(
        judge_peer.set_index("rule")["good_recall"]).to_numpy()
    threshold_run = json.loads((BASE / "thresholds/run.json").read_text(encoding="utf-8"))
    mask = (output["stage"].eq("reviewer-calibrated threshold") &
            output["configuration"].eq("B3 reviewer-calibrated z"))
    output.loc[mask, "reviewed_good_recall"] = threshold_run["crossfit_good_recall"]
    golden = pd.read_csv(BASE / "golden_method_metrics.csv")
    peer_rows = pd.DataFrame({
        "stage": "golden peer quality",
        "configuration": golden["facet_source"] + ": " + golden["method"] + ": " + golden["label_source"],
        "facet": golden["facet_source"],
        "retrieval": golden["method"],
        "selection": "saved peer rule",
        "grading": "human 0–2",
        "factor": "business only",
        "aggregation": "not applicable",
        "target_count": golden["labeled_targets"],
        "median_absolute_percentage_error": float("nan"),
        "label_cohort": golden["label_source"],
        "pairwise_accuracy": golden["pairwise_top10_accuracy"],
        "reviewed_good_recall": golden["good_recall"],
    })
    output = pd.concat([output, peer_rows], ignore_index=True)
    default_gold = pd.read_csv(BASE / "source_reviewed_default/golden/metrics.csv")
    default_rows = pd.DataFrame({
        "stage": "source-reviewed default golden peers",
        "configuration": default_gold["method"] + ": " + default_gold["label_source"],
        "facet": "source-reviewed Sonnet general",
        "retrieval": default_gold["method"],
        "selection": "saved peer rule", "grading": "human 0–2",
        "factor": "business only", "aggregation": "not applicable",
        "target_count": default_gold["labeled_targets"],
        "median_absolute_percentage_error": float("nan"),
        "label_cohort": default_gold["label_source"],
        "pairwise_accuracy": default_gold["pairwise_top10_accuracy"],
        "reviewed_good_recall": default_gold["good_recall"],
    })
    output = pd.concat([output, default_rows], ignore_index=True)
    routes = pd.read_csv(BASE / "golden_routes/metrics.csv")
    route_rows = pd.DataFrame({
        "stage": "golden selector routes",
        "configuration": routes["facet_source"] + ": " + routes["method"] + ": " + routes["label_source"],
        "facet": routes["facet_source"],
        "retrieval": "B3 or direct LLM",
        "selection": routes["method"],
        "grading": "human 0–2",
        "factor": "business only",
        "aggregation": "not applicable",
        "target_count": routes["labeled_targets"],
        "median_absolute_percentage_error": float("nan"),
        "label_cohort": routes["label_source"],
        "pairwise_accuracy": routes["pairwise_top10_accuracy"],
        "reviewed_good_recall": routes["good_recall"],
    })
    output = pd.concat([output, route_rows], ignore_index=True)
    exceptions = pd.read_csv(BASE / "gpt_scope_alignment/sensitivity/comparison.csv")
    exception_rows = pd.DataFrame({
        "stage": "scope exception sensitivity",
        "configuration": exceptions["variant"],
        "facet": exceptions["variant"],
        "retrieval": "B3",
        "selection": "mutual top ten, three-peer top-up",
        "grading": "human majority 0–2",
        "factor": "business only",
        "aggregation": "similarity-weighted mean",
        "target_count": exceptions["valuation_targets"],
        "median_absolute_percentage_error": exceptions["median_ape"],
        "label_cohort": "32 majority pairs; 160 development valuation targets",
        "reviewed_good_recall": exceptions["good_selected"] / exceptions["good_total"],
    })
    output = pd.concat([output, exception_rows], ignore_index=True)
    if output.duplicated(["stage", "configuration"]).any():
        raise ValueError("Duplicate experiment configuration")
    output.to_csv(OUT, index=False)
    print(output.groupby("stage").size().to_string())
    print(f"Total executed rows: {len(output)}")


if __name__ == "__main__":
    main()
