"""
Sector-specific facets for the specialized sub-models (recipe steps 5-6).

The twelve general facets (facets.py) describe every company the same way.
Aziz's question (2026-10-23): which facets make sense for manufacturers but
not for services firms? Two companies in the same FF49 industry can still
be poor comps (a truckload carrier and a freight broker are both "Trans"),
and the general facets often miss what tells them apart. So each sector
group (sectors.py) gets a few extra category facets that separate business
models inside that sector, and every company gets one more text facet,
its sub-sector, in a few words.

Filled by Claude Haiku from evidence, not from memory alone (Aziz,
2026-10-27: "Totally avoid relying on LLM memory only. Use tool calling, web
search..."): the company's saved website pages, and with --evidence a deeper
crawl of its site plus web search (v0/verification/evidence.py). Each facet
cites the evidence lines it rests on; the model's own knowledge fills only
what the evidence doesn't cover and is marked "model knowledge". Never
financial figures. Categories come from a
fixed list (the answer schema rejects anything else), so the sub-model
compares them value for value (sector_submodel.category_similarity).

To change a sector's facets: edit SECTOR_FACETS and bump PROMPT_VERSION;
profiles from an older version are redone by the next run. Barbara's
sector-facet list (Drive) is the reference for what to add.
"""

from __future__ import annotations

import hashlib
import json
import re

from facets import FINANCIAL_FIGURE, SCALE_FIGURE, Facet
from sectors import SECTOR_GROUPS, SECTOR_LABELS

PROMPT_VERSION = "2026-10-27b"   # b: evidence first (website pages, optional web search), cited; memory only for gaps

SUB_SECTOR = Facet(
    "sub_sector", "Sub-sector", "The narrow industry niche the company competes in, in a few words",
    "commercial HVAC equipment; payroll and HR software for mid-sized employers; less-than-truckload freight",
    guide="Name the niche a buyer would search for comps in, more specific than the industry: "
          "up to about eight words. For a company in several niches, name the largest first, "
          "separated by semicolons (at most three).")


def _f(name, label, captures, examples, categories, several=False, guide=""):
    return Facet(name, label, captures, examples, categories=tuple(categories), several=several, guide=guide)


# Sector facets follow Barbara's "Comprehensive Company Facet Framework",
# section 2 (Technology / SaaS, Manufacturing / Industrials, Financial
# Services, Healthcare / Life Sciences, Consumer / Retail, Energy / Utilities
# / Materials, Business / Professional Services): from each list, the facets
# that separate business models inside the sector and that a model can know
# from the company's name and website. Her lists' example values became the
# category lists, widened where they left companies in our 533 without a
# fitting category. Distribution / transport, construction / real estate and
# telecom / media are not in her framework; their facets are ours.
_CONSUMER = [
    _f("product_category", "Product category", "What consumers buy from it (Barbara: product category)",
       "food: snacks and frozen meals",
       ["food", "beverages", "apparel and footwear", "household and personal care", "home and furnishings",
        "electronics", "recreation and leisure goods", "general merchandise", "restaurant meals",
        "lodging and travel", "entertainment and gaming", "automotive", "other"], several=True),
    _f("market_position", "Market position", "Where it sits on price (Barbara: market position)",
       "mass-market: mainstream national brands",
       ["value / discount", "mass-market", "premium", "luxury"]),
    _f("distribution_model", "Distribution model", "How it reaches consumers (Barbara: distribution model)",
       "wholesale: sells through grocery and mass retailers",
       ["direct to consumer", "wholesale to retailers", "franchise", "company-operated locations",
        "licensing"], several=True),
    _f("purchase_frequency", "Purchase frequency", "How often consumers buy (Barbara: purchase frequency)",
       "daily: staple groceries",
       ["daily / staple", "periodic", "discretionary / occasional"]),
]

