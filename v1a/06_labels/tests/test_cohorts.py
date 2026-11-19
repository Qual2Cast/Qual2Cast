"""cohorts.py: counts of each cohort and the final-holdout lock."""

import pytest

import cohorts


def test_dev_293():
    d = cohorts.load("dev_293")
    assert len(d) == 293 and d["target_id"].nunique() == 45
    assert d["grade"].value_counts().to_dict() == {1: 178, 0: 91, 2: 24}
    assert d["round"].value_counts().to_dict() == {"round 3": 262, "round 2": 31}


def test_round1_majority_and_matthew_v2():
    r1 = cohorts.load("round1_36")
    assert len(r1) == 36 and r1["grade"].notna().sum() == 32
    m = cohorts.load("matthew_v2_262")
    assert len(m) == 262 and m["grade"].value_counts().to_dict() == {1: 124, 0: 78, 2: 60}


def test_final_holdout_is_locked():
    with pytest.raises(cohorts.LockedCohort):
        cohorts.load("final_holdout_24")
    d = cohorts.load("final_holdout_24", final_check=True)
    assert len(d) == 24 and (d["grade"] == 2).sum() == 19 and d["grade"].isna().sum() == 5
    assert (d["peer"] == 0).sum() == 0          # a No is never a 0
