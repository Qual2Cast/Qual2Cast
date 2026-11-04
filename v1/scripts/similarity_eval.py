"""
Evaluation for the similarity methods (v1, 2026-11-03): the reviewers'
golden set under the agreed rule, Sol's grades as an alternative check, and
the metrics on a comp list. No model calls and no multiples (the valuation
stays in valuation.py).

The rule for the reviewers' scores (agreed 2026-11-03):
  1. Only the three reviewers' scores (Riya, Barbara, Matthew) on the 36
     PCTY/WEN pairs; 2 = direct comp, 1 = adjacent, 0 = not a comp. No Sol or
     Haiku verdict enters.
  2. Main set: a pair's grade is the one at least 2 of the 3 gave. Pairs
     with three different grades are left out ("no majority").
  3. Strict check: the pairs all three graded the same, reported apart.
  4. A comp in a method's list that no reviewer scored is unlabeled, never 0.
  5. Metrics: precision@10 and NDCG@10 (golden_set.py) on the labeled comps
     of the list, with the share of the list that is labeled.
Sol's 0-2 grades (graded_peer_selection.py, gpt-6.1-sol) are an alternative
evaluation on the holdout targets, not used for decisions.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

import golden_set as gs

REVIEWERS = ("riya", "barbara", "matthew")
K = gs.K
# The six reasons for a 0 in the team's shared rubric (the golden-set Sheet, also given to Sol); golden_set.REASONS
# predates "Different industry", which round 1's reviewers already used.
REASONS = ["Different industry", *gs.REASONS]


def reviewer_sets(labels: pd.DataFrame, reviewers: Sequence[str] = REVIEWERS
                  ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """From reviewer labels (`target_id`, `comp_id`, `score_<reviewer>` for
    each of the three `reviewers`; round 1: riya, barbara, matthew; round 2:
    reviewer_a, reviewer_b, reviewer_c): the majority set (the grade at least 2
    of 3 gave), the unanimous set, and the pairs with no majority. Each has
    target, comp, grade (no majority: the three scores instead)."""
    if len(reviewers) != 3:
        raise ValueError("the agreed rule is for three reviewers")
    s = labels[[f"score_{r}" for r in reviewers]].astype(str).apply(lambda c: c.str.strip()).astype(int)
    counts = s.apply(lambda row: row.value_counts(), axis=1).fillna(0)
    top = counts.max(axis=1)
    grade = counts.idxmax(axis=1)
    pairs = labels[gs.KEY].rename(columns={"target_id": "target", "comp_id": "comp"}).reset_index(drop=True)
    pairs = pairs.assign(grade=grade.to_numpy().astype(int), agree=top.to_numpy().astype(int))
    majority = pairs[pairs["agree"] >= 2].drop(columns="agree").reset_index(drop=True)
    unanimous = pairs[pairs["agree"] == 3].drop(columns="agree").reset_index(drop=True)
    split = pd.concat([pairs, s.reset_index(drop=True)], axis=1)
    no_majority = split[split["agree"] < 2].drop(columns=["agree", "grade"]).reset_index(drop=True)
    return majority, unanimous, no_majority


def single_reviewer(labels: pd.DataFrame, reviewer: str) -> pd.DataFrame:
    """One reviewer's grades as target, comp, grade: a robustness view beside
    the majority set, not a replacement for it."""
    return pd.DataFrame({"target": labels["target_id"].to_numpy(), "comp": labels["comp_id"].to_numpy(),
                         "grade": labels[f"score_{reviewer}"].astype(str).str.strip().astype(int).to_numpy()})


def list_metrics(selected: pd.DataFrame, grades: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """Per target that has any graded pair: the comps listed (at most k, in
    `rank` order), how many of them are graded and that share, precision@k
    (share graded 1 or 2) and direct share (graded 2) over the graded ones,
    and NDCG@k on the graded comps in list order (unlabeled ones skipped)
    against the best order of all that target's graded pairs. Also how many
    of the target's graded good comps (1 or 2) and direct comps (2) the list
    contains, out of how many, and how many graded non-comps (0) it lists."""
    g = grades.set_index(["target", "comp"])["grade"]
    rows = []
    for t in grades["target"].unique():
        listed = selected[selected["target"] == t].sort_values("rank").head(k)
        gains = [g[(t, c)] for c in listed["comp"] if (t, c) in g.index]
        tg = grades[grades["target"] == t]
        on_list = tg["comp"].isin(set(listed["comp"]))
        rows.append({"target": t, "listed": len(listed), "labeled": len(gains),
                     "labeled share": len(gains) / len(listed) if len(listed) else np.nan,
                     f"precision@{k}": gs.precision_at_k(gains, k) if gains else np.nan,
                     "direct share": float(np.mean([x == 2 for x in gains])) if gains else np.nan,
                     f"NDCG@{k}": gs.ndcg_at_k(gains, tg["grade"].tolist(), k) if gains else np.nan,
                     "good total": int((tg["grade"] >= 1).sum()), "good listed": int((on_list & (tg["grade"] >= 1)).sum()),
                     "direct total": int((tg["grade"] == 2).sum()), "direct listed": int((on_list & (tg["grade"] == 2)).sum()),
                     "non-comps listed": int((on_list & (tg["grade"] == 0)).sum())})
    return pd.DataFrame(rows)


def rank_matrix(rankings: dict[str, pd.DataFrame], selected: dict[str, pd.DataFrame], reviewed: pd.DataFrame,
                target: str, k: int = K) -> pd.DataFrame:
    """For one target, where each reviewed comp stands under each method: its
    rank among the pool under that method's similarity (`rankings[method]`:
    target, comp, rank) and a mark for the list (`selected[method]`):
    "✓" listed, "+" listed by the top-up, "×" in the top k but dropped by the
    mutual filter, nothing if outside the top k. Rows are the reviewed comps
    (`reviewed`: target, comp, grade), best grade first."""
    rev = reviewed[reviewed["target"] == target]
    order = {"2": 0, "1": 1, "split": 2, "0": 3}
    rev = rev.assign(grade=rev["grade"].astype(str)).sort_values("grade", key=lambda s: s.map(order), kind="stable")
    out = {}
    for name, ranking in rankings.items():
        r = ranking[ranking["target"] == target].set_index("comp")["rank"]
        sel = selected[name]
        sel = sel[sel["target"] == target].set_index("comp")
        cells = []
        for c in rev["comp"]:
            if c not in r.index:
                cells.append("–")
                continue
            if c in sel.index:
                mark = "+" if bool(sel.at[c, "topped_up"]) else "✓"
            else:
                mark = "×" if r[c] <= k else ""
            cells.append(f"{int(r[c])}{mark}")
        out[name] = cells
    return pd.DataFrame(out, index=pd.MultiIndex.from_arrays([rev["comp"].to_numpy(), rev["grade"].to_numpy()],
                                                             names=["comp", "grade"]))


def strict_check(selected: pd.DataFrame, unanimous: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """Per target in the unanimous set: how many of its agreed comps (graded
    1 or 2) and agreed non-comps (graded 0) there are, and how many of each
    are in the method's list."""
    rows = []
    for t, u in unanimous.groupby("target"):
        listed = set(selected[selected["target"] == t].sort_values("rank").head(k)["comp"])
        good, bad = u.loc[u["grade"] >= 1, "comp"], u.loc[u["grade"] == 0, "comp"]
        rows.append({"target": t, "agreed comps": len(good), "agreed comps listed": int(good.isin(listed).sum()),
                     "agreed non-comps": len(bad), "agreed non-comps listed": int(bad.isin(listed).sum())})
    return pd.DataFrame(rows)


