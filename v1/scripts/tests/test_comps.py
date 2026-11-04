"""
Tests for the comp universe (universe.py) and the facet prompt and checks (facets.py).

Run from v0/:  python -m pytest tests -q
"""

import math

import pandas as pd
import pytest

import facets as fc
import universe as uv


# ---------------------------------------------------------------- universe

def test_financials_split_from_company_info():
    info, financials = uv.load_list()
    assert not set(uv.FINANCIAL_COLUMNS) & set(info.columns)
    assert list(financials.columns) == ["IQ_COMPANY_ID", *uv.FINANCIAL_COLUMNS]


def test_sic_codes_stay_zero_padded():
    info, _ = uv.load_list()
    bv = info[info["target_company_name"].str.startswith("BrightView")].iloc[0]
    assert (bv["target_sic4_code"], bv["target_sic2_code"]) == ("0700", "07")


def test_candidates_need_us_hq_and_listed_sic2():
    info = pd.DataFrame({"IQ_COMPANY_ID": ["a", "b", "c"],
                         "target_country_iso3": ["USA", "CAN", "USA"],
                         "target_sic2_code": ["35", "35", "99"]})
    out = uv.select_candidates(info, target_sic2={"35"})
    assert out["candidate"].tolist() == [True, False, False]


@pytest.mark.parametrize("multiple, kept, reason", [
    (3.0, True, ""), (30.0, True, ""), (10.0, True, ""),
    (2.99, False, "below_3"), (30.01, False, "above_30"), (-5.0, False, "below_3"),
    (math.nan, False, "missing"),
])
def test_multiple_range_is_inclusive(multiple, kept, reason):
    fin = pd.DataFrame({"IQ_COMPANY_ID": ["x"], "target_ev_to_ebitda": [multiple]})
    row = uv.multiple_check(fin).iloc[0]
    assert (row["kept"], row["drop_reason"]) == (kept, reason)


def test_universe_on_snapshot():
    companies, financials = uv.build_universe()
    assert len(companies) == 560 and companies["candidate"].all()
    assert companies["in_universe"].sum() == 533     # 20 above 30, 7 below 3
    assert list(financials.columns) == ["IQ_COMPANY_ID", *uv.FINANCIAL_COLUMNS]


# ---------------------------------------------------------------- facets

def test_twelve_facets_numbered_f1_to_f12():
    assert len(fc.FACETS) == 12
    for pages in (False, True):
        props = fc.answer_schema(pages)["$defs"]["BusinessAnswer"]["properties"]
        assert set(fc.FACET_NAMES) <= set(props)
    assert fc.FACET_ID["offering_description"] == "F1"
    assert fc.FACET_ID["regulatory_exposure"] == "F12"


def test_citations_asked_only_with_pages():
    # the facets are the same either way; with pages one list of citations is added
    for pages in (False, True):
        facet = fc.answer_schema(pages)["$defs"]["Facet_end_markets"]["properties"]
        assert set(facet) == {"status", "value"}
    assert "citations" not in fc.answer_schema(False)["properties"]
    assert fc.answer_schema(True)["properties"]["citations"] == {"type": "array", "items": {"type": "string"}}


def empty(f):
    shape = {"text": {"value": ""}, "one of": {"category": "", **({"detail": ""} if f.detail else {})},
             "any of": {"items": []}}[f.kind]
    return {"status": "unknown", **shape}


def business(name="widgets", **overrides):
    """One business with every facet unknown; overrides fill some facets."""
    raw = {"business": name, **{f.name: empty(f) for f in fc.FACETS}}
    for facet, fields in overrides.items():
        raw[facet] = {**raw[facet], "status": "filled", **fields}
    return raw


def answer(pages=True, knows_company=True, citations=(), businesses=None, **overrides):
    """A valid answer: one business with the overrides, or the businesses
    given (several only with splitting on, see split_on). pages: the answer to
    a prompt with pages, which lists citations."""
    listed = [business(**overrides)] if businesses is None else businesses
    raw = {"knows_company": knows_company, "notes": ""}
    if fc.SPLIT_BUSINESSES:
        raw["businesses"] = listed
    else:
        assert len(listed) == 1, "several businesses need the split_on fixture"
        raw["company"] = listed[0]
    if pages:
        raw["citations"] = list(citations)
    return raw


@pytest.fixture
def split_on(monkeypatch):
    """Business splitting on (versions f-j; off since 2026-10-25)."""
    monkeypatch.setattr(fc, "SPLIT_BUSINESSES", True)


LINES = {"P1.1": "We design rooftop heating and cooling units for commercial buildings."}
URLS = {"P1": "https://example.com/"}


def check(raw, lines=LINES, urls=URLS):
    """The first business's checked facets."""
    return fc.check_answer(raw, lines, urls)["businesses"][0]["facets"]


