"""Rubric v2: four yes/no questions per target-comp pair, score derived from the answers.

Rounds 1 and 2 asked each reviewer for one 0/1/2 judgment plus a reason on every 0.
A 1 never said which half (product or customers) matched, and "same product" and
"same customers" were never defined, so reviewers split on definitions, not facts.
From round 3 the reviewer answers four yes/no questions (QUESTIONS) and the score
is computed: 2 = yes to all four, 1 = yes to product or customers but not all four,
0 = no to both product and customers. The guide is v1/RUBRIC_V2.md.

  uv run python v1/scripts/rubric_v2.py convert <old sheet>.csv <new sheet>.csv   # never overwrites
  uv run python v1/scripts/rubric_v2.py check <filled sheet>.csv
  uv run python v1/scripts/rubric_v2.py scores <filled sheet>.csv <scores>.csv

Reviewer names are read from the sheet's columns (same_product_<reviewer>).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from itertools import combinations
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import golden_set as gs  # noqa: E402

QUESTIONS = {
    "same_product": "Can a customer of the target buy the same kind of product or service from the comp instead?",
    "same_customers": "Does the comp sell to the same type of buyer (consumer or business; for business "
                      "buyers, the buyer's industry)?",
    "same_revenue_model": "Does the comp earn money the same way (sells goods, sells a service, subscription, "
                          "commission or fees, insurance premiums, interest)?",
    "same_chain_step": "Does the comp sit at the same step of the chain (makes it, distributes it, sells it to "
                       "the end user, services it)?",
}
EXTRA = ["business_graded", "notes"]
ANSWERS = {"yes": True, "y": True, "true": True, "no": False, "n": False, "false": False}
KEY = gs.KEY
OLD = gs.SCORE_COLUMNS  # score, reason_if_0, notes


def columns(reviewer: str) -> list[str]:
    """The column set one reviewer fills in."""
    return [f"{q}_{reviewer}" for q in QUESTIONS] + [f"{c}_{reviewer}" for c in EXTRA]


def reviewers_in(sheet: pd.DataFrame) -> list[str]:
    """Reviewer names, from the sheet's same_product_<reviewer> columns, in sheet order."""
    return [c[len("same_product_"):] for c in sheet.columns if c.startswith("same_product_")]


def derive_score(same_product: bool, same_customers: bool, same_revenue_model: bool, same_chain_step: bool) -> int:
    """2 = yes to all four; 1 = yes to product or customers but not all four; 0 = no to both."""
    if same_product and same_customers and same_revenue_model and same_chain_step:
        return 2
    if same_product or same_customers:
        return 1
    return 0


def parse_answer(value) -> bool | None:
    """yes/no (any capitals; y, n, true, false accepted) -> bool; blank -> None; anything else -> ValueError."""
    v = "" if value is None or (isinstance(value, float) and np.isnan(value)) else str(value).strip().casefold()
    if v == "":
        return None
    if v not in ANSWERS:
        raise ValueError(v)
    return ANSWERS[v]


def check_sheet(sheet: pd.DataFrame, reviewers: Sequence[str] | None = None) -> pd.DataFrame:
    """Every problem in a filled sheet, one row per (pair, reviewer, problem): all four answers
    blank (not scored yet), some blank (answer all four), or an answer that is not yes or no.
    Empty when the sheet is complete."""
    reviewers = list(reviewers) if reviewers is not None else reviewers_in(sheet)
    rows = []
    for r in reviewers:
        for _, row in sheet.iterrows():
            answers, bad = {}, []
            for q in QUESTIONS:
                try:
                    answers[q] = parse_answer(row[f"{q}_{r}"])
                except ValueError as e:
                    bad.append(f"{q} {str(e)!r} is not yes or no")
            rows.extend((row["pair"], r, b) for b in bad)
            blank = [q for q, a in answers.items() if a is None and q not in {b.split()[0] for b in bad}]
            if bad:
                continue
            if len(blank) == len(QUESTIONS):
                rows.append((row["pair"], r, "not scored yet"))
            elif blank:
                rows.append((row["pair"], r, "answer all four questions (blank: " + ", ".join(blank) + ")"))
    return pd.DataFrame(rows, columns=["pair", "reviewer", "problem"])


