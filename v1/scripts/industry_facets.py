"""
Industry-specific facets by SIC2 (Barbara's "SIC2 - 83 Industry Facet
Dictionary", posted 2026-11-04; the copy the code reads is
reference/sic2_industry_facet_dictionary.md).

Each two-digit SIC major group gets four to nineteen free-text facets that
separate business models inside that industry, each with example values.
Every company gets the facets of its own SIC2 (target_sic2_code in the
universe), filled evidence-first from its saved website pages, cited line by
line, with the model's own knowledge filling only gaps (flagged
from_memory), like sector_facets.py. No financial figures.

To change the facets, edit the dictionary file and bump PROMPT_VERSION;
profiles from an older version are redone by the next fill_industry_facets.py
run.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from sector_facets import _has_figure, evidence_text  # noqa: F401  (evidence_text is reused by the fill script)

DICTIONARY = Path(__file__).resolve().parent / "reference" / "sic2_industry_facet_dictionary.md"
PROMPT_VERSION = "2026-11-04a"   # a: Barbara's dictionary as posted 2026-11-04, free-text values, cited
STATUSES = ("stated", "not_applicable", "unknown")

_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def load_dictionary(path: Path = DICTIONARY) -> dict[str, dict]:
    """{sic2: {sic2, title, notes, facets: [{name, label, examples}]}} from the markdown."""
    text = path.read_text(encoding="utf-8")
    out: dict[str, dict] = {}
    for section in re.split(r"\n(?=### SIC )", text)[1:]:
        lines = section.splitlines()
        head = re.match(r"### SIC (\d\d)\s*[—-]+\s*(.+)", lines[0])
        if not head:
            continue
        code, title = head.group(1), head.group(2).strip()
        notes = [_LINK.sub(r"\1", l).strip() for l in lines[1:]
                 if l.strip() and not l.startswith(("|", "#", "[Official"))]
        facets, seen = [], set()
        for line in lines:
            if not line.startswith("|") or "---" in line or "Industry-Specific Facets" in line:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2 or not cells[0]:
                continue
            name, k = slug(cells[0]), 2
            while name in seen:
                name, k = f"{slug(cells[0])}_{k}", k + 1
            seen.add(name)
            facets.append({"name": name, "label": cells[0],
                           "examples": [e.strip() for e in cells[1].split("•") if e.strip()]})
        out[code] = {"sic2": code, "title": title, "notes": " ".join(notes), "facets": facets}
    return out


INSTRUCTIONS = """You describe a company's business model for a private-equity analyst who is choosing comparable public companies. You get the company's name, website and two-digit SIC industry, the facets that matter inside that industry, and evidence about the company: lines from its own website. Every evidence line starts with a label, such as [P1.3] (saved website page 1, line 3).

Base every facet on the evidence. For each facet you fill, cite the labels of the 1 to 3 lines that best support it in "cites". Only when the evidence says nothing about a facet may you use what you already know about this specific company; then leave "cites" empty. Never guess from the company's name, its web address or what is typical for similar companies: a facet that neither the evidence nor your knowledge of this company supports is "unknown".

Describe the company as it is now: leave out businesses the evidence or your knowledge says it has sold, spun off or closed. If the company has several lines of business, cover the ones the facet applies to, the largest first.

Each facet takes a short value in the company's own terms, at most twenty-five words, in the style of the facet's examples. Status is "stated" when you fill it, "not_applicable" when the facet does not apply to this company (for example, a facet about a product line the company does not have), and "unknown" otherwise.

Also say whether you recognize this specific company from what you already know ("knows_company").

Rules:
- Never write financial figures, sizes, counts, percentages, tickers or valuations. Where the examples show numbers, describe the scale or mix in words instead.
- Notes: one short sentence, only if something is uncertain; otherwise an empty string."""


def facet_block(f: dict) -> str:
    return f"- {f['name']} ({f['label']}). Examples: " + "; ".join(f["examples"]) + "."


def build_prompt(company: dict, industry: dict, evidence: str = "") -> str:
    """company: company_name, website. industry: one entry of load_dictionary()."""
    parts = [INSTRUCTIONS, "", f"Company: {company['company_name']} ({company['website']})",
             f"Industry (SIC {industry['sic2']}): {industry['title']}"]
    if industry["notes"]:
        parts.append(f"About this industry group: {industry['notes']}")
    parts += ["", "Facets:", *[facet_block(f) for f in industry["facets"]], "",
              "Evidence:", evidence or "(no evidence was found for this company)"]
    return "\n".join(parts)


def answer_schema(industry: dict) -> dict:
    props = {"knows_company": {"type": "boolean"}, "notes": {"type": "string"}}
    for f in industry["facets"]:
        props[f["name"]] = {"type": "object", "additionalProperties": False,
                            "properties": {"status": {"type": "string", "enum": list(STATUSES)},
                                           "value": {"type": "string"},
                                           "cites": {"type": "array", "items": {"type": "string"}}},
                            "required": ["status", "value", "cites"]}
    return {"type": "object", "additionalProperties": False, "properties": props, "required": list(props)}


def fingerprint(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}\n{model}\n{prompt}".encode("utf-8")).hexdigest()[:16]


def check_answer(raw: dict, industry: dict, labels: set[str] | dict | None = None) -> tuple[dict, list[str]]:
    """Checked facets {name: {status, value, cites, source}} and the issues
    found, with the same rules as sector_facets.check_answer: a citation is
    kept only if its label was in the prompt; a filled facet without a valid
    citation is "model knowledge" (from_memory) when the model knows the
    company and becomes unknown when it doesn't; a value with a figure is
    kept but flagged."""
    labels = set(labels or ())
    issues: list[str] = []
    known = bool(raw.get("knows_company"))
    if not known:
        issues.append("company_not_known")
    out = {}
    for f in industry["facets"]:
        a = raw.get(f["name"]) or {}
        status = a.get("status") if a.get("status") in STATUSES else "unknown"
        cites = [c.strip().strip("[]") for c in (a.get("cites") or [])]
        if [c for c in cites if c not in labels]:
            issues.append(f"unknown_cite:{f['name']}")
        cites = list(dict.fromkeys(c for c in cites if c in labels))
        value = (a.get("value") or "").strip()
        if status == "stated" and not value:
            status = "unknown"
        source = ""
        if status == "stated":
            if cites:
                source = "evidence"
            elif known:
                source = "model knowledge"
                issues.append(f"from_memory:{f['name']}")
            else:
                issues.append(f"unsupported:{f['name']}")
                status = "unknown"
        if status == "stated" and _has_figure(value):
            issues.append(f"figure_in_value:{f['name']}")
        out[f["name"]] = {"label": f["label"], "status": status, "value": value if status == "stated" else "",
                          "cites": cites if status == "stated" else [], "source": source}
    return out, issues


def schema_json(industry: dict) -> str:
    return json.dumps(answer_schema(industry), indent=1)
