"""
Pydantic models for the Codex company profiles: the one definition of what a
profile is, used by step2_extract_profiles.py in two layers.

1. Shape (`ProfileAnswer`): what the model must return. Its JSON Schema is
   what Codex is given (--output-schema), and every answer is validated
   against it. Every list item is a {value, quote} pair (one quote per item),
   tags must come from fixed lists, no keys may be missing or extra. An answer
   that fails here is rejected as a whole.

2. Rules (`QuoteCheck`, `ItemCheck`): each item and quote is validated on its
   own against the scraped pages. An item that breaks a rule is dropped from
   the tables (kept in the profile JSON) with a named reason:
     quote_too_short     fewer than MIN_QUOTE_WORDS (4) words (brands: 1)
     quote_too_long      more than MAX_QUOTE_WORDS words
     quote_not_found     the quote isn't on any page the model was given
     brand_not_in_quote  a brand whose quote doesn't contain the brand name
     empty_value         blank value
     value_too_long      list item over MAX_ITEM_WORDS (20) words
     financial           value mentions money, headcount, or stock information
   A field is "stated" if at least one item passes, "unverified" if items
   were given but none passed, "unknown" if the model said the pages don't
   say. Field-level problems (e.g. "stated" with no items) are recorded too.

Passing these checks shows a profile is well-formed and that every value is
backed by a real quote from the company's own website. It does not show the
value is a correct reading of the quote: that is measured by human audit.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from typing import Annotated, Literal, get_args

from pydantic import (BaseModel, BeforeValidator, ConfigDict, ValidationError, ValidationInfo,
                      create_model, field_validator, model_validator)
from pydantic_core import PydanticCustomError

# the scrape's text filters (fetch_and_clean also puts src/ on the path)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "website_scrape"))
from fetch_and_clean import FINANCIAL_FIGURE, TICKER_TAG  # noqa: E402

MIN_QUOTE_WORDS = 4          # brands: 1 (the brand name itself is the evidence).
                             # The model is asked for 5+; 4 still blocks two-word
                             # scraps but accepts e.g. "Headquartered in Houston, Tx."
MAX_QUOTE_WORDS = 40         # the model is asked for under 25
MAX_ITEM_WORDS = 20          # a list item is a name or short phrase, not prose

CustomerType = Literal["businesses", "consumers", "government", "healthcare_providers",
                       "patients", "other"]
RevenueStream = Literal["product_sales", "aftermarket_parts_and_service",
                        "recurring_subscription", "professional_services",
                        "transaction_or_usage_fees", "licensing_or_royalties",
                        "rental_or_leasing", "advertising", "contract_manufacturing",
                        "distribution_resale", "patient_care_or_reimbursement",
                        "asset_management_fees", "other"]
OperatingRole = Literal["manufacturer", "designer_brand_owner", "software_developer",
                        "service_provider", "distributor_wholesaler", "retailer",
                        "platform_marketplace", "healthcare_provider",
                        "financial_services", "drug_or_biotech_developer",
                        "real_estate_operator", "other"]
Status = Literal["stated", "unknown"]

TEXT_FIELDS = ["business_description", "business_model", "geographic_footprint"]
LIST_FIELDS = ["products_services", "customers", "end_markets", "sales_channels", "brands"]
TAG_FIELDS = ["customer_types", "revenue_streams", "operating_roles"]
FIELDS = TEXT_FIELDS + LIST_FIELDS + TAG_FIELDS


# ---------------------------------------------------------------- 1. shape

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Item(Strict):
    value: str
    quote: str


class CustomerTypeItem(Strict):
    value: CustomerType
    quote: str


class RevenueStreamItem(Strict):
    value: RevenueStream
    quote: str


class OperatingRoleItem(Strict):
    value: OperatingRole
    quote: str


class TextAnswer(Strict):
    status: Status
    value: str
    evidence: list[str]


class ListAnswer(Strict):
    status: Status
    items: list[Item]


class CustomerTypesAnswer(Strict):
    status: Status
    items: list[CustomerTypeItem]


class RevenueStreamsAnswer(Strict):
    status: Status
    items: list[RevenueStreamItem]


class OperatingRolesAnswer(Strict):
    status: Status
    items: list[OperatingRoleItem]


class ProfileAnswer(Strict):
    """What the model returns. matching_summary and evidence_quality are not
    in it: the script builds them from the checked items (build_summary,
    rate_evidence), so every phrase in the summary traces to a quote."""
    business_description: TextAnswer
    business_model: TextAnswer
    geographic_footprint: TextAnswer
    products_services: ListAnswer
    customers: ListAnswer
    end_markets: ListAnswer
    sales_channels: ListAnswer
    brands: ListAnswer
    customer_types: CustomerTypesAnswer
    revenue_streams: RevenueStreamsAnswer
    operating_roles: OperatingRolesAnswer
    identifying_terms: list[str]
    notes: str


def answer_schema() -> dict:
    """JSON Schema for ProfileAnswer, as given to Codex / the Anthropic API.
    Titles and descriptions are dropped: Pydantic copies class docstrings
    (notes for developers) into "description", and the model's instructions
    belong in the prompt."""
    def strip(node):
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k not in ("title", "description")}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node
    return strip(ProfileAnswer.model_json_schema())


# ---------------------------------------------------------------- 2. rules

def norm(text: str) -> str:
    """Lowercase letters and digits only, so quotes match despite curly
    apostrophes, dashes, or spacing differences. Trademark symbols are removed
    first: NFKD would turn "Greensmaster™" into "GreensmasterTM"."""
    text = re.sub(r"[™®©℠]", " ", text)
    text = unicodedata.normalize("NFKD", text).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# Stock-market language that would reveal a public company. Narrower than
# fetch_and_clean.PUBLIC_COMPANY (a sentence filter for web pages), which
# also drops "investors"/"shareholders": legitimate customers of an asset
# manager, so not usable on extracted values.
STOCK_TALK = re.compile(
    r"\b(?:stock exchange|ticker|stock symbol|publicly[ -]traded|listed on (?:the )?"
    r"(?:NYSE|NASDAQ|Nasdaq)|share price|market capitali[sz]ation|dividends?"
    r"|earnings (?:call|per share)|initial public offering|IPO)\b", re.I)   # whole words: "stickers" isn't "ticker"


def leaks_financials(text: str) -> bool:
    """Money amounts, headcount, tickers, or stock-market language."""
    return bool(FINANCIAL_FIGURE.search(text) or TICKER_TAG.search(text)
                or STOCK_TALK.search(text))


class QuoteCheck(BaseModel):
    """One quote, checked against the pages. Validate with
    context={"pages": {page_id: text}, "field": name}."""
    quote: str
    found_on: list[str] = []

    @model_validator(mode="after")
    def _quote_on_page(self, info: ValidationInfo):
        ctx = info.context
        n = len(self.quote.split())
        need = 1 if ctx["field"] == "brands" else MIN_QUOTE_WORDS
        if n < need:
            raise PydanticCustomError("quote_too_short",
                                      "quote has {n} words; at least {need} required",
                                      {"n": n, "need": need})
        if n > MAX_QUOTE_WORDS:
            raise PydanticCustomError("quote_too_long",
                                      "quote has {n} words; at most {max} allowed",
                                      {"n": n, "max": MAX_QUOTE_WORDS})
        q = norm(self.quote)
        self.found_on = [pid for pid, text in ctx["pages"].items() if q and q in norm(text)]
        if not self.found_on:
            raise PydanticCustomError("quote_not_found",
                                      "quote not found on any page the model was given")
        return self


class ItemCheck(QuoteCheck):
    """One list item: its value and the quote that supports it."""
    value: str

    @field_validator("value")
    @classmethod
    def _value_ok(cls, v: str) -> str:
        if not v.strip():
            raise PydanticCustomError("empty_value", "value is empty")
        n = len(v.split())
        if n > MAX_ITEM_WORDS:
            raise PydanticCustomError("value_too_long",
                                      "value has {n} words; at most {max} allowed (list items "
                                      "are short names, not prose)", {"n": n, "max": MAX_ITEM_WORDS})
        if leaks_financials(v):
            raise PydanticCustomError("financial",
                                      "value mentions money, headcount or stock information")
        return v

    @model_validator(mode="after")
    def _brand_in_quote(self, info: ValidationInfo):
        if info.context["field"] != "brands":
            return self
        # A value may give several names for one brand ("SAPS; Space Alternated
        # Phase Shift", "Tahoe / Ultra C Tahoe"): one of them must be quoted.
        names = [n for n in re.split(r"[;/()]", self.value) if norm(n)]
        if not any(norm(n) in norm(self.quote) for n in names):
            raise PydanticCustomError("brand_not_in_quote", "quote doesn't contain the brand name")
        return self


def _errors(exc: ValidationError) -> list[dict]:
    return [{"type": e["type"], "msg": e["msg"]} for e in exc.errors()]


def check_items(field: str, answer, pages: dict[str, str]) -> dict:
    """Check every item of a list or tag field; returns the field record."""
    record = {"status": answer.status, "items": [], "issues": []}
    if answer.status == "unknown":
        if answer.items:
            record["issues"].append({"type": "unknown_with_items",
                                     "msg": "marked unknown but items given; items ignored"})
        return record
    seen = set()
    for item in answer.items:
        key = norm(str(item.value))
        if key in seen:
            continue   # same value listed twice
        seen.add(key)
        try:
            checked = ItemCheck.model_validate(
                {"value": item.value, "quote": item.quote},
                context={"pages": pages, "field": field})
            record["items"].append({"value": checked.value, "quote": checked.quote,
                                    "found_on": checked.found_on, "verified": True,
                                    "issues": []})
        except ValidationError as exc:
            record["items"].append({"value": item.value, "quote": item.quote,
                                    "found_on": [], "verified": False,
                                    "issues": _errors(exc)})
    if not record["items"]:
        record["status"] = "unknown"
        record["issues"].append({"type": "stated_without_items",
                                 "msg": "marked stated but no items given"})
    elif not any(i["verified"] for i in record["items"]):
        record["status"] = "unverified"
    return record


def check_text(field: str, answer: TextAnswer, pages: dict[str, str]) -> dict:
    """Check a prose field: its value and each of its evidence quotes."""
    record = {"status": answer.status, "value": answer.value, "evidence": [], "issues": []}
    if answer.status == "unknown":
        if answer.value.strip() or answer.evidence:
            record["issues"].append({"type": "unknown_with_value",
                                     "msg": "marked unknown but a value was given; ignored"})
        record["value"] = ""
        return record
    if not answer.value.strip():
        record.update(status="unknown", value="")
        record["issues"].append({"type": "stated_without_items", "msg": "marked stated but empty"})
        return record
    if leaks_financials(answer.value):
        record.update(status="unverified", value="")
        record["issues"].append({"type": "financial",
                                 "msg": "value mentions money, headcount or stock information"})
        return record
    for quote in answer.evidence:
        try:
            checked = QuoteCheck.model_validate({"quote": quote},
                                                context={"pages": pages, "field": field})
            record["evidence"].append({"quote": quote, "found_on": checked.found_on,
                                       "verified": True, "issues": []})
        except ValidationError as exc:
            record["evidence"].append({"quote": quote, "found_on": [], "verified": False,
                                       "issues": _errors(exc)})
    if not any(e["verified"] for e in record["evidence"]):
        record["status"] = "unverified"
        if not record["evidence"]:
            record["issues"].append({"type": "stated_without_evidence",
                                     "msg": "marked stated but no quotes given"})
    return record


def check_answer(answer: ProfileAnswer, pages: dict[str, str]) -> dict:
    """Layer 2 for a whole answer that passed layer 1: every field checked."""
    profile = {}
    for field in FIELDS:
        ans = getattr(answer, field)
        profile[field] = (check_text(field, ans, pages) if field in TEXT_FIELDS
                          else check_items(field, ans, pages))
    profile.update(identifying_terms=answer.identifying_terms, notes=answer.notes, issues=[])
    return profile


# Summary lines, in order: (field, label). Only list and tag fields, where
# every item has its own verified quote; prose fields are left out so the
# summary contains nothing that isn't individually backed.
SUMMARY_LINES = [
    ("operating_roles", "Operating role"),
    ("products_services", "Products and services"),
    ("customers", "Customers"),
    ("customer_types", "Customer types"),
    ("end_markets", "End markets"),
    ("sales_channels", "Sales channels"),
    ("revenue_streams", "Revenue streams"),
]
SUMMARY_MAX_ITEMS = 8        # per line; the full lists are in their own columns


def build_summary(profile: dict) -> str:
    """matching_summary, built from verified (and already masked) items with a
    fixed template, identical in form for every company. Unknown fields say
    so instead of being left out, so missing information is visible."""
    lines = []
    for field, label in SUMMARY_LINES:
        values = [v.replace("_", " ") for v in verified_values(profile[field])]
        if not values:
            lines.append(f"{label}: not stated on the website.")
            continue
        shown = values[:SUMMARY_MAX_ITEMS]
        more = f" (+{len(values) - len(shown)} more)" if len(values) > len(shown) else ""
        lines.append(f"{label}: {'; '.join(shown)}{more}.")
    return " ".join(lines)


def rate_evidence(profile: dict) -> str:
    """evidence_quality, by a fixed rule on field statuses:
      sufficient    what it sells (products_services), to whom (customers) and
                    how it earns (business_model or revenue_streams) are stated
      partial       what it sells or what it does (business_description) is stated
      insufficient  neither
    """
    stated = {f for f in FIELDS if profile[f]["status"] == "stated"}
    if {"products_services", "customers"} <= stated and stated & {"business_model", "revenue_streams"}:
        return "sufficient"
    if stated & {"products_services", "business_description"}:
        return "partial"
    return "insufficient"


def verified_values(record: dict) -> list[str]:
    """Values that passed every check (what goes into the tables)."""
    if "items" in record:
        return [i["value"] for i in record["items"] if i["verified"]]
    return [record["value"]] if record["status"] == "stated" and record["value"] else []


def source_pages(record: dict) -> list[str]:
    """Pages where this field's verified quotes were found."""
    parts = record.get("items", record.get("evidence", []))
    pages = []
    for p in parts:
        if p["verified"]:
            pages += [pid for pid in p["found_on"] if pid not in pages]
    return pages


