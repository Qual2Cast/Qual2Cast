"""
Facets: recipe step 3. Descriptive attributes that, read together, give a
reasonable sense of a company's business model, defined so every company
can have them.

Twelve facets (F1-F12), agreed 2026-10-24, each with what it captures and
example values. Two kinds:
- text facets (products, services, end markets, ...): a short value written
  like the examples;
- category facets (customer segment, revenue model, geography, ...): a
  category from a fixed list, so companies can be compared value for value,
  plus a short detail ("B2B: mechanical contractors, building owners"). Some
  take one category, some any that apply.

A company that runs unrelated businesses (supermarkets and car dealerships)
gets one profile per business, B1 the largest: each business has its own
F1-F12, so it can be matched to comps in that business. Most companies have
one business.

The model fills every facet from what it knows about the company, given its
name and website (decided 2026-10-24: the recipe has the LLM populate the
facets, and fills should be close to 100%). The scraped website pages only
fill gaps: a company left with an unknown facet gets a second call with
its saved pages, and only the unknown facets are taken from it
(fill_gaps), so a poor scraped description never overrides what the model
knew. Each facet records its source: "model knowledge", "website" or both.
In the first call it is always model knowledge, so the model isn't asked
for it. In the second, every page line is labeled (P1.3) and the model
cites labels instead of copying quotes; the cited lines and their URLs are
looked up here. "unknown" is only for a facet the model doesn't know and
the pages don't give.

The model describes only companies it knows (version i). It first says
whether it knows this company (knows_company); a name or web address alone
isn't knowing it, and it must not guess from the name or from what is
typical for similar names. In the first call, "doesn't know" makes every
facet unknown here, whatever the model wrote (a made-up company once came
back with 11 of 12 facets invented from its name), and the company goes to
the second call, where the pages are all it may use.

Answers are one-line JSON with details of about twenty words and notes only
for real gaps.

The model never sees financial fields and is told not to write financial
figures. Company size is a category with no detail (small, mid-sized,
large, among the largest within its industry), so it can't hold a figure:
a free-text size let the model write "five thousand employees" even when
digits were banned.

This file defines the facets once. The prompt, the answer schema Codex must
follow, the checks on each answer, and the output tables are all built from
FACETS. fill_facets.py runs the model. Correctness isn't checked here; that
is the manual review in the recipe's evals section.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, create_model

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "website_scrape"))
from fetch_and_clean import FINANCIAL_FIGURE, SCALE_FIGURE, TICKER_TAG  # noqa: E402  (also adds src/)

# Bump when the facets, prompt or input text change: profiles made with an
# older version are redone by the next run.
PROMPT_VERSION = "2026-10-25k"   # k: one profile per company, no business splits (SPLIT_BUSINESSES)
MAX_INPUT_WORDS = 7000       # page text sent per company, when pages are included
MAX_BUSINESSES = 4           # more than this are combined by the model (flagged if not)
# One profile per company (decided 2026-10-25): splitting a company into its
# unrelated businesses (versions f-j) is left for later. False: the answer
# schema holds exactly one business, the whole company. True: one profile per
# unrelated business, B1 the largest, checked by fill_facets.py's third pass.
SPLIT_BUSINESSES = False


@dataclass(frozen=True)
class Facet:
    name: str
    label: str
    captures: str                       # what it captures
    examples: str                       # example values, in the format a reader sees
    categories: tuple[str, ...] = ()    # category facets: the category must be from this list
    several: bool = False               # category facets: any that apply, else exactly one
    guide: str = ""                     # what else the model needs, in plain sentences
    detail: bool = True                 # category facets: a short detail with each category
    guide_when_split: str = ""          # added to the guide when SPLIT_BUSINESSES

    @property
    def kind(self) -> str:
        if not self.categories:
            return "text"
        return "any of" if self.several else "one of"


FACETS = [
    Facet("offering_description", "Core offering", "What the company sells, and to whom",
          "Designs and manufactures rooftop HVAC units for commercial buildings",
          guide="Write two or three plain sentences: what it sells, to whom, and how it "
                "makes or delivers it."),
    Facet("primary_products", "Primary products", "The main products it sells",
          "HR software; medical devices; hot-mix asphalt",
          guide="Use general names, not brand names. Name up to about five, separated by "
                "semicolons. If the company sells no products, set the status to "
                "not_applicable."),
    Facet("primary_services", "Primary services", "The main services it provides",
          "consulting; freight logistics; payroll processing",
          guide="Name up to about five, separated by semicolons. If the company sells no "
                "services, set the status to not_applicable. Support that comes with a "
                "product, such as a warranty, is not a service."),
    Facet("customer_segment", "Customer segment", "Who buys its products or services",
          "B2B: mechanical contractors, commercial building owners; B2G: school districts",
          categories=("B2B", "B2C", "B2G"), several=True,
          guide="B2B means businesses and private institutions. B2C means individual "
                "consumers or patients. B2G means government agencies. In the detail, name "
                "the customer groups."),
    Facet("end_markets", "End markets", "The industries it serves",
          "healthcare; retail; manufacturing",
          guide="Name the industries or markets where customers use its products or services, "
                "up to about five, separated by semicolons. For a consumer business, name the "
                "consumer market, such as home improvement."),
    Facet("revenue_model", "Revenue model", "How it earns money",
          "product sales: equipment sold through dealers; service fees: installation and repair",
          categories=("product sales", "subscription", "transaction or usage fees",
                      "licensing or royalties", "service fees", "project or contract",
                      "rental or leasing", "advertising", "healthcare reimbursement",
                      "interest or premiums", "commissions or management fees", "other"),
          several=True, guide="In the detail, say what customers pay for."),
    Facet("value_chain_position", "Value chain position", "Its role in the industry",
          "OEM / manufacturer: builds HVAC units from purchased components, sold to contractors",
          categories=("raw materials", "component supplier", "OEM / manufacturer", "brand owner",
                      "distributor", "retailer", "service provider", "software / platform",
                      "asset operator", "financial intermediary", "other"),
          several=True,
          guide="A brand owner designs and markets products that other companies make. An "
                "asset operator owns and runs physical assets, such as plants, networks, "
                "buildings or vehicle fleets. In the detail, say what the company takes in and "
                "who it sells to."),
    Facet("geography_served", "Geography served", "Where it sells or operates",
          "US regional: Alabama, Florida, Georgia and the Carolinas",
          categories=("US regional", "US national", "North America", "global"),
          guide="Choose the widest area. US regional means some states or one region. In "
                "the detail, name the regions, states or countries."),
    Facet("company_size", "Company size", "How large it is within its own industry",
          "mid-sized",
          categories=("small", "mid-sized", "large", "among the largest"), detail=False,
          guide="Judge scale within the company's own industry. Small means a niche or local "
                "player with one or a few sites. Mid-sized means an established player in its "
                "segment with several sites. Large means a major player in its industry with "
                "many sites or a broad customer base. Among the largest means one of the few "
                "biggest companies in its industry. Size is scale only: where it operates "
                "belongs in geography served, and how it sells in distribution channels. Judge "
                "from the kind and number of sites, the range of products, the kind of "
                "customers and how the company describes itself, not from revenue or "
                "employee counts."),
    Facet("specialization", "Product specialization", "How wide its range of offerings is",
          "related lines: HVAC units, controls and replacement parts",
          categories=("niche specialist", "related lines", "diversified"),
          guide="A niche specialist has one product or service line. Related lines means "
                "several lines that share customers, technology or channels. Diversified means "
                "separate businesses with different customers. In the detail, name the "
                "lines or businesses.",
          guide_when_split="Judge each business on its own: a business that was split off is "
                           "rarely diversified."),
    Facet("distribution_channels", "Distribution channels", "How its products reach customers",
          "distributors / dealers: independent HVAC dealers; direct sales: national accounts",
          categories=("direct sales", "distributors / dealers", "own locations",
                      "third-party retail", "online", "partners / resellers", "agents / brokers",
                      "other"),
          several=True, guide="In the detail, say who or what the channel is."),
    Facet("regulatory_exposure", "Regulatory exposure", "How much regulation controls the business",
          "high: medical devices that need FDA clearance",
          categories=("high", "medium", "low"),
          guide="High means the company needs approval or a license to operate or sell, as for "
                "utilities, hospitals, drugs and medical devices, banks, insurers and airlines. "
                "Medium means important industry rules apply, such as environmental, safety, "
                "transport or data privacy rules. Low means only normal business rules apply. "
                "In the detail, name the regulated activity and the main regulators or rules."),
]
FACET_NAMES = [f.name for f in FACETS]
FACET_BY_NAME = {f.name: f for f in FACETS}
FACET_ID = {f.name: f"F{i}" for i, f in enumerate(FACETS, start=1)}   # F1 core offering, ...


# ---------------------------------------------------------------- answer shape

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


Status = Literal["filled", "not_applicable", "unknown"]
CITATION = re.compile(r"^\s*B(\d+)\s+([a-z_]+)\s*:\s*(.*)$")   # "B1 primary_products: P1.3, P2.1"


def _facet_model(facet: Facet) -> type[BaseModel]:
    """text: value. one of: category + detail (category only if not
    facet.detail). any of: a list of category + detail. Every facet also has a
    status."""
    fields = {"status": (Status, ...)}
    if facet.kind == "text":
        fields["value"] = (str, ...)
    elif facet.kind == "one of":
        fields["category"] = (Literal[(*facet.categories, "")], ...)
        if facet.detail:
            fields["detail"] = (str, ...)
    else:
        item = create_model(f"Item_{facet.name}", __base__=Strict,
                            category=(Literal[facet.categories], ...), detail=(str, ...))
        fields["items"] = (list[item], ...)
    return create_model(f"Facet_{facet.name}", __base__=Strict, **fields)


def _answer_model(pages: bool) -> type[BaseModel]:
    """With pages, the answer also lists its citations, one string per facet
    filled from the pages ("B1 primary_products: P1.3, P2.1"). They are one
    list of strings rather than a list inside each facet because the Claude
    API refuses the larger schema ("compiled grammar is too large",
    2026-10-24); check_answer parses them."""
    business = create_model(
        "BusinessAnswer", __base__=Strict,
        business=(str, ...),       # short general name, e.g. "supermarkets"
        **{f.name: (_facet_model(f), ...) for f in FACETS},
    )
    # knows_company first, so the model says whether it knows the company
    # before it describes anything; without splitting, room for one business
    citations = {"citations": (list[str], ...)} if pages else {}
    described = {"businesses": (list[business], ...)} if SPLIT_BUSINESSES else {"company": (business, ...)}
    return create_model("FacetAnswer", __base__=Strict, knows_company=(bool, ...),
                        **described, **citations, notes=(str, ...))


_answer_models: dict = {}


def answer_model(pages: bool) -> type[BaseModel]:
    """The answer without pages (name and website only) or with pages, as
    SPLIT_BUSINESSES says now."""
    key = (pages, SPLIT_BUSINESSES)
    if key not in _answer_models:
        _answer_models[key] = _answer_model(pages)
    return _answer_models[key]


def answer_schema(pages: bool) -> dict:
    """JSON Schema for the answer, as given to Codex (--output-schema).
    Titles and descriptions are dropped: the instructions are in the prompt."""
    def strip(node):
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k not in ("title", "description")}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node
    return strip(answer_model(pages).model_json_schema())


# ---------------------------------------------------------------- prompt

def facet_guide() -> str:
    """The facets in plain English, one block per facet, as the model reads them."""
    blocks = []
    for f in FACETS:
        if f.kind == "text":
            answer = "" if f.guide.startswith("Write") else "Write a short text."
        elif f.kind == "one of":
            answer = f"Choose one: {', '.join(f.categories)}." + (
                " Add a short detail." if f.detail else " No detail.")
        else:
            answer = (f"Choose all that apply: {', '.join(f.categories)}. "
                      "Add a short detail for each.")
        guide = f"{f.guide} {f.guide_when_split}" if SPLIT_BUSINESSES and f.guide_when_split else f.guide
        lines = [f"{FACET_ID[f.name]} {f.label} ({f.name}): {f.captures}.", answer, guide,
                 f"Example: {f.examples}"]
        blocks.append("\n  ".join(line for line in lines if line))
    return "\n\n".join(blocks)


def instructions(pages: bool) -> str:
    """The prompt's instructions; with pages, also how to cite page lines."""
    you_get = ("You get the company's name and website, and text from a few pages of its "
               "website. Each line of page text starts with a label: [P1.3] is page P1, "
               "line 3." if pages else "You get the company's name and website.")
    use = "Use what you know about the company, and the website pages." if pages else \
          "Use what you know about the company."
    if pages:
        known = """First, say whether you know this company: set "knows_company" to true \
only if you recognize this specific company from what you already know. \
Either way, describe it: if you don't know it, use only the website pages. \
Do not guess anything from the company's name, its web address, or what is \
typical for companies with similar names; a facet the pages don't support \
is "unknown"."""
    else:
        known = """First, say whether you know this company: set "knows_company" to true \
only if you recognize this specific company from what you already know. A \
name and a web address alone are not knowing the company: do not guess what \
a company does from its name, its web address, or what is typical for \
companies with similar names. If you don't know the company, can't tell \
which company it is, or it may be fictional, set "knows_company" to false \
and every facet to "unknown"."""
    which_b = "B1 is the first business you list" if SPLIT_BUSINESSES else "always B1"
    sources = f"""

For every facet you fill from the website pages, add one entry to \
"citations": the business, the facet's name and the labels of the 1 or 2 \
page lines that best support it, written like "B1 primary_products: P1.3, \
P2.1" ({which_b}). A facet you fill from what you already know about the \
company gets no citation.""" if pages else ""
    if SPLIT_BUSINESSES:
        businesses = f"""\
Then decide how many businesses the company runs today. Most companies run \
one business. Count separate businesses only when they are unrelated: they \
sell different things to different customers in different industries, for \
example supermarkets and car dealerships. These are one business, not \
several: product lines that share customers, technology or sales channels; \
products or equipment for different end uses within one industry; the same \
business in different regions or countries; reporting segments within one \
industry. When in doubt, it is one business. List each business, the \
largest first, with a short general name, such as "supermarkets". List at \
most {MAX_BUSINESSES}; if there are more, combine the smallest ones.

Then fill in every facet below for each business."""
    else:
        businesses = """\
Describe the whole company as one business: if it runs several product \
lines, segments or businesses, cover all of them in each facet, the largest \
first. Give it a short general name, such as "supermarkets".

Then fill in every facet below."""
    whom = "a company and the businesses it runs" if SPLIT_BUSINESSES else "a company"
    return f"""\
You describe {whom}. A research project uses these descriptions to find \
comparable companies.

{you_get}

{known}

Describe the company as it is now. Leave out businesses it has sold, spun \
off or closed, and businesses it holds only as a minority stake or joint \
venture.

{businesses} {use}

For a company you know, fill every facet you can. If you are not sure of a \
detail, give your best description of this company and say what is \
uncertain in "notes". If a business sells no products, or no services, set \
that facet to "not_applicable". Write "unknown" for a facet you know nothing \
about. Do not make up facts.{sources}

Write general values, like the examples. Use general product names, not \
brand names. Keep each detail to one phrase of about twenty words at most \
that names the specific customers, products or channels, and do not repeat \
the category in it. Leave the value or detail empty when the status is \
"unknown" or "not_applicable".

Do not give financial information: no revenue, profit, market value, share \
price, stock ticker, stock exchange or employee counts.

Everything you need is in this message. Do not run commands, open files or \
search the web. Write the JSON on one line, with no indentation or line \
breaks.

Facets:

{facet_guide()}

Also write "notes": leave it empty unless something important is uncertain \
or missing; then say what in one short sentence."""


