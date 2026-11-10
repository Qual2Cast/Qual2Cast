"""Locate disagreement and coverage issues without inferring causal failures."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
BASE = V1 / "integration"
OUT = BASE / "error_diagnosis"


def main() -> None:
    runs = {"GPT general": "gpt_general", "GPT + Fiona + Barbara": "gpt_all"}
    frames = []
    for label, folder in runs.items():
        path = BASE / "holdout_routes" / folder / "evaluation/target_results.csv"
        table = pd.read_csv(path, dtype={"target": str})
        table["facet_condition"] = label
        frames.append(table)
    data = pd.concat(frames, ignore_index=True)
    data["absolute_percent_error"] = data["error %"].abs()
    info = pd.read_csv(V1 / "universe/20261025T060358Z/universe.csv",
                       dtype=str).set_index("IQ_COMPANY_ID")
    data["company"] = data["target"].map(info["target_company_name"])
    data["ticker"] = data["target"].map(info["target_ciq_ticker"])
    pivot = data.pivot_table(index=["target", "ticker", "company", "facet_condition"],
                             columns="method", values="absolute_percent_error",
                             aggfunc="first").reset_index()
    if "B3 selected" not in pivot or "B3 then LLM" not in pivot:
        raise ValueError("Required peer routes are missing")
    pivot["judge_change_pp"] = pivot["B3 then LLM"] - pivot["B3 selected"]
    pivot["large_b3_error"] = pivot["B3 selected"].gt(50)
    pivot["judge_improves"] = pivot["judge_change_pp"].lt(0)
    out = OUT
    out.mkdir(parents=True, exist_ok=True)
    pivot.to_csv(out / "holdout_target_comparison.csv", index=False)
    peer = pd.read_csv(BASE / "judge_gpt61sol/eval_293/disagreements.csv",
                       dtype={"target": str, "comp": str})
    peer["target_name"] = peer["target"].map(info["target_company_name"])
    peer["comp_name"] = peer["comp"].map(info["target_company_name"])
    peer.to_csv(out / "peer_grade_disagreements.csv", index=False)
    summary = {}
    for label, group in pivot.groupby("facet_condition"):
        summary[label] = {
            "targets": len(group), "large_b3_error": int(group["large_b3_error"].sum()),
            "judge_improved": int(group["judge_improves"].sum()),
            "judge_worsened": int(group["judge_change_pp"].gt(0).sum()),
            "judge_no_estimate": int(group["B3 then LLM"].isna().sum()),
        }
    summary["reviewer_disagreements"] = len(peer)
    source = pd.read_csv(BASE / "web_evidence/coverage.csv")
    scope = pd.read_csv(BASE / "sources/yiming_review_list.csv")
    claims = pd.read_csv(BASE / "claim_check/verdicts.csv")
    cited_claims = pd.read_csv(BASE / "claim_check_cited/verdicts.csv")
    growth = pd.read_csv(BASE / "growth/rule_errors.csv")
    candidate = pd.read_csv(BASE / "candidate_methods/reviewed_metrics.csv")
    base = candidate[candidate["method"].eq("B3 embedding plus TF-IDF")]
    if len(base) != 1:
        raise ValueError("The corrected B3 diagnostic row is missing")
    stage_rows = [
        {"stage": "source", "flag": "no usable official-site lines after refresh",
         "count": int(source["usable_lines"].eq(0).sum()), "denominator": len(source)},
        {"stage": "business scope", "flag": "Yiming review queue",
         "count": len(scope), "denominator": 533},
        {"stage": "facet extraction: memory-first", "flag": "source verifier not found, missed, partly or contradicted",
         "count": int(claims["verdict"].isin(["not_found", "missed", "partly", "contradicted"]).sum()),
         "denominator": len(claims)},
        {"stage": "facet extraction: source-cited", "flag": "source verifier not found, missed, partly or contradicted",
         "count": int(cited_claims["verdict"].isin(["not_found", "missed", "partly", "contradicted"]).sum()),
         "denominator": len(cited_claims)},
        {"stage": "candidate ranking", "flag": "reviewed bad peer selected by corrected B3",
         "count": int(base.iloc[0]["bad_selected"]),
         "denominator": int(base.iloc[0]["labeled pairs"])},
        {"stage": "peer grading", "flag": "GPT judge differs from Barbara 0–2 grade",
         "count": len(peer), "denominator": 293},
        {"stage": "valuation", "flag": "B3 absolute percentage error above 50",
         "count": int(pivot["large_b3_error"].sum()), "denominator": len(pivot)},
        {"stage": "growth extraction", "flag": "holdout_c rule false positive or false negative",
         "count": int(growth["cohort"].eq("holdout_c").sum()),
         "denominator": int(pd.read_csv(BASE / "growth/rule_metrics.csv").query(
             "cohort == 'holdout_c' and event_type == 'ALL'")["true"].iloc[0])},
    ]
    pd.DataFrame(stage_rows).to_csv(out / "stage_diagnostics.csv", index=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