def test_unrelated_businesses_get_own_profiles(split_on):
    raw = answer(businesses=[business("supermarkets", primary_products={"value": "groceries"}),
                             business("car dealerships", primary_products={"value": "new cars"})])
    out = fc.check_answer(raw, LINES, URLS)
    assert [(b["business_id"], b["business"]) for b in out["businesses"]] ==         [("B1", "supermarkets"), ("B2", "car dealerships")]
    assert out["businesses"][1]["facets"]["primary_products"]["value"] == "new cars"
    assert out["issues"] == []


@pytest.mark.parametrize("count, issue", [(0, "no_business"), (5, "too_many_businesses")])
def test_business_count_problems_flagged(count, issue, split_on):
    raw = answer(businesses=[business(f"b{i}") for i in range(count)])
    assert issue in fc.check_answer(raw, LINES, URLS)["issues"]


def test_without_pages_source_is_model_knowledge():
    out = check(answer(pages=False, end_markets={"value": "commercial buildings"}),
                lines={}, urls={})
    assert out["end_markets"]["source"] == ["model knowledge"] and out["end_markets"]["flags"] == []
    assert out["primary_products"]["source"] == []          # unknown: no source


def test_without_pages_citations_are_rejected():
    with pytest.raises(Exception):
        check(answer(pages=True, end_markets={"value": "commercial buildings"}), lines={}, urls={})


def test_cited_line_is_looked_up_with_its_url():
    out = check(answer(end_markets={"value": "commercial buildings"},
                       citations=["B1 end_markets: P1.1"]))["end_markets"]
    assert out["source"] == ["https://example.com/"]
    assert out["quotes"] == [{"block": "P1.1", "page": "P1", "url": "https://example.com/",
                              "quote": LINES["P1.1"], "quote_found": True}]
    assert out["flags"] == []


def test_with_pages_an_uncited_facet_of_a_known_company_is_model_knowledge():
    out = check(answer(end_markets={"value": "commercial buildings"}))["end_markets"]
    assert out["source"] == ["model knowledge"] and out["flags"] == []


@pytest.mark.parametrize("fields, citations, knows, flag", [
    ({}, ["B1 end_markets: P1.9"], True, "quote_not_found"),       # a label not in the prompt
    ({}, [], False, "website_without_quote"),                      # unknown company, nothing cited
    ({"value": ""}, [], True, "no_value"),
])
def test_source_problems_flagged_not_dropped(fields, citations, knows, flag):
    out = check(answer(knows_company=knows, citations=citations,
                       end_markets={"value": "data centers", **fields}))
    assert flag in out["end_markets"]["flags"]


def test_not_applicable_needs_no_citation():
    # Andersen Group, 2026-10-24: a services firm's products, from the pages, no citation
    out = check(answer(knows_company=False, primary_products={"status": "not_applicable", "value": ""}))
    assert out["primary_products"]["flags"] == []


def test_prompt_describes_the_company_now_and_splits_only_unrelated_businesses(split_on):
    prompt, _ = fc.build_prompt(RECORD, with_pages=False)
    assert "Describe the company as it is now" in prompt and "minority stake" in prompt
    assert "the same business in different regions" in prompt and "When in doubt, it is one business" in prompt


def test_one_profile_per_company_by_default():
    # 2026-10-25: no splitting; the schema has room for one business only
    assert not fc.SPLIT_BUSINESSES
    schema = fc.answer_schema(False)
    assert "company" in schema["properties"] and "businesses" not in schema["properties"]
    prompt, _ = fc.build_prompt(RECORD, with_pages=False)
    assert "Describe the whole company as one business" in prompt
    assert "Count separate businesses" not in prompt
    out = fc.check_answer(answer(pages=False, end_markets={"value": "x"}), {}, {})
    assert [b["business_id"] for b in out["businesses"]] == ["B1"]
    with pytest.raises(Exception):     # a list of businesses doesn't fit the schema
        fc.check_answer({"knows_company": True, "businesses": [business("a"), business("b")],
                         "notes": ""}, {}, {})


def test_citation_that_cant_be_read_is_an_issue():
    out = fc.check_answer(answer(end_markets={"value": "data centers"},
                                 citations=["end markets come from P1.1"]), LINES, URLS)
    assert "citation_not_read" in out["issues"]
    assert out["businesses"][0]["facets"]["end_markets"]["quotes"] == []


def test_any_of_keeps_detail_per_category():
    out = check(answer(customer_segment={"items": [
        {"category": "B2B", "detail": "mechanical contractors; building owners"},
        {"category": "B2G", "detail": "school districts"}]}))["customer_segment"]
    # a semicolon inside a detail becomes a comma, so the value splits back cleanly
    assert out["value"] == "B2B: mechanical contractors, building owners; B2G: school districts"
    assert out["category"] == "B2B; B2G" and out["flags"] == []


