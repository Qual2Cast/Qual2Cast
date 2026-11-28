"""Rubric v3 on synthetic sheets (no real labels)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rubric_v3 as r3  # noqa: E402

Q = list(r3.QUESTIONS)


def sheet(rows, reviewers=("a", "b")):
    """rows: list of dicts {reviewer: (overall_call, p, c, rm, cs, unsure)}; is_anchor optional per row."""
    out = []
    for i, row in enumerate(rows):
        d = {"pair": f"P{i:03d}", "target_id": f"T{i}", "comp_id": f"C{i}", "is_anchor": row.get("anchor", 0)}
        for r in reviewers:
            vals = row.get(r, ("",) * 6)
            for col, v in zip([r3.OVERALL, *Q, "unsure"], vals):
                d[f"{col}_{r}"] = v
            d[f"business_graded_{r}"] = ""
            d[f"notes_{r}"] = ""
        out.append(d)
    return pd.DataFrame(out)


def test_columns_and_reviewers():
    assert r3.columns("x")[0] == "overall_call_x"
    assert r3.columns("x")[1:5] == [f"{q}_x" for q in Q]
    assert r3.reviewers_in(sheet([{}], ("m", "b"))) == ["m", "b"]


def test_score_rule():
    assert r3.derive_score(True, True, True, True) == 2
    assert r3.derive_score(True, True, False, True) == 1      # revenue model only demotes
    assert r3.derive_score(False, True, True, True) == 1      # customers alone: adjacent
    assert r3.derive_score(False, False, True, True) == 0     # product or customers must pass


def test_parse_unsure():
    assert r3.parse_unsure("") == []
    assert r3.parse_unsure("Customers, chain") == ["same_customers", "same_chain_step"]
    assert r3.parse_unsure("all") == ["overall_call", *Q]
    with pytest.raises(ValueError):
        r3.parse_unsure("customerz")


def test_check_sheet_problems():
    s = sheet([
        {"a": ("yes", "yes", "yes", "yes", "yes", ""), "b": ("", "", "", "", "", "")},        # b not scored
        {"a": ("yes", "yes", "", "yes", "yes", ""), "b": ("maybe", "no", "no", "no", "no", "")},  # half; bad
        {"a": ("", "yes", "no", "no", "no", ""), "b": ("no", "no", "no", "no", "no", "prod")},   # overall call blank; bad unsure
    ])
    p = r3.check_sheet(s)
    got = set(zip(p["pair"], p["reviewer"], p["problem"].str.split().str[0]))
    assert ("P000", "b", "not") in got
    assert ("P001", "a", "answer") in got
    assert ("P001", "b", "overall_call") in got
    assert ("P002", "a", "overall") in got
    assert ("P002", "b", "unsure") in got
    assert not any(p["pair"].eq("P000") & p["reviewer"].eq("a"))


def test_scores_and_agreement_exclude_anchors():
    rows = [
        {"a": ("yes", "yes", "yes", "yes", "yes", ""), "b": ("yes", "yes", "yes", "yes", "yes", "")},
        {"a": ("yes", "no", "yes", "yes", "yes", "customers"), "b": ("no", "no", "no", "yes", "yes", "")},
        {"a": ("no", "no", "no", "yes", "no", ""), "b": ("no", "no", "no", "yes", "no", "")},
        {"a": ("yes", "yes", "yes", "no", "yes", ""), "b": ("yes", "yes", "yes", "yes", "yes", "")},
        {"anchor": 1, "a": ("no", "no", "no", "no", "no", ""), "b": ("yes", "yes", "yes", "yes", "yes", "")},
    ]
    sc = r3.scores(sheet(rows))
    assert sc["score_a"].tolist() == [2, 1, 0, 1, 0]
    assert sc["score_b"].tolist() == [2, 0, 0, 2, 2]
    assert sc["unsure_a"].iloc[1] == "same_customers"
    ag = r3.agreement(sc).set_index("item")
    assert ag.loc["same_product", "pairs"] == 4                   # anchor left out
    assert ag.loc["same_customers", "agreement"] == pytest.approx(0.75)
    assert ag.loc["same_customers", "unsure"] == 1
    assert ag.loc["peer", "agreement"] == pytest.approx(0.75)
    assert ag.loc["direct", "agreement"] == pytest.approx(0.75)
    assert ag.loc["same_product", "kappa"] == pytest.approx(1.0)
    assert r3.agreement(sc, include_anchors=True).set_index("item").loc["same_product", "pairs"] == 5


def test_kappa_matches_definition():
    x = pd.Series([1, 1, 0, 0, 1, 0, 1, 1])
    y = pd.Series([1, 0, 0, 0, 1, 1, 1, 1])
    po = (x == y).mean()
    pe = x.mean() * y.mean() + (1 - x.mean()) * (1 - y.mean())
    assert r3._kappa(x, y) == pytest.approx((po - pe) / (1 - pe))


def test_overall_vs_derived():
    rows = [
        {"a": ("yes", "yes", "yes", "yes", "yes", "")},
        {"a": ("yes", "no", "yes", "yes", "yes", "")},
        {"a": ("no", "no", "no", "yes", "yes", "")},
        {"a": ("no", "no", "yes", "yes", "yes", "")},
    ]
    sc = r3.scores(sheet(rows, ("a",)))
    b = r3.overall_vs_derived(sc).iloc[0]
    assert b["pairs"] == 4
    assert b["score2_call_yes"] == 1 and b["score1_call_yes"] == 1 and b["score1_call_no"] == 1
    assert b["agree_peer"] == pytest.approx(0.75)
    assert b["agree_direct"] == pytest.approx(0.75)


def test_consensus_agreed_single_disputed_tiebreak():
    rows = [
        {"a": ("yes", "yes", "yes", "yes", "yes", ""), "b": ("yes", "yes", "yes", "yes", "yes", ""),
         "t": ("", "", "", "", "", "")},
        {"a": ("yes", "no", "yes", "yes", "yes", ""), "b": ("yes", "no", "no", "yes", "yes", ""),
         "t": ("yes", "no", "yes", "yes", "yes", "")},
        {"a": ("yes", "yes", "yes", "yes", "yes", ""), "b": ("", "", "", "", "", ""),
         "t": ("", "", "", "", "", "")},
    ]
    sc = r3.scores(sheet(rows, ("a", "b", "t")))
    c = r3.consensus(sc, ["a", "b"]).set_index("pair")
    assert c.loc["P000", "score"] == 2 and c.loc["P000", "same_product_source"] == "agreed"
    assert c.loc["P001", "disputed"] == "same_customers" and np.isnan(c.loc["P001", "score"])
    assert c.loc["P002", "single_reviewer"] and c.loc["P002", "same_product_source"] == "single"
    t = r3.consensus(sc, ["a", "b"], tiebreak="t").set_index("pair")
    assert t.loc["P001", "same_customers_source"] == "tiebreak:t" and t.loc["P001", "score"] == 1
    assert t.loc["P001", "tie_broken"]
    # tie-break allowed only on items it earned
    e = r3.consensus(sc, ["a", "b"], tiebreak="t", tiebreak_items=["same_product"]).set_index("pair")
    assert e.loc["P001", "same_customers_source"] == "disputed"


def test_final_labels_per_outcome_tiebreak():
    Y = ("yes",) * 5 + ("",)
    rows = [
        # same outcome (direct) everywhere: agreed
        {"a": Y, "b": Y, "t": ("no", "no", "no", "no", "no", "")},
        # both adjacent but on different questions: peer and direct agreed, no tie-break needed
        {"a": ("no", "yes", "no", "yes", "yes", ""), "b": ("no", "no", "yes", "yes", "yes", ""), "t": Y},
        # a direct, b not a peer: split on both outcomes; the judge (adjacent) decides
        {"a": Y, "b": ("no", "no", "no", "yes", "yes", ""), "t": ("yes", "yes", "no", "yes", "yes", "")},
        # a direct, b adjacent: split on direct only; the judge has no answer, so direct stays open
        {"a": Y, "b": ("yes", "yes", "yes", "no", "yes", ""), "t": ("",) * 6},
        # anchor
        {"anchor": 1, "a": Y, "b": Y, "t": Y},
    ]
    sc = r3.scores(sheet(rows, ("a", "b", "t")))
    f = r3.final_labels(sc, ["a", "b"], "t").set_index("pair")
    assert f.loc["P000", "score"] == 2 and f.loc["P000", "direct_source"] == "agreed"
    assert f.loc["P001", "score"] == 1 and not f.loc["P001", "tie_broken_peer"]
    assert f.loc["P002", "direct_source"] == f.loc["P002", "peer_source"] == "tiebreak:t"
    assert f.loc["P002", "score"] == 1 and f.loc["P002", "overall_call_source"] == "tiebreak:t"
    assert f.loc["P002", "overall_call"] is True and f.loc["P001", "overall_call_source"] == "agreed"
    assert f.loc["P003", "direct_source"] == "disputed" and f.loc["P003", "peer_source"] == "agreed"
    assert np.isnan(f.loc["P003", "score"])
    j = r3.judge_vs_agreed(sc, f.reset_index(), "t").set_index("outcome")
    # agreed direct (non-anchor): P000 (yes; judge no), P001 (no; judge yes) -> 0 of 2
    assert j.loc["direct", "agreed_pairs"] == 2 and j.loc["direct", "agreement"] == 0
    assert j.loc["direct", "tie_broken"] == 1 and j.loc["direct", "still_open"] == 1   # P003, judge blank
    # no judge: splits stay open
    n = r3.final_labels(sc, ["a", "b"], None).set_index("pair")
    assert n.loc["P002", "peer_source"] == "disputed"


def test_earned_questions():
    # humans agree half the time on customers; the model matches human a exactly and b as a does
    rows = []
    for a, b in [("yes", "yes"), ("no", "no"), ("yes", "no"), ("no", "yes"), ("yes", "yes"), ("no", "no")]:
        rows.append({"a": ("yes", "yes", a, "yes", "yes", ""), "b": ("yes", "yes", b, "yes", "yes", ""),
                     "m": ("yes", "yes", a, "yes", "yes", "")})
    sc = r3.scores(sheet(rows, ("a", "b", "m")))
    e = r3.earned_questions(sc, ["a", "b"], "m").set_index("item")
    assert bool(e.loc["same_customers", "earned"])
    assert e.loc["same_customers", "model_kappa"] >= e.loc["same_customers", "human_kappa"]


def test_build_sheet_and_anchors():
    pool = pd.DataFrame({
        "target_id": ["T1", "T1", "T2", "T2", "T3"], "comp_id": ["C1", "C2", "C3", "C4", "C5"],
        "target_ticker": ["NVR", "NVR", "X", "X", "Y"], "comp_ticker": ["DHI", "Z", "Q", "R", "S"],
        "batch": ["round 3"] * 5})
    for c in r3.DESCRIPTION:
        if c not in pool:
            pool[c] = "d"
    saved = r3.ANCHORS
    r3.ANCHORS = [("NVR", "DHI", "same_product", "clear yes", "yes")]
    try:
        s1 = r3.build_sheet(pool, ["m"], seed=1)
        s2 = r3.build_sheet(pool, ["m"], seed=1)
    finally:
        r3.ANCHORS = saved
    assert s1.equals(s2)                                          # fixed seed
    assert s1["pair"].tolist() == ["P001", "P002", "P003", "P004", "P005"]
    assert s1["is_anchor"].sum() == 1
    assert s1.loc[s1["is_anchor"] == 1, "comp_ticker"].iloc[0] == "DHI"
    for bad in ("rank", "similarity", "batch", "score", "multiple"):
        assert not any(bad in c for c in s1.columns)
    t = s1["target_id"].tolist()
    assert all(t.index(x) + t.count(x) - 1 == len(t) - 1 - t[::-1].index(x) for x in set(t))   # target grouped
    assert list(s1.columns[-2:]) == ["target_id", "comp_id"]
    assert all(c in s1.columns for c in r3.columns("m"))


def test_key_block_round_trip(tmp_path):
    """The sheet is written with the key above the header (.csv combined; .xlsx one tab per reviewer, own columns
    first); the reader finds the header, merges the tabs by pair and gets every value back."""
    from openpyxl import load_workbook
    s = sheet([{"a": ("yes", "yes", "no", "yes", "yes", "customers"), "b": ("no", "no", "no", "yes", "yes", "")},
               {"anchor": 1}], ("a", "b"))
    s.insert(1, "target_company", ["T co", "T co"])
    s.insert(2, "comp_company", ["C co", "D co"])
    csv_path, xlsx_path = tmp_path / "s.csv", tmp_path / "s.xlsx"
    r3.save_sheet(s, csv_path, xlsx_path)
    assert csv_path.read_text(encoding="utf-8-sig").lstrip('"').startswith("RUBRIC V3 KEY")
    wb = load_workbook(xlsx_path)
    assert wb.sheetnames == ["a", "b"]
    for tab, r in (("a", "a"), ("b", "b")):
        rows = list(wb[tab].iter_rows(values_only=True))
        header = next(row for row in rows if row[0] == "pair")
        assert list(header[:4]) == ["pair", "target_company", "comp_company", "is_anchor"]
        assert list(header[4:12]) == r3.columns(r)                      # own columns hug the left
        assert not any(c and c.endswith("_b" if r == "a" else "_a") for c in header)   # no one else's columns
        assert any(row[1] == f"overall_call_{r}" for row in rows)       # key names the reviewer's own columns
    for p in (csv_path, xlsx_path):
        back = r3._read(p)
        assert set(back.columns) == set(s.columns)
        back = back[list(s.columns)]
        assert back.astype(str).to_numpy().tolist() == s.astype(str).to_numpy().tolist()
        assert r3.scores(back)["score_a"].iloc[0] == 1 and r3.scores(back)["score_b"].iloc[0] == 0
    key_cols = [row[0] for row in r3.KEY_ROWS]
    assert key_cols[0] == "overall_call_<you>" and "same_customers_<you>" in key_cols