def reviewer_sheet(pool: pd.DataFrame, shown: dict[str, pd.DataFrame], reviewers: Sequence[str],
                   seed: int = 2026, prefix: str = "R2") -> pd.DataFrame:
    """A blind labeling sheet for several reviewers: golden_set.labeler_sheet's
    layout (target and comp side by side, shuffled, no rank, method, similarity
    or multiple), with a score / reason_if_0 / notes column set per reviewer.
    Pairs are numbered <ticker>-<prefix>-01, ... so they can't be mistaken for
    round 1's."""
    sheet = gs.labeler_sheet(pool, shown, seed).drop(columns=gs.SCORE_COLUMNS)
    sheet["pair"] = sheet["pair"].str.replace("-", f"-{prefix}-", n=1, regex=False)
    ids = sheet[gs.KEY]
    sheet = sheet.drop(columns=gs.KEY)
    for r in reviewers:
        for c in gs.SCORE_COLUMNS:
            sheet[f"{c}_{r}"] = ""
    return pd.concat([sheet, ids], axis=1)


def check_reviewer_sheet(sheet: pd.DataFrame, reviewers: Sequence[str]) -> pd.DataFrame:
    """Every problem in a filled sheet, one row per (pair, reviewer, problem):
    a score that isn't 0, 1 or 2 (blank = not scored yet), a 0 without one of
    the six REASONS, or a reason on a 1 or 2. Empty when the sheet is complete."""
    reasons = {r.casefold() for r in REASONS}
    rows = []
    for r in reviewers:
        score = sheet[f"score_{r}"].fillna("").astype(str).str.strip()
        reason = sheet[f"reason_if_0_{r}"].fillna("").astype(str).str.strip()
        for pair, s, why in zip(sheet["pair"], score, reason):
            if s == "":
                rows.append((pair, r, "not scored yet"))
            elif s not in {"0", "1", "2"}:
                rows.append((pair, r, f"score {s!r} is not 0, 1 or 2"))
            elif s == "0" and why.casefold() not in reasons:
                rows.append((pair, r, "a 0 needs one of the six reasons"))
            elif s != "0" and why:
                rows.append((pair, r, "a 1 or 2 takes no reason (use notes)"))
    return pd.DataFrame(rows, columns=["pair", "reviewer", "problem"])


def sol_grades(paths: Sequence[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sol's saved grades (`grades.csv`: target, comp, score) from one or more
    runs, as target, comp, grade, run; pairs without a grade (insufficient
    evidence) are left out, and the first run listed wins where runs overlap.
    Also a table per later run: overlapping pairs and exact agreement with the
    runs before it."""
    frames, stats = [], []
    for p in paths:
        d = pd.read_csv(p, dtype={"target": str, "comp": str}).dropna(subset=["score"])
        d = d.assign(grade=d["score"].astype(int), run=str(Path(p).parent.name))[["target", "comp", "grade", "run"]]
        if frames:
            before = pd.concat(frames)
            both = d.merge(before, on=["target", "comp"], suffixes=("", "_before"))
            stats.append({"run": d["run"].iloc[0] if len(d) else "", "graded pairs": len(d), "overlap": len(both),
                          "exact agreement": (both["grade"] == both["grade_before"]).mean() if len(both) else np.nan})
            d = d[~d.set_index(["target", "comp"]).index.isin(before.set_index(["target", "comp"]).index)]
        else:
            stats.append({"run": d["run"].iloc[0] if len(d) else "", "graded pairs": len(d), "overlap": 0,
                          "exact agreement": np.nan})
        frames.append(d)
    return pd.concat(frames, ignore_index=True), pd.DataFrame(stats)
