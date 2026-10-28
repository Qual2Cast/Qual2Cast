"""Build the companion notebook for reviewer labels and fixed-holdout results."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


DEST = Path(__file__).resolve().parent / "notebooks/gold_and_holdout_integration.ipynb"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


def main() -> None:
    cells = [
        markdown("""
# Comparable-company selection: reviewer labels and the fixed holdout

This report extends Michael's 27 October SIC2 v0 baseline with three independent reviewer label sets and the **160-company holdout**. It uses the same 373-company training pool and the baseline's candidate, peer-selection, and valuation functions. Company identity remains one `IQ_COMPANY_ID`; source-checked business activities are stored under that identifier.

The 36 reviewed pairs cover two development targets (PCTY and WEN). They assess **peer relevance**, not facet-fill accuracy. The holdout evaluates EV/EBITDA estimation; it does not validate private-company prediction, because its targets and peers are public companies.
"""),
        code("""
from pathlib import Path
import json
import sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display

ROOT = next(p for p in (Path.cwd(), *Path.cwd().parents)
            if (p / "v0/README.md").exists() and (p / "src/project_data.py").exists())
sys.path[:0] = [str(ROOT / "v0"), str(ROOT / "src")]
OUT = ROOT / "outputs-local/comps_pilot_targets"
GOLD = OUT / "golden_set/reviewer_evaluation"
FACETS = OUT / "facet_eval/20261028T135602Z"
SPLIT = OUT / "business_structure_refinement"
HOLDOUT = OUT / "holdout_completion"
pd.set_option("display.max_colwidth", 55)
"""),
        markdown("""
## 1. Fixed inputs and comparison rules

The frozen v0 split is stratified on SIC2, after the team's 3–30 EV/EBITDA eligibility rule reduces the 560-company list to 533 public firms. The financial and SIC fields come from the saved `company_list_v3` Capital IQ snapshot; this run does not query the Capital IQ API. All holdout targets are compared only with training firms. Once eligibility is fixed, peer-selection calls do not read financial multiples; the valuation stage reads them after peer lists are produced. The embedding cache is checked against the team's saved candidate scores. The LLM routes read company names, websites, and business facets, without multiples or reviewer labels. The holdout LLM backend is recorded separately from the original Haiku training run.
"""),
        code("""
candidate_run = json.loads((SPLIT / "holdout_all_candidates/run.json").read_text())
split = pd.read_csv(OUT / "split" / candidate_run["split_run"] / "split.csv", dtype=str)
print(split["sample"].value_counts().to_string())
print(f"Holdout candidates: {candidate_run['pairs']:,}; "
      f"maximum saved-score discrepancy: {candidate_run['max_saved_pair_cosine_difference']:.2g}")
"""),
        markdown("""
## 2. Peer labels and facet selection

Riya, Barbara, and Matthew independently scored the same 36 pairs from 0 to 2. A majority label is used only when at least two reviewers chose the same score; four three-way ties remain unresolved. Fiona's facet evaluator ranks peers from saved per-facet cosine scores. Each ablation removes one facet without fitting weights. The comparison below reports pairwise ranking accuracy on those labeled pairs; these two targets are development evidence, not an independent holdout.

Route precision and NDCG use only the reviewed candidates in the 36-pair pool. A shorter selected list can therefore have high precision with low coverage; the route table reports its length.
"""),
        code("""
gold_run = json.loads((GOLD / "run.json").read_text())
facet_scores = pd.read_csv(FACETS / "summary.csv")
key = facet_scores[facet_scores["variant"].isin(
    ["generic (step 4)", "generic minus F3 primary_services"])]
show = key[["variant", "labels", "labeled pairs", "pairwise accuracy",
            "recall@10 of best comps", "top-10 labeled share"]].copy()
display(show.round(3))
print("Reviewer agreement:")
display(pd.read_csv(GOLD / "reviewer_agreement.csv").round(3))
routes_gold = pd.read_csv(GOLD / "route_metrics.csv")
display(routes_gold[routes_gold["target"].eq("mean")][[
    "reviewer", "route", "listed in top 10", "precision@10", "direct hits@10",
    "NDCG@10"]].round(3))
