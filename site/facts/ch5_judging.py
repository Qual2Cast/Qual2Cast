"""Facts for Judging comps (judging.qmd). Pattern: see ch2_data.py.

Rubric v3 structure comes from the blind sheet as written (outputs-local/v2/06_labels/rubric_v3/rubric_v3_sheet.csv),
not yet filled. Agreement so far is on the labels that exist (rubric v3 answers are not in yet):
  - Barbara: dev_293, her old 0/1/2 form (v1a/06_labels cohorts.py: barbara_293/review/pairs.csv, score_barbara);
  - Matthew: matthew_v2_262, rubric v2 four yes/no questions with the score derived (round3/round3_scores_v2.csv).
They used different rubrics, so their kappa mixes person and rubric (GRADING_REVIEW.md).

Cohen's kappa here is unweighted: (observed agreement - chance agreement) / (1 - chance agreement), with chance from
each rater's own marginals. Peer = grade 1 or 2. The same numbers come out of sklearn's cohen_kappa_score, which
v2/05_agent_grading/scripts/filter_comparison.py used for agreement.csv and filters.csv (the tests check this).
"""

from __future__ import annotations

import csv

import numpy as np
import pandas as pd

from facts.common import fact, pinned


def _n(x) -> str:
    return f"{int(x):,}"


def _pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%"


def _k(x: float) -> str:
    return f"{x:.2f}".replace("-", "−")


def cohen_kappa(a, b) -> float:
    """Unweighted Cohen's kappa of two equal-length label sequences."""
    a, b = np.asarray(a), np.asarray(b)
    cats = np.union1d(a, b)
    po = float((a == b).mean())
    pe = float(sum((a == c).mean() * (b == c).mean() for c in cats))
    return (po - pe) / (1 - pe)


# ---------------------------------------------------------------- rubric v3 sheet (structure only; not yet filled)
_sheet_path = pinned("rubric_v3_sheet")
with open(_sheet_path, encoding="utf-8-sig", newline="") as fh:
    _header_row = next(i for i, row in enumerate(csv.reader(fh)) if row and row[0] == "pair")   # key rows sit above
_sheet = pd.read_csv(_sheet_path, skiprows=_header_row, dtype=str, encoding="utf-8-sig")
_reviewers = [c.removeprefix("overall_call_") for c in _sheet.columns if c.startswith("overall_call_")]
_questions = [c for c in _sheet.columns if c.endswith(f"_{_reviewers[0]}") and c.startswith(("overall_call_", "same_"))]
_score_questions = [c for c in _questions if c.startswith("same_")]
_anchor = _sheet["is_anchor"].astype(int) == 1

rubric_questions = fact("rubric_questions", len(_questions), str(len(_questions)), source="rubric_v3_sheet")
rubric_score_questions = fact("rubric_score_questions", len(_score_questions), str(len(_score_questions)),
                              source="rubric_v3_sheet")
rubric_pairs = fact("rubric_pairs", len(_sheet), _n(len(_sheet)), source="rubric_v3_sheet")
rubric_targets = fact("rubric_targets", _sheet["target_id"].nunique(), _n(_sheet["target_id"].nunique()),
                      source="rubric_v3_sheet")
rubric_anchors = fact("rubric_anchors", int(_anchor.sum()), _n(_anchor.sum()), source="rubric_v3_sheet")
rubric_scored_pairs = fact("rubric_scored_pairs", int((~_anchor).sum()), _n((~_anchor).sum()), source="rubric_v3_sheet")
rubric_reviewer_sets = fact("rubric_reviewer_sets", len(_reviewers), str(len(_reviewers)), source="rubric_v3_sheet")

# ---------------------------------------------------------------- Barbara (old form) vs Matthew (rubric v2)
_barb = pd.read_csv(pinned("labels_barbara_dev293"), dtype={"target_id": str, "comp_id": str})
_matt = pd.read_csv(pinned("labels_matthew_v2"), dtype={"target_id": str, "comp_id": str}, encoding="utf-8-sig")
_bm = _matt.merge(_barb[["target_id", "comp_id", "score_barbara"]].rename(columns={"score_barbara": "barbara"}),
                  on=["target_id", "comp_id"], how="inner")
_bm = _bm[_bm["barbara"].notna() & _bm["score_matthew"].notna()]
_b, _m = _bm["barbara"].astype(float), _bm["score_matthew"].astype(float)


def _yes(col: pd.Series) -> pd.Series:
    return col.astype(str).str.strip().str.lower().isin(["true", "yes", "1", "1.0"])


bm_pairs = fact("bm_pairs", len(_bm), _n(len(_bm)), source="labels_barbara_dev293+labels_matthew_v2")
bm_peer_agreement = fact("bm_peer_agreement", float(((_b >= 1) == (_m >= 1)).mean()),
                         _pct(((_b >= 1) == (_m >= 1)).mean()), source="labels_barbara_dev293+labels_matthew_v2")
