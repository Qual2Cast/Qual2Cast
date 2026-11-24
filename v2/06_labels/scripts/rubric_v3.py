"""Rubric v3: an overall call first, then four yes/no questions per target-comp pair; the score is derived.

What changed from v2 (v2/06_labels/RUBRIC_V2.md, the record of rounds 3 and earlier) is written up in v2/06_labels/RUBRIC_V3.md:
- an overall call first: "Would you put this company in the target's comp set?" (yes/no, column
  overall_call_<reviewer>), answered before the four questions; it is a second outcome, never part of the score
  (called the "blind question" in drafts before 2026-11-24; renamed because the sheet itself is blind);
- question 2 is tightened (the same buyers, not the same industry or payer);
- an optional "unsure" column per reviewer that lists the questions the reviewer was unsure about (it never
  changes an answer);
- twelve anchor pairs (three per question) are worked examples in the guide; they stay in the sheet, flagged
  is_anchor, and are left out of agreement and scoring.

Score (unchanged from v2): 2 = yes to all four; 1 = yes to product or customers but not all four; 0 = no to both.
Revenue model and chain step can only demote a direct peer to adjacent.

  uv run python v2/06_labels/scripts/rubric_v3.py build-sheet               # writes the blind sheet once
  uv run python v2/06_labels/scripts/rubric_v3.py check <filled sheet>.csv
  uv run python v2/06_labels/scripts/rubric_v3.py scores <filled sheet>.csv <out dir>
  uv run python v2/06_labels/scripts/rubric_v3.py consensus <filled sheet>.csv <out>.csv [--tiebreak terra]

Reviewer names are read from the sheet's columns (same_product_<reviewer>).
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import v2paths as v2  # noqa: E402
v2.setup()

import argparse
import hashlib
import json
from collections.abc import Sequence
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

import rubric_v2 as r2   # 06_labels (rubric v2): parse_answer, derive_score

QUESTIONS = {
    "same_product": "Can a customer of the target buy the same kind of product or service from the comp instead?",
    "same_customers": "Would the target's own customers consider buying this kind of thing from the comp? "
                      "(The same buyers, in the same buying role. Same industry or same payer alone is not yes.)",
    "same_revenue_model": "Does the comp earn money the same way (sells goods, sells a service, subscription, "
                          "commission or fees, insurance premiums, interest)?",
    "same_chain_step": "Does the comp sit at the same step of the chain (makes it, distributes it, sells it to "
                       "the end user, services it)?",
}
OVERALL = "overall_call"
OVERALL_QUESTION = "Would you put this company in the target's comp set?"
SHORT = {"overall": OVERALL, "overall_call": OVERALL, "blind": OVERALL, "product": "same_product", "customers": "same_customers",
         "revenue_model": "same_revenue_model", "revenue": "same_revenue_model", "chain_step": "same_chain_step",
         "chain": "same_chain_step"}
REVIEWERS = ["matthew", "barbara", "riya"]
KEY = ["target_id", "comp_id"]
DESCRIPTION = ["target_ticker", "target_company", "target_sic_industry", "target_website", "target_offering",
               "target_customers", "target_business_scope", "comp_ticker", "comp_company", "comp_sic_industry",
               "comp_website", "comp_offering", "comp_customers"]
SEED = 2026

# Twelve worked examples (RUBRIC_V3.md, "Anchor pairs"): three per question. Rulings are proposed; the team
# confirms them. (target ticker, comp ticker, question, kind, proposed answer)
ANCHORS = [
    ("NVR", "DHI", "same_product", "clear yes", "yes"),
    ("PANL", "HTLD", "same_product", "clear no", "no"),
    ("DGII", "ZBRA", "same_product", "borderline", "no"),
    ("THR", "FLS", "same_customers", "clear yes", "yes"),
    ("JBHT", "TRN", "same_customers", "clear no", "no"),
    ("MD", "CHE", "same_customers", "borderline", "no"),
    ("ED", "AVA", "same_revenue_model", "clear yes", "yes"),
    ("IMKT.A", "BROS", "same_revenue_model", "clear no", "no"),
    ("SHEN", "BOC", "same_revenue_model", "borderline", "no"),
    ("OC", "CSL", "same_chain_step", "clear yes", "yes"),
    ("ACH", "RMD", "same_chain_step", "clear no", "no"),
    ("ABNB", "INN", "same_chain_step", "borderline", "no"),
]


# ---------------------------------------------------------------- columns and parsing

def columns(reviewer: str) -> list[str]:
    """The column set one reviewer fills in, in sheet order."""
    return ([f"{OVERALL}_{reviewer}"] + [f"{q}_{reviewer}" for q in QUESTIONS]
            + [f"unsure_{reviewer}", f"business_graded_{reviewer}", f"notes_{reviewer}"])


def reviewers_in(sheet: pd.DataFrame) -> list[str]:
    return [c[len("same_product_"):] for c in sheet.columns if c.startswith("same_product_")]


parse_answer = r2.parse_answer
derive_score = r2.derive_score


def parse_unsure(value) -> list[str]:
    """The questions a reviewer ticked as unsure: blank -> []; "customers, chain" -> [same_customers,
    same_chain_step]; "all" -> every question. Unknown names raise ValueError."""
    v = "" if value is None or (isinstance(value, float) and np.isnan(value)) else str(value).strip().casefold()
    if not v:
        return []
    if v in ("all", "x", "yes", "y"):
        return [OVERALL, *QUESTIONS]
    out = []
    for part in v.replace(";", ",").replace("/", ",").split(","):
        p = part.strip().replace(" ", "_")
        if not p:
            continue
        name = SHORT.get(p, p if p in QUESTIONS or p == OVERALL else None)
        if name is None:
            raise ValueError(part.strip())
        out.append(name)
    return list(dict.fromkeys(out))


def _is_anchor(sheet: pd.DataFrame) -> pd.Series:
    if "is_anchor" not in sheet.columns:
        return pd.Series(False, index=sheet.index)
    return sheet["is_anchor"].astype(str).str.strip().str.casefold().isin(["1", "true", "yes"])


# ---------------------------------------------------------------- check

def check_sheet(sheet: pd.DataFrame, reviewers: Sequence[str] | None = None) -> pd.DataFrame:
    """Every problem in a filled sheet, one row per (pair, reviewer, problem): an answer that is not yes or no, a
    misspelled unsure entry, a pair with some questions answered and others blank, an overall call missing when the
    four are answered (or the reverse), or a pair not answered yet. Empty when the sheet is complete."""
    reviewers = list(reviewers) if reviewers is not None else reviewers_in(sheet)
    rows = []
    for r in reviewers:
        for _, row in sheet.iterrows():
            answers, bad = {}, []
            for q in [OVERALL, *QUESTIONS]:
                col = f"{q}_{r}"
                try:
                    answers[q] = parse_answer(row.get(col, ""))
                except ValueError as e:
                    bad.append(f"{q} {str(e)!r} is not yes or no")
            try:
                parse_unsure(row.get(f"unsure_{r}", ""))
            except ValueError as e:
                bad.append(f"unsure {str(e)!r} is not a question name (product, customers, revenue_model, "
                           "chain_step, overall)")
            rows.extend((row["pair"], r, b) for b in bad)
            if bad:
                continue
            blank4 = [q for q in QUESTIONS if answers[q] is None]
            if answers[OVERALL] is None and len(blank4) == len(QUESTIONS):
                rows.append((row["pair"], r, "not scored yet"))
                continue
            if blank4:
                rows.append((row["pair"], r, "answer all four questions (blank: " + ", ".join(blank4) + ")"))
            if answers[OVERALL] is None:
                rows.append((row["pair"], r, "overall call blank"))
    return pd.DataFrame(rows, columns=["pair", "reviewer", "problem"])


# ---------------------------------------------------------------- scores

def scores(sheet: pd.DataFrame, reviewers: Sequence[str] | None = None) -> pd.DataFrame:
    """Per pair: is_anchor; per reviewer the overall call and four answers as True/False (None where blank), the
    derived score_<reviewer> (NaN until all four are answered), unsure_<reviewer> (the questions ticked, joined
    with ';') and business_graded_<reviewer>. Invalid answers raise ValueError: run check_sheet first."""
    reviewers = list(reviewers) if reviewers is not None else reviewers_in(sheet)
    out = sheet[["pair", *KEY]].copy()
    out["is_anchor"] = _is_anchor(sheet).to_numpy()
    for r in reviewers:
        parsed = {q: sheet[f"{q}_{r}"].map(parse_answer) for q in QUESTIONS}
        out[f"{OVERALL}_{r}"] = sheet[f"{OVERALL}_{r}"].map(parse_answer) if f"{OVERALL}_{r}" in sheet else None
        for q, col in parsed.items():
            out[f"{q}_{r}"] = col
        complete = pd.concat(parsed.values(), axis=1).notna().all(axis=1)
        score = pd.Series(np.nan, index=sheet.index, dtype=float)
        score[complete] = [derive_score(*(parsed[q][i] for q in QUESTIONS)) for i in sheet.index[complete]]
        out[f"score_{r}"] = score
        if f"unsure_{r}" in sheet:
            out[f"unsure_{r}"] = sheet[f"unsure_{r}"].map(lambda v: ";".join(parse_unsure(v)))
        if f"business_graded_{r}" in sheet:
            out[f"business_graded_{r}"] = sheet[f"business_graded_{r}"]
    return out


def _kappa(x: pd.Series, y: pd.Series, weights: str | None = None) -> float:
    x, y = x.astype(float).to_numpy(), y.astype(float).to_numpy()
    if len(x) == 0:
        return np.nan
    if len(set(x) | set(y)) < 2:
        return 1.0 if (x == y).all() else np.nan   # one category only: kappa undefined unless identical
    return float(cohen_kappa_score(x, y, weights=weights))


def agreement(scored: pd.DataFrame, reviewers: Sequence[str] | None = None,
              include_anchors: bool = False) -> pd.DataFrame:
    """One row per (reviewer pair, item) for the overall call, each of the four questions, peer (score >= 1),
    direct (score 2) and the 0/1/2 score: pairs answered by both, raw agreement, Cohen's kappa (linear weights
    for the score row), each reviewer's yes rate, and how many of those answers either reviewer ticked unsure.
    Read kappa next to the yes rate: when nearly everything is yes, kappa can be low even at high agreement."""
    reviewers = list(reviewers) if reviewers is not None else reviewers_in(scored)
    s = scored if include_anchors else scored[~scored["is_anchor"].astype(bool)]
    rows = []
    for a, b in combinations(reviewers, 2):
        items = {OVERALL: (s[f"{OVERALL}_{a}"], s[f"{OVERALL}_{b}"])}
        items.update({q: (s[f"{q}_{a}"], s[f"{q}_{b}"]) for q in QUESTIONS})
        items["peer"] = (s[f"score_{a}"].ge(1).where(s[f"score_{a}"].notna()),
                         s[f"score_{b}"].ge(1).where(s[f"score_{b}"].notna()))
        items["direct"] = (s[f"score_{a}"].eq(2).where(s[f"score_{a}"].notna()),
                           s[f"score_{b}"].eq(2).where(s[f"score_{b}"].notna()))
        items["score"] = (s[f"score_{a}"], s[f"score_{b}"])
        for item, (x, y) in items.items():
            both = x.notna() & y.notna()
            x, y = x[both], y[both]
            row = {"reviewers": f"{a} vs {b}", "item": item, "pairs": int(both.sum()),
                   "agreement": float((x.astype(float).to_numpy() == y.astype(float).to_numpy()).mean())
                   if both.any() else np.nan,
                   "kappa": _kappa(x, y, "linear" if item == "score" else None)}
            if item != "score":
                row[f"yes_rate_{a}"] = float(x.astype(float).mean()) if both.any() else np.nan
                row[f"yes_rate_{b}"] = float(y.astype(float).mean()) if both.any() else np.nan
            if item in (OVERALL, *QUESTIONS) and f"unsure_{a}" in s and f"unsure_{b}" in s:
                unsure = (s.loc[both, f"unsure_{a}"].fillna("").str.split(";").map(lambda v: item in v)
                          | s.loc[both, f"unsure_{b}"].fillna("").str.split(";").map(lambda v: item in v))
                row["unsure"] = int(unsure.sum())
            rows.append(row)
    return pd.DataFrame(rows)


def overall_vs_derived(scored: pd.DataFrame, reviewers: Sequence[str] | None = None,
                     include_anchors: bool = False) -> pd.DataFrame:
    """Per reviewer: how the overall call lines up with the derived score. Counts of overall-call yes/no by score
    0/1/2, and agreement and kappa of overall-call yes against peer (score >= 1) and against direct (score 2). A low match says
    the formula and the reviewer's own call disagree; RUBRIC_V3.md says how to read it."""
    reviewers = list(reviewers) if reviewers is not None else reviewers_in(scored)
    s = scored if include_anchors else scored[~scored["is_anchor"].astype(bool)]
    rows = []
    for r in reviewers:
        both = s[f"{OVERALL}_{r}"].notna() & s[f"score_{r}"].notna()
        call, score = s.loc[both, f"{OVERALL}_{r}"].astype(bool), s.loc[both, f"score_{r}"]
        row = {"reviewer": r, "pairs": int(both.sum())}
        for sc in (0, 1, 2):
            row[f"score{sc}_call_yes"] = int((call & score.eq(sc)).sum())
            row[f"score{sc}_call_no"] = int((~call & score.eq(sc)).sum())
        for name, target in (("peer", score.ge(1)), ("direct", score.eq(2))):
            row[f"agree_{name}"] = float((call == target).mean()) if both.any() else np.nan
            row[f"kappa_{name}"] = _kappa(call, target)
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- consensus and tie-break