@pytest.mark.parametrize("category, detail, stored", [
    ("medium", "medium: environmental permits", "environmental permits"),
    ("high", "High : utility rates set by the state", "utility rates set by the state"),
    ("direct sales", "direct sales team calls on hospitals", "direct sales team calls on hospitals"),
    ("medium", "permits; safety rules", "permits, safety rules"),
])
def test_detail_drops_a_repeat_of_its_category(category, detail, stored):
    assert fc.clean_detail(category, detail) == stored


def test_one_of_keeps_detail():
    out = check(answer(regulatory_exposure={"category": "high",
                                            "detail": "devices need FDA clearance"}))
    assert (out["regulatory_exposure"]["value"], out["regulatory_exposure"]["category"]) == \
        ("high: devices need FDA clearance", "high")


def test_company_size_is_a_category_without_text():
    # no free text, so no room for a figure ("five thousand employees")
    props = fc.answer_schema(False)["$defs"]["Facet_company_size"]["properties"]
    assert set(props) == {"status", "category"}
    assert props["category"]["enum"] == ["small", "mid-sized", "large", "among the largest", ""]
    out = check(answer(company_size={"category": "mid-sized"}))["company_size"]
    assert (out["value"], out["category"], out["flags"]) == ("mid-sized", "mid-sized", [])


def test_company_size_with_text_rejected():
    with pytest.raises(Exception):
        check(answer(company_size={"category": "large", "detail": "five thousand employees"}))


@pytest.mark.parametrize("name, fields", [
    ("geography_served", {"category": "mars"}),               # one of: not in the list
    ("regulatory_exposure", {"category": "moderate"}),        # the list says medium
    ("customer_segment", {"items": [{"category": "partners", "detail": ""}]}),
    ("customer_segment", {"value": "B2B"}),                   # wrong shape for a category facet
    ("end_markets", {"source": "website"}),                   # no source field: code decides
])
def test_answer_outside_schema_rejected(name, fields):
    with pytest.raises(Exception):
        check(answer(**{name: fields}))


RECORD = {"company_name": "Acme Widgets, Inc.", "website": "www.acmewidgets.com",
          "pages": [{"page_id": "P1", "url": "https://www.acmewidgets.com/about",
                     "title": "About Acme", "meta": "", "blocks": ["Acme makes rooftop units."]}]}


def test_prompt_gives_name_and_website():
    prompt, lines = fc.build_prompt(RECORD, with_pages=False)
    assert "Company: Acme Widgets, Inc." in prompt and "Website: www.acmewidgets.com" in prompt
    assert "<page" not in prompt and lines == {} and '"citations"' not in prompt


def test_prompt_with_pages_labels_each_line_without_urls():
    prompt, lines = fc.build_prompt(RECORD, with_pages=True)
    assert '<page id="P1">' in prompt and "[P1.2] Acme makes rooftop units." in prompt
    assert lines == {"P1.1": "About Acme", "P1.2": "Acme makes rooftop units."}
    assert '"citations"' in prompt and "https://" not in prompt
    assert fc.input_fingerprint(RECORD, True) != fc.input_fingerprint(RECORD, False)


def test_page_text_stops_at_word_budget(monkeypatch):
    monkeypatch.setattr(fc, "MAX_INPUT_WORDS", 4)
    record = {**RECORD, "pages": [{**RECORD["pages"][0], "title": "",
                                   "blocks": ["one two three", "four five six", "seven"]}]}
    _, lines = fc.build_prompt(record, with_pages=True)
    assert lines == {"P1.1": "one two three", "P1.2": "four"}


def test_load_profiles_reads_every_version_with_its_run(tmp_path):
    import json
    from fill_facets import load_profiles
    run_dir = tmp_path / "codex_runs" / "X" / "t1"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({"model": "gpt-6-luna", "seconds": 9.5,
                                                  "usage": {"input_tokens": 100, "output_tokens": 20}}))
    facets = {"status": "filled", "value": "x", "category": "", "source": ["model knowledge"],
              "quotes": [], "flags": []}
    old = {"IQ_COMPANY_ID": "X", "prompt_version": "e", "llm_status": "ok", "created_at": "1",
           "facets": {"end_markets": facets, "primary_products": {**facets, "status": "unknown"}}}
    new = {"IQ_COMPANY_ID": "X", "prompt_version": "g", "llm_status": "ok", "created_at": "2",
           "llm_run_dir": "codex_runs/X/t1",
           "businesses": [{"business_id": "B1", "business": "a", "facets": {"end_markets": facets}},
                          {"business_id": "B2", "business": "b", "facets": {"end_markets": facets}}]}
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles_history").mkdir()
    (tmp_path / "profiles" / "X.json").write_text(json.dumps(new))
    (tmp_path / "profiles_history" / "X_old.json").write_text(json.dumps(old))
    out = load_profiles(tmp_path).set_index(["prompt_version", "business_id"])
    assert sorted(out.index) == [("e", "B1"), ("g", "B1"), ("g", "B2")]
    assert (out.loc[("e", "B1"), "facets_filled"], out.loc[("e", "B1"), "facets_total"]) == (1, 2)
    assert out.loc[("e", "B1"), "model"] == "default"            # no run.json
    assert (out.loc[("g", "B2"), "model"], out.loc[("g", "B2"), "output_tokens"]) == ("gpt-6-luna", 20)


