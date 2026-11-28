"""Named sets of reviewed target-comp pairs. Every v2 component loads labels from here, by name.

  load(name)  one row per pair: target_id, comp_id, target_ticker, comp_ticker, grade (0/1/2; NaN = not
              graded), peer (1 if grade >= 1, 0 if grade 0, NaN if not graded), then the cohort's own columns.
  table()     one row per cohort: pairs, targets, grade counts, who and which rubric.

Cohorts
  dev_293          Barbara, rounds 2-3 old 0/1/2 form (six reasons, multi-business rule). 293 pairs, 45 targets:
                   31 round-2 + 262 round-3 pairs from the B3 "Sonnet + Fiona sub-sector" lists. One reviewer,
                   not consensus gold. The default cohort (current.toml [labels]).
  round1_36        PCTY and WEN, 36 pairs pooled from v0's four routes; Riya, Barbara and Matthew under the
                   round-1 rubric. grade = the grade at least two of the three gave (32 pairs); NaN otherwise.
  matthew_v2_262   Matthew, rubric v2 (four yes/no questions, score derived): the same 262 round-3 pairs.
  matthew_v3_311   Matthew, rubric v3 (overall call, then the four questions; score derived): the 311 scored pairs of
                   the v3 sheet (dev_293 + 30 extra B3 pairs, less the 12 anchors), 67 targets.
  barbara_v3_311   Barbara, rubric v3, the same 311 pairs.
  v3_agreed        Matthew and Barbara, rubric v3, the same 311 pairs. grade = the score derived from the answers
                   both gave, only where they gave the same answer to all four questions (rubric_v3.py consensus);
                   NaN where any question is disputed (to be tie-broken). overall_call is NaN where they split.
                   Read from the run pinned in current.toml [rubric_v3] scores.
  v3_final         The headline rubric v3 labels (team ruling 2026-11-27): per outcome, the two reviewers' outcome
                   where they reach the same one (direct, peer, overall call), else the LLM judge's (2 of 3;
                   rubric_v3.py final). grade = 2 direct, 1 peer not direct, 0 not a peer. The same 311 pairs.
                   Read from current.toml [rubric_v3] final.
  final_holdout_24 LOCKED. Barbara's direct-peer Yes/No on the 24 pairs whose comp is in the universe (all holdout
                   companies). Yes -> grade 2; No -> NaN (she picked these as candidates; No is not a 0). Loads
                   only with final_check=True, which only 10_final_holdout passes.

Blank grades are never read as 0. Grades come from the seeded files in outputs-local/v1a/06_labels/ (read in place by v2) (and
10_final_holdout/ for the locked cohort); their v1 sources are in outputs-local/v1a/seed_manifest.json.
"""

from __future__ import annotations

import sys as _sys  # v2: shared paths (common/paths.py) put every component's scripts on the path
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import json

import numpy as np
import pandas as pd

L = v2.src("06_labels")   # v2: existing labels are read from outputs-local/v1a (v2 copy wins if made)
COHORTS = {
    "dev_293": ("Barbara", "rounds 2-3 old 0/1/2 form"),
    "round1_36": ("Riya, Barbara, Matthew (majority of 3)", "round 1: 0/1/2, blank = 0 with one of five reasons"),
    "matthew_v2_262": ("Matthew", "rubric v2: four yes/no questions, score derived"),
    "matthew_v3_311": ("Matthew", "rubric v3: overall call + four yes/no questions, score derived"),
    "barbara_v3_311": ("Barbara", "rubric v3: overall call + four yes/no questions, score derived"),
    "v3_agreed": ("Matthew and Barbara (agreed)", "rubric v3: grade only where both answer all four questions alike"),
    "v3_final": ("Matthew and Barbara, LLM judge on split outcomes", "rubric v3: same outcome, split outcomes tie-broken 2 of 3"),
    "final_holdout_24": ("Barbara", "direct-peer Yes/No (Yes = 2; No is not a 0) [locked]"),
}
LOCKED = {"final_holdout_24"}


class LockedCohort(PermissionError):
    pass


def _tickers() -> pd.Series:
    uni = pd.read_csv(v2.path(v2.current()["universe"]["universe"]), dtype=str)
    return uni.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]


def _finish(d: pd.DataFrame) -> pd.DataFrame:
    t = _tickers()
    d = d.copy()
    d["target_id"], d["comp_id"] = d["target_id"].astype(str), d["comp_id"].astype(str)
    d["grade"] = pd.to_numeric(d["grade"], errors="coerce")
    d["peer"] = np.where(d["grade"].isna(), np.nan, (d["grade"] >= 1).astype(float))
    d.insert(2, "target_ticker", d["target_id"].map(t))
    d.insert(3, "comp_ticker", d["comp_id"].map(t))
    front = ["target_id", "comp_id", "target_ticker", "comp_ticker", "grade", "peer"]
    d = d[front + [c for c in d.columns if c not in front]]
    if d.duplicated(["target_id", "comp_id"]).any():
        raise ValueError("duplicate pairs in cohort")
    return d.reset_index(drop=True)


