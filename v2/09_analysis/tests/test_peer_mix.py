"""peer_mix.py: failing-question patterns, the per-group mix table, and the tables on the pinned v3 labels."""

import pandas as pd
import pytest

import peer_mix as pm


def test_pattern():
    assert pm.pattern(True, True, True, True) is None                      # direct
    assert pm.pattern(False, False, True, True) is None                    # not a peer
    assert pm.pattern(None, True, True, True) is None                      # unanswered
    assert pm.pattern(False, True, True, True) == "product no, customers yes"
    assert pm.pattern(True, False, False, False) == "product yes, customers no"
    assert pm.pattern(True, True, False, True) == "product+customers yes, revenue model no"
    assert pm.pattern(True, True, True, False) == "product+customers yes, chain step no"
    assert pm.pattern(True, True, False, False) == "product+customers yes, revenue model and chain step no"


def test_sic_division():
    assert pm.sic_division("0700") == "A agriculture"
    assert pm.sic_division("1731") == "C construction"
    assert pm.sic_division("6022") == "H finance, insurance, real estate"


def test_mix_table():
    pairs = pd.DataFrame({"target_id": ["A", "A", "A", "B", "B", "C"],
                          "comp_id": ["a1", "a2", "a3", "b1", "b2", "c1"],
                          "grade": [2, 1, 0, 1, 0, 0], "group": ["x", "x", "x", "x", "x", "y"]})
    t = pm.mix_table(pairs, "group").set_index("group")
    assert t.loc["x", "targets"] == 2 and t.loc["x", "labelled_pairs"] == 5 and bool(t.loc["x", "small_group"])
    assert t.loc["x", "direct_per_target"] == pytest.approx(0.5)
    assert t.loc["x", "adjacent_per_target"] == pytest.approx(1.0)
    assert t.loc["x", "targets_ge1_direct"] == pytest.approx(0.5)
    assert t.loc["x", "targets_0_direct_ge1_adjacent"] == pytest.approx(0.5)
    assert t.loc["y", "targets_no_peer"] == pytest.approx(1.0)
    assert t.loc["all", "targets"] == 3 and t.loc["all", "direct_share"] == pytest.approx(1 / 6)


def test_adjacent_patterns_sources():
    pairs = pd.DataFrame({"target_id": ["A", "A"], "comp_id": ["a1", "a2"], "grade": [1, 1], "group": ["x", "x"]})
    ans = {"target_id": ["A", "A"], "comp_id": ["a1", "a2"]}
    for r, rows in {"matthew": [(False, True, True, True), (True, True, False, True)],
                    "barbara": [(False, True, True, True), (True, True, True, False)],
                    "terra": [(False, True, False, True), (True, True, True, True)]}.items():
        for i, q in enumerate(pm.QUESTIONS):
            ans[f"{q}_{r}"] = [row[i] for row in rows]
        ans[f"score_{r}"] = [1, 1] if r != "terra" else [1, 2]
    t = pm.adjacent_patterns(pairs, pd.DataFrame(ans))
    t = t[t["group"] == "all"].set_index(["source", "pattern"])["count"]
    assert t["humans_same", "product no, customers yes"] == 1 and t["humans_same", "humans differ"] == 1
    assert t["terra", "product no, customers yes"] == 1 and t["terra", "source not adjacent"] == 1


def test_build_on_pinned_labels():
    tables, meta = pm.build()
    pairs = tables["pairs"]
    assert len(pairs) == 311 and pairs["target_id"].nunique() == 67
    assert not pairs["group"].isna().any() and pairs["sic4"].str.len().eq(4).all()
    t1 = tables["t1_mix_by_group"].set_index("group")
    assert t1.loc["all", "labelled_pairs"] == 311 and t1.drop("all")["targets"].sum() == 67
    assert (t1.drop("all")["targets"] >= pm.MIN_TARGETS).all()
    assert not any("ebitda" in c.lower() for t in tables.values() for c in t.columns)
    keeps = tables["t5_keep_rates"]
    assert (keeps.loc[keeps["group"] == "all", "keep_selector_n"].sum()) == 311