def test_tables_written_before_any_profile(tmp_path):
    # e.g. a run stopped by the usage limit before its first answer
    from fill_facets import write_tables
    write_tables(tmp_path)
    table = pd.read_csv(tmp_path / "tables" / "facets.csv")
    assert len(table) == 533 and table["llm_status"].eq("not_run").all()


# ---------------------------------------------------------------- Claude backend (no API call)

def fake_message(stop_reason="end_turn", text='{"businesses": [], "notes": ""}', category=None):
    from types import SimpleNamespace as NS
    return NS(model="claude-haiku-5-5", _request_id="req_1", stop_reason=stop_reason,
              stop_details=NS(category=category) if category else None,
              usage=NS(input_tokens=100, cache_read_input_tokens=50, cache_creation_input_tokens=0,
                       output_tokens=20),
              content=[NS(type="thinking", thinking=""), NS(type="text", text=text)],
              to_json=lambda: "{}")


def fake_client(monkeypatch, reply):
    """claude_client() returns a stand-in whose messages.create records its
    arguments and returns (or raises) reply."""
    from types import SimpleNamespace as NS
    import fill_facets as ff
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(ff, "claude_client", lambda: NS(messages=NS(create=create)))
    return sent


def test_claude_answer_saved_with_usage(monkeypatch, tmp_path):
    import fill_facets as ff
    sent = fake_client(monkeypatch, fake_message())
    out = ff.call_claude("INSTRUCTIONS\n\nthe company", tmp_path, fc.answer_schema(False),
                         "claude-haiku-5-5", "low", instructions_len=len("INSTRUCTIONS"))
    assert out["llm_status"] == "ok" and out["text"] == '{"businesses": [], "notes": ""}'
    assert (tmp_path / "response.json").read_text(encoding="utf-8") == out["text"]
    assert out["usage"] == {"input_tokens": 150, "cached_input_tokens": 50,
                            "cache_write_input_tokens": 0, "output_tokens": 20}
    assert sent["model"] == "claude-haiku-5-5" and sent["output_config"]["effort"] == "low"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    # the instructions, the same for every company, are the cached system prompt
    assert sent["system"] == [{"type": "text", "text": "INSTRUCTIONS",
                               "cache_control": {"type": "ephemeral"}}]
    assert sent["messages"] == [{"role": "user", "content": "the company"}]


@pytest.mark.parametrize("reply, status, stop", [
    (fake_message("refusal", text="", category="general_harms"), "refusal", False),
    (fake_message("max_tokens"), "truncated", False),
])
def test_claude_refusal_and_cutoff_recorded(monkeypatch, tmp_path, reply, status, stop):
    import fill_facets as ff
    fake_client(monkeypatch, reply)
    out = ff.call_claude("p", tmp_path, fc.answer_schema(False), "claude-haiku-5-5", None)
    assert out["llm_status"] == status and not out.get("stop_run")
    assert not (tmp_path / "response.json").exists()


def test_claude_out_of_credit_stops_the_run(monkeypatch, tmp_path):
    import anthropic
    import httpx
    import fill_facets as ff
    error = anthropic.BadRequestError(
        "Your credit balance is too low to access the Anthropic API.",
        response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com")),
        body=None)
    fake_client(monkeypatch, error)
    out = ff.call_claude("p", tmp_path, fc.answer_schema(False), "claude-haiku-5-5", None)
    assert out["llm_status"] == "api_error" and out["stop_run"]


def test_profile_from_another_model_is_redone():
    import fill_facets as ff
    profile = {"llm_status": "ok", "prompt_version": fc.PROMPT_VERSION, "model": "gpt-6-luna",
               "input_sha256": fc.input_fingerprint(RECORD, False)}
    assert ff.is_current(profile, RECORD, "gpt-6-luna")
    assert not ff.is_current(profile, RECORD, "claude-haiku-5-5")


# ---------------------------------------------------------------- second pass: pages fill gaps only

def test_pages_fill_only_unknown_facets():
    known = fc.check_answer(answer(pages=False, end_markets={"value": "data centers"}), {}, {})
    paged = fc.check_answer(answer(end_markets={"value": "page says hospitals"},
                                   primary_products={"value": "rooftop units"},
                                   citations=["B1 end_markets: P1.1", "B1 primary_products: P1.1"]),
                            LINES, URLS)
    filled, matched = fc.fill_gaps(known["businesses"], paged["businesses"])
    facets = known["businesses"][0]["facets"]
    assert matched and filled == ["B1 primary_products"]
    assert facets["end_markets"]["value"] == "data centers"          # what the model knew stays
    assert facets["primary_products"]["value"] == "rooftop units"
    assert facets["primary_products"]["source"] == ["https://example.com/"]


