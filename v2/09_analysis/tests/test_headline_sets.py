"""headline_sets.py: the two meanings of "agreed" on the pinned rubric v3 labels, and the common-pair cut."""

import pandas as pd

import cohorts
import headline_sets as hs


def test_common_pairs():
    a = pd.DataFrame({"target_id": ["A", "A", "B"], "comp_id": ["a1", "a2", "b1"], "keep": [True, False, True]})
    b = pd.DataFrame({"target_id": ["A", "B"], "comp_id": ["a2", "b1"], "keep": [True, True]})
    assert sorted(hs.common_pairs([a, b])) == [("A", "a2"), ("B", "b1")]


def test_outcome_sets_on_v3_labels():
    m, b = cohorts.load("matthew_v3_311"), cohorts.load("barbara_v3_311")
    s = hs.outcome_sets(m, b)
    assert len(s["all_four"]["peer"]) == len(s["all_four"]["direct"]) == 180
    assert len(s["same_outcome"]["peer"]) == 244 and len(s["same_outcome"]["direct"]) == 276
    # a pair both call direct has all four questions yes from both, so both sets hold the same direct peers
    d4, ds = s["all_four"]["direct"], s["same_outcome"]["direct"]
    assert int(d4["score"].eq(2).sum()) == int(ds["score"].eq(2).sum()) == 101
    assert int(s["same_outcome"]["peer"]["score"].eq(1).sum()) == 146
    assert len(s["matthew_v3_alone"]["peer"]) == len(s["barbara_v3_alone"]["peer"]) == 311


def test_agent_profile_stacks_extra_run_and_covers_v3_pairs():
    import progress as pr
    a = pr.built_in("agent_ge1")
    assert len(a["keeps"]) == 323 and not a["keeps"].duplicated(["target_id", "comp_id"]).any()
    assert len(a["run_files"]) == 2 and " + " in a["run"]
    m = cohorts.load("matthew_v3_311")
    pairs = set(zip(a["keeps"]["target_id"], a["keeps"]["comp_id"]))
    assert all(p in pairs for p in zip(m["target_id"], m["comp_id"]))
