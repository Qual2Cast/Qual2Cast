import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
import v2paths as v2  # noqa: E402
v2.setup()

import traits as tr  # noqa: E402
import trait_stability as ts  # noqa: E402


def answer(value="yes", knows=True):
    raw = {n: {"answer": value, "reason": "sells pumps to refiners"} for n in tr.QUESTION_NAMES}
    return {"knows_company": knows, **raw, "notes": ""}


def test_ten_questions_four_tags_six_traits():
    assert len(tr.QUESTIONS) == 10 and len(tr.TAGS) == 4 and len(tr.TRAITS) == 6
    assert len(set(tr.QUESTION_NAMES)) == 10


def test_schema_requires_every_question():
    s = tr.answer_schema()
    assert set(s["required"]) == {"knows_company", "notes", *tr.QUESTION_NAMES}
    assert s["properties"]["recurring_revenue"]["properties"]["answer"]["enum"] == ["yes", "no", "unknown"]


def test_prompt_has_every_question_and_the_company():
    p = tr.build_prompt("Acme Pumps", "acme.example", "We make pumps.")
    assert p.startswith(tr.INSTRUCTIONS)
    for q in tr.QUESTIONS:
        assert q.question in p
    assert "Company: Acme Pumps" in p and "We make pumps." in p


def test_unknown_company_without_pages_is_all_unknown():
    answers, issues = tr.check_answer(answer("yes", knows=False), had_pages=False)
    assert {a["answer"] for a in answers.values()} == {"unknown"}
    assert "company_not_known_no_pages" in issues


def test_unknown_company_with_pages_keeps_answers():
    answers, issues = tr.check_answer(answer("no", knows=False), had_pages=True)
    assert {a["answer"] for a in answers.values()} == {"no"} and not issues


def test_bad_answer_and_figures():
    raw = answer()
    raw["big_ticket"] = {"answer": "maybe", "reason": ""}
    with pytest.raises(ValueError):
        tr.check_answer(raw, True)
    raw = answer()
    raw["asset_heavy"]["reason"] = "spends $2 billion a year on plants"
    _, issues = tr.check_answer(raw, True)
    assert "figure_in_reason:asset_heavy" in issues


def test_page_text_word_cap():
    lines = {"P1.1": "a " * 1000, "P1.2": "b " * 1000}
    assert len(tr.page_text(lines, 1500).split()) == 1500


def table(values: dict) -> pd.DataFrame:
    rows = []
    for iq, v in values.items():
        row = {"IQ_COMPANY_ID": iq, "ticker": iq, "llm_status": "ok"}
        for n in tr.QUESTION_NAMES:
            row[n], row[f"{n}_reason"] = v.get(n, "yes"), ""
        rows.append(row)
    return pd.DataFrame(rows).set_index("IQ_COMPANY_ID")


def test_stability_flags_flips_and_unknowns():
    ids = [f"C{i}" for i in range(10)]
    a = table({i: {} for i in ids})
    b = table({i: ({"big_ticket": "no"} if k < 3 else {}) | ({"asset_heavy": "unknown"} if k < 3 else {})
               for k, i in enumerate(ids)})
    summary, flips = ts.compare(a, b)
    s = summary.set_index("question")
    assert s.at["big_ticket", "flip_rate"] == 0.3 and s.at["big_ticket", "verdict"].startswith("reword")
    assert s.at["asset_heavy", "unknown_rate_max"] == 0.3 and "unknown" in s.at["asset_heavy", "verdict"]
    assert s.at["recurring_revenue", "verdict"] == "keep"
    assert len(flips) == 3


def test_round_2_questions_and_round_1_prompt_unchanged():
    assert tr.ROUND_2_NAMES == ["maintenance_led", "publicly_funded", "serial_acquirer", "mission_critical"]
    assert tr.PROMPT_VERSION == "2026-11-24a" and tr.PROMPT_VERSION_R2 == "2026-11-24b"
    assert tr.INSTRUCTIONS.startswith(
        "You describe a company for a research project that compares companies' business models. Answer ten yes/no")
    assert "Answer four yes/no" in tr.INSTRUCTIONS_R2
    for q in tr.ROUND_2:
        assert q.question in tr.INSTRUCTIONS_R2 and q.question not in tr.INSTRUCTIONS
    s = tr.answer_schema(tr.ROUND_2)
    assert set(s["required"]) == {"knows_company", "notes", *tr.ROUND_2_NAMES}
    assert tr.build_prompt("Acme", "acme.example", "", 2).startswith(tr.INSTRUCTIONS_R2)


def test_round_2_check_and_table_row():
    raw = {"knows_company": True, "notes": "",
           **{n: {"answer": "no", "reason": "makes new pumps"} for n in tr.ROUND_2_NAMES}}
    answers, issues = tr.check_answer(raw, True, tr.ROUND_2)
    assert set(answers) == set(tr.ROUND_2_NAMES) and not issues
    row = tr.table_row(answers, tr.ROUND_2)
    assert row["serial_acquirer"] == "no" and "offers_products" not in row
    with pytest.raises(ValueError):
        tr.check_answer({"knows_company": True, "notes": ""}, True, tr.ROUND_2)


def test_stability_reads_round_2_tables():
    ids = [f"C{i}" for i in range(5)]
    def t2(values):
        rows = [{"IQ_COMPANY_ID": i, "ticker": i, "llm_status": "ok",
                 **{n: values.get(i, "no") for n in tr.ROUND_2_NAMES},
                 **{f"{n}_reason": "" for n in tr.ROUND_2_NAMES}} for i in ids]
        return pd.DataFrame(rows).set_index("IQ_COMPANY_ID")
    summary, _ = ts.compare(t2({}), t2({"C0": "yes"}))
    assert list(summary.question) == tr.ROUND_2_NAMES
    assert summary.set_index("question").at["maintenance_led", "flips"] == 1