def earned_questions(scored: pd.DataFrame, humans: Sequence[str], model: str,
                     include_anchors: bool = False) -> pd.DataFrame:
    """Whether a model (an LLM judge answering the same sheet as reviewer `model`) has earned the tie-break on each
    question: its mean kappa against each human, on all pairs it and that human both answered, is at least the
    humans' kappa with each other (mean over human pairs). One row per item (overall call + four questions)."""
    s = scored if include_anchors else scored[~scored["is_anchor"].astype(bool)]
    rows = []
    for item in [OVERALL, *QUESTIONS]:
        def k(a, b):
            both = s[f"{item}_{a}"].notna() & s[f"{item}_{b}"].notna()
            return _kappa(s.loc[both, f"{item}_{a}"], s.loc[both, f"{item}_{b}"])
        human = [k(a, b) for a, b in combinations(humans, 2)]
        vs_model = [k(model, h) for h in humans]
        h, m = np.nanmean(human) if human else np.nan, np.nanmean(vs_model) if vs_model else np.nan
        rows.append({"item": item, "human_kappa": h, "model_kappa": m,
                     "earned": bool(np.isfinite(h) and np.isfinite(m) and m >= h)})
    return pd.DataFrame(rows)


def consensus(scored: pd.DataFrame, reviewers: Sequence[str] | None = None, tiebreak: str | None = None,
              tiebreak_items: Sequence[str] | None = None) -> pd.DataFrame:
    """One row per pair: for the overall call and each of the four questions, the agreed answer and where it came
    from: "agreed" (every human who answered gave the same answer, at least two answered), "single" (one human
    answered), "tiebreak:<name>" (humans split and the tie-break reviewer's answer is used; only for
    tiebreak_items, default all) or "disputed" (humans split, no usable tie-break). Then the consensus score
    (derived when all four questions are resolved), n_reviewers, disputed (the questions still open, for the next
    tie-break), tie_broken and single_reviewer flags, and is_anchor. The headline uses pairs that are neither
    tie-broken nor single-reviewer; tie-broken pairs are a sensitivity row."""
    reviewers = [r for r in (list(reviewers) if reviewers is not None else reviewers_in(scored)) if r != tiebreak]
    items = [OVERALL, *QUESTIONS]
    allowed = set(tiebreak_items) if tiebreak_items is not None else set(items)
    out = scored[["pair", *KEY, "is_anchor"]].copy()
    answered = pd.DataFrame({r: scored[[f"{q}_{r}" for q in QUESTIONS]].notna().any(axis=1) for r in reviewers})
    out["n_reviewers"] = answered.sum(axis=1).to_numpy()
    disputed, tie_broken = [[] for _ in range(len(scored))], [False] * len(scored)
    for item in items:
        values, sources = [], []
        for i, (_, row) in enumerate(scored.iterrows()):
            got = [row[f"{item}_{r}"] for r in reviewers if row[f"{item}_{r}"] is not None
                   and not (isinstance(row[f"{item}_{r}"], float) and np.isnan(row[f"{item}_{r}"]))]
            if not got:
                values.append(None); sources.append("")
            elif len(set(got)) == 1:
                values.append(bool(got[0])); sources.append("agreed" if len(got) >= 2 else "single")
            else:
                tb = row.get(f"{item}_{tiebreak}") if tiebreak else None
                if tiebreak and item in allowed and tb is not None and not (isinstance(tb, float) and np.isnan(tb)):
                    values.append(bool(tb)); sources.append(f"tiebreak:{tiebreak}"); tie_broken[i] = True
                else:
                    values.append(None); sources.append("disputed"); disputed[i].append(item)
        out[item], out[f"{item}_source"] = values, sources
    complete = out[list(QUESTIONS)].notna().all(axis=1)
    out["score"] = np.nan
    out.loc[complete, "score"] = [derive_score(*(bool(out.at[i, q]) for q in QUESTIONS)) for i in out.index[complete]]
    out["disputed"] = [";".join(d) for d in disputed]
    out["tie_broken"] = tie_broken
    out["single_reviewer"] = out["n_reviewers"].eq(1)
    return out


