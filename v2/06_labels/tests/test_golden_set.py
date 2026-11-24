"""Tests for the golden set pool, label checks and ranking metrics (golden_set.py)."""

import numpy as np
import pandas as pd
import pytest

import golden_set as gs


def route(target, comps):
    return pd.DataFrame({"target": target, "comp": comps, "rank": range(1, len(comps) + 1)})


def test_pool_is_the_union_of_routes_for_the_golden_targets_only():
    routes = {"a": pd.concat([route("T", ["x", "y"]), route("U", ["z"])]), "b": route("T", ["y", "w"])}
    pool = gs.build_pool(routes, ["T"])
    assert list(pool["comp_id"]) == ["w", "x", "y"]
    y = pool[pool["comp_id"] == "y"].iloc[0]
    assert (y["rank: a"], y["rank: b"]) == (2, 1)
    assert np.isnan(pool[pool["comp_id"] == "x"].iloc[0]["rank: b"])


def sheet_for(pool):
    shown = {s: pd.DataFrame({"ticker": ["T", "x", "y", "w"], "company": list("TXYW")},
                             index=["T", "x", "y", "w"]) for s in ("target", "comp")}
    return gs.labeler_sheet(pool, shown)


def test_sheet_hides_ranks_and_has_blank_scores():
    pool = gs.build_pool({"a": route("T", ["x", "y", "w"])}, ["T"])
    sheet = sheet_for(pool)
    assert not any("rank" in c for c in sheet.columns)
    assert list(sheet["pair"]) == ["T-01", "T-02", "T-03"]
    assert (sheet[gs.SCORE_COLUMNS] == "").all().all()
    assert sheet.columns[-2:].tolist() == gs.KEY
    assert sheet.equals(sheet_for(pool))   # same order every time


def labels_from(sheet, scores, reasons):
    sheet = sheet.copy()
    sheet["score"], sheet["reason_if_0"] = scores, reasons
    return sheet


def test_check_labels_flags_unreviewed_zeros_and_bad_entries():
    pool = gs.build_pool({"a": route("T", ["x", "y", "w"])}, ["T"])
    sheet = sheet_for(pool)
    ok = labels_from(sheet, ["2", "", "1"], ["", "different customers", ""])
    assert gs.check_labels(ok, pool).empty
    assert gs.scores(ok)["score"].tolist() == [2, 0, 1]
    assert gs.scores(ok)["reason"].tolist() == ["", "Different customers", ""]
    p = gs.check_labels(labels_from(sheet, ["2", "", "3"], ["", "", ""]), pool)
    assert len(p) == 2 and p["problem"].str.contains("not reviewed|not 1, 2").all()
    assert not gs.check_labels(labels_from(sheet, ["0", "2", "1"], ["Generic", "", ""]), pool).empty
    assert not gs.check_labels(labels_from(sheet, ["1", "2", "1"], ["Different scale", "", ""]), pool).empty
    assert gs.check_labels(labels_from(sheet, ["2.0", "1", "2"], ["", "", ""]), pool).empty   # Excel's 2.0


def test_check_labels_flags_missing_and_extra_pairs():
    pool = gs.build_pool({"a": route("T", ["x", "y"])}, ["T"])
    sheet = labels_from(sheet_for(pool), ["1", "1"], ["", ""])
    assert "pair missing" in gs.check_labels(sheet.iloc[:1], pool)["problem"].iloc[0]
    other = gs.build_pool({"a": route("T", ["x", "w"])}, ["T"])
    assert gs.check_labels(sheet, other)["problem"].str.contains("not in the pool|missing").all()


def test_precision_hits_and_ndcg():
    assert gs.precision_at_k([2, 0, 1, 0]) == 0.5
    assert gs.precision_at_k([2, 0, 1, 0, 0], k=2) == 0.5
    assert np.isnan(gs.precision_at_k([]))
    assert gs.direct_hits_at_k([2, 1, 2, 0], k=2) == 1
    pool = [2, 2, 1, 0, 0]
    assert gs.ndcg_at_k([2, 2, 1], pool) == pytest.approx(1.0)
    worse = gs.ndcg_at_k([0, 1, 2], pool)
    assert 0 < worse < 1
    by_hand = (0 + 1 / np.log2(3) + 2 / np.log2(4)) / (2 + 2 / np.log2(3) + 1 / np.log2(4))
    assert worse == pytest.approx(by_hand)
    assert np.isnan(gs.ndcg_at_k([0, 0], [0, 0, 0]))


def test_evaluate_scores_routes_against_the_whole_pool():
    routes = {"good": route("T", ["x", "y"]), "bad": route("T", ["w", "y"])}
    pool = gs.build_pool(routes, ["T"])
    final = pool[gs.KEY].assign(score=pool["comp_id"].map({"x": 2, "y": 1, "w": 0}))
    r = gs.evaluate(routes, final, ["T"]).set_index(["route", "target"])
    assert r.loc[("good", "T"), "precision@10"] == 1.0
    assert r.loc[("good", "T"), "direct hits@10"] == 1
    assert r.loc[("good", "T"), "NDCG@10"] == pytest.approx(1.0)
    assert r.loc[("bad", "T"), "precision@10"] == 0.5
    assert r.loc[("bad", "T"), "NDCG@10"] < 1
    assert ("good", "mean") in r.index