def scores(sheet: pd.DataFrame, reviewers: Sequence[str] | None = None) -> pd.DataFrame:
    """Per pair: the four answers of each reviewer as True/False (None where blank) and the derived
    score_<reviewer> (NaN until all four are answered). Invalid answers raise ValueError; run
    check_sheet first."""
    reviewers = list(reviewers) if reviewers is not None else reviewers_in(sheet)
    out = sheet[["pair", *KEY]].copy()
    for r in reviewers:
        parsed = {q: sheet[f"{q}_{r}"].map(parse_answer) for q in QUESTIONS}
        for q, col in parsed.items():
            out[f"{q}_{r}"] = col
        complete = pd.concat(parsed.values(), axis=1).notna().all(axis=1)
        score = pd.Series(np.nan, index=sheet.index, dtype=float)
        score[complete] = [derive_score(*(parsed[q][i] for q in QUESTIONS)) for i in sheet.index[complete]]
        out[f"score_{r}"] = score
        if f"business_graded_{r}" in sheet.columns:
            out[f"business_graded_{r}"] = sheet[f"business_graded_{r}"]
    return out


def agreement(scored: pd.DataFrame, reviewers: Sequence[str] | None = None) -> pd.DataFrame:
    """For each pair of reviewers: the share of pairs (answered by both) where they agree, per
    question and on the derived score, with the number of pairs compared."""
    reviewers = list(reviewers) if reviewers is not None else reviewers_in(scored)
    rows = []
    for a, b in combinations(reviewers, 2):
        both = scored[f"score_{a}"].notna() & scored[f"score_{b}"].notna()
        row = {"reviewers": f"{a} vs {b}", "pairs": int(both.sum())}
        for q in list(QUESTIONS) + ["score"]:
            x, y = scored.loc[both, f"{q}_{a}"], scored.loc[both, f"{q}_{b}"]
            row[q] = float((x.to_numpy() == y.to_numpy()).mean()) if both.any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def convert_sheet(old: pd.DataFrame, reviewers: Sequence[str] | None = None) -> pd.DataFrame:
    """A round-2-layout sheet (score / reason_if_0 / notes per reviewer) in the v2 layout: the
    pair and company columns unchanged, then per reviewer the four blank question columns,
    business_graded and the old notes, then the two id columns last. Old scores and reasons, where
    any are filled, are kept as old_score_<reviewer> / old_reason_<reviewer> for reference; they are
    not translated into answers (a 1 never said which half matched)."""
    if reviewers is None:
        reviewers = [c[len("score_"):] for c in old.columns if c.startswith("score_")]
    old = old.fillna("")
    drop = [f"{c}_{r}" for r in reviewers for c in OLD]
    front = [c for c in old.columns if c not in drop + KEY]
    new = old[front].copy()
    for r in reviewers:
        for c in columns(r):
            new[c] = old[f"notes_{r}"] if c == f"notes_{r}" and f"notes_{r}" in old.columns else ""
        score = old.get(f"score_{r}", pd.Series("", index=old.index)).astype(str).str.strip()
        if score.ne("").any():
            new[f"old_score_{r}"] = score
            new[f"old_reason_{r}"] = old.get(f"reason_if_0_{r}", pd.Series("", index=old.index))
    return pd.concat([new, old[KEY]], axis=1)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="old-layout sheet -> v2 layout (never overwrites)")
    c.add_argument("src", type=Path)
    c.add_argument("dst", type=Path)
    c.add_argument("--reviewers", nargs="*", help="default: read from score_<reviewer> columns")
    k = sub.add_parser("check", help="problems in a filled v2 sheet")
    k.add_argument("sheet", type=Path)
    s = sub.add_parser("scores", help="derived scores and reviewer agreement from a filled v2 sheet")
    s.add_argument("sheet", type=Path)
    s.add_argument("dst", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "convert":
        if args.dst.exists():
            print(f"kept {args.dst} (never overwritten)")
            return
        new = convert_sheet(gs.read_labels(args.src), args.reviewers)
        args.dst.parent.mkdir(parents=True, exist_ok=True)
        new.to_csv(args.dst, index=False, encoding="utf-8-sig")
        print(f"wrote {args.dst}: {len(new)} pairs, reviewers {reviewers_in(new)}")
    elif args.cmd == "check":
        problems = check_sheet(gs.read_labels(args.sheet))
        print(problems.to_string(index=False) if len(problems) else "complete: no problems")
        print(problems.groupby(["reviewer"]).size().to_string() if len(problems) else "")
    else:
        sheet = gs.read_labels(args.sheet)
        problems = check_sheet(sheet)
        bad = problems[problems["problem"] != "not scored yet"]
        if len(bad):
            print(bad.to_string(index=False))
            raise SystemExit("fix the answers above first")
        scored = scores(sheet)
        args.dst.parent.mkdir(parents=True, exist_ok=True)
        scored.to_csv(args.dst, index=False, encoding="utf-8-sig")
        for r in reviewers_in(sheet):
            counts = scored[f"score_{r}"].value_counts().sort_index()
            print(f"{r}: " + ", ".join(f"{int(k)}={int(v)}" for k, v in counts.items())
                  + f", unscored={int(scored[f'score_{r}'].isna().sum())}")
        print(agreement(scored).to_string(index=False))


if __name__ == "__main__":
    main()