route_ndcg = routes_gold[routes_gold["target"].eq("mean")].pivot(
    index="reviewer", columns="route", values="NDCG@10")
fig_route, ax_route = plt.subplots(figsize=(9, 3.5))
route_ndcg.plot.bar(ax=ax_route)
ax_route.set_ylabel("NDCG@10 on reviewed peers")
ax_route.set_xlabel("Reviewer")
ax_route.set_ylim(0, 1)
ax_route.legend(title="Route", fontsize=7, loc="upper left", bbox_to_anchor=(1, 1))
fig_route.tight_layout()
fig_route.savefig(GOLD / "route_ndcg_by_reviewer.png", dpi=180)
plt.show()

fig, ax = plt.subplots(figsize=(9.5, 3.5))
chart = key.pivot(index="labels", columns="variant", values="pairwise accuracy")
chart.index = chart.index.str.replace("gold:facet_labels_", "", regex=False)
chart.plot.bar(ax=ax, color=["#2f6b91", "#e09b47"])
ax.set_ylabel("Pairwise ranking accuracy")
ax.set_xlabel("Reviewer labels")
ax.set_ylim(0, 1)
ax.legend(title="Facet set", fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
fig.tight_layout()
fig.savefig(FACETS / "reviewer_f3_pairwise.png", dpi=180)
plt.show()
"""),
        markdown("""
### Related validation work

The peer-label analysis above does not check the LLM's facet extraction. Riya's facet-fill rubric and Yiming's `v0/verification/` compare individual facet claims with dated source evidence; Yiming reports problems in 24.5% of 208 checkable facets across 20 companies. His name-masked website-only test filled 61% of facets. Yifan and Richard's separate `verification/gold-labels` branch adds a 40-company benchmark and RAG evidence retrieval.

Kethan's `v0/peer_evaluation.py` judges accepted peers against saved website passages with a 0–3 rubric; its completed 663-pair run uses the earlier size split. His root pipeline notebook remains on the unmerged `kethan/wip` branch with size stratification. These results are not substituted for the 160-target SIC2 holdout valuation outcomes.

References: `v0/verification/README.md`, `v0/PEER_EVALUATION.md`, and the 27 October team standups in the Rational AI Google Chat.
"""),
        code("""
checks = pd.DataFrame([
    {"component": "facet claims", "owner": "Riya / Yiming", "unit": "company × facet",
     "local code": "v0/verification/", "used here": "context; separate gold"},
    {"component": "RAG evidence", "owner": "Yifan / Richard", "unit": "company × facet",
     "local code": "verification/gold-labels branch", "used here": "not merged"},
    {"component": "LLM peer judge", "owner": "Kethan", "unit": "accepted target × peer",
     "local code": "v0/peer_evaluation.py", "used here": "older size split"},
    {"component": "three-reviewer gold", "owner": "Riya / Barbara / Matthew",
     "unit": "target × peer", "local code": "v0/reviewer_gold_eval.py",
     "used here": "facet comparison"},
])
display(checks)
"""),
        markdown("""
## 3. Business-structure evidence

The source-linked check distinguishes concurrent operating activities from product variants and from formerly owned businesses. It keeps all activities under the original company ID. The ten-case source audit is a targeted regression test, not an estimate of population accuracy. A separate paired trial found that inserting this context into the existing judge prompt worsened valuation error, so the default matcher remains unchanged.

The source groups also permit a narrow post-selection diagnostic: flag peers among the 40 audited companies that have multiple unrelated businesses, then compare estimates after excluding them. For example, AIR's direct LLM list includes BUKS; Butler reports both aerospace and gaming operations, with approximately 62% and 38% of FY2026 revenue, respectively, so its whole-company multiple is not a pure aerospace multiple ([company investor page](https://butlernational.com/investing/)). This 40-company check does not classify the full peer universe.
"""),
        code("""
source = json.loads((SPLIT / "source_benchmark/summary.json").read_text())
peer = json.loads((SPLIT / "peer_test/summary.json").read_text())
trial = json.loads((SPLIT / "holdout_test/summary.json").read_text())
display(pd.DataFrame({
    "check": ["activity status (34 labels)", "exact business groups (9 cases)"],
    "saved": [f"{source['activity_correct_saved']}/34", f"{source['group_exact_saved']}/9"],
    "source checked": [f"{source['activity_correct_refined']}/34",
                       f"{source['group_exact_refined']}/9"],
}))
print(f"Paired development trial: {peer['control']['median_ape']:.2f}% → "
      f"{peer['selective_scope']['median_ape']:.2f}% median APE; "
      f"six-target pilot holdout: {trial['control']['median_ape']:.2f}% → "
      f"{trial['selective_scope']['median_ape']:.2f}%.")
scope_result = HOLDOUT / "evaluation/source_scope_sensitivity/sensitivity.csv"
if scope_result.exists():
    print("Known mixed-business peer exclusion (sensitivity only):")
    display(pd.read_csv(scope_result).round(2))
"""),
        markdown("""
## 4. Four peer-selection routes

1. **Cosine:** rank all training firms by the mean of available facet similarities.
2. **Cosine → LLM:** the LLM accepts or rejects cosine candidates at z ≥ 2.
3. **Direct LLM:** the LLM selects up to ten firms from the complete training pool.
4. **LLM → cosine:** cosine scores rerank and weight the direct selections.

The four routes use the same holdout targets and pool. The holdout calls batch independent targets to avoid repeating a large pool prompt; this differs from the original Haiku one-target-per-call training protocol. Missing peers are reported as coverage loss, without an unreported fallback. The reviewer-based F3 ablation is shown beside these routes as a prespecified candidate change.
"""),
        code("""
llm_run = json.loads((HOLDOUT / "llm_run.json").read_text())
issue_path = HOLDOUT / "answer_issues.csv"
issues = pd.read_csv(issue_path) if issue_path.exists() else pd.DataFrame()
llm_run.setdefault("answer_issues", len(issues))
llm_run.setdefault("inference_protocol", "one target per call")
display(pd.DataFrame([llm_run])[["model", "inference_protocol", "targets_done", "holdout_total",
                                 "training_pool", "judged_pairs", "accepted_judge_pairs",
                                 "direct_pairs", "answer_issues", "complete"]])
print(f"Invalid or repeated labels discarded: {len(issues)}")
"""),
        code("""
universe = pd.read_csv(ROOT / "outputs-local/comps/universe" / candidate_run["universe_run"] /
                       "universe.csv", dtype=str).set_index("IQ_COMPANY_ID")
air_id = universe.index[universe["target_ciq_ticker"].eq("AIR")][0]
direct_peers = pd.read_csv(HOLDOUT / "direct.csv", dtype={"target": str, "comp": str})
judged_peers = pd.read_csv(HOLDOUT / "judge.csv", dtype={"target": str, "comp": str})
print("AIR: direct selections and their recorded reasons")
example = direct_peers[direct_peers["target"].eq(air_id)].copy()
example["peer ticker"] = example["comp"].map(universe["target_ciq_ticker"])
display(example[["rank", "peer ticker", "reason"]].head(10))
print("AIR: cosine shortlist decisions")
example = judged_peers[judged_peers["target"].eq(air_id)].copy()
example["peer ticker"] = example["comp"].map(universe["target_ciq_ticker"])
display(example[["peer ticker", "score", "reason"]].head(10))
"""),
        markdown("""
## 5. Holdout valuation

The team’s `valuation.estimate` calculates a peer mean, similarity-weighted mean, or median EV/EBITDA. The no-matching control uses the median of the 373 training companies. The same 160 holdout target multiples are the answer key for every route. Median absolute percentage error (APE) is shown with the number of targets that received an estimate; those counts matter when routes abstain.
"""),
        code("""
evaluation = pd.read_csv(HOLDOUT / "evaluation/summary.csv")
columns = ["comp rule", "targets", "median abs % error", "% within 25%",
           "% closer than no matching"]
display(evaluation[columns].round(2))
print("Prespecified F3 ablation on identical targets:")
display(pd.read_csv(HOLDOUT / "evaluation/paired_f3.csv").round(2))
print("Four routes on their common target set:")
common = HOLDOUT / "evaluation/route_common_support.csv"
if common.exists():
    display(pd.read_csv(common).round(2))
    print("Direct LLM versus LLM followed by cosine on identical targets:")
    display(pd.read_csv(HOLDOUT / "evaluation/reverse_hybrid_paired.csv").round(2))
else:
    print("LLM holdout routes are still running.")

view = evaluation[evaluation["comp rule"].isin([
    "no matching, training-pool median", "cosine z >= 2, weighted mean",
    "cosine minus F3 z >= 2, weighted mean", "cosine then LLM, weighted mean",
    "LLM direct, mean", "LLM then cosine, weighted mean"])]
labels = {"no matching, training-pool median": "No matching",
          "cosine z >= 2, weighted mean": "Cosine",
          "cosine minus F3 z >= 2, weighted mean": "Cosine without F3",
          "cosine then LLM, weighted mean": "Cosine → LLM",
          "LLM direct, mean": "Direct LLM",
          "LLM then cosine, weighted mean": "LLM → cosine"}
colors = ["#8a9299", "#397aa6", "#c48635", "#397aa6", "#397aa6", "#397aa6"]
fig, ax = plt.subplots(figsize=(8.5, 4))
bars = ax.barh(view["comp rule"].map(labels), view["median abs % error"], color=colors)
for bar, n in zip(bars, view["targets"]):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
            f"{bar.get_width():.1f}%  ({n}/160)", va="center", fontsize=9)