SECTOR_FACETS: dict[str, list[Facet]] = {
    "software": [
        _f("software_category", "Software category", "What the software does (Barbara: software category)",
           "HR and payroll: payroll, benefits and time tracking",
           ["ERP and finance", "HR and payroll", "CRM, marketing and sales", "cybersecurity",
            "data, analytics and AI", "IT and developer infrastructure", "collaboration and content",
            "industry-specific (vertical) software", "payments and fintech", "consumer internet and marketplaces",
            "IT services and consulting", "other"], several=True),
        _f("deployment_model", "Deployment model", "How the software is delivered (Barbara: deployment model)",
           "SaaS: cloud subscription",
           ["SaaS / cloud", "on-premise", "hybrid", "not applicable (services or internet)"]),
        _f("customer_size", "Customer size", "Its typical customer (Barbara: customer size)",
           "mid-market: employers with tens to a few thousand staff",
           ["consumers", "SMB", "mid-market", "enterprise", "government"], several=True),
        _f("product_architecture", "Product architecture", "One product or a suite (Barbara: product architecture)",
           "platform: payroll, HR, time and benefits on one system",
           ["platform / suite", "point solution", "API / infrastructure"]),
    ],
    "manufacturing": [
        _f("manufacturing_type", "Manufacturing type", "How it makes products (Barbara: manufacturing type)",
           "discrete: builds individual units on assembly lines",
           ["discrete", "process", "assembly", "outsourced / fabless"], several=True),
        _f("production_model", "Production model", "Built for an order or for stock (Barbara: production model)",
           "make-to-order: each unit configured to the customer's order",
           ["make-to-order", "make-to-stock", "both"]),
        _f("product_complexity", "Product complexity", "How engineered its products are (Barbara: product complexity)",
           "engineered: custom-configured equipment",
           ["commodity", "engineered", "precision / high-spec"]),
        _f("production_role", "Production role", "Where it sits in its customers' supply chain (Barbara: production role, supply chain position)",
           "final manufacturer: sells finished units to contractors",
           ["final manufacturer / OEM", "tier 1 supplier", "tier 2 or component supplier",
            "contract manufacturer", "materials producer"], several=True),
        _f("end_market_exposure", "End-market exposure", "Which end markets drive demand (Barbara: end-market exposure)",
           "industrial: factories and commercial buildings",
           ["aerospace and defense", "automotive and transportation", "industrial", "construction and buildings",
            "energy", "electronics and semiconductors", "healthcare and life sciences", "consumer",
            "agriculture", "other"], several=True),
    ],
    "financials": [
        _f("financial_business_type", "Financial business type", "What kind of financial firm (Barbara: financial business type)",
           "insurance brokerage: places commercial insurance for clients",
           ["banking", "specialty lending", "property and casualty insurance", "life and health insurance",
            "insurance brokerage", "asset / wealth management", "exchanges and market infrastructure",
            "payments", "other"], several=True),
        _f("revenue_driver", "Revenue driver", "What it earns on (Barbara: revenue driver)",
           "fees: commissions on placed premiums",
           ["net interest income", "fees and commissions", "premiums", "investment income"], several=True),
        _f("customer_type", "Customer type", "Who its clients are (Barbara: customer type)",
           "corporate: small and mid-sized businesses",
           ["retail", "corporate", "institutional", "government"], several=True),
        _f("balance_sheet_dependence", "Balance sheet dependence", "Whether it carries the risk (Barbara: balance sheet dependence)",
           "fee-based: no underwriting risk",
           ["balance-sheet intensive", "fee-based", "mixed"]),
    ],
    "healthcare": [
        _f("healthcare_segment", "Healthcare segment", "Part of healthcare (Barbara: healthcare segment)",
           "services: home health and hospice care",
           ["pharma", "biotech", "medtech / devices", "diagnostics and tools", "provider services",
            "healthcare IT", "payer", "distribution / pharmacy", "other"], several=True),
        _f("product_stage", "Product stage", "Whether its products are on the market (Barbara: product stage)",
           "commercial: sells approved products",
           ["commercial", "clinical", "research", "not applicable (services)"]),
        _f("customer_payer", "Customer / payer", "Who pays (Barbara: customer / payer, reimbursement exposure)",
           "Medicare and Medicaid: government programs pay for most visits",
           ["hospitals and providers", "private insurance", "Medicare and Medicaid", "patients / consumers",
            "pharma and biotech companies", "employers", "other"], several=True),
        _f("therapeutic_area", "Therapeutic area", "Main clinical area (Barbara: therapeutic area)",
           "cardiovascular: heart rhythm devices",
           ["oncology", "cardiovascular", "neurology and behavioral health", "orthopedics and spine",
            "metabolic and diabetes", "infectious disease", "ophthalmology", "dental", "general / multiple",
            "other"], several=True),
    ],
    "consumer_products": _CONSUMER,
    "consumer_venues": _CONSUMER,
    "business_services": [
        _f("service_category", "Service category", "What service it sells (Barbara: service category)",
           "outsourcing: payroll and benefits administration",
           ["consulting and advisory", "outsourcing / BPO", "staffing", "facilities and field services",
            "engineering and technical services", "marketing and information services",
            "education and training", "personal and consumer services", "other"], several=True),
        _f("engagement_model", "Engagement model", "How clients engage it (Barbara: engagement model)",
           "managed service: multi-year outsourced contracts",
           ["project", "retainer", "managed service", "per transaction / per visit"], several=True),
        _f("labor_specialization", "Labor specialization", "Who delivers it (Barbara: labor specialization)",
           "specialist: licensed technicians",
           ["generalist / low-skill", "skilled trades", "licensed professionals", "technical / IT specialists"]),
        _f("client_segment", "Client segment", "Its typical client (Barbara: client segment)",
           "enterprise: large employers",
           ["consumers", "SMB", "enterprise", "government"], several=True),
    ],
    "energy_resources": [
        _f("industry_position", "Industry position", "Where it sits in the chain (Barbara: industry position)",
           "regulated utility: electric and gas distribution",
           ["upstream / production", "midstream", "downstream", "regulated utility", "independent power",
            "mining", "agriculture", "services to producers"], several=True),
        _f("commodity_exposure", "Commodity exposure", "What it produces or delivers (Barbara: commodity exposure)",
           "electricity and natural gas",
           ["oil", "natural gas", "electricity", "water", "metals", "minerals and aggregates",
            "crops and livestock", "other"], several=True),
        _f("revenue_structure", "Revenue structure", "How prices are set (Barbara: revenue structure)",
           "regulated: rates approved by state commissions",
           ["spot", "contracted", "regulated"], several=True),
        _f("energy_transition", "Energy transition exposure", "Fossil or renewable (Barbara: energy transition exposure)",
           "mixed: gas plants and solar",
           ["renewables", "fossil fuels", "mixed", "not applicable"]),
    ],
    "distribution_transport": [
        _f("logistics_role", "Role", "What it moves or distributes (ours: not in Barbara's framework)",
           "industrial distributor: MRO parts to factories",
           ["industrial distributor", "consumer goods distributor", "healthcare distributor",
            "technology distributor", "trucking", "less-than-truckload", "rail", "air", "marine",
            "freight brokerage / logistics", "passenger transport"], several=True),
        _f("asset_intensity", "Asset intensity", "Whether it owns the fleet or warehouses (Barbara core: capital intensity)",
           "asset-heavy: owns its fleet and terminals",
           ["asset-heavy", "asset-light", "mixed"]),
        _f("value_added", "Value added", "What it adds besides moving goods (ours)",
           "value-added services: inventory management and repair",
           ["pure distribution", "value-added services", "contract logistics"], several=True),
    ],
    "construction_real_estate": [
        _f("construction_role", "Role", "Its role in building or property (ours)",
           "specialty contractor: mechanical and electrical work",
           ["homebuilder", "general contractor", "specialty contractor", "engineering and design",
            "land developer", "property owner / REIT", "property services"], several=True),
        _f("project_type", "Project type", "What kind of projects (ours)",
           "infrastructure: roads and bridges",
           ["residential", "commercial / institutional", "industrial", "infrastructure", "energy and utilities"],
           several=True),
        _f("public_funding", "Public funding", "How much of its work is publicly funded (ours)",
           "high: mostly state transportation departments",
           ["high", "medium", "low"]),
    ],
    "media_telecom": [
        _f("media_type", "Type", "What kind of telecom or media business (ours)",
           "wireless carrier",
           ["wireless / wireline carrier", "cable / broadband", "towers and infrastructure", "broadcasting",
            "publishing", "digital media", "communications software"], several=True),
        _f("revenue_source", "Revenue source", "Who pays (ours)",
           "subscribers: monthly plans",
           ["subscribers", "advertisers", "wholesale / carriers", "content licensing"], several=True),
    ],
    "other": [],
}