# ---------------------------------------------------------------- the blind sheet

def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources() -> dict[str, Path]:
    L = v2.V1A_OUTPUTS / "06_labels"
    return {"workbook_323": L / "barbara_293" / "sonnet_label_b3_kept_30_20261119T030414Z.xlsx",
            "workbook_323_manifest": L / "barbara_293" / "sonnet_label_b3_kept_30_20261119T030414Z.json",
            "round3_v2_sheet": L / "round3" / "round3_sheet_v2.csv",
            "dev_293_pairs": L / "barbara_293" / "review" / "pairs.csv",
            "round2_sheet": L / "round2" / "round2_sonnet_sheet.csv",
            "facets": v2.ROOT / v2.current()["profiles"]["general"]}


def pair_pool() -> pd.DataFrame:
    """The 293 dev pairs (31 round-2 + 262 round-3) plus the 30 extra B3 pairs, one row per (target_id, comp_id),
    with description columns from the 323-row label workbook (gaps filled from the Sonnet facet table) and a
    `batch` column (round 2, round 3, b3_kept_30). No method, rank, similarity, multiple or old grade."""
    import cohorts
    src = sources()
    wb = pd.read_excel(src["workbook_323"], dtype=str)
    dev = cohorts.load("dev_293")[["target_id", "comp_id", "round"]]
    extra = wb[wb["batch"] == "b3_kept_30"][KEY].assign(round="b3_kept_30")
    pool = pd.concat([dev, extra], ignore_index=True).drop_duplicates(KEY).rename(columns={"round": "batch"})
    desc = wb.drop_duplicates(KEY).set_index(KEY)
    pool = pool.join(desc[[c for c in DESCRIPTION if c in desc.columns]], on=KEY)
    facets = pd.read_csv(src["facets"], dtype=str).drop_duplicates("IQ_COMPANY_ID").set_index("IQ_COMPANY_ID")
    for side in ("target", "comp"):
        ids = pool[f"{side}_id"]
        for col, facet in ((f"{side}_offering", "offering_description"), (f"{side}_customers", "customer_segment"),
                           (f"{side}_company", "target_company_name")):
            fill = ids.map(facets[facet]) if facet in facets.columns else None
            if fill is not None:
                pool[col] = pool[col].where(pool[col].notna() & pool[col].astype(str).str.strip().ne(""), fill)
    for c in DESCRIPTION:
        if c not in pool.columns:
            pool[c] = ""
    return pool.fillna("")