bm_kappa_peer = fact("bm_kappa_peer", cohen_kappa(_b >= 1, _m >= 1), _k(cohen_kappa(_b >= 1, _m >= 1)),
                     source="labels_barbara_dev293+labels_matthew_v2")
bm_kappa_grade = fact("bm_kappa_grade", cohen_kappa(_b, _m), _k(cohen_kappa(_b, _m)),
                      source="labels_barbara_dev293+labels_matthew_v2")

# Matthew's answers on his 262 pairs: yes rates, and the "product no, customers yes" pairs behind most of the gap
_mp, _mc = _yes(_matt["same_product_matthew"]), _yes(_matt["same_customers_matthew"])
matthew_yes_product = fact("matthew_yes_product", float(_mp.mean()), _pct(_mp.mean(), 0), source="labels_matthew_v2")
matthew_yes_customers = fact("matthew_yes_customers", float(_mc.mean()), _pct(_mc.mean(), 0), source="labels_matthew_v2")
_pncy = _bm[~_yes(_bm["same_product_matthew"]) & _yes(_bm["same_customers_matthew"])]
matthew_prodno_custyes = fact("matthew_prodno_custyes", len(_pncy), _n(len(_pncy)), source="labels_matthew_v2")
bm_prodno_custyes_barbara1 = fact("bm_prodno_custyes_barbara1", int((_pncy["barbara"] == 1).sum()),
                                  _n((_pncy["barbara"] == 1).sum()), source="labels_barbara_dev293+labels_matthew_v2")
bm_prodno_custyes_barbara0 = fact("bm_prodno_custyes_barbara0", int((_pncy["barbara"] == 0).sum()),
                                  _n((_pncy["barbara"] == 0).sum()), source="labels_barbara_dev293+labels_matthew_v2")


def tbl_bm_crosstab() -> pd.DataFrame:
    """Matthew's answers (rubric v2) against Barbara's 0/1/2 grades: the table in
    v2/05_agent_grading/GRADING_REVIEW.md ("How much the reviewers agree"), rebuilt from the label files."""
    product, customers = _yes(_bm["same_product_matthew"]), _yes(_bm["same_customers_matthew"])
    rows = np.where(product, "same product: yes",
                    np.where(customers, "product no, customers yes", "product no, customers no"))
    t = pd.crosstab(pd.Series(rows, name="Matthew's answers"), _bm["barbara"].astype(int).to_numpy())
    t = t.reindex(["same product: yes", "product no, customers yes", "product no, customers no"])
    t = t.reindex(columns=[0, 1, 2], fill_value=0)
    t.columns = [f"Barbara {c}" for c in t.columns]
    return t.reset_index()


# ---------------------------------------------------------------- agent grade >= 1 as a peer filter vs each reviewer
# As in filter_comparison.py's filters.csv: every pair counts; "insufficient evidence" counts as not kept.
_v = pd.read_csv(pinned("agent_verdicts"), dtype={"target": str, "comp": str})
_v = _v.rename(columns={"target": "target_id", "comp": "comp_id"})[["target_id", "comp_id", "score"]]


def _filter_scores(labels: pd.DataFrame, grade_col: str) -> dict:
    d = labels.merge(_v, on=["target_id", "comp_id"], how="inner")
    d = d[d[grade_col].notna()]
    kept = pd.to_numeric(d["score"], errors="coerce").fillna(-1) >= 1
    truth = d[grade_col].astype(float) >= 1
    tp = int((kept & truth).sum())
    return {"pairs": len(d), "precision": tp / kept.sum(), "recall": tp / truth.sum(), "kappa": cohen_kappa(truth, kept)}


_ab = _filter_scores(_barb, "score_barbara")
_am = _filter_scores(_matt, "score_matthew")
_src_b = "agent_verdicts+labels_barbara_dev293"
_src_m = "agent_verdicts+labels_matthew_v2"
agent_vs_barbara_precision = fact("agent_vs_barbara_precision", _ab["precision"], _pct(_ab["precision"]), source=_src_b)
agent_vs_barbara_recall = fact("agent_vs_barbara_recall", _ab["recall"], _pct(_ab["recall"]), source=_src_b)
agent_vs_barbara_kappa = fact("agent_vs_barbara_kappa", _ab["kappa"], _k(_ab["kappa"]), source=_src_b)
agent_vs_matthew_precision = fact("agent_vs_matthew_precision", _am["precision"], _pct(_am["precision"]), source=_src_m)
agent_vs_matthew_recall = fact("agent_vs_matthew_recall", _am["recall"], _pct(_am["recall"]), source=_src_m)
agent_vs_matthew_kappa = fact("agent_vs_matthew_kappa", _am["kappa"], _k(_am["kappa"]), source=_src_m)