assert set(SECTOR_FACETS) == set(SECTOR_GROUPS), set(SECTOR_FACETS) ^ set(SECTOR_GROUPS)

STATUSES = ("stated", "not_applicable", "unknown")


def facets_for(sector: str) -> list[Facet]:
    """The facets a company in this sector gets: sub-sector first."""
    return [SUB_SECTOR, *SECTOR_FACETS.get(sector, [])]


def all_facet_names() -> list[str]:
    seen = [SUB_SECTOR.name]
    for fs in SECTOR_FACETS.values():
        seen += [f.name for f in fs if f.name not in seen]
    return seen


INSTRUCTIONS = """You describe a company's business model for a private-equity analyst who is choosing comparable public companies. You get the company's name, website and sector, and evidence about it: lines from its own website and, when available, web search results. Every evidence line starts with a label, such as [P1.3] (saved website page 1, line 3), [W2.4] (another page of its website) or [S3.1] (web search result 3).

Base every facet on the evidence. For each facet you fill, cite the labels of the 1 to 3 lines that best support it in "cites". Only when the evidence says nothing about a facet may you use what you already know about this specific company; then leave "cites" empty. Never guess from the company's name, its web address or what is typical for similar companies: a facet that neither the evidence nor your knowledge of this company supports is "unknown".

Describe the company as it is now: leave out businesses the evidence or your knowledge says it has sold, spun off or closed. Describe the whole company as one business: if it has several lines, cover all of them, the largest first.

For a category facet, choose categories only from its list (one, or any that apply, as the facet says) and add a short detail of at most twenty words in the company's own terms. Status is "stated" when you fill it, "not_applicable" when the facet does not apply to this company, and "unknown" otherwise.

Also say whether you recognize this specific company from what you already know ("knows_company").

Rules:
- Never write financial figures, sizes, counts, percentages, tickers or valuations. Use words, not digits.
- Notes: one short sentence, only if something is uncertain; otherwise an empty string."""


