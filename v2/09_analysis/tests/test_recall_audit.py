"""EXPERIMENTAL recall audit (recall_audit.py): candidate builder, target table and draw on synthetic data.
No saved runs, no model calls."""

import pandas as pd

import recall_audit as ra


def ranking():
    # targets A and B over a pool of A, B, c1..c25; rank 1 = most similar; the target itself is in its own ranking
    rows = []
    for t in ("A", "B"):
        comps = [x for x in ["A", "B"] + [f"c{i}" for i in range(1, 26)]]
        for k, c in enumerate(comps, 1):
            rows.append({"target": t, "rank": k, "comp": c, "similarity": 1 - k / 100})
    return pd.DataFrame(rows)


def test_candidates_skip_labelled_and_target_keep_rank_order():
    r = ranking()
    labelled = {("A", "B"), ("A", "c1"), ("A", "c3"), ("B", "c2")}
    selected = labelled | {("A", "c4")}                     # c4 selected but not on the sheet
    c = ra.audit_candidates(r, labelled, ["B", "A"], selected, per_target=15)
    keys = set(zip(c["target_id"], c["comp_id"]))
    assert not keys & labelled                               # no overlap with labelled pairs
    assert not (c["target_id"] == c["comp_id"]).any()        # target excluded
    assert c.groupby("target_id").size().to_dict() == {"A": 15, "B": 15}
    assert c["target_id"].drop_duplicates().tolist() == ["B", "A"]      # targets in the given order
    for _, d in c.groupby("target_id"):
        assert d["rank"].is_monotonic_increasing
        assert d["audit_order"].tolist() == list(range(1, 16))
    a = c[c["target_id"] == "A"]
    # A: rank 1 is A itself, 2 B (labelled), 3 c1 (labelled), 4 c2, 5 c3 (labelled), 6 c4 ...
    assert a["comp_id"].tolist()[:3] == ["c2", "c4", "c5"]
    assert a.set_index("comp_id").at["c4", "band"] == "selected top-10, not on sheet"
    assert a.set_index("comp_id").at["c2", "band"] == "unselected top-10"
    # unlabelled top-10 rows come before rank 11+, and the bands follow rank
    assert (a["rank"] <= 10).tolist() == sorted((a["rank"] <= 10).tolist(), reverse=True)
    assert set(a.loc[a["rank"] > 20, "band"]) <= {"21+"}


def test_band():
    assert ra.band(3, False) == "unselected top-10"
    assert ra.band(10, True) == "selected top-10, not on sheet"
    assert [ra.band(k, False) for k in (11, 15, 16, 20, 21, 300)] == ["11-15", "11-15", "16-20", "16-20", "21+", "21+"]


def test_cap_per_target():
    c = ra.audit_candidates(ranking(), set(), ["A"], set(), per_target=4)
    assert c["comp_id"].tolist() == ["B", "c1", "c2", "c3"]


def test_target_table_pools_and_draw():
    labels = pd.DataFrame({"target_id": ["T1", "T1", "T2", "T2", "T3", "T4", "T4"],
                           "comp_id": ["a", "b", "a", "b", "a", "a", "b"],
                           "target_ticker": ["T1", "T1", "T2", "T2", "T3", "T4", "T4"],
                           "grade": [0, 1, 2, 2, 0, 0, 1]})
    sheet = set(zip(labels["target_id"], labels["comp_id"])) | {("T4", "x")}
    selected = pd.DataFrame({"target_id": ["T1", "T1", "T2", "T2", "T3", "T3", "T4", "T4", "T4"],
                             "comp_id": ["a", "b", "a", "b", "a", "z", "a", "b", "x"]})
    anchors = pd.DataFrame({"target_id": ["T4"], "comp_id": ["x"], "comp_ticker": ["X"], "score": [2.0]})
    t = ra.target_table(labels, anchors, selected, sheet).set_index("target_id")
    assert t.at["T1", "pool"].startswith("thin")
    assert t.at["T2", "pool"].startswith("control")
    assert t.at["T3", "pool"] == "" and not t.at["T3", "full_list_on_sheet"]     # z not on the sheet
    assert t.at["T4", "pool"] == "" and t.at["T4", "anchor_direct"] == 1        # anchor scored direct
    d = ra.draw(t.reset_index(), seed=1, n_thin=1, n_control=1).set_index("target_id")
    assert d.at["T1", "group"] == "thin" and d.at["T2", "group"] == "control"
    assert d.loc[["T1", "T2"], "draw_order"].tolist() == [1, 2]