ax.set_xlabel("Median absolute percentage error (%)")
ax.invert_yaxis()
ax.set_xlim(0, max(view["median abs % error"]) * 1.42)
fig.tight_layout()
fig.savefig(HOLDOUT / "evaluation/holdout_methods.png", dpi=180)
plt.show()
"""),
        markdown("""
## 6. Interpretation and next decision

The two-target reviewer set favors removing F3 (`primary_services`): majority-label pairwise accuracy rises from 0.851 to 0.921, and all three individual reviewers also improve. On the 160-target holdout, cosine at z ≥ 2 improves from 37.32% to 33.29% median APE after removing F3, but the bootstrap interval for the paired median change includes zero (−2.04 to +0.08 percentage points). The effect reverses under the z ≥ 2.5 rule on its common 158 targets. F3 removal remains a candidate, not a new default.

On the 107 targets covered by all four routes, cosine has 36.83% median APE; cosine → LLM has 37.50%, direct LLM 37.79%, and LLM → cosine 37.93%. Their paired intervals against cosine include zero. Direct LLM and LLM → cosine both cover 119/160 and have 33.78% median APE on those 119; reranking improves 40 targets and worsens 42. The fourth route has no demonstrated holdout advantage.

The source-backed grouping corrects the targeted activity and business partitions, but adding scope text to the judge worsened the paired pilot results. Excluding source-confirmed mixed-business peers changes cosine median APE from 37.32% to 37.98% over all 160 targets; among 48 affected targets, 27 improve and 21 worsen. Only 4–6 targets are affected in each LLM route, and filtering loses one estimate per route. Keep the business groups as auditable metadata while extending the peer universe beyond 560 and testing website-observable private-company inputs. The public holdout does not establish performance on private transactions.

**Source files:** `v0/reviewer_gold_eval.py`, `v0/facet_eval.py`, `v0/business_split_refinement.py`, `v0/holdout_split_candidates.py`, `v0/holdout_batched_routes.py`, `v0/holdout_evaluation.py`, and `v0/source_scope_sensitivity.py`. Team inputs are the saved v0 facet/candidate/financial tables and the three-reviewer golden-set Sheet snapshot. `v0/README.md` records the original route definitions.
"""),
    ]
    notebook = nbf.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"}})
    DEST.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, DEST)
    print(DEST.name)


if __name__ == "__main__":
    main()
