"""Tests for similarity_eval.py: the reviewer rule, list metrics, Sol grades."""

import numpy as np
import pandas as pd
import pytest

import similarity_eval as se


def labels() -> pd.DataFrame:
    return pd.DataFrame({
        "target_id": ["T", "T", "T", "U"], "comp_id": ["A", "B", "C", "D"],
        "score_riya": ["2", "1", "0", "0"], "score_barbara": ["2", "0", "1", "0"],
        "score_matthew": ["2", "0", "2", "0"]})


def test_reviewer_sets_follow_the_rule():
    majority, unanimous, none = se.reviewer_sets(labels())
    assert majority.set_index("comp")["grade"].to_dict() == {"A": 2, "B": 0, "D": 0}
    assert unanimous["comp"].tolist() == ["A", "D"]
    assert none["comp"].tolist() == ["C"] and none["score_riya"].tolist() == [0]


def test_reviewer_sets_take_any_three_names():
    renamed = labels().rename(columns={"score_riya": "score_reviewer_a", "score_barbara": "score_reviewer_b",
                                       "score_matthew": "score_reviewer_c"})
    majority, unanimous, _ = se.reviewer_sets(renamed, ["reviewer_a", "reviewer_b", "reviewer_c"])
    assert majority.set_index("comp")["grade"].to_dict() == {"A": 2, "B": 0, "D": 0}
    assert unanimous["comp"].tolist() == ["A", "D"]


def test_list_metrics_skip_unlabeled():
    grades = pd.DataFrame({"target": ["T"] * 3, "comp": ["A", "B", "C"], "grade": [2, 0, 1]})
    selected = pd.DataFrame({"target": "T", "comp": ["X", "B", "A", "Y"], "rank": [1, 2, 3, 4]})
    m = se.list_metrics(selected, grades).iloc[0]
    assert m["listed"] == 4 and m["labeled"] == 2 and m["labeled share"] == 0.5
    assert m["precision@10"] == 0.5 and m["direct share"] == 0.5
    ideal = 2 + 1 / np.log2(3)
    assert m["NDCG@10"] == pytest.approx((0 + 2 / np.log2(3)) / ideal)
    assert (m["good total"], m["good listed"], m["direct total"], m["direct listed"], m["non-comps listed"]) == (2, 1, 1, 1, 1)
    none = se.list_metrics(selected.assign(target="Z"), grades).iloc[0]
    assert none["listed"] == 0 and np.isnan(none["precision@10"]) and none["good listed"] == 0


def test_single_reviewer_keeps_their_grades():
    g = se.single_reviewer(labels(), "riya")
    assert g.set_index("comp")["grade"].to_dict() == {"A": 2, "B": 1, "C": 0, "D": 0}


def test_rank_matrix_marks_listed_topped_up_and_dropped():
    rankings = {"m": pd.DataFrame({"target": "T", "comp": ["A", "B", "C", "D"], "rank": [1, 2, 3, 15]})}
    selected = {"m": pd.DataFrame({"target": "T", "comp": ["A", "C"], "rank": [1, 3], "topped_up": [False, True]})}
    reviewed = pd.DataFrame({"target": "T", "comp": ["D", "B", "C", "A"], "grade": ["0", "split", "1", 2]})
    m = se.rank_matrix(rankings, selected, reviewed, "T")
    assert m.index.get_level_values("comp").tolist() == ["A", "C", "B", "D"]
    assert m["m"].tolist() == ["1✓", "3+", "2×", "15"]


def test_strict_check_counts():
    _, unanimous, _ = se.reviewer_sets(labels())
    selected = pd.DataFrame({"target": ["T", "U"], "comp": ["A", "D"], "rank": [1, 1]})
    c = se.strict_check(selected, unanimous).set_index("target")
    assert c.loc["T", "agreed comps listed"] == 1 and c.loc["T", "agreed non-comps"] == 0
    assert c.loc["U", "agreed non-comps listed"] == 1


def test_sol_grades_first_run_wins(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    pd.DataFrame({"target": ["T", "T", "T"], "comp": ["A", "B", "C"], "score": [2.0, np.nan, 0.0]}).to_csv(
        tmp_path / "one" / "grades.csv", index=False)
    pd.DataFrame({"target": ["T", "T", "T"], "comp": ["A", "B", "C"], "score": [1.0, 1.0, 0.0]}).to_csv(
        tmp_path / "two" / "grades.csv", index=False)
    grades, stats = se.sol_grades([tmp_path / "one" / "grades.csv", tmp_path / "two" / "grades.csv"])
    assert grades.set_index("comp")["grade"].to_dict() == {"A": 2, "C": 0, "B": 1}
    assert grades.set_index("comp")["run"].to_dict() == {"A": "one", "C": "one", "B": "two"}
    assert stats["overlap"].tolist() == [0, 2] and stats["exact agreement"].iloc[1] == 0.5


def test_reviewer_sheet_is_blind_and_has_a_column_set_per_reviewer():
    pool = pd.DataFrame({"target_id": ["T", "T", "U"], "comp_id": ["A", "B", "A"]})
    shown_all = pd.DataFrame({"ticker": ["TT", "UU", "AA", "BB"], "company": ["T co", "U co", "A co", "B co"]},
                             index=["T", "U", "A", "B"])
    sheet = se.reviewer_sheet(pool, {"target": shown_all, "comp": shown_all}, ["reviewer_a", "reviewer_b"])
    assert sorted(sheet["pair"]) == ["TT-R2-01", "TT-R2-02", "UU-R2-01"]
    assert {"score_reviewer_a", "reason_if_0_reviewer_b", "notes_reviewer_b"} <= set(sheet.columns)
    assert not {"rank", "similarity", "score"} & set(sheet.columns)
    assert list(sheet.columns[-2:]) == ["target_id", "comp_id"]


def test_check_reviewer_sheet_flags_every_problem():
    sheet = pd.DataFrame({"pair": ["P1", "P2", "P3", "P4"],
                          "score_a": ["2", "0", "0", ""], "reason_if_0_a": ["", "Different customers", "", ""],
                          "score_b": ["1", "3", "0", "1"], "reason_if_0_b": ["why", "", "not similar", ""]})
    problems = se.check_reviewer_sheet(sheet, ["a", "b"])
    got = set(map(tuple, problems.to_numpy()))
    assert got == {("P3", "a", "a 0 needs one of the six reasons"), ("P4", "a", "not scored yet"),
                   ("P1", "b", "a 1 or 2 takes no reason (use notes)"), ("P2", "b", "score '3' is not 0, 1 or 2"),
                   ("P3", "b", "a 0 needs one of the six reasons")}
    assert se.check_reviewer_sheet(sheet.iloc[[1]].assign(score_b="1", reason_if_0_b=""), ["a", "b"]).empty


def test_six_reasons_include_different_industry():
    assert "Different industry" in se.REASONS and len(se.REASONS) == 6
    sheet = pd.DataFrame({"pair": ["P1"], "score_a": ["0"], "reason_if_0_a": ["different industry"]})
    assert se.check_reviewer_sheet(sheet, ["a"]).empty