def test_company_the_model_doesnt_know_keeps_nothing():
    # it said it doesn't know the company but guessed anyway: code drops the guesses
    raw = answer(pages=False, knows_company=False,
                 end_markets={"value": "commercial construction"},
                 primary_products={"value": "rooftop HVAC units"})
    out = fc.check_answer(raw, {}, {})
    assert out["knows_company"] is False and out["issues"] == ["company_not_known"]
    assert all(f["status"] == "unknown" for f in out["businesses"][0]["facets"].values())


def test_with_pages_an_unknown_company_is_described_from_them():
    raw = answer(knows_company=False, end_markets={"value": "commercial buildings"},
                 citations=["B1 end_markets: P1.1"])
    out = check(raw)
    assert out["end_markets"]["value"] == "commercial buildings"


def test_pages_answer_taken_whole_when_nothing_was_known(split_on):
    known = fc.check_answer(answer(pages=False, knows_company=False), {}, {})
    paged = fc.check_answer(answer(knows_company=False, citations=["B1 end_markets: P1.1"],
                                   businesses=[business("a", end_markets={"value": "x"}), business("b")]),
                            LINES, URLS)
    filled, matched = fc.fill_gaps(known["businesses"], paged["businesses"])
    assert matched and filled == ["B1 end_markets"]
    assert [b["business"] for b in known["businesses"]] == ["a", "b"]


def test_prompt_forbids_guessing_from_the_name():
    prompt, _ = fc.build_prompt(RECORD, with_pages=False)
    assert '"knows_company"' in prompt and "do not guess what" in prompt
    assert "may be fictional" in prompt


def test_pages_fill_nothing_when_businesses_differ(split_on):
    known = fc.check_answer(answer(pages=False, end_markets={"value": "data centers"}), {}, {})
    paged = fc.check_answer(answer(businesses=[business("a"), business("b")]), LINES, URLS)
    assert fc.fill_gaps(known["businesses"], paged["businesses"]) == ([], False)


def test_two_passes_end_to_end(monkeypatch, tmp_path):
    """First pass for every company without pages; second pass only for the one
    left with an unknown facet, with its pages. A second pass that fails (API
    error) is retried by the next run; after that a rerun does nothing."""
    import json
    import sys
    import fill_facets as ff
    universe = pd.DataFrame({"IQ_COMPANY_ID": ["A", "B"], "target_company_name": ["Acme", "Birch"],
                             "target_ciq_website": ["acme.com", "birch.com"],
                             "target_ciq_ticker": ["ACM", "BIR"], "in_universe": [True, True]})
    pages = tmp_path / "page_text"
    pages.mkdir()
    for iq in ("A", "B"):
        (pages / f"{iq}.json").write_text(json.dumps({"status": "ok", "pages": [
            {"page_id": "P1", "url": f"https://{iq}.com/", "category": "home", "title": "",
             "meta": "", "blocks": ["We design rooftop heating and cooling units."]}]}))
    monkeypatch.setattr(ff, "build_universe", lambda: (universe, None))
    monkeypatch.setattr(ff, "SCRAPE_PAGE_TEXT", pages)
    monkeypatch.setattr(ff, "claude_api_key", lambda: "test")
    calls, second_pass_tries = [], []

    def fake_fill_one(record, out_dir, args, workdir, with_pages=False):
        calls.append((record["IQ_COMPANY_ID"], with_pages, len(record["pages"])))
        if with_pages:
            second_pass_tries.append(record["IQ_COMPANY_ID"])
        if with_pages and len(second_pass_tries) == 1:            # the first try fails
            return {"llm_status": "api_error", "error": "400: compiled grammar is too large",
                    "llm_run_dir": "codex_runs/x", "input_figures": []}
        _, lines = fc.build_prompt(record, with_pages)
        if not with_pages:   # A: everything known; B: products unknown
            raw = answer(pages=False, **{f.name: ({"value": "x"} if f.kind == "text" else
                         {"category": f.categories[0], **({"detail": ""} if f.detail else {})}
                         if f.kind == "one of" else {"items": [{"category": f.categories[0], "detail": ""}]})
                         for f in fc.FACETS
                         if not (record["IQ_COMPANY_ID"] == "B" and f.name == "primary_products")})
        else:
            raw = answer(primary_products={"value": "rooftop units"},
                         citations=["B1 primary_products: P1.1"])
        urls = {p["page_id"]: p["url"] for p in record["pages"]}
        return {"llm_status": "ok", "answer": fc.check_answer(raw, lines, urls),
                "llm_run_dir": "codex_runs/x", "input_figures": []}
    monkeypatch.setattr(ff, "fill_one", fake_fill_one)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["fill_facets.py", "--out", str(out)])
    ff.main()
    assert sorted(calls[:2]) == [("A", False, 0), ("B", False, 0)]    # first pass: no pages
    assert calls[2:] == [("B", True, 1)]                              # second pass: B, with pages
    b = json.loads((out / "profiles" / "B.json").read_text())
    assert b["gap_fill"]["llm_status"] == "api_error"
    assert b["businesses"][0]["facets"]["primary_products"]["status"] == "unknown"
    calls.clear()
    ff.main()                                     # retries the failed second pass only
    assert calls == [("B", True, 1)]
    b = json.loads((out / "profiles" / "B.json").read_text())
    assert b["gap_fill"]["filled"] == ["B1 primary_products"]
    assert b["businesses"][0]["facets"]["primary_products"]["value"] == "rooftop units"
    assert b["businesses"][0]["facets"]["end_markets"]["value"] == "x"   # first pass kept
    a = json.loads((out / "profiles" / "A.json").read_text())
    assert "gap_fill" not in a
    table = pd.read_csv(out / "tables" / "facets.csv", dtype=str).fillna("")
    assert table.set_index("IQ_COMPANY_ID").loc["B", "filled_from_pages"] == "primary_products"
    calls.clear()
    ff.main()                                     # nothing left to do
    assert calls == []


