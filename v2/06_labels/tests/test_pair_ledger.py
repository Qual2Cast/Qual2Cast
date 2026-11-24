"""pair_ledger.py: grades, answers that are not grades, spans."""

from pathlib import Path
import sys

import pandas as pd

import pair_ledger as pl  # noqa: E402


def test_graded_blank_is_not_judged_and_never_zero():
    d = pl.graded(["T", "T", "T"], ["A", "B", "C"], [2, None, 0], ["ok", "ok", "error"])
    assert d["grade"].tolist()[0] == 2 and pd.isna(d["grade"].tolist()[1])
    assert d["peer"].tolist()[0] == 1 and d["peer"].tolist()[2] == 0
    assert d["status"].tolist() == ["ok", "no grade", "error"]


def test_spans_use_dates_of_judged_sources_only():
    src = pd.DataFrame({
        "source": ["s1", "s2"], "stage": ["human_review"] * 2, "rubric": ["r"] * 2, "who": ["A", "B"],
        "pairs": [2, 5], "judged": [2, 0], "judged_first": ["2026-11-10", "2026-11-04"],
        "judged_last": ["2026-11-10", "2026-11-04"]})
    long = pd.DataFrame({"source": ["s1", "s1", "s2"], "target_id": ["T", "T", "T"],
                         "comp_id": ["A", "B", "A"], "judged": [True, True, False]})
    row = pl.spans(src, long).iloc[0]
    assert (row["first"], row["last"], row["unique_pairs_judged"]) == ("2026-11-10", "2026-11-10", 2)
    assert row["sent_not_judged"] == "s2 (5)"
