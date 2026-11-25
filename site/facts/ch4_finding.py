"""Facts for Finding comps (finding.qmd). Pattern: see ch2_data.py.

Three steps, each from its saved run (the runs v2/current.toml names):
  - B3 list (03_retrieval): every training target's comp list, "mutual top 10, topped up to 3".
  - Selector (04_selection): Sonnet keeps or drops each B3 comp, one call per target, all 373 training targets.
  - Agent grade (05_agent_grading): grades 0/1/2 per pair, on the 293 B3 pairs of the 45 reviewed targets only.
The agent did not run after the selector: both read the same B3 list. So "kept by the selector" and "graded >= 1
by the agent" are compared on the same 293 pairs (fig_filter_keeps), not chained as a funnel.

The "how we got here" box: v0's four comp-choosing routes on the 160 holdout targets (the v0 holdout, not the locked
final holdout), compared on the 107 targets every route covers, by median absolute % error of EV/EBITDA.
"""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import pandas as pd

from facts.common import fact, pinned


def _n(x) -> str:
    return f"{int(x):,}"


def _pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%"


def _signed(x: float, digits: int = 1) -> str:
    return f"{x:+.{digits}f}".replace("-", "−")


# ---------------------------------------------------------------- B3 list (03_retrieval)
_cand = pd.read_csv(pinned("b3_candidates"), dtype={"target": str, "comp": str})
_b3 = _cand[_cand["selected"]]
_per_target_top = _cand.groupby("target").size()
_per_target = _b3.groupby("target").size()
assert _per_target_top.nunique() == 1, "every target's candidate list should have the same length (k)"

b3_targets = fact("b3_targets", _b3["target"].nunique(), _n(_b3["target"].nunique()), source="b3_candidates")
b3_pairs = fact("b3_pairs", len(_b3), _n(len(_b3)), source="b3_candidates")
b3_k = fact("b3_k", int(_per_target_top.iloc[0]), str(int(_per_target_top.iloc[0])), source="b3_candidates")
b3_min_comps = fact("b3_min_comps", int(_per_target.min()), str(int(_per_target.min())), source="b3_candidates")
b3_median_comps = fact("b3_median_comps", float(_per_target.median()), f"{_per_target.median():g}",
                       source="b3_candidates")
b3_pairs_topped_up = fact("b3_pairs_topped_up", int(_b3["topped_up"].sum()), _n(_b3["topped_up"].sum()),
                          source="b3_candidates")

# ---------------------------------------------------------------- selector (04_selection), all training targets
_judg = pd.read_csv(pinned("sel_judgments"), dtype={"target": str, "comp": str})
_judged = _b3.merge(_judg[["target", "comp", "score"]], on=["target", "comp"], how="left")
assert _judged["score"].notna().all(), "the selector judged every B3 pair"
_kept = _judged[_judged["score"] == 1]
_kept_per_target = _judged.groupby("target")["score"].sum()

sel_kept_pairs = fact("sel_kept_pairs", len(_kept), _n(len(_kept)), source="b3_candidates+sel_judgments")
sel_keep_rate = fact("sel_keep_rate", len(_kept) / len(_judged), _pct(len(_kept) / len(_judged)),
                     source="b3_candidates+sel_judgments")
sel_targets_kept = fact("sel_targets_kept", int((_kept_per_target > 0).sum()), _n((_kept_per_target > 0).sum()),
                        source="b3_candidates+sel_judgments")
sel_targets_no_comp = fact("sel_targets_no_comp", int((_kept_per_target == 0).sum()),
                           _n((_kept_per_target == 0).sum()), source="b3_candidates+sel_judgments")

# ---------------------------------------------------------------- agent grade (05_agent_grading), 45 reviewed targets
_v = pd.read_csv(pinned("agent_verdicts"), dtype={"target": str, "comp": str})
_cfg = json.loads(pinned("agent_config").read_text(encoding="utf-8"))
assert _v["status"].eq("ok").all(), "every agent call finished"
_grade = pd.to_numeric(_v["score"], errors="coerce")

agent_targets = fact("agent_targets", _v["target"].nunique(), _n(_v["target"].nunique()), source="agent_verdicts")
agent_pairs = fact("agent_pairs", len(_v), _n(len(_v)), source="agent_verdicts")
agent_grade2 = fact("agent_grade2", int((_grade == 2).sum()), _n((_grade == 2).sum()), source="agent_verdicts")
agent_grade1 = fact("agent_grade1", int((_grade == 1).sum()), _n((_grade == 1).sum()), source="agent_verdicts")
agent_grade0 = fact("agent_grade0", int((_grade == 0).sum()), _n((_grade == 0).sum()), source="agent_verdicts")
agent_insufficient = fact("agent_insufficient", int(_grade.isna().sum()), _n(_grade.isna().sum()),
                          source="agent_verdicts")
agent_ge1 = fact("agent_ge1", int((_grade >= 1).sum()), _n((_grade >= 1).sum()), source="agent_verdicts")
agent_pairs_lookup = fact("agent_pairs_lookup", int((_v["lookups"] > 0).sum()), _n((_v["lookups"] > 0).sum()),
                          source="agent_verdicts")
agent_share_lookup = fact("agent_share_lookup", float((_v["lookups"] > 0).mean()), _pct((_v["lookups"] > 0).mean()),
                          source="agent_verdicts")
agent_max_steps = fact("agent_max_steps", int(_cfg["max_steps"]), str(int(_cfg["max_steps"])), source="agent_config")