def test_second_pass_runs_again_after_a_rescrape(monkeypatch, tmp_path):
    """A company the model doesn't know, whose pages give nothing (a browser
    error screen), stays unknown and isn't called again; once its pages are
    rescraped, the second pass runs again and fills it."""
    import json
    import sys
    import fill_facets as ff
    universe = pd.DataFrame({"IQ_COMPANY_ID": ["E"], "target_company_name": ["Englewood"],
                             "target_ciq_website": ["englewood.com"], "target_ciq_ticker": ["ENG"],
                             "in_universe": [True]})
    pages = tmp_path / "page_text"
    pages.mkdir()

    def scrape(text):
        (pages / "E.json").write_text(json.dumps({"status": "ok", "pages": [
            {"page_id": "P1", "url": "http://englewood.com/en/home", "category": "home", "title": "",
             "meta": "", "blocks": [text]}]}))
    scrape("Your connection is not private")
    monkeypatch.setattr(ff, "build_universe", lambda: (universe, None))
    monkeypatch.setattr(ff, "SCRAPE_PAGE_TEXT", pages)
    monkeypatch.setattr(ff, "claude_api_key", lambda: "test")
    calls = []

    def fake_fill_one(record, out_dir, args, workdir, with_pages=False):
        calls.append(with_pages)
        prompt, lines = fc.build_prompt(record, with_pages)
        if not with_pages:
            raw = answer(pages=False, knows_company=False)
        elif "cosmetics" in prompt:
            raw = answer(knows_company=False, end_markets={"value": "beauty brands"},
                         citations=["B1 end_markets: P1.1"])
        else:
            raw = answer(knows_company=False)      # the error screen tells it nothing
        urls = {p["page_id"]: p["url"] for p in record["pages"]}
        return {"llm_status": "ok", "answer": fc.check_answer(raw, lines, urls),
                "llm_run_dir": "codex_runs/x", "input_figures": []}
    monkeypatch.setattr(ff, "fill_one", fake_fill_one)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["fill_facets.py", "--out", str(out)])
    ff.main()
    assert calls == [False, True]
    calls.clear()
    ff.main()                                     # same pages: not called again
    assert calls == []
    scrape("We develop and manufacture skincare and cosmetics for beauty brands.")
    ff.main()                                     # rescraped: the second pass runs again
    assert calls == [True]
    e = json.loads((out / "profiles" / "E.json").read_text())
    assert e["businesses"][0]["facets"]["end_markets"]["value"] == "beauty brands"


# ---------------------------------------------------------------- third pass: business splits

def three_businesses():
    raw = answer(pages=False, businesses=[business("building envelope", offering_description={"value": "roofing"}),
                                          business("interconnect", offering_description={"value": "cables"}),
                                          business("foodservice", offering_description={"value": "cups"})])
    return fc.check_answer(raw, {}, {})["businesses"]


def check_of(*statuses, cites=None):
    cites = cites or [["P1.1"]] * len(statuses)
    return {"checks": [{"business_id": f"B{i}", "status": s, "cite": c}
                       for i, (s, c) in enumerate(zip(statuses, cites), start=1)], "notes": ""}


def test_split_check_removes_businesses_the_website_doesnt_show(split_on):
    kept, record = fc.apply_split_check(three_businesses(), check_of("shown", "not shown", "not shown"),
                                        LINES, URLS)
    assert [(b["business_id"], b["business"]) for b in kept] == [("B1", "building envelope")]
    assert record["outcome"] == "removed"
    assert [b["business"] for b in record["removed"]] == ["interconnect", "foodservice"]
    assert record["businesses"][0]["quotes"][0]["url"] == "https://example.com/"