def facet_block(f: Facet) -> str:
    captures = re.sub(r"\s*\((Barbara|ours)[^)]*\)", "", f.captures)   # provenance notes stay out of the prompt
    head = f"- {f.name} ({f.label}): {captures}. Example: {f.examples}."
    if f.categories:
        head += f" {'Any that apply' if f.several else 'Exactly one'} of: " + "; ".join(f.categories) + "."
    if f.guide:
        head += " " + f.guide
    return head


def evidence_text(lines: dict[str, str]) -> str:
    """Labeled lines grouped by source ("P1", "W2", "S3"), in label order."""
    groups: dict[str, list[str]] = {}
    for label, text in lines.items():
        groups.setdefault(label.split(".")[0], []).append(f"[{label}] {text}")
    return "\n\n".join(f'<source id="{sid}">\n' + "\n".join(body) + "\n</source>" for sid, body in groups.items())


def build_prompt(company: dict, evidence: str = "") -> str:
    """company: company_name, website, sector. evidence: the labeled lines
    (evidence_text, or verification.evidence.Evidence.text)."""
    fs = facets_for(company["sector"])
    return "\n".join([INSTRUCTIONS, "", f"Company: {company['company_name']} ({company['website']})",
                      f"Sector: {SECTOR_LABELS.get(company['sector'], company['sector'])}", "",
                      "Facets:", *[facet_block(f) for f in fs], "",
                      "Evidence:", evidence or "(no evidence was found for this company)"])