def anchor_keys(pool: pd.DataFrame) -> dict[tuple[str, str], tuple[str, str, str]]:
    """(target_id, comp_id) -> (question, kind, proposed answer) for the twelve anchors; every anchor must be in
    the pool exactly once."""
    out = {}
    for t, c, q, kind, ans in ANCHORS:
        hit = pool[(pool["target_ticker"] == t) & (pool["comp_ticker"] == c)]
        if len(hit) != 1:
            raise ValueError(f"anchor {t}-{c}: {len(hit)} rows in the pool")
        out[(hit["target_id"].iloc[0], hit["comp_id"].iloc[0])] = (q, kind, ans)
    return out


def build_sheet(pool: pd.DataFrame, reviewers: Sequence[str] = REVIEWERS, seed: int = SEED) -> pd.DataFrame:
    """The blind sheet: targets in a random order and, within a target, its comps in a random order (so the old
    pair labels' rank order is gone but a reviewer reads one target at a time); new pair ids P001...; is_anchor;
    the description columns; blank column sets per reviewer; target_id and comp_id last."""
    rng = np.random.default_rng(seed)
    targets = pool["target_id"].drop_duplicates().to_numpy()
    rng.shuffle(targets)
    order = {t: i for i, t in enumerate(targets)}
    p = pool.assign(_t=pool["target_id"].map(order), _c=rng.random(len(pool))).sort_values(["_t", "_c"])
    anchors = anchor_keys(pool)
    sheet = pd.DataFrame({"pair": [f"P{i:03d}" for i in range(1, len(p) + 1)],
                          "target_company": p["target_company"].to_numpy(), "comp_company": p["comp_company"].to_numpy(),
                          "is_anchor": [1 if k in anchors else 0 for k in zip(p["target_id"], p["comp_id"])]})
    for r in reviewers:
        for c in columns(r):
            sheet[c] = ""
    for c in RIGHT:
        sheet[c] = p[c].to_numpy()
    sheet["target_id"], sheet["comp_id"] = p["target_id"].to_numpy(), p["comp_id"].to_numpy()
    return sheet