def test_split_check_renumbers_what_is_kept(split_on):
    kept, _ = fc.apply_split_check(three_businesses(), check_of("shown", "not shown", "shown"), LINES, URLS)
    assert [(b["business_id"], b["business"]) for b in kept] == [("B1", "building envelope"), ("B2", "foodservice")]


def test_split_check_removes_nothing_when_the_pages_show_no_business(split_on):
    businesses = three_businesses()
    kept, record = fc.apply_split_check(businesses, check_of("not shown", "not shown", "not shown"), LINES, URLS)
    assert kept == businesses and record["outcome"] == "not_checked" and record["removed"] == []


def test_split_check_shown_needs_a_real_line(split_on):
    # "shown" citing a label that wasn't in the prompt doesn't count
    kept, record = fc.apply_split_check(three_businesses(), check_of("shown", "shown", "shown",
                                        cites=[["P1.1"], ["P9.9"], []]), LINES, URLS)
    assert [b["business"] for b in kept] == ["building envelope"]
    assert [c["shown"] for c in record["businesses"]] == [True, False, False]


def test_split_check_reads_labels_in_brackets(split_on):
    # American Financial and Cass, 2026-10-24: the model wrote "[P1.6]"
    kept, record = fc.apply_split_check(three_businesses(), check_of("shown", "not shown", "not shown",
                                        cites=[["[P1.1]"], [], []]), LINES, URLS)
    assert record["outcome"] == "removed" and record["businesses"][0]["shown"]


def test_split_check_keeps_a_business_named_in_the_pages_and_flags_it(split_on):
    # Boston Omaha, 2026-10-24: billboards on the pages, model said not shown
    lines = {"P1.1": "Boston Omaha runs billboards, broadband and surety insurance businesses."}
    businesses = fc.check_answer(answer(pages=False, businesses=[
        business("outdoor advertising billboards"), business("rural broadband internet")]), {}, {})["businesses"]
    kept, record = fc.apply_split_check(businesses, check_of("not shown", "shown"), lines, URLS)
    assert [b["business"] for b in kept] == ["outdoor advertising billboards", "rural broadband internet"]
    assert record["outcome"] == "confirmed" and record["disputed"] == ["outdoor advertising billboards"]
    assert record["businesses"][0]["name_words_in_pages"] == ["billboards"]


def test_name_words_ignore_generic_and_shared_words():
    lines = {"P1.1": "Our specialty commercial insurance and annuity history."}
    assert fc.name_words_in_pages("retirement annuities and life insurance",
                                  ["specialty commercial insurance"], lines) == ["annuities"]
    assert fc.name_words_in_pages("foodservice products", ["building envelope"], lines) == []


def test_split_check_prompt_lists_the_businesses_and_the_pages(split_on):
    record = {**RECORD, "pages": [{**RECORD["pages"][0], "blocks": ["We make roofing membranes."]}]}
    prompt, lines = fc.split_check_prompt(record, three_businesses())
    assert "B1 building envelope: roofing" in prompt and "B3 foodservice: cups" in prompt
    assert "[P1.2] We make roofing membranes." in prompt and lines["P1.2"] == "We make roofing membranes."
    assert "Use only the pages" in prompt
    schema = fc.split_check_schema(["B1", "B2", "B3"])
    assert schema["properties"]["checks"]["items"]["properties"]["business_id"]["enum"] == ["B1", "B2", "B3"]