def answer_schema(sector: str) -> dict:
    props, required = {"knows_company": {"type": "boolean"}, "notes": {"type": "string"}}, ["knows_company", "notes"]
    for f in facets_for(sector):
        p = {"status": {"type": "string", "enum": list(STATUSES)}}
        if f.categories:
            p["categories"] = {"type": "array", "items": {"type": "string", "enum": list(f.categories)}}
            p["detail"] = {"type": "string"}
        else:
            p["value"] = {"type": "string"}
        p["cites"] = {"type": "array", "items": {"type": "string"}}
        props[f.name] = {"type": "object", "additionalProperties": False, "required": list(p), "properties": p}
        required.append(f.name)
    return {"type": "object", "additionalProperties": False, "required": required, "properties": props}


def fingerprint(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}\n{model}\n{prompt}".encode("utf-8")).hexdigest()[:16]


def _has_figure(text: str) -> bool:
    return bool(FINANCIAL_FIGURE.search(text) or SCALE_FIGURE.search(text))


def check_answer(raw: dict, sector: str, labels: set[str] | dict | None = None) -> tuple[dict, list[str]]:
    """Checked facets {name: {status, categories, detail} or {status, value},
    plus cites and source} and the issues found.

    Citations are kept only if the label was in the prompt (else issue
    unknown_cite). A filled facet with a valid citation has source
    "evidence"; one without is "model knowledge" (issue from_memory) when
    the model knows the company, and becomes unknown when it doesn't (issue
    unsupported), so nothing is guessed from the name. A single-choice facet
    with several categories keeps the first; a value with a figure is kept
    but flagged."""
    labels = set(labels or ())
    issues: list[str] = []
    known = bool(raw.get("knows_company"))
    if not known:
        issues.append("company_not_known")
    out = {}
    for f in facets_for(sector):
        a = raw.get(f.name) or {}
        status = a.get("status") if a.get("status") in STATUSES else "unknown"
        cites = [c.strip().strip("[]") for c in (a.get("cites") or [])]
        bad = [c for c in cites if c not in labels]
        cites = list(dict.fromkeys(c for c in cites if c in labels))
        if bad:
            issues.append(f"unknown_cite:{f.name}")
        if f.categories:
            cats = list(dict.fromkeys(c for c in (a.get("categories") or []) if c in f.categories))
            if not f.several and len(cats) > 1:
                issues.append(f"several_categories:{f.name}")
                cats = cats[:1]
            if status == "stated" and not cats:
                issues.append(f"no_category:{f.name}")
                status = "unknown"
            text = (a.get("detail") or "").strip()
        else:
            cats, text = None, (a.get("value") or "").strip()
            if status == "stated" and not text:
                status = "unknown"
        source = ""
        if status == "stated":
            if cites:
                source = "evidence"
            elif known:
                source = "model knowledge"
                issues.append(f"from_memory:{f.name}")
            else:
                issues.append(f"unsupported:{f.name}")
                status = "unknown"
        if _has_figure(text):
            issues.append(f"figure_in_value:{f.name}")
        entry = {"status": status, "cites": cites if status == "stated" else [], "source": source}
        if cats is not None:
            entry.update(categories=cats if status == "stated" else [], detail=text if status == "stated" else "")
        else:
            entry["value"] = text if status == "stated" else ""
        out[f.name] = entry
    return out, issues


def table_row(facets: dict) -> dict:
    """Flat columns for sector_facets.csv: <facet>_status, <facet> (text or
    "cat1; cat2: detail"), <facet>_categories ("cat1|cat2"), <facet>_source
    ("evidence" or "model knowledge") and <facet>_cites."""
    row = {}
    for name, a in facets.items():
        row[f"{name}_status"] = a["status"]
        if "categories" in a:
            row[f"{name}_categories"] = "|".join(a["categories"])
            row[name] = ("; ".join(a["categories"]) + (f": {a['detail']}" if a["detail"] else "")) if a["categories"] else ""
        else:
            row[name] = a["value"]
        row[f"{name}_source"] = a.get("source", "")
        row[f"{name}_cites"] = " ".join(a.get("cites", []))
    return row


def schema_json(sector: str) -> str:
    return json.dumps(answer_schema(sector), indent=1)