# Column layout (Michael, 2026-11-24): the answer columns hug the left, right after a short pair label, so a
# reviewer types without scrolling; the long descriptions are reading material on the right, target and comp side
# by side. LEFT is frozen in the .xlsx.
LEFT = ["pair", "target_company", "comp_company", "is_anchor"]
RIGHT = ["target_offering", "comp_offering", "target_customers", "comp_customers", "target_sic_industry",
         "comp_sic_industry", "target_business_scope", "target_website", "comp_website", "target_ticker",
         "comp_ticker"]


def reviewer_columns(sheet: pd.DataFrame) -> set[str]:
    return {c for r in reviewers_in(sheet) for c in columns(r) if c in sheet.columns}


def tab_columns(sheet: pd.DataFrame, reviewer: str) -> list[str]:
    """One reviewer's tab: the pair label, that reviewer's columns, then everything else that is not another
    reviewer's (descriptions, ids)."""
    theirs = reviewer_columns(sheet)
    left = [c for c in LEFT if c in sheet.columns]
    mine = [c for c in columns(reviewer) if c in sheet.columns]
    rest = [c for c in sheet.columns if c not in left and c not in theirs]
    return left + mine + rest


# The key printed above the header row of the sheet, so reviewers can check a question's meaning without leaving
# the sheet (Michael, 2026-11-24). Columns: what to fill, the question, what yes means, what no means.
KEY_TITLE = ("RUBRIC V3 KEY. Fill the shaded columns (the ones ending in your name) with yes or no. Answer the overall "
             "call first, then the four questions. Full guide and 12 worked examples: v2/06_labels/RUBRIC_V3.md.")
