"""Offline tests for agent_loop.py: no model, no network."""

import json

import pandas as pd
import pytest

import agent_loop as al


def company(side, iq, name, website, lines):
    return al.Company(iq, name, website, side, "- offering_description: test",
                      {f"P1.{i}": {"text": t, "url": f"https://{website}/"} for i, t in enumerate(lines, 1)})


@pytest.fixture
def state():
    t = company("target", "T1", "Acme Payroll Inc.", "acmepayroll.com",
                ["Payroll software for mid-sized employers.", "HR and benefits in one platform.",
                 "Our time tracking module serves restaurants."])
    c = company("comp", "C1", "Paystar Corp", "paystar.com",
                ["Cloud payroll and HR for businesses.", "Careers at Paystar.", "Payroll tax filing services."])
    return al.PairState(t, c)


def answers(*items):
    """A fake model that returns the given answers in order and records each prompt."""
    seen = []

    def model(prompt, run_dir, schema):
        seen.append(prompt)
        return {"llm_status": "ok", "text": json.dumps(items[len(seen) - 1])}
    model.seen = seen
    return model


def final(score, t=("T:P1.1",), c=("C:P1.1",), **kw):
    base = {"action": "final", "side": None, "query": None, "why": "", "score": score,
            "verdict": al.VERDICTS[score], "offering_fit": "match", "customer_fit": "match",
            "business_model_fit": "match", "reason": "same payroll product, same buyers",
            "reason_if_0": "Different industry" if score == 0 else "", "missing_evidence": "",
            "target_citations": list(t), "comp_citations": list(c)}
    return {**base, **kw}


def lookup(action, side, query):
    return {**final(None), "action": action, "side": side, "query": query, "verdict": "insufficient_evidence",
            "target_citations": [], "comp_citations": []}


def test_start_shows_both_companies_within_budget(state):
    state.start(words=6)
    assert "T:P1.1" in state.shown and "C:P1.1" in state.shown
    assert "T:P1.3" not in state.shown


def test_search_site_adds_best_unseen_line(state):
    state.start(words=1)
    added = al.search_site(state, state.comp, "tax filing")
    assert added[0] == "C:P1.3"
    assert al.search_site(state, state.comp, "zzzz") == []


def test_web_search_drops_investor_pages_for_target_only(state, tmp_path):
    results = [{"url": "https://investors.acmepayroll.com/news", "title": "Acme news", "snippet": "Acme sells payroll software to mid-sized employers."},
               {"url": "https://example.com/acme", "title": "Review", "snippet": "Acme payroll serves mid-sized firms."}]
    added, dropped = al.web_search(state, state.target, "payroll customers", lambda q, d: results, tmp_path)
    assert added == ["T:S1.1"] and dropped[0]["reason"] == "investor_host"
    added, _ = al.web_search(state, state.comp, "Paystar payroll", lambda q, d: results, tmp_path)
    assert len(added) == 2       # the comp is public: investor pages are allowed


def test_run_pair_lookup_then_final(state, tmp_path):
    model = answers(lookup("search_site", "comp", "tax filing"), final(2, c=("C:P1.3",)))
    result = al.run_pair(state, tmp_path, model, None, max_steps=3, start_words=6)
    assert result["status"] == "ok" and result["answer"]["score"] == 2
    assert "C:P1.3" in model.seen[1]                  # the found line was shown at step 2
    assert state.lookups[0]["added"] == ["C:P1.3"]


def test_bad_citation_is_retried_once_then_invalid(state, tmp_path):
    bad = final(2, c=("C:P9.9",))
    result = al.run_pair(state, tmp_path, answers(bad, final(1)), None, max_steps=3)
    assert result["status"] == "ok" and result["answer"]["score"] == 1
    state2 = al.PairState(state.target, state.comp)
    result = al.run_pair(state2, tmp_path / "b", answers(bad, bad), None, max_steps=3)
    assert result["status"] == "invalid"


def test_last_step_must_be_final(state, tmp_path):
    model = answers(lookup("search_site", "comp", "payroll"), lookup("search_site", "comp", "hr"))
    result = al.run_pair(state, tmp_path, model, None, max_steps=2)
    assert result["status"] == "invalid"
    assert "MUST be final" in model.seen[1]


def test_zero_needs_a_reason_and_null_needs_no_citation(state):
    state.start()
    with pytest.raises(ValueError):
        al.check_final(final(0, reason_if_0=""), state)
    assert al.check_final(final(None, t=(), c=(), verdict="insufficient_evidence"), state)["comp_citations"] == []


def test_prompt_never_shows_similarity_or_multiples(state):
    state.start()
    text = al.prompt(state, 1, 4)
    for word in ("similarity", "EV/EBITDA", "rank"):
        assert word.lower() not in text.lower().replace("never use or look up valuations, multiples", "")


def test_gold_pairs_are_the_frozen_36():
    pairs = al.load_pairs("gold")
    assert len(pairs) == 36 and pairs["target"].nunique() == 2
    assert not pairs.duplicated(["target", "comp"]).any()


def test_selected_pairs_filter_by_ticker():
    pairs = al.load_pairs("selected", tickers=["WEN"])
    assert pairs["target"].nunique() == 1 and len(pairs) == 6
    assert len(al.load_pairs("selected", tickers=["WEN"], top_k=3)) == 3