def build_prompt(record: dict, with_pages: bool) -> tuple[str, dict[str, str]]:
    """The company's name and website, plus (with_pages) its scraped page
    text with each line labeled; and label ("P1.3") -> that line, for looking
    up citations. Empty when no page text was sent, and then the prompt is the
    one without pages. Blocks repeated across pages (menus, footers) are sent
    once; the page text stops at MAX_INPUT_WORDS words."""
    parts, lines, seen, budget = [], {}, set(), MAX_INPUT_WORDS
    for page in record["pages"] if with_pages else []:
        page_lines = []
        for block in [x for x in [page["title"], page["meta"]] if x] + page["blocks"]:
            # the scrape already drops sentences with figures from the page
            # text, but not from titles ("Get Up To $500 In 5 Minutes")
            if block.lower() in seen or budget <= 0 or _figures(block):
                continue
            seen.add(block.lower())
            words = block.split()
            block = block if len(words) <= budget else " ".join(words[:budget])
            budget -= len(words)
            label = f"{page['page_id']}.{len(page_lines) + 1}"
            lines[label] = block
            page_lines.append(f"[{label}] {block}")
        if page_lines:
            parts.append(f'<page id="{page["page_id"]}">\n' + "\n".join(page_lines) + "\n</page>")
    head = f"Company: {record['company_name']}\nWebsite: {record['website']}"
    return instructions(bool(lines)) + "\n\n" + "\n\n".join([head, *parts]), lines