KEY_NOTE = ("The sheet is blind on purpose: no method, rank, similarity, multiple or earlier grade, and pairs are in "
            "a random order. Don't look these up, and don't look at other reviewers' columns until everyone is done.")
KEY_HEADER = ["your column", "question", "yes means", "no means / notes"]
KEY_ROWS = [
    ["overall_call_<you>", OVERALL_QUESTION,
     "you would use it as a comp for this target (your first impression, from the descriptions, websites and "
     "what you know)",
     "you wouldn't. Answer it before the four questions; it checks the score, never part of it"],
    ["same_product_<you>", QUESTIONS["same_product"],
     "one actual buyer of the target could place the same order with the comp",
     "roofing maker vs HVAC installer: no. Same category but not the same order: no"],
    ["same_customers_<you>", "Would the target's own customers consider buying this kind of thing from the comp?",
     "the same buyers, in the same buying role, could switch between the two",
     "same industry or same payer alone is not yes (hospice vs neonatal physician group: no)"],
    ["same_revenue_model_<you>", QUESTIONS["same_revenue_model"],
     "both sell goods, or both a service, subscription, commissions or fees, premiums, or interest",
     "food maker (goods) vs restaurant (service): no. Judge the comp by its larger part"],
    ["same_chain_step_<you>", QUESTIONS["same_chain_step"],
     "both make it, or both distribute it, sell it to the end user, or service it",
     "a distributor vs the manufacturer it buys from: no"],
    ["unsure_<you>", "Optional: the questions you were unsure about",
     "list them, e.g. customers, chain_step (or all)", "never changes an answer; shows where wording needs work"],
    ["business_graded_<you>", "Which target business you judged", "e.g. whole company, or concrete pumping", ""],
    ["notes_<you>", "Anything else", "e.g. which product line matches", ""],
]
KEY_SCORE = ("Score (computed by the notebook, don't type it): 2 = yes to all four questions; 1 = yes to product or "
             "customers but not all four; 0 = no to both product and customers. is_anchor = 1 marks a worked "
             "example from the guide; it is not scored.")


def key_block(width: int) -> list[list[str]]:
    """The key rows printed above the sheet's header, each padded to `width` cells, then one blank row. Each key
    row is ["", column name, one line: question | YES ... | NO ...]; the line is left unwrapped so it runs across
    the empty cells to its right, which keeps the frozen pair-label columns narrow."""
    def line(name, q, yes, no):
        if name.startswith(("unsure_", "business_graded_", "notes_")):     # free-text columns: no yes/no
            return f"{q}: {yes}" + (f" ({no})" if no else "")
        return f"{q}   |   YES: {yes}   |   NO: {no}"
    lines = [["", name, line(name, q, yes, no)] for name, q, yes, no in KEY_ROWS]
    rows = [[KEY_TITLE], [KEY_NOTE], [], ["", "your column", " | ".join(KEY_HEADER[1:])], *lines, [], [KEY_SCORE], []]
    return [r + [""] * (width - len(r)) for r in rows]


ANSWER_COLUMNS = (OVERALL, *QUESTIONS)


