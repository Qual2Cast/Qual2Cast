"""Tests for the LLM good/bad step (cosine_then_llm.py). No model is called."""

import pandas as pd

import facets as fc
import cosine_then_llm as jc


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


def test_prompt_versions_differ_only_in_company_size():
    # see v1/PROMPT_VERSIONS.md: the saved version lists all twelve facets, the current one leaves out F9
    info, facets = company_tables()
    new, _ = jc.build_prompt("T", ["Z", "A"], info, facets)
    saved, _ = jc.build_prompt("T", ["Z", "A"], info, facets, jc.SAVED_PROMPT_VERSION)
    assert jc.PROMPT_VERSION != jc.SAVED_PROMPT_VERSION
    assert "- Company size:" not in new and "- Company size:" in saved
    assert [l for l in saved.splitlines() if not l.startswith("- Company size:")] == new.splitlines()


def test_write_tables_refuses_to_empty_a_table_of_another_version(tmp_path):
    import json
    import pytest
    out = jc.output_paths(tmp_path)
    out.judgments.mkdir(parents=True)
    (out.judgments / "T.json").write_text(json.dumps({
        "target": "T", "llm_status": "ok", "prompt_version": jc.SAVED_PROMPT_VERSION, "model": "m", "comps": [],
        "issues": [], "candidates_run": "r", "judged_at": "t"}), encoding="utf-8")
    info, _ = company_tables()
    pairs = pd.DataFrame(columns=["target", "comp", "rank", "similarity", "z"])
    with pytest.raises(SystemExit, match="Pass --prompt-version"):
        jc.write_tables(out, pairs, info)                          # the default (current) version
    assert jc.write_tables(out, pairs, info, jc.SAVED_PROMPT_VERSION).exists()


def test_b3_flag_picks_the_baseline_lists_not_the_z_shortlist():
    import pytest
    pairs = pd.DataFrame({"target": "T", "comp": ["A", "B", "C"], "z": [2.5, 1.0, 2.1],
                          "selected": [True, True, False]})
    assert jc.pick_pairs(pairs, 2.0)["comp"].tolist() == ["A", "C"]                 # v0: z >= 2
    assert jc.pick_pairs(pairs, 2.0, "selected")["comp"].tolist() == ["A", "B"]     # --b3: the baseline list
    as_text = pairs.assign(selected=pairs["selected"].astype(str))                  # read back from CSV
    assert jc.pick_pairs(as_text, 2.0, "selected")["comp"].tolist() == ["A", "B"]
    with pytest.raises(SystemExit, match="method1_candidates"):
        jc.pick_pairs(pairs.drop(columns="selected"), 2.0, "selected")