def _v3(file: str) -> pd.DataFrame:
    """One table of the pinned rubric v3 run (current.toml [rubric_v3] scores), anchors left out."""
    d = pd.read_csv(v2.path(v2.current()["rubric_v3"]["scores"]) / file, dtype={"target_id": str, "comp_id": str},
                    encoding="utf-8-sig")
    return d[~d["is_anchor"].astype(bool)]


def load(name: str, final_check: bool = False) -> pd.DataFrame:
    if name not in COHORTS:
        raise KeyError(f"unknown cohort {name!r}; known: {list(COHORTS)}")
    if name in LOCKED and not final_check:
        raise LockedCohort(f"{name} is the locked final holdout; it loads only in 10_final_holdout (final_check=True)")
    if name == "dev_293":
        d = pd.read_csv(v2.src("06_labels", "barbara_293", "review", "pairs.csv"), dtype={"target_id": str, "comp_id": str})
        d = d.rename(columns={"score_barbara": "grade"})[
            ["target_id", "comp_id", "grade", "pair", "rank", "similarity", "reason_if_0_barbara", "notes_barbara"]]
        round2 = pd.read_csv(v2.src("06_labels", "round2", "round2_sonnet_sheet.csv"), dtype=str)
        r2 = set(zip(round2["target_id"], round2["comp_id"]))
        d.insert(3, "round", ["round 2" if k in r2 else "round 3" for k in zip(d["target_id"], d["comp_id"])])
        return _finish(d)
    if name == "round1_36":
        raw = pd.DataFrame(json.loads(v2.src("06_labels", "round1", "reviewer_labels_20261028.json").read_text(encoding="utf-8"))["labels"])
        scores = raw[["score_riya", "score_barbara", "score_matthew"]].apply(pd.to_numeric, errors="coerce")
        def majority(row):
            counts = row.dropna().value_counts()
            return counts.index[0] if len(counts) and counts.iloc[0] >= 2 else np.nan
        d = raw[["target_id", "comp_id"]].assign(grade=scores.apply(majority, axis=1), **scores)
        return _finish(d)
    if name == "matthew_v2_262":
        d = pd.read_csv(v2.src("06_labels", "round3", "round3_scores_v2.csv"), dtype=str, encoding="utf-8-sig")
        keep = [c for c in d.columns if c.endswith("_matthew")]
        d = d[["target_id", "comp_id", *keep]].rename(columns={"score_matthew": "grade"})
        return _finish(d)
    if name in ("matthew_v3_311", "barbara_v3_311"):
        r = name.split("_")[0]
        s = _v3("scores.csv")
        keep = [c for c in s.columns if c.endswith(f"_{r}") and c != f"score_{r}"]
        d = s[["target_id", "comp_id", f"score_{r}", "pair", *keep]].rename(columns={f"score_{r}": "grade"})
        return _finish(d)
    if name == "v3_agreed":
        c = _v3("consensus.csv")
        d = c.drop(columns=["is_anchor"]).rename(columns={"score": "grade"})
        return _finish(d)
    if name == "v3_final":
        f = pd.read_csv(v2.path(v2.current()["rubric_v3"]["final"]) / "final.csv",
                        dtype={"target_id": str, "comp_id": str}, encoding="utf-8-sig")
        d = f[~f["is_anchor"].astype(bool)].drop(columns=["is_anchor"]).rename(columns={"score": "grade"})
        return _finish(d)
    m = pd.read_csv(v2.src("10_final_holdout", "direct_peers_24", "manifest.csv"), dtype=str)
    d = pd.DataFrame({"target_id": m["target_id"], "comp_id": m["comp_id"],
                      "grade": [2 if v == "Yes" else np.nan for v in m["Barbara - If Direct"]],
                      "barbara_if_direct": m["Barbara - If Direct"], "comp_sample": m["comp_sample"]})
    return _finish(d)


def table(include_locked: bool = False) -> pd.DataFrame:
    rows = []
    for name, (who, rubric) in COHORTS.items():
        if name in LOCKED and not include_locked:
            rows.append({"cohort": name, "who": who, "rubric": rubric, "pairs": None, "targets": None})
            continue
        d = load(name, final_check=include_locked)
        g = d["grade"]
        rows.append({"cohort": name, "who": who, "rubric": rubric, "pairs": len(d), "targets": d["target_id"].nunique(),
                     "grade 2": int((g == 2).sum()), "grade 1": int((g == 1).sum()), "grade 0": int((g == 0).sum()),
                     "not graded": int(g.isna().sum())})
    return pd.DataFrame(rows)
