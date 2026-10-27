"""Tests for the LLM good/bad step (judge_comps.py). No model is called."""

import json
from types import SimpleNamespace

import pandas as pd

import facets as fc
import judge_comps as jc


def company_tables():
    info = pd.DataFrame({"target_company_name": ["Target Co", "Zeta Inc", "Alpha LLC"],
                         "target_ciq_website": ["t.com", "z.com", "a.com"],
                         "target_ciq_ticker": ["TGT", "ZET", "ALP"]}, index=["T", "Z", "A"])
    rows = {}
    for iq in info.index:
        r = {}
        for f in fc.FACETS:
            r[f.name], r[f"{f.name}_status"] = f"{iq} {f.name}", "filled"
        rows[iq] = r
    rows["Z"]["primary_products_status"] = "not_applicable"
    rows["A"]["end_markets_status"] = "unknown"
    return info, pd.DataFrame.from_dict(rows, orient="index")


def test_prompt_lists_candidates_alphabetically_without_ranks_or_tickers():
    info, facets = company_tables()
    prompt, labels = jc.build_prompt("T", ["Z", "A"], info, facets)
    assert labels == {"C1": "A", "C2": "Z"}                    # Alpha before Zeta, whatever the input order
    assert prompt.index("C1: Alpha LLC") < prompt.index("C2: Zeta Inc")
    assert "Target: Target Co (t.com)" in prompt
    assert "TGT" not in prompt and "ZET" not in prompt
    assert "similarity" not in prompt.lower() and "rank" not in prompt.lower()
    assert "- Primary products: none" in prompt               # Zeta: not applicable
    assert "- End markets: unknown" in prompt                 # Alpha: unknown


def test_check_answer_scores_and_issues():
    labels = {"C1": "A", "C2": "Z", "C3": "Q"}
    raw = {"comps": [{"label": "C1", "good": True, "reason": "same business"},
                     {"label": "C1", "good": False, "reason": "again"},
                     {"label": "C2", "good": False, "reason": "different"},
                     {"label": "C9", "good": True, "reason": "?"}]}
    rows, issues = jc.check_answer(raw, labels)
    assert [(r["comp"], r["score"]) for r in rows] == [("A", 1), ("Z", 0), ("Q", None)]
    assert set(issues) == {"duplicate_label:C1", "unknown_label:C9", "not_answered:C3"}


def test_schema_limits_labels():
    schema = jc.answer_schema(["C1", "C2"])
    item = schema["properties"]["comps"]["items"]
    assert item["properties"]["label"]["enum"] == ["C1", "C2"]
    assert item["properties"]["good"]["type"] == "boolean"


def test_fingerprint_changes_with_model_and_prompt():
    assert jc.fingerprint("p", "m1") != jc.fingerprint("p", "m2")
    assert jc.fingerprint("p", "m1") != jc.fingerprint("q", "m1")


def test_resume_retries_unanswered_candidates(tmp_path, monkeypatch):
    info, facets = company_tables()
    out = jc.output_paths(tmp_path)
    out.judgments.mkdir(parents=True)
    args = SimpleNamespace(backend="codex", model="test", effort=None, refresh=False,
                           candidates=tmp_path / "candidates", z=2)
    calls = []
    def call(*a, **kw):
        calls.append(True)
        labels = ["C1"] if len(calls) == 1 else ["C1", "C2"]
        return {"llm_status": "ok", "text": json.dumps({"comps": [
            {"label": label, "good": True, "reason": "Same business"} for label in labels]})}
    monkeypatch.setattr(jc, "call_model", call)
    first = jc.judge_one("T", ["A", "Z"], info, facets, out, args)
    assert "not_answered:C2" in first["issues"]
    second = jc.judge_one("T", ["A", "Z"], info, facets, out, args)
    assert second["status"] == "ok" and not second["issues"]
    assert len(calls) == 2
    assert jc.judge_one("T", ["A", "Z"], info, facets, out, args)["status"] == "current"