def _figures(text: str) -> list[str]:
    """Financial figures, headcounts, size or growth figures and ticker tags in
    text, found with the website scrape's own filters."""
    return [m.group(0).strip() for rx in (FINANCIAL_FIGURE, SCALE_FIGURE, TICKER_TAG)
            for m in rx.finditer(text)]


def figures_in_input(prompt: str, pages: bool) -> list[str]:
    """The figures (see _figures) in what the prompt says about the company:
    everything after the instructions. Should always be empty, since
    build_prompt leaves out every page line that has one; recorded per call
    as a check on that."""
    return _figures(prompt[len(instructions(pages)):])


def input_fingerprint(record: dict, with_pages: bool) -> str:
    """sha256 of the whole prompt; a profile whose fingerprint no longer
    matches (prompt, input mode or page text changed) is outdated."""
    return hashlib.sha256(build_prompt(record, with_pages)[0].encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- checks

def check_answer(raw: dict, lines: dict[str, str], page_urls: dict[str, str]) -> dict:
    """Validate the answer's shape (raises pydantic.ValidationError; a category
    outside its list fails here), then for each business and facet: look up
    each cited line, list the sources, and flag problems. `lines` is what
    build_prompt returned: empty means the prompt had no pages, and the answer
    has no citations.

    Returns {"businesses": [{"business_id": "B1", "business": ..., "facets":
    {...}}, ...], "issues": [...], "notes": ...}. Each facet is stored as
    `value` (what a reader sees: a category facet's categories with their
    details, "B2B: contractors; B2G: school districts"), `category` (category
    facets: the categories alone, "B2B; B2G"), `source` ("model knowledge"
    and/or the cited pages' URLs) and `quotes` (the cited lines).

    Without pages, an answer that says the model doesn't know the company
    (knows_company false) keeps nothing: every facet is unknown whatever the
    model wrote, so the company goes to the second pass with its pages."""
    answer = answer_model(bool(lines)).model_validate(raw).model_dump()
    if not SPLIT_BUSINESSES:                # one business: the whole company
        answer["businesses"] = [answer.pop("company")]
    if not lines and not answer["knows_company"]:
        return {**unknown_facets(answer["notes"]), "knows_company": False,
                "issues": ["company_not_known"]}
    cites, issues = {}, []      # (business number, facet) -> cited labels
    for entry in answer.get("citations", []):
        m = CITATION.match(entry)
        if not m or m.group(2) not in FACET_BY_NAME:
            issues.append("citation_not_read")
            continue
        labels = re.findall(r"P\d+\.\d+", m.group(3))
        cites.setdefault((int(m.group(1)), m.group(2)), []).extend(labels)
    businesses = [{"business_id": f"B{i}", "business": b["business"].strip(),
                   "facets": _check_facets(b, lines, page_urls, answer["knows_company"],
                                           {f: c for (n, f), c in cites.items() if n == i})}
                  for i, b in enumerate(answer["businesses"], start=1)]
    issues = list(dict.fromkeys(issues))
    if not businesses:
        issues.append("no_business")
    if len(businesses) > MAX_BUSINESSES:
        issues.append("too_many_businesses")
    return {"knows_company": answer["knows_company"], "businesses": businesses,
            "issues": issues, "notes": answer["notes"]}


def clean_detail(category: str, detail: str) -> str:
    """A category's detail as stored. Semicolons become commas (they would
    split the value when it is read back), and a repeat of the category at
    the start is removed: the model sometimes writes "medium: ..." as the
    detail of "medium" despite the prompt (12 of 360 details in the version i
    fill test), which would read "medium: medium: ...". Only the category
    followed by a colon is removed, so "direct sales team ..." stays."""
    detail = detail.replace(";", ",").strip()
    return re.sub(rf"^{re.escape(category)}\s*:\s*", "", detail, flags=re.I)


def _check_facets(b: dict, lines: dict[str, str], page_urls: dict[str, str],
                  knows_company: bool = True, cites: dict[str, list[str]] | None = None) -> dict:
    """One business's facets, checked (see check_answer). cites: facet ->
    the page-line labels the answer cites for it (with pages only). The
    source is model knowledge without pages; with pages it is the cited
    pages' URLs, or model knowledge for an uncited facet of a company the
    model knows. An uncited facet of a company it doesn't know can only have
    come from the pages, so it is flagged website_without_quote."""
    cites = cites or {}
    facets = {}
    for f in FACETS:
        a = b[f.name]
        if f.kind == "text":
            value, category = a["value"].strip(), ""
        else:
            items = a["items"] if f.kind == "any of" else (
                [{"category": a["category"], "detail": a.get("detail", "")}] if a["category"] else [])
            parts = [(i["category"], clean_detail(i["category"], i["detail"])) for i in items]
            value = "; ".join(f"{c}: {d}" if d else c for c, d in parts)
            category = "; ".join(c for c, _ in parts)
        quotes = [{"block": c, "page": c.split(".")[0], "url": page_urls.get(c.split(".")[0], ""),
                   "quote": lines.get(c, ""), "quote_found": c in lines}
                  for c in dict.fromkeys(cites.get(f.name, []))]
        stated = a["status"] != "unknown"
        if quotes:
            source = list(dict.fromkeys(q["url"] for q in quotes if q["url"]))
        else:
            source = ["model knowledge"] if stated and (not lines or knows_company) else []
        flags = []
        if a["status"] == "filled" and not value:
            flags.append("no_value")
        # not_applicable needs no citation (a services firm has no products)
        if lines and a["status"] == "filled" and not quotes and not knows_company:
            flags.append("website_without_quote")
        if any(not q["quote_found"] for q in quotes):
            flags.append("quote_not_found")
        if FINANCIAL_FIGURE.search(value) or TICKER_TAG.search(value):
            flags.append("financial_in_value")
        facets[f.name] = {"status": a["status"], "value": value, "category": category,
                          "source": source, "quotes": quotes, "flags": flags}
    return facets


def fill_gaps(businesses: list[dict], from_pages: list[dict]) -> tuple[list[str], bool]:
    """Fill the unknown facets of the first answer (from the name and website)
    with an answer made with the saved pages, in place; both in check_answer's
    format. Only unknown facets change, so nothing the model knew is replaced
    by page text. Businesses are matched by position (B1 with B1), and only
    if both answers list the same number of them; otherwise nothing changes.
    Returns the facets filled ("B1 primary_products") and whether the
    businesses matched. If the first answer has nothing filled (the model
    didn't know the company), the answer from the pages is taken whole,
    businesses and all."""
    if all(f["status"] == "unknown" for b in businesses for f in b["facets"].values()):
        businesses[:] = from_pages
        return [f"{b['business_id']} {name}" for b in from_pages
                for name, f in b["facets"].items() if f["status"] != "unknown"], True
    if len(businesses) != len(from_pages):
        return [], False
    filled = []
    for b, p in zip(businesses, from_pages):
        for name, facet in b["facets"].items():
            if facet["status"] == "unknown" and p["facets"][name]["status"] != "unknown":
                b["facets"][name] = p["facets"][name]
                filled.append(f"{b['business_id']} {name}")
    return filled, True


# ---------------------------------------------------------------- third pass: check business splits

def split_check_prompt(record: dict, businesses: list[dict]) -> tuple[str, dict[str, str]]:
    """For a company split into several businesses: the prompt that checks
    each business against the company's saved website pages, and label ->
    page line (as build_prompt). The model's own knowledge of a company's
    structure can be years out of date (Carlisle's foodservice unit, sold in
    2018, came back as a business in 2026); the current website is the
    evidence here, and the check can only remove a business."""
    full, lines = build_prompt(record, True)
    pages = full[full.index('<page id="'):] if lines else ""
    listed = "\n".join(f"{b['business_id']} {b['business']}: "
                       f"{b['facets']['offering_description']['value']}" for b in businesses)
    prompt = f"""\
An earlier answer said the company below runs these separate businesses:

{listed}

Below is text from the company's current website. Each line starts with a \
label: [P1.3] is page P1, line 3.

For each business, say whether these pages show that the company runs it \
today. "shown": the pages describe it, even under another name; in "cite", \
list the labels of the 1 or 2 lines that show it. "not shown": the pages \
don't mention it. Use only the pages, not what you already know about the \
company. Everything you need is in this message. Do not run commands, open \
files or search the web. Write the JSON on one line.

Company: {record['company_name']}
Website: {record['website']}

{pages}"""
    return prompt, lines


def split_check_schema(business_ids: list[str]) -> dict:
    """The answer to split_check_prompt: one check per business."""
    check = {"type": "object", "additionalProperties": False,
             "required": ["business_id", "status", "cite"],
             "properties": {"business_id": {"type": "string", "enum": business_ids},
                            "status": {"type": "string", "enum": ["shown", "not shown"]},
                            "cite": {"type": "array", "items": {"type": "string"}}}}
    return {"type": "object", "additionalProperties": False, "required": ["checks", "notes"],
            "properties": {"checks": {"type": "array", "items": check}, "notes": {"type": "string"}}}


# words that say nothing about which business it is
NAME_STOPWORDS = {"and", "the", "for", "with", "products", "product", "services", "service",
                  "specialty", "specialties", "industrial", "business", "businesses", "solutions",
                  "systems", "other", "technologies", "technology", "group", "operations"}


def name_words_in_pages(business: str, others: list[str], lines: dict[str, str]) -> list[str]:
    """The words of a business's name (4+ letters, not generic, not in the
    other businesses' names) that appear in the page text, matched on their
    first six letters ("billboards" ~ "billboard")."""
    text = " ".join(lines.values()).lower()
    other_words = {w for n in others for w in re.findall(r"[a-z]+", n.lower())}
    words = [w for w in re.findall(r"[a-z]+", business.lower())
             if len(w) > 3 and w not in NAME_STOPWORDS and w not in other_words]
    return [w for w in words if w[:6] in text]


def apply_split_check(businesses: list[dict], raw: dict, lines: dict[str, str],
                      page_urls: dict[str, str]) -> tuple[list[dict], dict]:
    """The businesses kept after the check, renumbered B1, B2, ... in their
    order, and a record of the check. All rules here are code, not model:
    - shown: the model says so and cites at least one line in the prompt;
    - disputed: the model says not shown, but words of the business's own
      name are in the pages (Boston Omaha, 2026-10-24: its billboards were
      on the pages and the model said not shown). Kept, for the manual
      review (issue split_disputed);
    - removed: not shown and not disputed, if another business is shown;
    - if the pages show no business they say nothing about the company's
      structure: nothing is removed, outcome "not_checked" (manual review)."""
    said = {c["business_id"]: c for c in raw["checks"]}
    names = [b["business"] for b in businesses]
    checked = []
    for b in businesses:
        c = said.get(b["business_id"], {"status": "not shown", "cite": []})
        labels = [x for cite in c["cite"] for x in re.findall(r"P\d+\.\d+", cite)]   # "[P1.6]" too
        quotes = [{"block": x, "page": x.split(".")[0], "url": page_urls.get(x.split(".")[0], ""),
                   "quote": lines.get(x, ""), "quote_found": x in lines}
                  for x in dict.fromkeys(labels)]
        shown = c["status"] == "shown" and any(q["quote_found"] for q in quotes)
        words = [] if shown else name_words_in_pages(b["business"], [n for n in names if n != b["business"]], lines)
        checked.append({"business_id": b["business_id"], "business": b["business"],
                        "model_said": c["status"], "quotes": quotes, "shown": shown,
                        "name_words_in_pages": words, "disputed": bool(words)})
    record = {"businesses": checked, "notes": raw.get("notes", ""),
              "disputed": [c["business"] for c in checked if c["disputed"]]}
    if not any(c["shown"] for c in checked):
        return businesses, {**record, "outcome": "not_checked", "removed": []}
    keep = [c["shown"] or c["disputed"] for c in checked]
    removed = [b for b, k in zip(businesses, keep) if not k]
    kept = [{**b, "business_id": f"B{i}"}
            for i, b in enumerate([b for b, k in zip(businesses, keep) if k], start=1)]
    return kept, {**record, "outcome": "removed" if removed else "confirmed", "removed": removed}


# ---------------------------------------------------------------- divestiture lines (no model)

# A page line that says the company sold, spun off or divested something:
# what the model knows about it may be out of date (American Financial's
# facets listed annuities its own site says it sold: "Sale of Annuity
# Business to MassMutual"). Matched lines flag the company for the manual
# review; facets are never changed by them.
DIVESTITURE = re.compile(
    r"\bsale of (?:its |our |the )?[\w&.,'\- ]{0,60}?(?:business|division|unit|segment|subsidiary|stake|operations)\b"
    r"|\bsold (?:its |our |the )[\w&.,'\- ]{0,60}?(?:business|division|unit|segment|subsidiary|stake|operations)\b"
    r"|\bdivest\w*|\bspin-?off\b|\bspun off\b|\bspin off\b|\bcompletes? (?:the )?sale\b",
    re.I)


def divestiture_lines(lines: dict[str, str]) -> list[str]:
    """The page lines ("P2.21: Sale of Annuity Business to MassMutual") that
    mention a sale, divestiture or spin-off."""
    return [f"{label}: {text}" for label, text in lines.items() if DIVESTITURE.search(text)]


def unknown_facets(reason: str) -> dict:
    """One business with every facet unknown, same format as a checked answer
    (when the model gave no usable answer)."""
    facets = {f.name: {"status": "unknown", "value": "", "category": "", "source": [],
                       "quotes": [], "flags": []} for f in FACETS}
    return {"knows_company": None, "businesses": [{"business_id": "B1", "business": "", "facets": facets}],
            "issues": [], "notes": reason}
