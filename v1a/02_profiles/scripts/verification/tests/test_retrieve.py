"""Offline tests for retrieve.py and tier R (no network, no API).

  python -m pytest v0/verification/tests -q
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evidence as evm  # noqa: E402
import retrieve as rv  # noqa: E402
import verify_with_evidence as vw  # noqa: E402


def make_ev():
    ev = evm.Evidence("IQ1", "Acme Inc.", "https://acme.com")
    ev.sources = {"P1": {"url": "https://acme.com", "type": "company_site", "title": "", "date": ""},
                  "W2": {"url": "https://acme.com/locations", "type": "company_site", "title": "", "date": ""},
                  "S1": {"url": "https://www.businesswire.com/x", "type": "press_release", "title": "",
                         "date": "2025-03-01"},
                  "S2": {"url": "https://craft.co/acme", "type": "database", "title": "", "date": ""}}
    ev.lines = {
        "P1.1": "Acme designs and manufactures rooftop HVAC units for commercial buildings.",
        "P1.2": "Join our caring team and grow with us today.",
        "W2.1": "We operate plants in Texas, Ohio and Mexico and have offices in Canada and Germany.",
        "W2.2": "Products are sold through a network of independent distributors and dealers.",
        "S1.1": "Acme completed the sale of its residential boiler business to Boilco.",
        "S2.1": "Acme is regulated by the EPA and holds state contractor licenses.",
    }
    return ev


VALUES = {"geography_served": "US national: serves the United States",
          "primary_products": "rooftop HVAC units; residential boilers",
          "distribution_channels": "distributors / dealers: independent HVAC distributors",
          "regulatory_exposure": "medium: EPA refrigerant rules"}


def test_tokens():
    assert rv.tokens("The Dealers and Companies' distributors") == ["dealer", "company", "distributor"]
    assert "the" not in rv.tokens("the class")
    assert rv.tokens("class") == ["class"]
    assert rv.tokens("US and U.S. stores near us") == ["united", "state", "united", "state", "store", "near"]


def test_retrieve_picks_facet_lines():
    picked = rv.retrieve(make_ev(), VALUES, k=2)
    assert picked["geography_served"][0] == "W2.1"
    assert picked["distribution_channels"][0] == "W2.2"
    assert picked["regulatory_exposure"][0] == "S2.1"
    assert "S1.1" in picked["primary_products"]             # deal words find the sale
    assert "P1.2" not in sum(picked.values(), [])          # filler line never picked
    assert all(len(v) <= 2 for v in picked.values())


def test_retrieve_kinds_and_empty():
    ev = make_ev()
    picked = rv.retrieve(ev, VALUES, kinds="P", k=5)
    assert all(lab.startswith("P") for labs in picked.values() for lab in labs)
    ev.lines = {}
    assert rv.retrieve(ev, VALUES) == {f: [] for f in rv.fc.FACET_NAMES}


def test_ties_go_to_better_source():
    ev = make_ev()
    ev.lines = {"S2.1": "Acme sells through dealers.", "S1.1": "Acme sells through dealers."}
    picked = rv.retrieve(ev, {}, k=2)
    assert picked["distribution_channels"] == ["S1.1", "S2.1"]   # press release before database


def test_hybrid_with_fake_embedder():
    ev = make_ev()

    def fake(texts):
        v = np.array([[1.0, 0.0] if "plants" in t or "Geography" in t else [0.0, 1.0] for t in texts])
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    picked = rv.retrieve(ev, VALUES, k=1, method="hybrid", embedder=fake)
    assert picked["geography_served"] == ["W2.1"]
    with pytest.raises(ValueError):
        rv.retrieve(ev, VALUES, method="nope")


def test_evidence_block_writes_each_line_once():
    ev = make_ev()
    picked = {"geography_served": ["W2.1"], "company_size": ["W2.1", "S1.1"]}
    block = rv.evidence_block(ev, picked, VALUES)
    assert block.count("We operate plants") == 1
    assert "[W2.1] (shown under F8)" in block
    assert "(press_release, 2025-03-01)" in block
    assert "F1 offering_description (Core offering): unknown\n  (no related evidence found)" in block
    assert rv.shown(picked) == ["W2.1", "S1.1"]


def fill_row():
    row = {"target_company_name": "Acme Inc."}
    for f in rv.fc.FACETS:
        v = VALUES.get(f.name, "")
        row[f"{f.name}_status"] = "filled" if v else "unknown"
        row[f.name] = v
    return pd.Series(row)


def test_tier_r_prompt_and_rules():
    ev, row = make_ev(), fill_row()
    prompt, lines = vw.build_prompt(row, ev, "R", k=2)
    assert prompt.startswith(vw.INSTRUCTIONS)               # cached prefix unchanged
    assert vw.R_NOTE in prompt and "W2.1" in lines and "P1.2" not in lines
    pws, _ = vw.build_prompt(row, ev, "PWS")
    assert vw.R_NOTE not in pws
    raw = {"checks": [{"facet": "geography_served", "verdict": "contradicted", "cite": ["W2.1"],
                       "reason": "plants in Mexico"},
                      {"facet": "end_markets", "verdict": "supported", "cite": ["P1.2"], "reason": "x"}]}
    out = {c["facet"]: c for c in vw.apply_rules(raw, lines, ev)}
    assert out["geography_served"]["verdict"] == "contradicted"
    assert (out["end_markets"]["verdict"], out["end_markets"]["issue"]) == ("not_found", "uncited")


def test_score_has_tier_r():
    gold = pd.DataFrame({"ticker": ["A", "A"], "facet": ["geography_served", "end_markets"],
                         "verdict": ["contradicted", "supported"]})
    v = pd.DataFrame({"ticker": "A", "facet": ["geography_served", "end_markets"] * 2,
                      "tier": ["PWS", "PWS", "R", "R"],
                      "verdict": ["not_found", "supported", "contradicted", "supported"]})
    s = vw.score(v, gold)
    assert list(s.index) == ["PWS", "R"]
    assert (s.loc["PWS", "problems_caught"], s.loc["R", "problems_caught"]) == (0, 1)
