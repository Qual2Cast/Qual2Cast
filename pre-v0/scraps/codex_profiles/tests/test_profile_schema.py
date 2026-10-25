"""
Tests for the validation rules (profile_schema.py) and the masking and table
checks (step2_extract_profiles.py). The page-text filter tests are in
website_scrape/tests/.
Each case is a problem found while building the pipeline; the tests keep it
from coming back after a rule change.

Run from scraps/codex_profiles/:  python -m pytest tests -q
"""

import copy

import pytest
from pydantic import ValidationError

import profile_schema as pm
import step2_extract_profiles as ep

PAGES = {
    "P1": "Through a strong network of professional distributors, dealers, rental "
          "stores and retailers in more than 125 countries. Headquartered in Houston, Tx. "
          "Toro's Greensmaster™ eTriflex™ 3360 delivers precision. "
          "ACM Research's proprietary Space Alternated Phase Shift (SAPS™) technology. "
          "We design pressure energy recovery devices for desalination plants.",
}
REAL = "Through a strong network of professional distributors, dealers, rental stores and retailers"


def item(value, quote, field="customers"):
    return pm.ItemCheck.model_validate({"value": value, "quote": quote},
                                       context={"pages": PAGES, "field": field})


def error_type(exc: ValidationError) -> str:
    return exc.errors()[0]["type"]


def answer(**overrides) -> dict:
    """A minimal valid raw answer; fields not overridden are 'unknown'."""
    raw = {f: ({"status": "unknown", "value": "", "evidence": []} if f in pm.TEXT_FIELDS
               else {"status": "unknown", "items": []}) for f in pm.FIELDS}
    raw.update(identifying_terms=[], notes="")
    raw.update(overrides)
    return raw


def lst(*pairs):
    return {"status": "stated", "items": [{"value": v, "quote": q} for v, q in pairs]}


# ---------------------------------------------------------------- per-item rules

def test_real_quote_passes_and_records_its_page():
    assert item("Dealers", REAL).found_on == ["P1"]


def test_invented_quote_is_rejected():
    with pytest.raises(ValidationError) as exc:
        item("Hotels", "this sentence does not appear anywhere on the pages")
    assert error_type(exc.value) == "quote_not_found"


def test_quote_length_limits():
    with pytest.raises(ValidationError) as exc:
        item("Dealers", "dealers rental stores")                     # 3 words
    assert error_type(exc.value) == "quote_too_short"
    assert item("Houston", "Headquartered in Houston, Tx.")         # 4 words is enough


def test_financial_values_are_rejected_but_stickers_and_investors_are_not():
    with pytest.raises(ValidationError) as exc:
        item("Revenue of $4.5 billion", REAL)
    assert error_type(exc.value) == "financial"
    assert not pm.leaks_financials("cards, stickers, labels")       # "stickers" contains "ticker"
    assert pm.leaks_financials("ticker symbol ABC")
    assert not pm.leaks_financials("Institutional and retail investors")


def test_list_items_must_be_short():
    with pytest.raises(ValidationError) as exc:
        item(" ".join(["word"] * 25), REAL)
    assert error_type(exc.value) == "value_too_long"


def test_brand_quote_must_contain_the_brand():
    with pytest.raises(ValidationError) as exc:
        item("Exmark", REAL, field="brands")
    assert error_type(exc.value) == "brand_not_in_quote"


def test_trademark_symbols_do_not_break_matching():
    q = "Toro's Greensmaster eTriflex 3360 delivers precision."       # quoted without ™
    assert item("Greensmaster eTriflex 3360", q, field="brands")


def test_combined_brand_value_passes_if_one_name_is_quoted():
    q = "ACM Research's proprietary Space Alternated Phase Shift (SAPS) technology."
    assert item("SAPS; Space Alternated Phase Shift", q, field="brands")


# ---------------------------------------------------------------- field and answer rules

def test_status_must_match_items():
    p = pm.check_answer(pm.ProfileAnswer.model_validate(answer(
        customers={"status": "unknown", "items": [{"value": "Hotels", "quote": REAL}]},
        end_markets={"status": "stated", "items": []})), PAGES)
    assert p["customers"]["status"] == "unknown"
    assert p["customers"]["issues"][0]["type"] == "unknown_with_items"
    assert p["end_markets"]["status"] == "unknown"
    assert p["end_markets"]["issues"][0]["type"] == "stated_without_items"


def test_field_with_no_passing_item_is_unverified_and_duplicates_merge():
    p = pm.check_answer(pm.ProfileAnswer.model_validate(answer(
        customers=lst(("Hotels", "not on the page at all, invented")),
        sales_channels=lst(("Dealers", REAL), ("dealers", REAL)))), PAGES)
    assert p["customers"]["status"] == "unverified"
    assert pm.verified_values(p["sales_channels"]) == ["Dealers"]


@pytest.mark.parametrize("change", [
    lambda a: a["customer_types"]["items"].append({"value": "b2b_saas", "quote": REAL}),
    lambda a: a.pop("notes"),
    lambda a: a.update(extra_key=1),
])
def test_wrong_shape_is_rejected(change):
    raw = answer(customer_types={"status": "stated", "items": []})
    change(raw)
    with pytest.raises(ValidationError):
        pm.ProfileAnswer.model_validate(raw)


def test_schema_sent_to_codex_has_no_code_built_fields():
    props = pm.answer_schema()["properties"]
    assert not {"matching_summary", "evidence_quality", "page_relevance"} & set(props)


