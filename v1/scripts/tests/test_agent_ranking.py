"""Offline tests for the per-facet scores (agent_loop --facet-scores) and agent_ranking.py."""

import json

import pandas as pd
import pytest

import agent_loop as al
import agent_ranking as ar
from test_agent_loop import answers, final, state  # noqa: F401  (fixture)


def facets(**scores):
    out = {k: {"score": None, "target_citations": [], "comp_citations": [], "reason": ""} for k in ar.FACET_POINTS}
    for k, v in scores.items():
        out[k] = {"score": v, "target_citations": ["T:P1.1"], "comp_citations": ["C:P1.1"], "reason": "x"}
    return out


def test_weights_sum_to_one():
    assert ar.TOTAL_POINTS == 66
    assert abs(sum(ar.WEIGHTS.values()) - 1) < 1e-12


def test_points_formula():
    w = ar.WEIGHTS
    r = ar.points({"primary_products": 100, "customer_segment": 50, "end_markets": None})
    c = w["primary_products"] + w["customer_segment"]
    e = w["primary_products"] + 0.5 * w["customer_segment"]
    assert r["coverage"] == round(100 * c, 2)
    assert r["evidence_points"] == round(100 * e, 2)
    assert r["observed_similarity"] == round(100 * e / c, 2)
    assert r["upper_bound"] == round(100 * e + 100 * (1 - c), 2)
    assert ar.points({})["observed_similarity"] is None          # nothing observed: S undefined


def test_unknown_is_not_zero():
    assert ar.points({"primary_products": None})["evidence_points"] == 0
    assert ar.points({"primary_products": None})["coverage"] == 0
    assert ar.points({"primary_products": 0})["coverage"] > 0     # an evidenced 0 is observed


def test_facet_scores_checked(state):  # noqa: F811
    state.facet_scores = True
    state.start()
    ok = al.check_final(final(2, facet_scores=facets(primary_products=100)), state)
    assert ok["facet_scores"]["primary_products"]["score"] == 100
    assert ok["facet_scores"]["end_markets"]["score"] is None
    bad = facets(primary_products=100)
    bad["primary_products"]["comp_citations"] = []
    with pytest.raises(ValueError):                                # a score needs both sides
        al.check_final(final(2, facet_scores=bad), state)
    bad = facets(primary_products=100)
    bad["primary_products"]["target_citations"] = ["C:P1.1"]
    with pytest.raises(ValueError):                                # target citation must be a target line
        al.check_final(final(2, facet_scores=bad), state)


def test_schema_and_prompt_only_with_flag(state):  # noqa: F811
    assert "facet_scores" not in al.step_schema()["properties"]
    assert "facet_scores" in al.step_schema(True)["required"]
    state.start()
    assert "Facet scores" not in al.prompt(state, 1, 4)
    state.facet_scores = True
    assert "Facet scores" in al.prompt(state, 1, 4)


def test_run_pair_and_row(state, tmp_path):  # noqa: F811
    state.facet_scores = True
    result = al.run_pair(state, tmp_path, answers(final(2, facet_scores=facets(primary_products=75))), None)
    assert result["status"] == "ok"
    pair = pd.Series({"target": "T1", "comp": "C1", "similarity": 0.5, "rank": 1})
    info = pd.DataFrame({"target_ciq_ticker": ["T", "C"]}, index=["T1", "C1"])
    row = al.result_row(pair, info, result, state)
    assert row["facet_primary_products"] == 75 and json.loads(row["facet_scores"])["end_markets"]["score"] is None


def test_rank_and_evaluate():
    rows = []
    for comp, sim, prod, label in [("a", 0.9, 25, 0), ("b", 0.5, 100, 2), ("c", 0.4, 75, 1)]:
        r = {"target": "T", "target_ticker": "T", "comp": comp, "similarity": sim, "score": 1, "status": "ok"}
        r |= {f"facet_{k}": None for k in ar.FACET_POINTS} | {"facet_primary_products": prod}
        rows.append((r, label))
    ranked = ar.rank(pd.DataFrame([r for r, _ in rows]))
    assert ranked["comp"].tolist() == ["b", "c", "a"] and ranked["e_rank"].tolist() == [1, 2, 3]
    labels = pd.DataFrame({"target_id": "T", "comp_id": ["a", "b", "c"], "score_barbara": [l for _, l in rows]})
    ev = ar.evaluate(ranked, labels, ks=(1,))
    assert ev["by_k"][1]["E"]["precision_at_k"] == 1 and ev["by_k"][1]["B3"]["precision_at_k"] == 0
    assert ev["by_k"][1]["E"]["pairwise_accuracy"] == 1 and ev["by_k"][1]["B3"]["pairwise_accuracy"] == 0


def test_industry_fields_and_block_weights():
    base = ar.industry_fields("28")
    assert [f["key"] for f in base] == ["I28-01", "I28-02", "I28-03", "I28-04", "I28-05", "I28-06"]
    pharma = ar.industry_fields(28, {"I28-07", "I28-08", "I28-09"})
    assert len(pharma) == 9                                          # conditional fields only when activated
    assert ar.industry_fields("80") and all(f["points"] for f in ar.industry_fields("80"))
    w = ar.pair_weights(base)
    assert abs(sum(w.values()) - 1) < 1e-9
    assert abs(sum(v for k, v in w.items() if k in ar.WEIGHTS) - 0.6) < 1e-9
    assert ar.pair_weights([]) == ar.WEIGHTS
    r = ar.points({"primary_products": 100, "I28-01": 100}, w)
    assert r["general_coverage"] == round(100 * ar.WEIGHTS["primary_products"], 2)
    assert r["industry_coverage"] == round(100 * 4 / 18, 2)


def test_industry_facets_in_schema_and_check(state):  # noqa: F811
    state.facet_scores = True
    state.industry = ar.industry_fields("59")
    state.start()
    assert "I59-01" in al.step_schema(state.facet_keys())["properties"]["facet_scores"]["required"]
    assert "I59-01: Specialty retail niche" in al.prompt(state, 1, 4)
    ans = facets(primary_products=50)
    ans["I59-01"] = {"score": 75, "target_citations": ["T:P1.2"], "comp_citations": ["C:P1.2"], "reason": "x"}
    out = al.check_final(final(1, facet_scores=ans), state)
    assert out["facet_scores"]["I59-01"]["score"] == 75 and out["facet_scores"]["I59-02"]["score"] is None


def test_final_rank_is_agent_then_s():
    rows = []
    for comp, grade, prod, cust in [("a", 1, 100, None), ("b", 2, 25, 25), ("c", 1, 50, 50)]:
        r = {"target": "T", "target_ticker": "T", "comp": comp, "similarity": 0.5, "score": grade, "status": "ok"}
        r |= {f"facet_{k}": None for k in ar.FACET_POINTS}
        r |= {"facet_primary_products": prod, "facet_customer_segment": cust}
        rows.append(r)
    ranked = ar.rank(pd.DataFrame(rows))
    assert ranked["comp"].tolist() == ["b", "a", "c"]      # grade 2 first; among 1s, a has S 100 > c's 50
    assert ranked.set_index("comp")["e_rank"]["a"] == 1     # by E, a (one facet at 100) still leads