def test_third_pass_end_to_end(monkeypatch, tmp_path, split_on):
    """A company split into two: the third pass removes the business its pages
    don't show; a rerun does nothing; a company with no pages is flagged."""
    import json
    import sys
    import fill_facets as ff
    universe = pd.DataFrame({"IQ_COMPANY_ID": ["C", "N"], "target_company_name": ["Carlisle", "Nopages"],
                             "target_ciq_website": ["carlisle.com", "nopages.com"],
                             "target_ciq_ticker": ["CSL", "NOP"], "in_universe": [True, True]})
    pages = tmp_path / "page_text"
    pages.mkdir()
    (pages / "C.json").write_text(json.dumps({"status": "ok", "pages": [
        {"page_id": "P1", "url": "https://carlisle.com/", "category": "home", "title": "", "meta": "",
         "blocks": ["We make roofing and building envelope products."]}]}))
    monkeypatch.setattr(ff, "build_universe", lambda: (universe, None))
    monkeypatch.setattr(ff, "SCRAPE_PAGE_TEXT", pages)
    monkeypatch.setattr(ff, "claude_api_key", lambda: "test")
    checks = []

    def fake_fill_one(record, out_dir, args, workdir, with_pages=False):
        raw = answer(pages=False, businesses=[
            business("building envelope", **{f.name: ({"value": "x"} if f.kind == "text" else
                     {"category": f.categories[0], **({"detail": ""} if f.detail else {})}
                     if f.kind == "one of" else {"items": [{"category": f.categories[0], "detail": ""}]})
                     for f in fc.FACETS}),
            business("foodservice", **{f.name: ({"value": "y"} if f.kind == "text" else
                     {"category": f.categories[0], **({"detail": ""} if f.detail else {})}
                     if f.kind == "one of" else {"items": [{"category": f.categories[0], "detail": ""}]})
                     for f in fc.FACETS})])
        return {"llm_status": "ok", "answer": fc.check_answer(raw, {}, {}),
                "llm_run_dir": "codex_runs/x", "input_figures": []}

    def fake_check_split(record, profile, out_dir, args, workdir):
        checks.append(record["IQ_COMPANY_ID"])
        return {"llm_status": "ok", "llm_run_dir": "codex_runs/y", "raw": check_of("shown", "not shown")}
    monkeypatch.setattr(ff, "fill_one", fake_fill_one)
    monkeypatch.setattr(ff, "check_split", fake_check_split)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["fill_facets.py", "--out", str(out)])
    ff.main()
    assert checks == ["C"]                       # N has no pages: no call
    c = json.loads((out / "profiles" / "C.json").read_text())
    assert [b["business"] for b in c["businesses"]] == ["building envelope"]
    assert c["split_check"]["outcome"] == "removed"
    assert c["split_check"]["removed"][0]["facets"]["offering_description"]["value"] == "y"   # kept on record
    n = json.loads((out / "profiles" / "N.json").read_text())
    assert n["split_check"]["outcome"] == "not_checked" and "split_not_checked" in n["issues"]
    table = pd.read_csv(out / "tables" / "facets.csv", dtype=str).fillna("").set_index("IQ_COMPANY_ID")
    assert table.loc["C", "businesses_removed"] == "foodservice" and table.loc["C", "split_check"] == "removed"
    checks.clear()
    ff.main()
    assert checks == []


@pytest.mark.parametrize("text, found", [
    ("Sale of Annuity Business to MassMutual", True),                 # American Financial's site
    ("Carlisle completes sale of Carlisle Interconnect Technologies", True),
    ("The company divested its electrical products group in 2022", True),
    ("The spin-off of our consumer segment created two companies", True),
    ("We sold the specialty chemicals unit to focus on lithium", True),
    ("Point-of-sale terminals for retailers and restaurants", False),
    ("We offer wholesale of building products to contractors", False),
    ("Our sales team serves customers in all fifty states", False),
])
def test_divestiture_lines_found(text, found):
    assert bool(fc.divestiture_lines({"P1.1": text})) == found


def test_review_reasons_collect_what_the_fill_recorded():
    import fill_facets as ff
    facets = fc.check_answer(answer(pages=False, end_markets={"value": "x"}), {}, {})["businesses"][0]
    full = fc.check_answer(answer(pages=False, **{f.name: ({"value": "x"} if f.kind == "text" else
                           {"category": f.categories[0], **({"detail": ""} if f.detail else {})}
                           if f.kind == "one of" else {"items": [{"category": f.categories[0], "detail": ""}]})
                           for f in fc.FACETS}), {}, {})["businesses"][0]
    assert ff.review_reasons({"issues": []}, full) == []
    assert ff.review_reasons({"issues": []}, facets) == ["facet_unknown"]
    assert ff.review_reasons({"issues": ["company_not_known", "pages_mention_divestiture"]}, full) == \
        ["described_from_pages_only", "pages_mention_divestiture"]
    flagged = {**full, "facets": {**full["facets"], "end_markets": {**full["facets"]["end_markets"],
                                                                     "flags": ["website_without_quote"]}}}
    assert ff.review_reasons({"issues": []}, flagged) == ["facet_flagged"]


def test_page_lines_with_figures_left_out_of_prompt():
    record = {**RECORD, "pages": [{**RECORD["pages"][0], "title": "Get Up To $500 In 5 Minutes",
                                   "blocks": ["Acme makes rooftop units.",
                                              "A $1.4B company with 5,000 associates."]}]}
    prompt, lines = fc.build_prompt(record, with_pages=True)
    assert list(lines.values()) == ["Acme makes rooftop units."]
    assert fc.figures_in_input(prompt, True) == []


def test_figures_in_input_checks_only_the_company_part():
    prompt, _ = fc.build_prompt(RECORD, with_pages=False)
    assert fc.figures_in_input(prompt, False) == []          # the instructions name revenue etc.
    assert fc.figures_in_input(prompt + "\nRevenue of $2 billion", False)


def test_company_without_saved_pages_gets_prompt_without_pages():
    record = {**RECORD, "pages": []}
    assert fc.build_prompt(record, True) == fc.build_prompt(record, False)
