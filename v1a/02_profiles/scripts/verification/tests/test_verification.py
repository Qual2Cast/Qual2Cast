"""Offline tests: no network, no API calls (fake fetcher and searcher).

  python -m pytest v0/verification/tests -q
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evidence as evm  # noqa: E402
import pages_only_fill as po  # noqa: E402
import verify_with_evidence as vw  # noqa: E402


# ---------------------------------------------------------------- source rules

@pytest.mark.parametrize("url,title,why", [
    ("https://www.sec.gov/Archives/x.htm", "", "blocked_domain"),
    ("https://finance.yahoo.com/quote/ABC", "", "blocked_domain"),
    ("https://s205.q4cdn.com/files/x.pdf", "", "blocked_domain"),
    ("https://ir.example.com/news", "", "investor_host"),
    ("https://example.com/investors/overview", "", "investor_path"),
    ("https://www.businesswire.com/news/x", "Example Reports Third Quarter 2026 Results", "public_company_only"),
    ("https://www.businesswire.com/news/x", "Example Opens New Plant in Ohio", ""),
    ("https://example.com/products", "Products", ""),
])
def test_blocked(url, title, why):
    assert evm.blocked(url, title) == why


def test_public_only_allowed_when_asked():
    assert evm.blocked("https://www.businesswire.com/x", "Q3 2026 results", allow_public_only=True) == ""


def test_source_type():
    site = "www.example.com"
    assert evm.source_type("https://example.com/about", site) == "company_site"
    assert evm.source_type("https://shop.example.com/x", site) == "company_site"
    assert evm.source_type("https://www.prnewswire.com/x", site) == "press_release"
    assert evm.source_type("https://en.wikipedia.org/wiki/X", site) == "reference"
    assert evm.source_type("https://craft.co/example", site) == "database"
    assert evm.source_type("https://www.hbsdealer.com/x", site) == "news"


def test_search_name():
    assert evm.search_name("Addus HomeCare Corporation") == "Addus HomeCare"
    assert evm.search_name("The Wendy's Company") == "Wendy's"
    assert evm.search_name("Brown & Brown, Inc.") == "Brown & Brown"
    assert evm.search_name("Resolute Holdings Management, Inc.") == "Resolute Holdings Management"


def test_queries_never_use_ticker():
    qs = evm.build_queries("Paylocity Holding Corporation", "www.paylocity.com")
    assert all('"Paylocity"' in q["query"] for q in qs)
    assert not any("PCTY" in q["query"] for q in qs)


def test_clean_line_drops_figures():
    assert evm.clean_line("We serve over 42,000 patients in 22 states.") == "We serve multiple patients in multiple states."
    assert evm.clean_line("It was the 11th largest writer of homeowners insurance.") == \
        "It was one of the largest writer of homeowners insurance."
    assert evm.clean_line("We operate more than 45 manufacturing plants in Europe.") == \
        "We operate multiple manufacturing plants in Europe."
    assert evm.clean_line("Revenue grew to $7.9 billion last year.") == ""
    assert evm.clean_line("We completed the sale of our annuity business to MassMutual.") != ""
    assert evm.clean_line("Learn more") == ""


# ---------------------------------------------------------------- providers

def test_parse_results_each_provider():
    serper = {"organic": [{"title": "A", "link": "https://a.com", "snippet": "s", "date": "Jan 1, 2026"}]}
    brave = {"web": {"results": [{"title": "B", "url": "https://b.com", "description": "<strong>s</strong>"}]}}
    tavily = {"results": [{"title": "C", "url": "https://c.com", "content": "s"}]}
    assert evm.parse_results("serper", serper)[0]["url"] == "https://a.com"
    assert evm.parse_results("brave", brave)[0]["snippet"] == "s"
    assert evm.parse_results("tavily", tavily)[0]["title"] == "C"


# ---------------------------------------------------------------- crawl and bundle

HOME = """<html><head><title>Example Co | Industrial Pumps</title>
<meta name="description" content="Example Co designs industrial pumps for water utilities."></head>
<body><main><h1>Industrial pumps for water and wastewater utilities</h1>
<p>Example Co designs and builds centrifugal pumps for water utilities and refineries.</p>
<a href="/products">Products</a> <a href="/locations">Locations</a> <a href="/investors">Investors</a>
<a href="/careers">Careers</a> <a href="/where-to-buy">Where to buy</a> <a href="https://other.com/x">Other</a>
</main></body></html>"""
PAGES = {
    "https://example.com/products": "<html><head><title>Products</title></head><body><main>"
        "<p>Our centrifugal pumps, valves and controls serve municipal water systems.</p></main></body></html>",
    "https://example.com/locations": "<html><head><title>Locations</title></head><body><main>"
        "<p>We operate plants in Texas, Ohio and Ontario, Canada, and sell across North America.</p>"
        "<p>We employ 1,200 people across 14 plants.</p></main></body></html>",
    "https://example.com/where-to-buy": "<html><head><title>Where to buy</title></head><body><main>"
        "<p>Our products are sold through independent distributors and direct to utilities.</p></main></body></html>",
}


class FakeFetcher:
    def __init__(self):
        self.asked = []

    def allowed(self, url):
        return True

    def get_html(self, url):
        self.asked.append(url)
        url = url.rstrip("/")
        if url in ("https://example.com", "https://www.example.com"):
            return "https://example.com/", HOME
        if url in PAGES:
            return url, PAGES[url]
        raise RuntimeError("404")


def fake_searcher(provider, key, query):
    return {"organic": [
        {"title": "Example Co acquires Acme Valves", "link": "https://www.businesswire.com/news/1",
         "snippet": "Example Co completed the acquisition of Acme Valves, adding industrial valves to its lineup."},
        {"title": "Example Co Q3 2026 results", "link": "https://www.businesswire.com/news/2",
         "snippet": "Example Co reported third quarter results with record sales growth this year."},
        {"title": "Example Co profile", "link": "https://craft.co/example",
         "snippet": "Example Co is a pump maker with operations in the United States and Canada."},
        {"title": "Example (EXM) quote", "link": "https://finance.yahoo.com/quote/EXM",
         "snippet": "Example Co stock price and quote information for investors today."},
    ]}


@pytest.fixture
def saved(tmp_path, monkeypatch):
    pages_dir = tmp_path / "page_text"
    pages_dir.mkdir()
    (pages_dir / "IQ1.json").write_text(json.dumps({"pages": [{
        "page_id": "P1", "url": "https://example.com/", "category": "home",
        "title": "Example Co", "meta": "", "blocks": ["Example Co designs industrial pumps for utilities."]}]}))
    monkeypatch.setattr(evm, "SAVED_PAGES", pages_dir)
    return tmp_path


def test_pick_links_wants_locations_and_dealers_skips_investors():
    page = evm.extract_page(HOME)
    picked = [u for _, u in evm.pick_links(page["links"], "https://example.com/", set(), 6)]
    assert "https://example.com/locations" in picked
    assert "https://example.com/where-to-buy" in picked
    assert not any("investors" in u or "careers" in u or "other.com" in u for u in picked)


def test_gather_labels_ranks_and_filters(saved, monkeypatch):
    monkeypatch.setattr(evm, "pick_provider", lambda name=None: ("serper", "k"))
    ev = evm.gather("IQ1", "Example Co, Inc.", "example.com", fetcher=FakeFetcher(),
                    searcher=fake_searcher, out_root=saved / "evidence")
    assert ev.lines["P1.2"].startswith("Example Co designs")          # saved page, same labels as the fill
    w_text = " ".join(v for k, v in ev.lines.items() if k.startswith("W"))
    assert "independent distributors" in w_text and "Ontario" in w_text
    assert "1,200" not in w_text                                        # figure line dropped
    s = {k: ev.sources[k] for k in ev.sources if k.startswith("S")}
    assert [v["type"] for v in s.values()] == ["press_release", "database"]   # ranked; results page and quote gone
    reasons = {d["reason"] for d in ev.dropped}
    assert {"public_company_only", "blocked_domain"} <= reasons
    assert "acquisition of Acme Valves" in ev.lines["S1.1"]
    assert (Path(ev.log_dir) / "evidence.json").exists() and (Path(ev.log_dir) / "search.json").exists()
    assert "[W1.1]" in ev.text("PW") and "[S1.1]" not in ev.text("PW")


def test_gather_without_key_records_it(saved, monkeypatch):
    monkeypatch.setattr(evm, "pick_provider", lambda name=None: ("", ""))
    ev = evm.gather("IQ1", "Example Co", "example.com", crawl=False, out_root=saved / "evidence")
    assert {"url": "", "reason": "no_search_api_key"} in ev.dropped


# ---------------------------------------------------------------- judge rules and score

def _ev():
    ev = evm.Evidence("IQ1", "Example Co", "example.com")
    ev.sources = {"P1": {"url": "u1", "type": "company_site"}, "S1": {"url": "u2", "type": "database"}}
    ev.lines = {"P1.1": "a", "S1.1": "b"}
    return ev


def test_apply_rules_uncited_and_database_only():
    ev = _ev()
    raw = {"checks": [
        {"facet": "offering_description", "verdict": "supported", "cite": ["P1.1"], "reason": "r"},
        {"facet": "primary_products", "verdict": "partly", "cite": ["P9.9"], "reason": "r"},
        {"facet": "geography_served", "verdict": "contradicted", "cite": ["[S1.1]"], "reason": "r"},
    ], "notes": ""}
    out = {c["facet"]: c for c in vw.apply_rules(raw, ev.lines, ev)}
    assert out["offering_description"]["verdict"] == "supported"
    assert out["primary_products"]["verdict"] == "not_found" and out["primary_products"]["issue"] == "uncited"
    assert out["geography_served"]["verdict"] == "not_found" and out["geography_served"]["issue"] == "database_only"
    assert out["company_size"]["verdict"] == "not_found"              # no check given
    assert len(out) == 12


def test_score():
    v = pd.DataFrame([
        {"ticker": "A", "facet": "f1", "tier": "P", "verdict": "not_found"},
        {"ticker": "A", "facet": "f2", "tier": "P", "verdict": "supported"},
        {"ticker": "A", "facet": "f1", "tier": "PWS", "verdict": "contradicted"},
        {"ticker": "A", "facet": "f2", "tier": "PWS", "verdict": "partly"},
        {"ticker": "A", "facet": "f3", "tier": "PWS", "verdict": "supported"},
    ])
    gold = pd.DataFrame([{"ticker": "A", "facet": "f1", "verdict": "contradicted"},
                         {"ticker": "A", "facet": "f2", "verdict": "supported"},
                         {"ticker": "A", "facet": "f3", "verdict": "no_evidence"}])
    s = vw.score(v, gold)
    assert s.loc["P", "decided"] == 1 and s.loc["P", "agree_on_decided_%"] == 100.0
    assert s.loc["PWS", "problems_caught"] == 1 and s.loc["PWS", "false_alarms"] == 1
    assert s.loc["PWS", "facets"] == 2                                 # gold no_evidence left out


# ---------------------------------------------------------------- pages-only fill

def test_masking():
    v = po.name_variants("Addus HomeCare Corporation", "www.addus.com")
    assert "Addus HomeCare" in v and "Addus" in v
    t = po.mask_text("Addus HomeCare is one of the nation's largest. Why Addus? Addus's caregivers", v)
    assert "Addus" not in t and t.count("the Company") == 3


def test_masking_skips_common_first_words():
    assert "American" not in po.name_variants("American Financial Group, Inc.", "afginc.com")


def test_pages_only_instructions():
    instr = po.pages_only_instructions()
    assert "Use only the website pages below" in instr
    assert "First, say whether you know this company" not in instr
    assert "Use what you know" not in instr


def test_no_pages_gives_empty_prompt():
    prompt, lines = po.build({"IQ_COMPANY_ID": "X", "company_name": "X Inc", "website": "x.com", "pages": []})
    assert prompt == "" and lines == {}
