"""Tests for the facet check against the saved website pages
(verify_facets.py). No model is called."""

import facets as fc
import verify_facets as vf


def facet(value, status="filled", category=""):
    return {"status": status, "value": value, "category": category, "source": ["model knowledge"],
            "quotes": [], "flags": []}


def profile():
    """A Carlisle-like profile: one outdated product line."""
    facets = {f.name: facet("", "unknown") for f in fc.FACETS}
    facets.update(
        offering_description=facet("Makes roofing and building envelope products for commercial buildings."),
        primary_products=facet("roofing membranes; insulation; industrial finishing equipment"),
        primary_services=facet("", "not_applicable"),
        customer_segment=facet("B2B: roofing contractors; B2G: schools", category="B2B; B2G"),
        company_size=facet("large", category="large"),
    )
    return {"IQ_COMPANY_ID": "IQ1", "company_name": "Example Co", "website": "example.com",
            "prompt_version": fc.PROMPT_VERSION, "created_at": "2026-10-25T00:00:00Z",
            "llm_status": "ok", "businesses": [{"business_id": "B1", "business": "building products",
                                                "facets": facets}]}


def record(words_per_page=150, pages=3):
    def page(i):
        # distinct text per page: blocks repeated across pages are sent once
        filler = " ".join([f"building envelope products page{i}"] * (words_per_page // 4))
        return {"page_id": f"P{i}", "url": f"https://example.com/{i}", "category": "about",
                "title": f"Page {i}", "meta": "", "blocks": [f"We make roofing membranes (page {i}). {filler}",
                                                              f"Our businesses are Construction Materials and "
                                                              f"Weatherproofing (page {i})."]}
    return {"IQ_COMPANY_ID": "IQ1", "company_name": "Example Co", "website": "example.com",
            "status": "ok", "pages": [page(i) for i in range(1, pages + 1)]}


def test_claims_split_lists_and_categories_skip_size_unknown_and_not_applicable():
    claims = vf.profile_claims(profile())
    by_facet = {}
    for c in claims:
        by_facet.setdefault(c["facet"], []).append(c["claim"])
    assert by_facet["primary_products"] == ["roofing membranes", "insulation", "industrial finishing equipment"]
    assert by_facet["customer_segment"] == ["B2B: roofing contractors", "B2G: schools"]
    assert len(by_facet["offering_description"]) == 1             # core offering: one claim
    assert "company_size" not in by_facet                          # judged from scale
    assert "primary_services" not in by_facet                      # not applicable
    assert "end_markets" not in by_facet                           # unknown
    assert [c["id"] for c in claims if c["facet"] == "primary_products"] == ["B1.F2.1", "B1.F2.2", "B1.F2.3"]


def test_prompt_has_claims_and_labeled_page_lines_and_schema_limits_ids():
    claims = vf.profile_claims(profile())
    prompt, lines = vf.build_prompt(record(), claims)
    assert "B1.F2.3 (Primary products): industrial finishing equipment" in prompt
    assert "[P1.1]" in prompt and "P1.1" in lines
    assert prompt.startswith(vf.INSTRUCTIONS)
    schema = vf.answer_schema([c["id"] for c in claims])
    item = schema["properties"]["claims"]["items"]
    assert item["properties"]["id"]["enum"] == [c["id"] for c in claims]
    assert item["properties"]["verdict"]["enum"] == ["supported", "contradicted", "not mentioned"]


def test_thin_page_guard():
    assert vf.page_coverage(vf.build_prompt(record(), [])[1])["adequate"]
    thin = vf.page_coverage(vf.build_prompt(record(words_per_page=30, pages=1), [])[1])
    assert not thin["adequate"] and thin["pages"] == 1


def test_code_decides_verdicts_from_valid_citations():
    claims = vf.profile_claims(profile())
    _, lines = vf.build_prompt(record(), claims)
    urls = {"P1": "https://example.com/1"}
    ids = {c["claim"]: c["id"] for c in claims}
    raw = {"claims": [
        {"id": ids["roofing membranes"], "verdict": "supported", "cite": ["[P1.2]"], "says": ""},
        {"id": ids["insulation"], "verdict": "supported", "cite": ["P9.9"], "says": ""},    # line not in prompt
        {"id": ids["industrial finishing equipment"], "verdict": "contradicted", "cite": ["P1.3"],
         "says": "only construction materials and weatherproofing"},
        {"id": ids["B2B: roofing contractors"], "verdict": "not mentioned", "cite": [], "says": ""},
        {"id": ids["B2B: roofing contractors"], "verdict": "supported", "cite": ["P1.2"], "says": ""},   # repeat
        {"id": "B9.F1.1", "verdict": "supported", "cite": ["P1.2"], "says": ""},
    ]}
    out, issues = vf.apply_verdicts(claims, raw, lines, urls, {"adequate": True})
    v = {c["claim"]: c for c in out}
    assert v["roofing membranes"]["verdict"] == "supported"
    assert v["roofing membranes"]["quotes"][0]["url"] == "https://example.com/1"
    assert v["insulation"]["verdict"] == "not_on_pages"
    assert v["insulation"]["flags"] == ["citation_not_found"]
    assert v["industrial finishing equipment"]["verdict"] == "contradicted"
    assert v["B2B: roofing contractors"]["verdict"] == "not_on_pages"    # first answer kept
    assert v["B2G: schools"]["flags"] == ["not_answered"]
    assert {"unknown_id:B9.F1.1", f"duplicate_id:{ids['B2B: roofing contractors']}"} <= set(issues)


def test_not_mentioned_on_thin_pages_is_not_checkable_but_citations_still_count():
    claims = vf.profile_claims(profile())[:2]
    lines = {"P1.1": "We make roofing membranes."}
    raw = {"claims": [{"id": claims[0]["id"], "verdict": "not mentioned", "cite": [], "says": ""},
                      {"id": claims[1]["id"], "verdict": "supported", "cite": ["P1.1"], "says": ""}]}
    out, _ = vf.apply_verdicts(claims, raw, lines, {}, {"adequate": False})
    assert [c["verdict"] for c in out] == ["not_checkable", "supported"]


def test_facet_verdict_rollup():
    assert vf.facet_verdict([]) == "not_checked"
    assert vf.facet_verdict(["supported", "contradicted"]) == "contradicted"
    assert vf.facet_verdict(["supported", "supported"]) == "supported"
    assert vf.facet_verdict(["supported", "not_on_pages"]) == "partly_supported"
    assert vf.facet_verdict(["not_on_pages", "not_checkable"]) == "not_on_pages"
    assert vf.facet_verdict(["not_checkable"]) == "not_checkable"