def save_sheet(sheet: pd.DataFrame, csv_path: Path, xlsx_path: Path) -> None:
    """Write the sheet twice, each with the key block above the header row.

    - The .xlsx is what reviewers use (upload it as one Google Sheet): one tab per reviewer, holding the pair label,
      that reviewer's columns right next to it, then the descriptions. The pair label (LEFT) is frozen, answer
      cells are shaded and have yes/no dropdowns, the key uses the reviewer's own column names.
    - The .csv is the combined machine copy (every reviewer's columns, same layout order).
    _read() finds the header row (first cell "pair") and merges the tabs back by pair, so a filled sheet downloaded
    from Google Sheets as .xlsx scores directly."""
    import csv
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    cols = list(sheet.columns)
    key = key_block(len(cols))
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerows(key)
        w.writerow(cols)
        w.writerows(sheet.astype(str).to_numpy().tolist())

    bold, wrap = Font(bold=True), Alignment(wrap_text=True, vertical="top")
    header_fill, answer_fill = PatternFill("solid", fgColor="DDE7F0"), PatternFill("solid", fgColor="FFF8E1")
    widths = {"pair": 7, "target_company": 26, "comp_company": 26, "is_anchor": 9, "notes": 34,
              "business_graded": 18, "unsure": 16, "offering": 60, "customers": 44, "website": 22}
    wb = Workbook()
    wb.remove(wb.active)
    for reviewer in reviewers_in(sheet) or [""]:
        tab_cols = tab_columns(sheet, reviewer) if reviewer else cols
        ws = wb.create_sheet(reviewer or "rubric_v3")
        tab_key = [[cell.replace("<you>", reviewer) if reviewer else cell for cell in row]
                   for row in key_block(len(tab_cols))]
        for row in tab_key:
            ws.append(row)
        header_row = len(tab_key) + 1
        ws.append(tab_cols)
        for values in sheet[tab_cols].astype(str).to_numpy().tolist():
            ws.append(values)
        last = header_row + len(sheet)
        ws.cell(1, 1).font = Font(bold=True, size=12)
        key_header_row = 4
        for r in range(key_header_row, key_header_row + len(KEY_ROWS) + 1):
            ws.cell(r, 2).font = bold
        ws.cell(key_header_row, 3).font = bold
        ws.cell(key_header_row + len(KEY_ROWS) + 2, 1).font = bold
        dv = DataValidation(type="list", formula1='"yes,no"', allow_blank=True, showErrorMessage=True,
                            errorTitle="yes or no", error="Type yes or no (or leave blank).")
        ws.add_data_validation(dv)
        for i, name in enumerate(tab_cols, start=1):
            letter = get_column_letter(i)
            ws.cell(header_row, i).font = bold
            ws.cell(header_row, i).fill = header_fill
            ws.cell(header_row, i).alignment = wrap
            base = name[: -len(reviewer) - 1] if reviewer and name.endswith(f"_{reviewer}") else name
            width = widths.get(base) or next((w for k, w in widths.items() if base.endswith(k)), None)
            if base in (OVERALL, *QUESTIONS):
                width = 13
                dv.add(f"{letter}{header_row + 1}:{letter}{last}")
            if reviewer and name.endswith(f"_{reviewer}"):
                for r in range(header_row + 1, last + 1):
                    ws.cell(r, i).fill = answer_fill
            if base.endswith(("offering", "customers")):
                for r in range(header_row + 1, last + 1):
                    ws.cell(r, i).alignment = wrap
            # column B also holds the key's column names (e.g. same_revenue_model_barbara)
            ws.column_dimensions[letter].width = max(width or 14, 28 if i == 2 else 0)
        ws.freeze_panes = f"{get_column_letter(len([c for c in LEFT if c in tab_cols]) + 1)}1"
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(tab_cols))}{last}"
    wb.save(xlsx_path)


def write_sheet(out_dir: Path, seed: int = SEED) -> Path:
    out_dir = Path(out_dir)
    dest, xlsx, manifest = out_dir / "rubric_v3_sheet.csv", out_dir / "rubric_v3_sheet.xlsx", out_dir / "manifest.json"
    if dest.exists() or xlsx.exists():
        raise SystemExit(f"{dest.name} or {xlsx.name} exists in {out_dir}; the sheet is written once and never "
                         "overwritten (move it to history/ first)")
    pool = pair_pool()
    sheet = build_sheet(pool, seed=seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_sheet(sheet, dest, xlsx)
    anchors = anchor_keys(pool)
    info = {"created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "seed": seed,
            "pairs": len(sheet), "targets": int(sheet["target_id"].nunique()),
            "by_batch": {k: int(v) for k, v in pool["batch"].value_counts().items()},
            "anchors": int(sheet["is_anchor"].sum()), "scored_pairs": int((sheet["is_anchor"] == 0).sum()),
            "reviewers": list(REVIEWERS), "columns_per_reviewer": columns("<reviewer>"),
            "key_rows_above_header": len(key_block(len(sheet.columns))),
            "anchor_pairs": [{"target_id": k[0], "comp_id": k[1], "question": v[0], "kind": v[1],
                              "proposed_answer": v[2]} for k, v in anchors.items()],
            "sheet_sha256": _sha(dest), "xlsx_sha256": _sha(xlsx),
            "sources_sha256": {name: _sha(path) for name, path in sources().items()},
            "note": "blind sheet: no method, rank, similarity, multiple or earlier grade; old pair labels replaced "
                    "(they followed B3 rank order). The key block sits above the header row (first cell 'pair')."}
    manifest.write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"wrote {dest} and {xlsx.name}: {len(sheet)} pairs, {info['targets']} targets, {info['anchors']} anchors")
    return dest


# ---------------------------------------------------------------- CLI

