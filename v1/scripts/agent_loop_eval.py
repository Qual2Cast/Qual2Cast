"""Score an agent_loop.py run.

Four checks, each on the pairs that have the needed labels:
  1. Agreement with the human reviewers: the round-1 majority grade (PCTY, WEN;
     similarity_eval.reviewer_sets) and, once it is filled, round 2
     (round2_filled.csv). Exact agreement, within one grade, and peer / not-peer
     accuracy. The one-shot Sol grader (graded_peer_selection.py, same rubric,
     first 900 website words, no lookups) is scored on the same pairs, so the
     two can be compared directly.
  2. Agreement with Sol's saved grades on any overlapping pairs (an
     alternative check, not a decision rule, as in similarity_eval).
  3. The filter: for the pairs that are in B3's own list, how many
     reviewer-labelled peers and non-peers each list keeps: B3 as is, B3 keeping
     the agent's 1s and 2s, B3 keeping only its 2s.
  4. Valuation (only with 20+ targets): median absolute % error of the
     similarity-weighted EV/EBITDA for the same three lists. The multiple is
     read here only, never by the agent.

  uv run python v1/scripts/agent_loop_eval.py --run outputs-local/v1/agent_loop/<run>
Writes <run>/eval/ (tables + summary.md).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))
import similarity_eval as se  # noqa: E402
import valuation  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

V1 = OUTPUTS_LOCAL / "v1"
ROUND1 = V1 / "golden_set/labels/reviewer_labels_20261028.json"
ROUND2 = V1 / "golden_set_showcase/labels/round2_filled.csv"
SOL_ONE_SHOT_GOLD = V1 / "golden_set/graded_batch_check/grades.csv"
SOL_HOLDOUT = [V1 / "holdout_completion/graded_peer_selection/grades.csv",
               V1 / "sector_facets/holdout_grades/grades.csv"]
CANDIDATES = V1 / "candidates_method1/20261104T074915Z"
UNIVERSE = V1 / "universe/20261025T060358Z"
MIN_TARGETS_FOR_VALUATION = 20


def human_grades() -> pd.DataFrame:
    """target, comp, grade, round, unanimous (majority rule; no-majority pairs left out)."""
    frames = []
    labels = pd.DataFrame(json.loads(ROUND1.read_text(encoding="utf-8"))["labels"]).fillna("")
    major, unan, _ = se.reviewer_sets(labels)
    frames.append(major.assign(round=1, unanimous=major.set_index(["target", "comp"]).index.isin(
        unan.set_index(["target", "comp"]).index)))
    if ROUND2.exists():
        sheet = pd.read_csv(ROUND2, dtype=str).fillna("")
        reviewers = [c.removeprefix("score_") for c in sheet.columns if c.startswith("score_")]
        major, unan, _ = se.reviewer_sets(sheet, reviewers)
        frames.append(major.assign(round=2, unanimous=major.set_index(["target", "comp"]).index.isin(
            unan.set_index(["target", "comp"]).index)))
    return pd.concat(frames, ignore_index=True)


def agreement(pred: pd.DataFrame, truth: pd.DataFrame, name: str, col: str = "score") -> dict:
    """pred: target, comp, <col> (NaN = insufficient evidence); truth: target, comp, grade."""
    d = truth.merge(pred[["target", "comp", col]], on=["target", "comp"], how="inner")
    graded = d.dropna(subset=[col])
    s, g = graded[col].astype(int), graded["grade"].astype(int)
    return {"grader": name, "pairs": len(d), "graded": len(graded), "insufficient": int(d[col].isna().sum()),
            "exact": int((s == g).sum()), "exact %": 100 * (s == g).mean() if len(graded) else np.nan,
            "within 1 %": 100 * ((s - g).abs() <= 1).mean() if len(graded) else np.nan,
            "peer vs not-peer %": 100 * ((s >= 1) == (g >= 1)).mean() if len(graded) else np.nan,
            "mean (grader - human)": (s - g).mean() if len(graded) else np.nan}


def confusion(pred: pd.DataFrame, truth: pd.DataFrame, col: str = "score") -> pd.DataFrame:
    d = truth.merge(pred[["target", "comp", col]], on=["target", "comp"], how="inner")
    d[col] = d[col].map(lambda v: "insufficient" if pd.isna(v) else str(int(v)))
    return pd.crosstab(d["grade"].rename("human"), d[col].rename("grader"))


def filter_lists(v: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """B3's own list for the run's targets, and the two agent filters of it."""
    cand = pd.read_csv(CANDIDATES / "candidates.csv", dtype={"target": str, "comp": str})
    b3 = cand[cand["selected"].astype(str).eq("True") & cand["target"].isin(v["target"])]
    b3 = b3[["target", "comp", "similarity", "rank"]]
    scored = b3.merge(v[["target", "comp", "score", "status"]], on=["target", "comp"], how="left")
    return {"B3 as is": b3,
            "B3, agent 1 or 2": scored[scored["score"] >= 1][b3.columns],
            "B3, agent 2 only": scored[scored["score"] == 2][b3.columns],
            "_coverage": scored}


def human_counts(lists: dict[str, pd.DataFrame], truth: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, lst in lists.items():
        if name.startswith("_"):
            continue
        d = lst.merge(truth, on=["target", "comp"], how="left")
        lab = d.dropna(subset=["grade"])
        rows.append({"list": name, "pairs": len(d), "labelled": len(lab),
                     "direct (2) kept": int((lab.grade == 2).sum()), "adjacent (1) kept": int((lab.grade == 1).sum()),
                     "non-peer (0) kept": int((lab.grade == 0).sum()),
                     "precision (1 or 2) %": 100 * (lab.grade >= 1).mean() if len(lab) else np.nan})
    return pd.DataFrame(rows)


def valuation_table(lists: dict[str, pd.DataFrame]) -> pd.DataFrame:
    fin = pd.read_csv(UNIVERSE / "financials.csv", dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = fin["target_ev_to_ebitda"].astype(float)
    results = {n: valuation.estimate(l, multiples, weight="similarity") for n, l in lists.items()
               if not n.startswith("_")}
    targets = sorted(lists["B3 as is"]["target"].unique())
    split = json.loads((CANDIDATES / "run.json").read_text(encoding="utf-8"))
    pool = pd.read_csv(V1 / "split" / split["split_run"] / "split.csv", dtype={"IQ_COMPANY_ID": str})
    pool = pool.loc[pool["sample"].eq("training"), "IQ_COMPANY_ID"]
    results["no matching"] = valuation.no_matching(targets, pool, multiples)
    return valuation.bootstrap(results, multiples, "no matching")


def evaluate(run: Path) -> dict:
    v = pd.read_csv(run / "verdicts.csv", dtype={"target": str, "comp": str})
    out = run / "eval"
    out.mkdir(exist_ok=True)
    truth = human_grades()
    agent = v[["target", "comp", "score"]]
    rows = [agreement(agent, truth, "agent loop")]
    tables = {"confusion_agent.csv": confusion(agent, truth)}
    if SOL_ONE_SHOT_GOLD.exists():
        one = pd.read_csv(SOL_ONE_SHOT_GOLD, dtype={"target": str, "comp": str})[["target", "comp", "score"]]
        common = v[["target", "comp"]]
        rows.append(agreement(one.merge(common), truth, "one-shot Sol (same pairs)"))
        tables["confusion_one_shot.csv"] = confusion(one.merge(common), truth)
    human = pd.DataFrame(rows)
    sol, _ = se.sol_grades([p for p in SOL_HOLDOUT if p.exists()]) if any(p.exists() for p in SOL_HOLDOUT) \
        else (pd.DataFrame(columns=["target", "comp", "grade"]), None)
    sol_row = pd.DataFrame([agreement(agent, sol[["target", "comp", "grade"]], "agent vs Sol holdout grades")])
    lists = filter_lists(v)
    counts = human_counts(lists, truth)
    n_targets = v["target"].nunique()
    val = valuation_table(lists) if n_targets >= MIN_TARGETS_FOR_VALUATION else None

    human.to_csv(out / "agreement_human.csv", index=False)
    sol_row.to_csv(out / "agreement_sol.csv", index=False)
    counts.to_csv(out / "filter_human_counts.csv", index=False)
    for name, t in tables.items():
        t.to_csv(out / name)
    if val is not None:
        val.to_csv(out / "valuation.csv")
    status = v["status"].value_counts().to_dict()
    lookups = {"mean lookups per pair": round(v["lookups"].mean(), 2),
               "pairs with a web search %": round(100 * (v["web_searches"] > 0).mean(), 1),
               "pairs with no lookup %": round(100 * (v["lookups"] == 0).mean(), 1)}
    md = [f"# Agent loop evaluation: {run.name}", "",
          f"{len(v)} pairs, {n_targets} targets. Status: {status}. Lookups: {lookups}.", "",
          "## 1. Agreement with the reviewers (majority grade)", "", human.round(1).to_markdown(index=False), "",
          "Agent loop, human (rows) vs agent (columns):", "", tables["confusion_agent.csv"].to_markdown(), ""]
    if "confusion_one_shot.csv" in tables:
        md += ["One-shot Sol, same pairs:", "", tables["confusion_one_shot.csv"].to_markdown(), ""]
    md += ["## 2. Agreement with Sol's holdout grades (alternative check)", "",
           sol_row.round(1).to_markdown(index=False), "",
           "## 3. The filter on B3's lists, against the reviewers", "", counts.round(1).to_markdown(index=False), ""]
    if val is not None:
        md += ["## 4. Valuation (similarity-weighted EV/EBITDA, median abs % error, 95% bootstrap)", "",
               val.round(1).to_markdown(), ""]
    else:
        md += [f"## 4. Valuation", "", f"Skipped: {n_targets} targets (needs {MIN_TARGETS_FOR_VALUATION}+).", ""]
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return {"human": human, "counts": counts, "valuation": val}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    evaluate(ap.parse_args(argv).run)


if __name__ == "__main__":
    main()
