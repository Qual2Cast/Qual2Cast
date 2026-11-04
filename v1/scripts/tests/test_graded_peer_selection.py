"""Selection checks for the optional 0-2 judge route."""

import pandas as pd
import pytest

from graded_peer_selection import check_batch, select
from judge_gold_eval import GoldenSetJudge


def test_ordinal_grade_precedes_cosine_and_excludes_nonpeers():
    pairs = pd.DataFrame([
        ("A", "high_cosine_adjacent", .95),
        ("A", "direct", .60),
        ("A", "nonpeer", .99),
        ("A", "unknown", .98),
    ], columns=["target", "comp", "similarity"])
    grades = pd.DataFrame([
        ("A", "high_cosine_adjacent", 1),
        ("A", "direct", 2),
        ("A", "nonpeer", 0),
        ("A", "unknown", None),
    ], columns=["target", "comp", "score"])

    direct_only = select(pairs, grades, 2)
    direct_then_adjacent = select(pairs, grades, 1)

    assert direct_only.comp.tolist() == ["direct"]
    assert direct_then_adjacent.comp.tolist() == ["direct", "high_cosine_adjacent"]
    assert direct_then_adjacent.judge_rank.tolist() == [1, 2]


def test_selection_caps_each_target_at_ten():
    pairs = pd.DataFrame([("A", f"C{i:02d}", 1 - i / 100) for i in range(12)],
                         columns=["target", "comp", "similarity"])
    grades = pairs[["target", "comp"]].assign(score=1)

    selected = select(pairs, grades, 1)

    assert len(selected) == 10
    assert selected.comp.tolist() == [f"C{i:02d}" for i in range(10)]


def test_batch_citations_must_belong_to_the_named_candidate():
    lines = {
        "B": {"T:P1.1": {"text": "Target"}, "C:P1.1": {"text": "Candidate B"}},
        "C": {"T:P1.1": {"text": "Target"}, "C:P1.1": {"text": "Candidate C"}},
    }
    answer = {"score": 1, "verdict": "adjacent_peer", "reason": "Limited overlap",
              "missing_evidence": "", "target_citations": ["T:P1.1"],
              "comp_citations": ["C2:P1.1"], "comp_id": "B"}
    raw = {"comps": [answer, {**answer, "comp_id": "C", "comp_citations": ["C2:P1.1"]}]}

    with pytest.raises(ValueError, match="supplied comp passage"):
        check_batch(raw, "A", ["B", "C"], lines, {"B": "C1", "C": "C2"},
                    GoldenSetJudge.__new__(GoldenSetJudge))