def _read(path: Path) -> pd.DataFrame:
    """A sheet as written by save_sheet or downloaded from Google Sheets: a .csv, or an .xlsx whose tabs (one per
    reviewer) are merged back by pair. With or without the key block: a tab's header is the first row whose
    first cell is "pair"."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        tabs = pd.read_excel(path, header=None, dtype=str, sheet_name=None)
        frames = [_body(raw, f"{path}:{name}") for name, raw in tabs.items()
                  if raw.shape[1] and raw.iloc[:, 0].fillna("").astype(str).str.strip().eq("pair").any()]
        if not frames:
            raise SystemExit(f"{path}: no tab with a header row (a row whose first cell is 'pair')")
        merged = frames[0]
        for f in frames[1:]:
            if set(f["pair"]) != set(merged["pair"]):
                raise SystemExit(f"{path}: the tabs don't hold the same pairs")
            new = [c for c in f.columns if c not in merged.columns]
            merged = merged.merge(f[["pair", *new]], on="pair", how="left", sort=False)
        return merged.fillna("")
    raw = pd.read_csv(path, header=None, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    return _body(raw, str(path))


def _body(raw: pd.DataFrame, where: str) -> pd.DataFrame:
    """The rows under the header row (first cell "pair") of one raw tab or CSV, with that row as column names."""
    first = raw.iloc[:, 0].fillna("").astype(str).str.strip()
    hits = first.index[first.eq("pair")]
    if not len(hits):
        raise SystemExit(f"{where}: no header row (a row whose first cell is 'pair')")
    h = hits[0]
    header = raw.iloc[h].fillna("").astype(str).str.strip()
    body = raw.iloc[h + 1:].copy()
    body.columns = header
    body = body.loc[:, header.ne("").to_numpy()]
    body = body[body["pair"].fillna("").astype(str).str.strip().ne("")]
    return body.reset_index(drop=True).fillna("")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-sheet", help="write the blind rubric v3 sheet once")
    b.add_argument("--out", type=Path, default=v2.out("06_labels") / "rubric_v3")
    k = sub.add_parser("check", help="problems in a filled v3 sheet")
    k.add_argument("sheet", type=Path)
    s = sub.add_parser("scores", help="derived scores, per-question agreement and overall-vs-derived")
    s.add_argument("sheet", type=Path)
    s.add_argument("out", type=Path)
    c = sub.add_parser("consensus", help="agreed answers, disputed questions, optional tie-break")
    c.add_argument("sheet", type=Path)
    c.add_argument("out", type=Path)
    c.add_argument("--tiebreak", help="reviewer name of the tie-break column set (e.g. terra or riya)")
    c.add_argument("--earned-only", action="store_true",
                   help="use the tie-break only on questions where it has earned it (earned_questions)")
    args = ap.parse_args(argv)

    if args.cmd == "build-sheet":
        write_sheet(args.out)
        return
    sheet = _read(args.sheet)
    problems = check_sheet(sheet)
    if args.cmd == "check":
        print(problems.to_string(index=False) if len(problems) else "complete: no problems")
        if len(problems):
            print(problems.groupby("reviewer").size().to_string())
        return
    bad = problems[problems["problem"] != "not scored yet"]
    if len(bad):
        print(bad.to_string(index=False))
        raise SystemExit("fix the answers above first")
    scored = scores(sheet)
    if args.cmd == "scores":
        args.out.mkdir(parents=True, exist_ok=True)
        scored.to_csv(args.out / "scores.csv", index=False, encoding="utf-8-sig")
        agree, bvd = agreement(scored), overall_vs_derived(scored)
        agree.to_csv(args.out / "agreement.csv", index=False)
        bvd.to_csv(args.out / "overall_vs_derived.csv", index=False)
        print(agree.to_string(index=False))
        print(bvd.to_string(index=False))
        return
    humans = [r for r in reviewers_in(sheet) if r != args.tiebreak]
    items = None
    if args.tiebreak and args.earned_only:
        earned = earned_questions(scored, humans, args.tiebreak)
        print(earned.to_string(index=False))
        items = earned.loc[earned["earned"], "item"].tolist()
    cons = consensus(scored, humans, args.tiebreak, items)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cons.to_csv(args.out, index=False, encoding="utf-8-sig")
    agreed = cons["n_reviewers"].ge(2) & cons["disputed"].eq("") & ~cons["tie_broken"] & cons["score"].notna()
    print(f"{len(cons)} pairs; unanswered: {int(cons['n_reviewers'].eq(0).sum())}; "
          f"single reviewer: {int(cons['single_reviewer'].sum())}; agreed on all items: {int(agreed.sum())}; "
          f"tie-broken: {int(cons['tie_broken'].sum())}; disputed: {int(cons['disputed'].ne('').sum())}")


if __name__ == "__main__":
    main()
