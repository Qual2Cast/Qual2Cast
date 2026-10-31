"""Offline tests for gold_from_labels.py (no network, no API).

  python -m pytest v0/verification/tests -q
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gold_from_labels as gl  # noqa: E402
import verify_with_evidence as vw  # noqa: E402


def sheet(tmp_path, rows):
    p = tmp_path / "labels.csv"
    pd.DataFrame(rows, columns=["ticker", "company", "facet_id", "facet", "haiku_value", "label",
                                "evidence_url", "note", "labeler"]).to_csv(p, index=False)
    return p


def rows_for(ticker, labels):
    return [[ticker, "Acme Inc.", f"F{i}", "x", v, lab, "https://acme.com", "", "Fiona "]
            for i, (v, lab) in enumerate(labels, start=1)]


COMPANIES = pd.DataFrame({"IQ_COMPANY_ID": ["IQ1", "IQ2"], "target_ciq_ticker": ["ACME", "GLIB.A"],
                          "target_company_name": ["Acme Inc.", "GCI Liberty"]})


def test_labels_map_to_verdicts(tmp_path):
    labs = [("v", "correct"), ("v", "Partly correct"), ("v", "outdated"), ("v", "wrong"), ("v", "can’t tell")]
    g = gl.read_labels(sheet(tmp_path, rows_for("ACME", labs)))
    assert g.verdict.tolist() == ["supported", "partly", "contradicted", "contradicted", "no_evidence"]
    assert g.facet.tolist()[:2] == ["offering_description", "primary_products"]
    assert g.labeler.iloc[0] == "Fiona"


def test_unknown_label_and_duplicates_rejected(tmp_path):
    with pytest.raises(SystemExit):
        gl.read_labels(sheet(tmp_path, rows_for("ACME", [("v", "maybe")])))
    with pytest.raises(SystemExit):
        gl.read_labels(sheet(tmp_path, rows_for("ACME", [("v", "correct")]) * 2))


def test_fill_table_layout_and_status(tmp_path):
    labs = [("Sells widgets", "correct"), ("not_applicable", "correct"), ("unknown", "wrong")]
    g = gl.read_labels(sheet(tmp_path, rows_for("acme", labs)))
    t = gl.fill_table(g, COMPANIES)
    r = t.iloc[0]
    assert (r.IQ_COMPANY_ID, r.llm_status) == ("IQ1", "ok")
    assert (r.offering_description_status, r.offering_description) == ("filled", "Sells widgets")
    assert (r.primary_products_status, r.primary_products) == ("not_applicable", "")
    assert r.primary_services_status == "unknown"
    assert r.regulatory_exposure_status == "unknown"        # facet not in the sheet
    assert "Sells widgets" in vw.facet_block(r)


def test_ticker_not_in_universe(tmp_path):
    g = gl.read_labels(sheet(tmp_path, rows_for("NOPE", [("v", "correct")])))
    with pytest.raises(SystemExit):
        gl.fill_table(g, COMPANIES)


def test_gold_scores_with_verifier(tmp_path):
    g = gl.read_labels(sheet(tmp_path, rows_for("ACME", [("v", "correct"), ("v", "wrong"), ("v", "can't tell")])))
    verdicts = pd.DataFrame({"ticker": "ACME", "tier": "P", "facet": g.facet,
                             "verdict": ["supported", "contradicted", "partly"]})
    s = vw.score(verdicts, g)
    assert s.loc["P", "facets"] == 2                         # can't tell left out
    assert (s.loc["P", "problems_caught"], s.loc["P", "false_alarms"]) == (1, 0)