# the selector on the same 293 pairs the agent graded (same B3 pairs: the full lists of the 45 reviewed targets)
_same = _v[["target", "comp"]].merge(_judged[["target", "comp", "score"]], on=["target", "comp"], how="left")
assert len(_same) == len(_v) and _same["score"].notna().all()
assert len(_b3[_b3["target"].isin(_v["target"])]) == len(_v), "the agent graded the full B3 lists of its targets"
sel_kept_on_agent_pairs = fact("sel_kept_on_agent_pairs", int((_same["score"] == 1).sum()),
                               _n((_same["score"] == 1).sum()), source="agent_verdicts+sel_judgments")


def fig_filter_keeps():
    """Pairs each filter keeps, on the same B3 pairs of the reviewed targets (bar style from
    v2/05_agent_grading/agent_grading.ipynb section 3.4, the outcomes chart)."""
    counts = pd.Series({"B3 list": agent_pairs.value, "Selector keeps": sel_kept_on_agent_pairs.value,
                        "Agent grade ≥ 1": agent_ge1.value, "Agent grade 2": agent_grade2.value}, name="pairs")
    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(counts.index, counts.values, color="slategray")
    ax.bar_label(bars, padding=3)
    ax.set(ylabel="Number of pairs")
    ax.set_ylim(0, max(counts.max() * 1.15, 1))
    fig.text(0.01, 0.01, f"Source: B3 list, selector judgments and ranking_45targets_sonnet/verdicts.csv; "
                         f"the {agent_pairs.value} B3 pairs of the {agent_targets.value} reviewed targets", fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, 1))
    return fig


def fig_agent_outcomes():
    """Agent grade counts. Code from v2/05_agent_grading/agent_grading.ipynb section 3.4 (cell "v1
    peer_evaluation.ipynb section 7.2"), nearly verbatim: the title (it typed the pair count) is left to the caption
    and nothing is saved to disk."""
    pair_results = pd.read_csv(pinned("agent_verdicts"), dtype={"target": str, "comp": str})
    pair_results["judge_score"] = pd.to_numeric(pair_results["score"], errors="coerce")
    ok = pair_results["status"].eq("ok")
    graded_results = pair_results.loc[ok & pair_results.judge_score.notna()].copy()
    total = len(pair_results)
    score_counts = graded_results.judge_score.value_counts().reindex([0, 1, 2], fill_value=0)
    insufficient = int((ok & pair_results.judge_score.isna()).sum())
    failed = int((~ok).sum())

    outcome_counts = pd.Series([*score_counts.tolist(), insufficient, failed],
                               index=["0: Not peer", "1: Adjacent", "2: Direct", "Insufficient\nevidence",
                                      "Failed /\ninvalid"],
                               name="pairs")
    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(outcome_counts.index, outcome_counts.values, color="slategray")
    ax.bar_label(bars, padding=3)
    ax.set(xlabel="Outcome", ylabel="Number of pairs")
    ax.set_ylim(0, max(outcome_counts.max() * 1.15, 1))
    fig.text(0.01, 0.01, f"Source: ranking_45targets_sonnet/verdicts.csv; all {total} pairs", fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, 1))
    return fig


# ---------------------------------------------------------------- "how we got here": v0's four routes
# The four routes as named in v0/holdout_evaluation.py (route_common_support.csv). Paired change there = a route's
# absolute % error minus cosine's, per common target (positive = worse than cosine); its 95% interval is a bootstrap
# of the median. v0_paired_change_range is the union of the three other routes' intervals; v0_routes_differing counts
# the routes whose interval excludes 0 (in either direction).
V0_ROUTES = ["cosine z >= 2, weighted mean", "cosine then LLM, weighted mean", "LLM direct, mean",
             "LLM then cosine, weighted mean"]
V0_REFERENCE = "cosine z >= 2, weighted mean"
V0_NO_MATCHING = "no matching, training-pool median"

_te = pd.read_csv(pinned("v0_target_errors"), dtype={"target": str})
_te = _te.dropna(subset=["estimate"])
_common = set.intersection(*(set(_te.loc[_te["method"] == r, "target"]) for r in V0_ROUTES))
_ape = _te[_te["target"].isin(_common)].assign(ape=lambda d: d["error %"].abs()).groupby("method")["ape"].median()
_routes_ape = _ape[V0_ROUTES]
_support = pd.read_csv(pinned("v0_route_support")).set_index("method")
_others = _support.drop(index=V0_REFERENCE)
_excl0 = ((_others["paired change 95% low"] > 0) | (_others["paired change 95% high"] < 0)).sum()

v0_routes = fact("v0_routes", len(V0_ROUTES), str(len(V0_ROUTES)), source="v0_target_errors")
v0_holdout_targets = fact("v0_holdout_targets", _te["target"].nunique(), _n(_te["target"].nunique()),
                          source="v0_target_errors")
v0_common_targets = fact("v0_common_targets", len(_common), _n(len(_common)), source="v0_target_errors")
v0_err_no_matching = fact("v0_err_no_matching", float(_ape[V0_NO_MATCHING]), f"{_ape[V0_NO_MATCHING]:.1f}%",
                          source="v0_target_errors")
v0_err_routes_range = fact("v0_err_routes_range", (float(_routes_ape.min()), float(_routes_ape.max())),
                           f"{_routes_ape.min():.1f}% to {_routes_ape.max():.1f}%", source="v0_target_errors")
v0_paired_change_range = fact(
    "v0_paired_change_range",
    (float(_others["paired change 95% low"].min()), float(_others["paired change 95% high"].max())),
    f"{_signed(_others['paired change 95% low'].min())} to {_signed(_others['paired change 95% high'].max())} pp",
    source="v0_route_support")
v0_routes_differing = fact("v0_routes_differing", int(_excl0), f"{int(_excl0)} of {len(_others)}",
                          source="v0_route_support")
