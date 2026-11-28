"""Rubric v3 LLM judge, offline: call_cli is mocked, so no model is called."""

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import judge_v3 as j  # noqa: E402
import judge_v3_prompt as jp  # noqa: E402
import rubric_v3 as r3  # noqa: E402

FINANCIAL = re.compile(r"\b(ev|ebitda|ev/ebitda|multiples?|valuations?|enterprise value)\b", re.I)
HUMAN_NAMES = re.compile(r"matthew|barbara|riya", re.I)


@pytest.fixture(scope="module")
def desc():
    return j.descriptions()


@pytest.fixture(scope="module")
def filled():
    return r3._read(j.pinned()["filled"])


def answer(**over):
    a = {"overall_call": "yes", "same_product": "yes", "same_customers": "yes", "same_revenue_model": "yes",
         "same_chain_step": "yes", "business_graded": "whole company", "unsure": [], "reason": "same business"}
    a.update(over)
    return a


def fake_cli(responses):
    """A call_cli stand-in: pops one response per call (a dict = ok answer; a str = an error)."""
    calls = []

    def call(prompt, run_dir, schema, backend, model=None, effort=None, timeout=600, instructions_len=0):
        calls.append({"prompt": prompt, "run_dir": Path(run_dir), "instructions_len": instructions_len})
        r = responses.pop(0) if responses else answer()
        if isinstance(r, dict):
            return {"llm_status": "ok", "text": json.dumps(r), "stop_run": False}
        return {"llm_status": "cli_error", "error": r, "stop_run": "limit" in r}
    return call, calls


def test_guide_text_and_order():
    ins = jp.INSTRUCTIONS
    assert not FINANCIAL.search(ins) and not HUMAN_NAMES.search(ins)
    # the 2026-11-27 rulings, quoted from the guide
    guide = j.GUIDE_FILE.read_text(encoding="utf-8")
    for quote in ["Do the same buyers, in the same role, also buy from the comp, even if they buy something "
                  "different from it?",
                  "If that buyer can place the same order with the comp's **main business**, yes. The main business "
                  "is the one the comp's description leads with.",
                  "Question 1 is judged against the comp's main business",
                  "Question 2 can be met by any\nbusiness of the comp (team ruling 2026-11-27)",
                  "Product is no too (broadband is a smaller line, not the main business)"]:
        assert quote in ins and quote in guide
    # every anchor's why-text is in the prompt
    for t, c, *_ in r3.ANCHORS:
        assert f"| {t} (" in ins and f"| {c} (" in ins
    # overall call is asked before the four, in the prompt and in the schema
    assert ins.index("`overall_call`") < ins.index("`same_product`")
    assert list(j.answer_schema()["properties"])[:5] == j.ANSWERS
    assert j.ANSWERS[0] == r3.OVERALL


def test_prompt_has_no_reviewer_or_financial_columns(desc, filled):
    notes = {v for r in ("matthew", "barbara") for v in filled[f"notes_{r}"] if len(str(v)) > 25}
    graded = {v for r in ("matthew", "barbara") for v in filled[f"business_graded_{r}"] if len(str(v)) > 25}
    for pair in desc.index:
        # even a row carrying every reviewer column renders only the description columns
        prompt = j.build_prompt(filled.set_index("pair").loc[pair])
        assert prompt == j.build_prompt(desc.loc[pair])
        assert not HUMAN_NAMES.search(prompt)
        # (reviewers sometimes copied a business name from target_business_scope into business_graded)
        cells = " ".join(str(desc.at[pair, c]) for c in jp.PAIR_COLUMNS)
        assert not any(n in prompt and n not in cells for n in notes | graded)
        # financial words only where a business description itself uses them (e.g. "valuation-driven")
        bare = prompt
        for c in jp.PAIR_COLUMNS:
            bare = bare.replace(str(desc.at[pair, c]), "")
        assert not FINANCIAL.search(bare), pair
    p318 = j.build_prompt(desc.loc["P318"])
    assert not FINANCIAL.search(p318) and "Thermon" in p318 and "Flowserve" in p318
    assert p318.startswith(jp.INSTRUCTIONS)


def test_description_columns_match_filled(desc, filled):
    f = filled.set_index("pair")
    for c in jp.PAIR_COLUMNS:
        assert (f.loc[desc.index, c] == desc[c]).all(), c


def test_selections(desc):
    split = j.select_pairs("split", desc)
    assert len(split) == 83 and not desc.loc[split, "is_anchor"].any()
    s = pd.read_csv(j.pinned()["scores"] / "scores.csv", dtype={"pair": str}).set_index("pair").loc[split]
    direct = s["score_matthew"].eq(2) != s["score_barbara"].eq(2)
    peer = s["score_matthew"].ge(1) != s["score_barbara"].ge(1)
    assert direct.sum() == 35 and peer.sum() == 67 and (direct | peer).all()
    pilot = j.select_pairs("pilot", desc)
    assert len(pilot) == 32 and desc.loc[pilot, "is_anchor"].sum() == 12
    assert set(pilot) - set(desc.index[desc["is_anchor"]]) <= set(split)
    assert pilot == j.select_pairs("pilot", desc)          # seeded
    assert len(j.select_pairs("anchors", desc)) == 12 and len(j.select_pairs("all", desc)) == 323