# ---------------------------------------------------------------- 3. output tables
# The tables are validated row by row before they are written; a row that
# breaks a rule stops the run instead of being written.

FieldStatus = Literal["stated", "unknown", "unverified"]
TAG_VALUES = {"customer_types": set(get_args(CustomerType)),
              "revenue_streams": set(get_args(RevenueStream)),
              "operating_roles": set(get_args(OperatingRole))}
MASKED_COLUMNS = [f for f in TEXT_FIELDS + LIST_FIELDS if f != "brands"] + ["matching_summary", "notes"]


class _MatchingRowRules(BaseModel):
    """Rules every matching_inputs.csv row must meet. Validate with
    context={"names": [company-name variants]} for the masking check."""
    model_config = ConfigDict(extra="forbid")   # e.g. no financial columns

    @model_validator(mode="after")
    def _consistent(self, info: ValidationInfo):
        problems = []
        row = self.model_dump()
        for f in FIELDS:
            value, status, sources = row[f], row[f"{f}__status"], row[f"{f}__sources"]
            if status == "stated" and not (value and sources):
                problems.append(f"{f}: stated but value or source missing")
            if status != "stated" and (value or sources):
                problems.append(f"{f}: {status} but value or source filled in")
            if f in TAG_VALUES and value:
                bad = set(value.split("; ")) - TAG_VALUES[f]
                if bad:
                    problems.append(f"{f}: tags not in the allowed list: {sorted(bad)}")
        for col in FIELDS + ["matching_summary", "notes"]:
            if leaks_financials(row[col]):
                problems.append(f"{col}: mentions money, headcount or stock information")
        for name in (info.context or {}).get("names", []):
            flags = re.I if "." in name or name.islower() else 0
            pattern = re.compile(r"(?<![\w])" + re.escape(name) + r"(?![\w])", flags)
            for col in MASKED_COLUMNS:
                if pattern.search(row[col]):
                    problems.append(f"{col}: company name '{name}' not masked")
        statuses = {f: {"status": row[f"{f}__status"]} for f in FIELDS}
        if row["evidence_quality"] != rate_evidence(statuses):
            problems.append("evidence_quality doesn't follow from the field statuses")
        if not row["matching_summary"]:
            problems.append("matching_summary is empty")
        if problems:
            raise PydanticCustomError("row_inconsistent", "; ".join(problems))
        return self


def _matching_row_fields() -> dict:
    fields = {k: (str, ...) for k in ("IQ_COMPANY_ID", "scrape_status", "llm_status",
                                      "matching_summary", "masking_fixes", "notes",
                                      "all_source_urls", "backend", "extracted_at")}
    fields["evidence_quality"] = (Literal["sufficient", "partial", "insufficient"], ...)
    for f in FIELDS:
        fields[f] = (str, ...)
        fields[f"{f}__status"] = (FieldStatus, ...)
        fields[f"{f}__sources"] = (str, ...)
    return fields


MatchingRow = create_model("MatchingRow", __base__=_MatchingRowRules, **_matching_row_fields())


def _blank_to_none(v):
    return None if v is None or (isinstance(v, str) and not v.strip()) else v


Money = Annotated[float | None, BeforeValidator(_blank_to_none)]


class FinancialRow(Strict):
    """One financial_fields.csv row: the ID and the five supplied financial
    columns, nothing else; values must be numbers (or blank)."""
    IQ_COMPANY_ID: str
    target_revenue: Money
    target_ebitda: Money
    target_margin: Money
    target_debt_to_revenue: Money
    target_ev_to_ebitda: Money
