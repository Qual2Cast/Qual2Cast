"""Improvement ledger (progress.py) on synthetic cohorts: no real labels, no saved runs."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import progress as pr  # noqa: E402


def cohort():
    # target A: 4 pairs (scores 2, 1, 0, 0); target B: 2 pairs (1, 0); target C: 1 pair (2)
    return pd.DataFrame({"target_id": ["A", "A", "A", "A", "B", "B", "C"],
                         "comp_id": ["a1", "a2", "a3", "a4", "b1", "b2", "c1"],
                         "score": [2, 1, 0, 0, 1, 0, 2]})


def keeps(pairs):
    k = cohort()[pr.KEY].assign(keep=False)
    for t, c in pairs:
        k.loc[(k.target_id == t) & (k.comp_id == c), "keep"] = True
    return k


def test_known_precision_recall_kappa():
    # keep a1 (2), a3 (0), b1 (1); C keeps nothing
    m = pr.evaluate(cohort(), keeps([("A", "a1"), ("A", "a3"), ("B", "b1")]), boot=50)
    assert m["kept"] == 3 and m["labelled_pairs"] == 7 and m["targets"] == 3
    assert m["coverage"] == pytest.approx(2 / 3)
    # any peer: A precision 1/2, B 1/1 -> mean 0.75 (C has no kept pairs, left out); recall A 1/2, B 1/1, C 0/1
    assert m["peer_precision_mean"] == pytest.approx(0.75)
    assert m["peer_recall_mean"] == pytest.approx((0.5 + 1 + 0) / 3)
    assert m["peer_precision_pooled"] == pytest.approx(2 / 3)
    assert m["peer_recall_pooled"] == pytest.approx(2 / 4)
    # direct: A 1/2, B 0/1 -> 0.25; recall A 1/1, C 0/1 -> 0.5 (B has no direct peer, left out)
    assert m["direct_precision_mean"] == pytest.approx(0.25)
    assert m["direct_recall_mean"] == pytest.approx(0.5)
    truth = np.array([1, 1, 0, 0, 1, 0, 1])
    keep = np.array([1, 0, 1, 0, 1, 0, 0])
    po = (truth == keep).mean()
    pe = truth.mean() * keep.mean() + (1 - truth.mean()) * (1 - keep.mean())
    assert m["peer_kappa"] == pytest.approx((po - pe) / (1 - pe))
    assert m["peer_precision_mean_lo"] <= m["peer_precision_mean"] <= m["peer_precision_mean_hi"]


def test_unlabelled_pairs_are_ignored_and_missing_keeps_count_as_not_kept():
    k = pd.concat([keeps([("A", "a1")]), pd.DataFrame({"target_id": ["A", "Z"], "comp_id": ["zz", "z1"],
                                                       "keep": [True, True]})])
    m = pr.evaluate(cohort(), k, boot=10)
    assert m["kept"] == 1 and m["labelled_pairs"] == 7          # the two unlabelled kept pairs don't count
    partial = keeps([("A", "a1")]).iloc[:3]                      # file covers only 3 labelled pairs
    m2 = pr.evaluate(cohort(), partial, boot=10)
    assert m2["keeps_cover_pairs"] == 3 and m2["kept"] == 1


def test_targets_filter(tmp_path):
    f = tmp_path / "half.txt"
    f.write_text("A\nC\n", encoding="utf-8")
    m = pr.evaluate(cohort(), keeps([("A", "a1"), ("B", "b1")]), targets=pr.read_targets(f), boot=10)
    assert m["targets"] == 2 and m["labelled_pairs"] == 5 and m["kept"] == 1
    g = tmp_path / "half.csv"
    g.write_text("target_id,note\nB,x\n", encoding="utf-8")
    assert pr.read_targets(g) == ["B"]


def test_append_only_and_duplicate_refusal(tmp_path):
    ledger = tmp_path / "ledger.csv"
    base = {c: "" for c in pr.LEDGER_COLUMNS} | {"run": "r1", "cohort": "c", "split": "all", "profile": "selector",
                                                 "who": "first"}
    assert len(pr.append_rows(ledger, [base])) == 1
    first = ledger.read_text(encoding="utf-8")
    assert len(pr.append_rows(ledger, [base | {"who": "again"}])) == 0       # same run/cohort/split/profile
    assert ledger.read_text(encoding="utf-8") == first                         # nothing rewritten
    assert len(pr.append_rows(ledger, [base | {"who": "forced"}], force=True)) == 1
    assert len(pr.append_rows(ledger, [base | {"run": "r2"}])) == 1
    d = pr.read_ledger(ledger)
    assert d["who"].tolist() == ["first", "forced", "first"] and ledger.read_text(encoding="utf-8").startswith(first)
    assert pr.latest(d)["run"].tolist() == ["r2"]


def test_consensus_cohort_hook(tmp_path):
    f = tmp_path / "consensus.csv"
    pd.DataFrame({
        "pair": ["P1", "P2", "P3", "P4", "P5"], "target_id": ["A", "A", "B", "B", "C"],
        "comp_id": ["a1", "a2", "b1", "b2", "c1"], "is_anchor": [False, False, False, True, False],
        "n_reviewers": [2, 2, 1, 2, 2], "score": [2, 1, 0, 2, ""], "tie_broken": [False, True, False, False, False],
    }).to_csv(f, index=False)
    d, name, note = pr.load_cohort("v3", f)
    assert d[["target_id", "comp_id"]].values.tolist() == [["A", "a1"]]   # single, anchor, tie-broken, no score out
    assert "agreed pairs" in note
    d2, _, note2 = pr.load_cohort("v3", f, include_tiebroken=True)
    assert len(d2) == 2 and "tie-broken" in note2


def test_dev_293_refused():
    with pytest.raises(SystemExit):
        pr.load_cohort("dev_293")


def test_chart_writes_png(tmp_path):
    rows = []
    for i, prof in enumerate(["b3_all", "selector"]):
        m = pr.evaluate(cohort(), keeps([("A", "a1")]), boot=20)
        rows.append({c: "" for c in pr.LEDGER_COLUMNS} | {k: pr._fmt(v) for k, v in m.items()} |
                    {"profile": prof, "cohort": "c", "cohort_note": "synthetic", "split": "all",
                     "entry_utc": f"2026-11-2{i}T00:00:00Z", "change": "test", "run": f"r{i}"})
    pr.append_rows(tmp_path / "ledger.csv", rows)
    png = pr.chart(pr.read_ledger(tmp_path / "ledger.csv"), tmp_path / "p.png")
    assert png.exists() and png.stat().st_size > 1000