def test_select_from_file(desc, tmp_path):
    f = tmp_path / "ids.txt"
    f.write_text("P318\nP001, P002\n", encoding="utf-8")
    assert j.select_pairs(str(f), desc) == ["P001", "P002", "P318"]
    f.write_text("P999\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        j.select_pairs(str(f), desc)


def test_check_answer():
    assert j.check_answer(answer(unsure=["product", "product"]))["unsure"] == ["product"]
    with pytest.raises(ValueError):
        j.check_answer(answer(same_product="maybe"))
    with pytest.raises(ValueError):
        j.check_answer(answer(unsure=["facets"]))
    with pytest.raises(KeyError):
        j.check_answer({k: v for k, v in answer().items() if k != "reason"})


def test_run_resume_and_claude_cache(desc, tmp_path, monkeypatch):
    pairs = ["P001", "P002", "P003"]
    call, calls = fake_cli([answer(), "bad json", answer()])
    monkeypatch.setattr(j.cli_models, "call_cli", call)
    run = j.Run(tmp_path / "r", "claude-cli", "claude-sonnet-5-5", "sonnet")
    c = run.run(pairs, desc, "test", "cmd")
    assert c["ok"] == 2 and c["failed"] == 1 and len(calls) == 3
    assert calls[0]["instructions_len"] == len(jp.INSTRUCTIONS)
    assert calls[0]["prompt"].startswith(jp.INSTRUCTIONS)
    # resume: only the failed pair is called again
    call2, calls2 = fake_cli([answer()])
    monkeypatch.setattr(j.cli_models, "call_cli", call2)
    c = run.run(pairs, desc, "test", "cmd")
    assert c["skipped_done"] == 2 and c["ok"] == 1 and len(calls2) == 1
    assert "P002" in str(calls2[0]["run_dir"])
    assert (tmp_path / "r" / "history").exists()                      # the failed record was kept
    man = json.loads((tmp_path / "r" / "manifest.json").read_text(encoding="utf-8"))
    assert len(man["sessions"]) == 2 and man["answered_ok"] == 3 and man["sha256"]["guide"]
    # other settings in the same dir are refused
    with pytest.raises(SystemExit):
        j.Run(tmp_path / "r", "codex", "gpt-5.6-terra", "sonnet").run(pairs, desc, "test", "cmd")


def test_stop_after_consecutive_failures(desc, tmp_path, monkeypatch):
    pairs = list(desc.index[:8])
    call, calls = fake_cli([answer(), "e1", "e2", "e3", answer()])
    monkeypatch.setattr(j.cli_models, "call_cli", call)
    c = j.Run(tmp_path / "r", "codex", "gpt-5.6-terra", "terra").run(pairs, desc, "test", "cmd")
    assert len(calls) == 4 and c["ok"] == 1 and c["failed"] == 3 and c["not_run"] == 4
    assert calls[0]["instructions_len"] == 0                         # codex: whole prompt on stdin
    # a fatal error (usage limit) stops at once
    call, calls = fake_cli(["you've hit your limit"])
    monkeypatch.setattr(j.cli_models, "call_cli", call)
    c = j.Run(tmp_path / "r2", "codex", "gpt-5.6-terra", "terra").run(pairs, desc, "test", "cmd")
    assert len(calls) == 1 and c["not_run"] == 7


def test_collect_is_readable_by_rubric_v3(desc, tmp_path, monkeypatch):
    pairs = ["P001", "P002", "P318"]
    call, _ = fake_cli([answer(), answer(same_revenue_model="no", unsure=["revenue_model", "overall"]),
                        answer(same_product="no", overall_call="no")])
    monkeypatch.setattr(j.cli_models, "call_cli", call)
    j.Run(tmp_path / "r", "codex", "gpt-5.6-terra", "terra").run(pairs, desc, "test", "cmd")
    out = j.collect(tmp_path / "r")
    a = pd.read_csv(tmp_path / "r" / "judge_answers.csv", dtype=str, keep_default_na=False)
    assert list(a.columns[:4]) == ["pair", "target_id", "comp_id", "is_anchor"]
    assert list(a.columns[4:12]) == r3.columns("terra") and len(a) == 3
    sheet = r3._read(tmp_path / "r" / "filled_with_terra.csv")
    assert len(sheet) == 323 and r3.reviewers_in(sheet) == ["matthew", "barbara", "terra"]
    assert r3.check_sheet(sheet, ["terra"])["problem"].eq("not scored yet").sum() == 320
    sc = r3.scores(sheet).set_index("pair")
    assert sc.loc["P001", "score_terra"] == 2 and sc.loc["P002", "score_terra"] == 1
    assert sc.loc["P318", "score_terra"] == 1 and sc.loc["P318", "overall_call_terra"] is False
    assert sc.loc["P002", "unsure_terra"] == "same_revenue_model;overall_call"
    assert pd.isna(sc.loc["P003", "score_terra"])
    # the humans' columns are untouched
    pinned = r3.scores(r3._read(j.pinned()["filled"])).set_index("pair")
    assert sc["score_matthew"].equals(pinned["score_matthew"])
    assert (tmp_path / "r" / "scores" / "scores.csv").exists()
    fin = r3.final_labels(r3.scores(sheet), ["matthew", "barbara"], "terra")
    assert len(fin) == 323
    assert out["scores"][f"score_terra"].notna().sum() == 3