# ---------------------------------------------------------------- built in code

def test_summary_uses_only_verified_items_and_says_what_is_unknown():
    p = pm.check_answer(pm.ProfileAnswer.model_validate(answer(
        sales_channels=lst(("Dealers", REAL), ("Hotels", "invented quote not on any page")))), PAGES)
    summary = pm.build_summary(p)
    assert "Sales channels: Dealers." in summary and "Hotels" not in summary
    assert "Customers: not stated on the website." in summary


def test_evidence_quality_rule():
    def rated(*stated):
        return pm.rate_evidence({f: {"status": "stated" if f in stated else "unknown"}
                                 for f in pm.FIELDS})
    assert rated("products_services", "customers", "revenue_streams") == "sufficient"
    assert rated("products_services") == "partial"
    assert rated() == "insufficient"


def test_masking_keeps_generic_phrases_and_case_sensitive_brands():
    names = ep.name_variants("Energy Recovery, Inc.", "www.energyrecovery.com")
    text, _ = ep.mask("Makes pressure energy recovery devices. Energy Recovery sells them.", names, [])
    assert text == "Makes pressure energy recovery devices. the Company sells them."
    text, _ = ep.mask("Gives an advantage. Advantage mowers.", [], ["Advantage"])
    assert text == "Gives an advantage. [brand] mowers."


def test_model_never_sees_the_company_name_or_website():
    record = {"company_name": "Waters Corporation", "website": "www.waters.com",
              "pages": [{"page_id": "P1", "url": "https://www.waters.com/", "snapshot": "",
                         "title": "Waters | Lab instruments",
                         "meta": "WATERS makes chromatography systems.",
                         "blocks": ["Waters columns are tested in coastal waters at waters.com."]}]}
    prompt, pages = ep.build_prompt(record)
    assert "waters.com" not in prompt.lower() and "Waters" not in prompt and "WATERS" not in prompt
    assert "coastal waters" in prompt              # the ordinary word stays
    text, _ = ep.mask("Visit www.graco.com/us/en/about-graco/locations.html or gracoapps.de today.",
                      ep.name_variants("Graco Inc.", "www.graco.com"), [])
    assert "graco" not in text.lower() and text.endswith("today.")
    assert pages["P1"].startswith("the Company | Lab instruments")


def test_domain_stem_is_the_registered_name_not_a_subdomain():
    names = ep.name_variants("Quaker Chemical Corporation", "home.quakerhoughton.com")
    assert "home" not in names and "quakerhoughton" in names
    # the site uses the post-merger name
    text, _ = ep.mask("Quaker Houghton is there. Quaker fluids. Finding the AAON Way.",
                      names + ["AAON"], [])
    assert text == "the Company is there. the Company fluids. Finding the Company Way."
    # capitals and a leading abbreviation, both seen in Codex's identifying_terms
    text, _ = ep.mask("ASTEC plants. CPI secure cards.",
                      ep.name_variants("Astec Industries, Inc.", "www.astecindustries.com")
                      + ep.name_variants("CPI Card Group Inc.", "www.cpicardgroup.com"), [])
    assert text == "the Company plants. the Company secure cards."
    # generic first words are never masked on their own
    assert "Energy" not in ep.name_variants("Energy Recovery, Inc.", "www.energyrecovery.com")


def test_notes_with_financials_are_dropped():
    raw = answer(notes="The pages mention revenue of $2 billion.")
    p = ep.verify(raw, PAGES, ["Acme"])
    assert p["notes"] == "" and p["issues"][0]["type"] == "financial"


# ---------------------------------------------------------------- output tables

def good_row(**overrides) -> dict:
    p = ep.verify(answer(sales_channels=lst(("Dealers", REAL))), PAGES, ["Acme"])
    rec = {"IQ_COMPANY_ID": "IQ1", "scrape_status": "ok", "llm_status": "ok",
           "pages": [{"page_id": "P1", "url": "https://acme.com/"}], "profile": p}
    row = ep.flatten(rec)
    row.update(overrides)
    return row


def test_consistent_row_passes():
    pm.MatchingRow.model_validate(good_row(), context={"names": ["Acme"]})


@pytest.mark.parametrize("overrides", [
    {"customers": "Hotels"},                                      # value but status unknown
    {"sales_channels__sources": ""},                              # stated without a source
    {"customer_types": "b2b_saas", "customer_types__status": "stated",
     "customer_types__sources": "https://acme.com/"},             # tag outside the list
    {"notes": "Acme makes things."},                              # company name not masked
    {"evidence_quality": "sufficient"},                           # doesn't follow the rule
    {"target_revenue": "100"},                                    # a financial column
])
def test_inconsistent_rows_are_caught(overrides):
    with pytest.raises(ValidationError):
        pm.MatchingRow.model_validate(good_row(**overrides), context={"names": ["Acme"]})


def test_financial_rows_must_be_numbers():
    pm.FinancialRow.model_validate({"IQ_COMPANY_ID": "IQ1", "target_revenue": "1442.1",
                                    "target_ebitda": "", "target_margin": "0.15",
                                    "target_debt_to_revenue": "0.3", "target_ev_to_ebitda": "31"})
    with pytest.raises(ValidationError):
        pm.FinancialRow.model_validate({"IQ_COMPANY_ID": "IQ1", "target_revenue": "n/a",
                                        "target_ebitda": "", "target_margin": "",
                                        "target_debt_to_revenue": "", "target_ev_to_ebitda": ""})
