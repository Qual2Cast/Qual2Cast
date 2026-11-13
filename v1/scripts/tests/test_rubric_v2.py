"""Tests for the yes/no rubric (rubric_v2.py): derived score, sheet checks, conversion, agreement."""

import numpy as np
import pandas as pd
import pytest

import rubric_v2 as rv


@pytest.mark.parametrize("answers, score", [
    ((True, True, True, True), 2),
    ((True, True, True, False), 1),     # all but one: adjacent, not direct
    ((True, False, False, False), 1),   # product only
    ((False, True, True, True), 1),     # customers only
    ((False, False, True, True), 0),    # revenue model and chain step alone do not make a peer
    ((False, False, False, False), 0),
])
def test_score_is_derived_from_the_four_answers(answers, score):
    assert rv.derive_score(*answers) == score


def test_answers_accept_yes_no_in_any_case_and_blank():
    assert rv.parse_answer(" Yes ") is True
    assert rv.parse_answer("n") is False
    assert rv.parse_answer("") is None
    assert rv.parse_answer(np.nan) is None
    with pytest.raises(ValueError):
        rv.parse_answer("maybe")


def old_sheet():
    return pd.DataFrame({
        "pair": ["T-R3-01", "T-R3-02", "T-R3-03"],
        "target_ticker": ["T"] * 3, "comp_ticker": ["a", "b", "c"],
        "score_matthew": ["", "", ""], "reason_if_0_matthew": ["", "", ""], "notes_matthew": ["", "", ""],
        "score_barbara": ["", "", ""], "reason_if_0_barbara": ["", "", ""], "notes_barbara": ["", "", ""],
        "target_id": ["IQ1"] * 3, "comp_id": ["IQ2", "IQ3", "IQ4"],
    })


def test_convert_replaces_score_columns_with_the_four_questions_and_keeps_ids_last():
    new = rv.convert_sheet(old_sheet())
    assert rv.reviewers_in(new) == ["matthew", "barbara"]
    assert not any(c.startswith(("score_", "reason_if_0_")) for c in new.columns)
    for r in ("matthew", "barbara"):
        assert all(c in new.columns for c in rv.columns(r))
    assert new.columns[-2:].tolist() == rv.KEY
    assert list(new["pair"]) == ["T-R3-01", "T-R3-02", "T-R3-03"]
    assert (new[[c for c in new.columns if c.startswith("same_")]] == "").all().all()


def test_convert_keeps_old_scores_for_reference_but_does_not_translate_them():
    old = old_sheet()
    old.loc[0, ["score_barbara", "reason_if_0_barbara"]] = ["0", "Different customers"]
    old.loc[1, "score_barbara"] = "1"
    new = rv.convert_sheet(old)
    assert list(new["old_score_barbara"]) == ["0", "1", ""]
    assert new.loc[0, "old_reason_barbara"] == "Different customers"
    assert "old_score_matthew" not in new.columns          # nothing filled, nothing kept
    assert (new["same_customers_barbara"] == "").all()     # no translation


def filled():
    new = rv.convert_sheet(old_sheet())
    m = {"same_product_matthew": ["yes", "yes", "no"], "same_customers_matthew": ["yes", "no", "no"],
         "same_revenue_model_matthew": ["yes", "yes", "yes"], "same_chain_step_matthew": ["yes", "yes", "yes"],
         "same_product_barbara": ["Yes", "no", ""], "same_customers_barbara": ["yes", "yes", ""],
         "same_revenue_model_barbara": ["no", "yes", ""], "same_chain_step_barbara": ["yes", "yes", ""]}
    for c, v in m.items():
        new[c] = v
    return new


def test_check_flags_unscored_half_answered_and_invalid_rows_only():
    sheet = filled()
    sheet.loc[1, "same_chain_step_matthew"] = ""
    sheet.loc[2, "same_product_matthew"] = "kinda"
    problems = rv.check_sheet(sheet)
    got = set(zip(problems["pair"], problems["reviewer"], problems["problem"].str.split(" \\(").str[0]))
    assert ("T-R3-02", "matthew", "answer all four questions") in got
    assert ("T-R3-03", "matthew", "same_product 'kinda' is not yes or no") in got
    assert ("T-R3-03", "barbara", "not scored yet") in got
    assert len(problems) == 3


def test_scores_derive_per_reviewer_and_leave_unanswered_pairs_blank():
    scored = rv.scores(filled())
    assert list(scored["score_matthew"]) == [2, 1, 0]
    assert scored["score_barbara"].tolist()[:2] == [1, 1]
    assert np.isnan(scored["score_barbara"].iloc[2])
    assert scored["same_product_barbara"].iloc[0] is True


def test_agreement_is_per_question_over_pairs_both_answered():
    table = rv.agreement(rv.scores(filled()))
    row = table.iloc[0]
    assert row["reviewers"] == "matthew vs barbara" and row["pairs"] == 2
    assert row["same_product"] == 0.5          # pair 2: yes vs no
    assert row["same_customers"] == 0.5        # pair 2: no vs yes
    assert row["same_revenue_model"] == 0.5    # pair 1: yes vs no
    assert row["same_chain_step"] == 1.0
    assert row["score"] == 0.5                 # pair 1: 2 vs 1; pair 2: 1 vs 1


def test_convert_cli_never_overwrites(tmp_path, capsys):
    src, dst = tmp_path / "old.csv", tmp_path / "new.csv"
    old_sheet().to_csv(src, index=False)
    rv.main(["convert", str(src), str(dst)])
    assert dst.exists()
    before = dst.read_text()
    rv.main(["convert", str(src), str(dst)])
    assert dst.read_text() == before
    assert "kept" in capsys.readouterr().out
