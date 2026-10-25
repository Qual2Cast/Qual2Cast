"""Tests for the LLM's direct comp suggestions (suggest_comps.py). No model is called."""

import pandas as pd

import facets as fc
import suggest_comps as sc


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
    return info, pd.DataFrame.from_dict(rows, orient="index")


def test_pool_is_alphabetical_shared_and_only_business_facets():
    info, facets = company_tables()
    system, labels = sc.build_system(["Z", "T", "A"], info, facets)
    assert labels == {"P001": "A", "P002": "T", "P003": "Z"}
    assert system.index("P001: Alpha LLC") < system.index("P003: Zeta Inc")
    assert "primary products: none" in system                       # Zeta: not applicable
    assert "Z company_size" not in system and "Z end_markets" not in system
    assert "ZET" not in system                                       # no tickers
    prompt = sc.build_prompt(system, "T", info, facets)
    assert prompt.startswith(system)                                 # the shared part comes first (cached)
    assert prompt.endswith("- Regulatory exposure: T regulatory_exposure")


def test_check_answer_keeps_order_and_drops_bad_labels():
    labels = {"P001": "A", "P002": "T", "P003": "Z"}
    raw = {"comps": [{"label": "P003", "reason": "same"}, {"label": "P002", "reason": "itself"},
                     {"label": "P003", "reason": "again"}, {"label": "P999", "reason": "?"},
                     {"label": "P001", "reason": "also"}]}
    rows, issues = sc.check_answer(raw, labels, target="T")
    assert [(r["rank"], r["comp"]) for r in rows] == [(1, "Z"), (2, "A")]
    assert issues == ["chose_target", "duplicate_label:P003", "unknown_label:P999"]
    rows, issues = sc.check_answer(raw, labels, target="T", max_comps=1)
    assert [r["comp"] for r in rows] == ["Z"] and "over_1:P001" in issues
