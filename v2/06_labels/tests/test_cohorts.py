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


def test_rubric_v3_cohorts():
    m, b, a = (cohorts.load(n) for n in ("matthew_v3_311", "barbara_v3_311", "v3_agreed"))
    assert len(m) == len(b) == len(a) == 311 and m["target_id"].nunique() == 67
    assert m["grade"].value_counts().to_dict() == {0: 140, 2: 102, 1: 69}
    assert b["grade"].value_counts().to_dict() == {0: 123, 2: 135, 1: 53}
    assert a["grade"].value_counts().to_dict() == {2: 101, 0: 71, 1: 8} and a["grade"].isna().sum() == 131
    agreed = a["grade"].notna()
    assert (a.loc[agreed, "grade"].to_numpy() == m.loc[agreed, "grade"].to_numpy()).all()   # agreed = both reviewers' score
    assert (a.loc[agreed, "grade"].to_numpy() == b.loc[agreed, "grade"].to_numpy()).all()


def test_final_holdout_is_locked():
    with pytest.raises(cohorts.LockedCohort):
        cohorts.load("final_holdout_24")
    d = cohorts.load("final_holdout_24", final_check=True)
    assert len(d) == 24 and (d["grade"] == 2).sum() == 19 and d["grade"].isna().sum() == 5
    assert (d["peer"] == 0).sum() == 0          # a No is never a 0
