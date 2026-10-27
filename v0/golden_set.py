"""
The golden set: target-comp pairs scored by hand, and the metrics that use them.

A route (a way of choosing comps) is a table of ranked (target, comp) pairs.
The pool to label is the union of every route's pairs for the golden-set
targets, so each route is judged on its own picks and on the others'. The
labeler sees the companies, not the rank, the similarity, the LLM's verdict or
the multiples. Labels: 2 = direct competitor (same product, same customers),
1 = adjacent (overlapping product or customers); anything else counts as 0, and
every 0 carries one reason from REASONS.

Metrics, at k = 10 (a list shorter than k is scored on what it returned):
precision@k (the share scored 1 or 2), direct hits@k (the number scored 2) and
NDCG@k (whether the best peers are near the top; the gain is the score itself,
a 2 counts twice a 1, discounted by log2(position + 1) and divided by the best
order of that target's whole labeled pool). A peer no route found is not in
the pool, so these measure ranking, not recall.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

K = 10
REASONS = [
    "Different business model",
    "Different customers",
    "Different scale",
    "Generic wording only",
    "Wrong industry code",
]
_REASON_KEY = {r.casefold(): r for r in REASONS}
SCORE_COLUMNS = ["score", "reason_if_0", "notes"]
KEY = ["target_id", "comp_id"]


def build_pool(routes: Mapping[str, pd.DataFrame], targets: Sequence[str]) -> pd.DataFrame:
    """One row per (target, comp) in any route, for `targets`. Each route table
    has `target`, `comp` and `rank` (1 = best). The result has `target_id`,
    `comp_id` and one rank column per route (NaN where the route did not pick
    the pair)."""
    pool = None
    for name, df in routes.items():
        d = df[df["target"].isin(targets)][["target", "comp", "rank"]]
        d = d.rename(columns={"target": "target_id", "comp": "comp_id", "rank": f"rank: {name}"})
        d = d.drop_duplicates(KEY)
        pool = d if pool is None else pool.merge(d, on=KEY, how="outer")
    return pool.sort_values(KEY).reset_index(drop=True)


def labeler_sheet(pool: pd.DataFrame, shown: Mapping[str, pd.DataFrame], seed: int = 2026) -> pd.DataFrame:
    """The file the labeler fills in: per pair, the target and the comp side by
    side (`shown["target"]` and `shown["comp"]` are tables indexed by company
    id, with the same columns, including `ticker`), in an order that does not follow any route.
    Ids go last, for the join back to the pool."""
    sheet = pool[KEY].copy()
    for side in ("target", "comp"):
        info = shown[side].reindex(sheet[f"{side}_id"]).reset_index(drop=True)
        info.columns = [f"{side}_{c}" for c in info.columns]
        sheet = pd.concat([sheet, info], axis=1)
    rng = np.random.default_rng(seed)
    sheet = sheet.iloc[rng.permutation(len(sheet))]
    sheet = sheet.sort_values("target_id", kind="stable").reset_index(drop=True)
    number = (sheet.groupby("target_id").cumcount() + 1).astype(str).str.zfill(2)
    sheet.insert(0, "pair", sheet["target_ticker"] + "-" + number)
    for c in SCORE_COLUMNS:
        sheet[c] = ""
    first = ["pair"] + [c for c in sheet.columns if c not in KEY + ["pair"] + SCORE_COLUMNS]
    return sheet[first + SCORE_COLUMNS + KEY]


def read_labels(path) -> pd.DataFrame:
    """The labeler's file, every column as text (Excel's BOM and blanks handled)."""
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def _score(value: str) -> float:
    v = str(value).strip()
    if v == "":
        return 0.0
    try:
        x = float(v)
    except ValueError:
        return np.nan
    return x if x in (0.0, 1.0, 2.0) else np.nan


def check_labels(labels: pd.DataFrame, pool: pd.DataFrame) -> pd.DataFrame:
    """Everything wrong with the file, one row per problem (`pair`, `problem`);
    empty when it can be scored. A pair with no score and no reason is one the
    labeler has not reviewed yet, because a blank score counts as 0."""
    problems = []

    def add(pair, text):
        problems.append({"pair": pair, "problem": text})

    have = set(map(tuple, labels[KEY].to_numpy()))
    want = set(map(tuple, pool[KEY].to_numpy()))
    for t, c in sorted(want - have):
        add(f"{t}/{c}", "pair missing from the file")
    for t, c in sorted(have - want):
        add(f"{t}/{c}", "pair not in the pool")
    for _, r in labels[labels.duplicated(KEY, keep=False)].iterrows():
        add(r["pair"], "pair listed twice")
    for _, r in labels.iterrows():
        s, reason = _score(r["score"]), r["reason_if_0"].strip()
        if np.isnan(s):
            add(r["pair"], f"score {r['score']!r} is not 1, 2 or blank")
            continue
        if reason and reason.casefold() not in _REASON_KEY:
            add(r["pair"], f"reason {reason!r} is not one of the five")
        elif s == 0 and not reason:
            add(r["pair"], "not reviewed: a 0 (blank score) needs one reason")
        elif s > 0 and reason:
            add(r["pair"], "reason given but the score is 1 or 2; reasons are for 0s only")
    return pd.DataFrame(problems, columns=["pair", "problem"])


def scores(labels: pd.DataFrame) -> pd.DataFrame:
    """The final score of each pair (blank counts as 0) and its canonical reason."""
    out = labels[["pair", *KEY]].copy()
    out["score"] = labels["score"].map(_score).astype(int)
    out["reason"] = labels["reason_if_0"].str.strip().str.casefold().map(_REASON_KEY).fillna("")
    return out


def precision_at_k(gains: Sequence[float], k: int = K) -> float:
    g = list(gains)[:k]
    return float(np.mean([x > 0 for x in g])) if g else np.nan


def direct_hits_at_k(gains: Sequence[float], k: int = K) -> int:
    return int(sum(x == 2 for x in list(gains)[:k]))


def ndcg_at_k(gains: Sequence[float], pool_gains: Sequence[float], k: int = K) -> float:
    """`gains` in ranked order; `pool_gains` every labeled pair of the target
    (the best possible order is those sorted high to low). NaN if the pool has
    no 1 or 2, since no order is better than another."""
    def dcg(g):
        g = np.asarray(list(g)[:k], dtype=float)
        return float((g / np.log2(np.arange(2, len(g) + 2))).sum())

    ideal = dcg(sorted(pool_gains, reverse=True))
    return dcg(gains) / ideal if ideal > 0 else np.nan


def evaluate(routes: Mapping[str, pd.DataFrame], final: pd.DataFrame, targets: Sequence[str],
             k: int = K) -> pd.DataFrame:
    """One row per (route, target) and a mean over targets per route:
    how many pairs the route listed in its top k, precision@k, direct hits@k
    and NDCG@k."""
    score = final.set_index(KEY)["score"]
    rows = []
    for name, df in routes.items():
        for t in targets:
            ranked = df[df["target"] == t].sort_values("rank").drop_duplicates("comp")
            gains = [score.get((t, c), 0) for c in ranked["comp"]]
            pool_gains = score.xs(t, level="target_id").tolist()
            rows.append({"route": name, "target": t, f"listed in top {k}": min(len(gains), k),
                         f"precision@{k}": precision_at_k(gains, k),
                         f"direct hits@{k}": direct_hits_at_k(gains, k),
                         f"NDCG@{k}": ndcg_at_k(gains, pool_gains, k)})
    per_target = pd.DataFrame(rows)
    mean = per_target.drop(columns="target").groupby("route", sort=False).mean().reset_index().assign(target="mean")
    return pd.concat([per_target, mean], ignore_index=True)
