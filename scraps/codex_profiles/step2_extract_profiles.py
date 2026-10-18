"""
SCRAPS: set aside on 2026-10-18 (Codex extraction was started before the
matching method was settled). Kept runnable for reference; see scraps/README.md.

Codex profile extraction: a model reads the website pages saved
by website_scrape/scrape_websites.py and fills in a structured profile per company, then the
script verifies it and writes the tables used for matching.

The reading is done by Codex CLI by default (`codex exec`, signed in with each
student's own ChatGPT account, so no API credits are needed). The Anthropic
API can be used instead with --backend anthropic.

The answer format and every check are defined once, with Pydantic, in
profile_schema.py: the same models generate the JSON Schema the model must
follow and validate each answer (shape first, then each item on its own).
List and tag fields come back as items, each with its own verbatim quote;
prose fields (description, business model, geography) with 1-3 quotes. Each
quote must be found on a scraped page, which becomes that item's source.
Fields end up "stated", "unknown" (the pages don't say), or "unverified"
(items given but none passed); dropped items keep their reason.
Also returned: identifying_terms (used for masking) and notes. The
matching_summary and evidence_quality are built by the script from the
checked items (profile_schema.build_summary / rate_evidence), not by the model.

The model sees only the cleaned page text, with the company's own name and
website replaced by "the Company" and pages labeled by id, not URL: no
company name, SIC codes, financial fields, or ticker. It is also told not to
use outside knowledge, so a public company is profiled the way a private one
would be. Quotes are checked against this masked text.

Masking: every field except `brands` refers to the company as "the Company"
and describes products generically, without brand names. The script then
replaces any remaining company-name variant, domain name, or identifying term
the model listed, and records each replacement.

Guards against guessing:
  - one quote per item, checked against the saved page text; only items whose
    quote is found (and at least 5 words) reach the matching table
  - values mentioning money, headcount, tickers, or stock language are dropped
  - sites with almost no text get an all-"unknown" profile (no model call)
  - validation_report.csv counts, per column, what passed and why items were
    dropped; step3_audit_profiles.py samples profiles for human review of accuracy

Reads outputs-local/website_scrape/page_text/. Every stage's data is kept
(under --out, default outputs-local/scraps/codex_profiles/; see output_paths()):
  step2_extract/answer_schema.json    the JSON Schema the model must follow
  step2_extract/codex_runs/<IQ_ID>/<run time>/
                         prompt.txt     exactly what the model was given
                         response.json  its raw answer, before verification
                         events.jsonl, stderr.txt   Codex logs (incl. usage)
                         run.json       command, model, status, timings
  step2_extract/profiles/<IQ_ID>.json   the checked profile (earlier versions
                          move to step2_extract/profiles_history/)
  final_tables/
  matching_inputs.csv     one row per company: non-financial identifiers and
                          verified, masked profile fields with statuses and
                          source URLs. No financial columns.
  validation_report.csv   per column: stated/unknown/unverified counts, items
                          proposed vs passed, and drop reasons
  financial_fields.csv    only IQ_COMPANY_ID and the supplied financial columns,
                          kept apart so they can't leak into matching inputs

Usage:
  python step2_extract_profiles.py --sic2 35 --dry-run   # write prompts, no model calls
  python step2_extract_profiles.py --sic2 35             # profile one industry group
  python step2_extract_profiles.py                       # every scraped company
  python step2_extract_profiles.py --refresh             # redo existing profiles
  python step2_extract_profiles.py --tables-only         # rebuild final_tables/ only
  python step2_extract_profiles.py --reverify            # re-check saved answers

Codex setup (once per laptop): npm install -g @openai/codex, then `codex login`
and sign in with your ChatGPT account. Never commit ~/.codex/auth.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from pydantic import ValidationError

import profile_schema as pm  # also puts website_scrape/ and src/ on the import path
from fetch_and_clean import load_companies
from profile_schema import FIELDS, TEXT_FIELDS, LIST_FIELDS
from project_data import OUTPUTS_LOCAL
from scrape_websites import DEFAULT_OUT as SCRAPE_OUT, company_list
from scrape_websites import output_paths as scrape_paths

DEFAULT_OUT = OUTPUTS_LOCAL / "scraps" / "codex_profiles"


def output_paths(out_dir: Path) -> SimpleNamespace:
    """Where the Codex work writes (default outputs-local/scraps/codex_profiles/),
    plus the scrape's page text it reads."""
    s2 = out_dir / "step2_extract"
    return SimpleNamespace(
        page_text=scrape_paths(SCRAPE_OUT).page_text,
        codex_runs=s2 / "codex_runs",                # prompt, raw answer, logs per call
        answer_schema=s2 / "answer_schema.json",
        profiles=s2 / "profiles",                    # checked profiles
        profiles_history=s2 / "profiles_history",
        prompts_dry_run=s2 / "prompts_dry_run",
        audit=out_dir / "step3_audit",
        tables=out_dir / "final_tables",             # matching_inputs, financial_fields, ...
        logs=out_dir / "logs",
    )


FINANCIAL_COLUMNS = [
    "target_revenue",
    "target_ebitda",
    "target_margin",
    "target_debt_to_revenue",
    "target_ev_to_ebitda",
]

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
# models that accept the Anthropic server-side refusal fallback ("default" form)
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
MAX_INPUT_WORDS = 7000       # cap on page text sent per company
MIN_WORDS_FOR_LLM = 40       # below this the site says too little to profile
CODEX_TIMEOUT_SECONDS = 600
# Bump when the prompt or answer format changes; profiles from an older
# version are redone by the next run and left out of the tables until then.
PROMPT_VERSION = "2026-10-18e"   # e: model doesn't see the company name, website or page URLs

# fields written without names (brands is the one place names belong)
MASKED_FIELDS = [f for f in TEXT_FIELDS + LIST_FIELDS if f != "brands"]

FIELD_GUIDE = """\
- business_description: 2-3 neutral sentences on what the company does.
- products_services: the main products, product lines, or services, described
  generically (e.g. "zero-turn riding mowers", not a trade name).
- customers: who buys them (customer segments or types of buyer).
- end_markets: industries or markets the offerings are used in.
- business_model: how the company makes money (what it sells, to whom, how;
  e.g. "designs and manufactures equipment sold through dealers, plus
  replacement parts and service").
- sales_channels: how it reaches customers (direct sales force, dealers,
  distributors, e-commerce, retail stores, OEM partners, ...).
- geographic_footprint: where it sells or operates, as stated.
- brands: brand or product-line names, if the pages list them.
- customer_types, revenue_streams, operating_roles: tags from the allowed
  list that the pages support."""

INSTRUCTIONS = f"""\
You build structured company profiles for a research project that matches \
private companies to comparable companies. You will receive the text of a \
few pages from one company's website. Each page is labeled with an id (P1, \
P2, ...). The company's own name and website have been replaced by "the \
Company" throughout. Everything you need is in this message: do not run \
commands, open files, or browse.

Work only from those pages. Do not try to work out which company it is, and \
do not use anything you know about it from elsewhere, even if you recognize \
it: the same method has to work for a private company nobody has heard of. If the pages don't say something, mark \
that field "unknown" with an empty value (or no items) instead of inferring it. A \
reasonable reading of what the pages say is fine; filling gaps from general \
knowledge of the industry is not.

Evidence, checked automatically against the pages:
- List fields and tag fields: every item needs its own "quote" that supports \
that item. A quote is copied exactly from one page, character for character, \
5 to 25 words long (for "brands": the words on the page that contain the \
brand name). Items whose quote isn't on the pages, or is too short, are \
discarded. If you can't quote support for an item, leave it out.
- Prose fields (business_description, business_model, geographic_footprint): \
1-3 quotes in "evidence", same rules.

Leave out financial figures (revenue, sales, profit, order sizes in money), \
employee counts, stock tickers, exchange listings, and anything about \
shareholders or investors. Describe the business, not its finances.

Masking: in every field except "brands", and in "notes", never write the company's name, abbreviations of it, its website \
domain, or the names of its brands or trade-named products. Write "the \
Company" instead, and describe products generically. Brand and product-line \
names go only in "brands". Evidence quotes stay verbatim even if they \
contain names. In "identifying_terms", list every name, abbreviation, \
domain, and brand that would identify this company.

Fields:
{FIELD_GUIDE}

Also "notes": one sentence on gaps or caveats (e.g. "pages cover only one of \
several businesses"), or ""."""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_prompt(record: dict) -> tuple[str, dict[str, str]]:
    """Page text for the model, plus page id -> text for checking quotes.
    Blocks repeated across pages (menus, footers) are sent once. The model
    never sees the company's name or website: both are replaced by "the
    Company" in the text, and pages are labeled by id only, not URL, so a
    known company can't be recognized and described from memory."""
    names = name_variants(record["company_name"], record["website"])
    seen, budget = set(), MAX_INPUT_WORDS
    parts, page_text = [], {}
    for page in record["pages"]:
        lines = [x for x in [page["title"], page["meta"]] if x]
        for block in page["blocks"]:
            key = block.lower()
            if key in seen:
                continue
            seen.add(key)
            lines.append(block)
        text = mask("\n".join(lines), names, [])[0]
        words = text.split()
        if len(words) > budget:
            text = " ".join(words[:budget])
        if not text:
            continue
        budget -= len(text.split())
        page_text[page["page_id"]] = text
        snapshot = f' archived="{page["snapshot"]}"' if page["snapshot"] else ""
        parts.append(f'<page id="{page["page_id"]}"{snapshot}>\n{text}\n</page>')
        if budget <= 0:
            break
    return "\n\n".join(parts), page_text


# ---------------------------------------------------------------- verification

def input_fingerprint(record: dict) -> str:
    """sha256 of the page text the model reads for this company. A profile
    whose fingerprint no longer matches (page text re-parsed or re-scraped)
    is outdated."""
    return hashlib.sha256(build_prompt(record)[0].encode("utf-8")).hexdigest()


def is_current(profile: dict, record: dict | None) -> bool:
    """Made with the current prompt version from the current page text."""
    return (profile.get("prompt_version") == PROMPT_VERSION and record is not None
            and profile.get("input_sha256") == input_fingerprint(record))


def load_page_text(out_dir: Path, iq_id: str) -> dict | None:
    path = output_paths(out_dir).page_text / f"{iq_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


LEGAL_SUFFIXES = re.compile(
    r"\b(?:inc|incorporated|corp|corporation|co|ltd|limited|llc|plc|lp)\b\.?", re.I)
GENERIC_WORDS = re.compile(
    r"\b(?:company|companies|holdings?|group|international|the)\b", re.I)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace(",", " ")).strip(" .&-")


def name_variants(company_name: str, website: str) -> list[str]:
    """Ways the company's own name can appear: the full name, without legal
    suffixes ("BrightView Holdings"), without generic words too ("BrightView"),
    and the website's domain ("brightview.com", "brightview")."""
    full = company_name.strip()
    no_legal = _squash(LEGAL_SUFFIXES.sub(" ", full))
    core = _squash(GENERIC_WORDS.sub(" ", no_legal))
    domain = re.sub(r"^(?:https?://)?(?:www\.)?", "", website.strip().lower()).split("/")[0]
    # the registered name, not a subdomain: home.quakerhoughton.com -> quakerhoughton
    labels = domain.split(".")
    stem = labels[-3] if len(labels) >= 3 and labels[-2] in ("co", "com") else labels[-2] \
        if len(labels) >= 2 else labels[0]
    names = [full, no_legal, core]
    # a leading abbreviation: "CPI Card Group" -> "CPI" (from Riya's scraper)
    lead = full.split()[0].strip(",.") if full.split() else ""
    if len(lead) >= 3 and lead.isupper() and lead.isalpha():
        names.append(lead)
    # After a rebrand the site uses a newer name ("Quaker Houghton" for Quaker
    # Chemical): the name's first word counts if the domain starts with it
    # (from Riya's scraper). The stem itself also matches with spaces.
    first = re.findall(r"[A-Za-z][\w'-]*", core)[:1]
    if (first and len(first[0]) >= 4 and first[0].lower() not in GENERIC_NAME_WORDS
            and stem.startswith(first[0].lower())):
        names.append(first[0])
    # each name also in capitals, as in logos and headings ("ASTEC")
    variants = names + [n.upper() for n in names] + [domain, stem]
    return [v for v in dict.fromkeys(variants) if len(v) >= 3]


# Words that must not be masked on their own, even when a company's name
# starts with them ("Energy Recovery", "American Coastal"); from Riya's scraper.
GENERIC_NAME_WORDS = {
    "advanced", "alliance", "american", "applied", "capital", "central", "data",
    "digital", "energy", "first", "general", "global", "great", "innovative",
    "international", "national", "north", "pacific", "power", "precision",
    "premier", "smart", "solutions", "southern", "standard", "systems",
    "united", "universal", "western", "eastern", "new", "the", "best", "home",
}


def mask(text: str, names: list[str], terms: list[str]) -> tuple[str, list[str]]:
    """Replace company names with "the Company" and other identifying terms
    with "[brand]"; return the text and what was replaced. Longest terms go
    first, so "BrightView Design Group" isn't half-replaced via "BrightView"."""
    fixes = []
    # Names and brands match only as capitalized: many are ordinary phrases
    # ("Energy Recovery", "Power Solutions", "Advantage") that must stay when
    # used generically ("energy recovery devices"). Domains match in any case.
    # A domain stem ("waters", "repay") matches in any case except all
    # lowercase, which is the ordinary word ("coastal waters").
    pairs = ([(n, "the Company", re.I if "." in n or n.islower() else 0) for n in names]
             + [(t, "[brand]", 0) for t in terms])
    # web addresses that contain the domain stem ("graco.com/us/about-graco",
    # "gormanrupp.co.za") are replaced whole, first
    for n in names:
        if n.islower() and "." not in n:
            url = re.compile(r"[^\s\"'<>()]*" + re.escape(n) + r"[^\s\"'<>()]*", re.I)
            hits = [m for m in url.finditer(text) if re.search(r"[./]", m.group(0))]
            if hits:
                fixes.append(n)
                for m in reversed(hits):
                    text = text[:m.start()] + "the Company" + text[m.end():]
    for term, repl, flags in sorted(pairs, key=lambda p: -len(p[0])):
        stem = term.islower() and "." not in term
        # a stem also matches written as words: quakerhoughton = "Quaker Houghton"
        body = r"[\s-]?".join(map(re.escape, term)) if stem else re.escape(term)
        pattern = re.compile(r"(?<![\w])" + body + r"(?![\w])", flags)
        found = [m for m in pattern.finditer(text) if not (stem and m.group(0).islower())]
        if found:
            fixes.append(term)
            for m in reversed(found):
                text = text[:m.start()] + repl + text[m.end():]
    text = re.sub(r"\b[Tt]he the Company\b", "the Company", text)   # "the AAON Way"
    return text, fixes


def verify(raw: dict, page_text: dict[str, str], names: list[str]) -> dict:
    """Validate a raw answer in two layers (see profile_schema.py), then mask
    names left in the masked fields. Raises pydantic.ValidationError if the
    answer doesn't have the required shape."""
    answer = pm.ProfileAnswer.model_validate(raw)          # layer 1: shape
    profile = pm.check_answer(answer, page_text)           # layer 2: rules, per item

    # Masking: names the model should have left out of these fields
    brands = pm.verified_values(profile["brands"])
    terms = [t for t in dict.fromkeys(profile["identifying_terms"] + brands)
             if len(t) >= 3 and t not in names]
    fixes = []
    for field in MASKED_FIELDS:
        record = profile[field]
        for part in record.get("items", []):
            part["value"], found = mask(part["value"], names, terms)
            fixes += found
        if "value" in record:
            record["value"], found = mask(record["value"], names, terms)
            fixes += found
    for key in ("notes",):
        profile[key], found = mask(profile[key], names, terms)
        fixes += found
    profile["masking_fixes"] = sorted(set(fixes))
    if pm.leaks_financials(profile["notes"]):
        profile["notes"] = ""
        profile["issues"].append({"type": "financial", "msg": "notes mentioned money, "
                                  "headcount or stock information; dropped"})
    # Built in code from the checked, masked items (see profile_schema.py)
    profile["matching_summary"] = pm.build_summary(profile)
    profile["evidence_quality"] = pm.rate_evidence(profile)
    return profile


def unknown_profile(reason: str) -> dict:
    """All-unknown profile, same format as a checked one."""
    profile = {f: ({"status": "unknown", "value": "", "evidence": [], "issues": []}
                   if f in TEXT_FIELDS else {"status": "unknown", "items": [], "issues": []})
               for f in FIELDS}
    profile.update(identifying_terms=[], masking_fixes=[], issues=[], notes=reason)
    profile["matching_summary"] = pm.build_summary(profile)
    profile["evidence_quality"] = pm.rate_evidence(profile)
    return profile


# ---------------------------------------------------------------- model calls

def find_codex() -> str:
    """The Codex executable (CODEX_BIN overrides, e.g. for testing)."""
    exe = os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not exe:
        raise SystemExit(
            "Codex CLI not found. Install it once per laptop:\n"
            "  npm install -g @openai/codex\n"
            "  codex login      (sign in with your ChatGPT account)\n"
            "or use --backend anthropic with an API key.")
    return exe


def call_codex(prompt: str, run_dir: Path, schema_path: Path, workdir: str,
               model: str | None, effort: str | None) -> dict:
    """Run `codex exec` once; the answer is written to run_dir/response.json."""
    response_path = run_dir / "response.json"
    cmd = [find_codex(), "exec",
           "--skip-git-repo-check",   # workdir is an empty temp folder, not the repo,
           "--ephemeral",             # so Codex doesn't load the repo's AGENTS.md
           "--sandbox", "read-only",
           "--cd", workdir,
           "--output-schema", str(schema_path),
           "--output-last-message", str(response_path),
           "--json"]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--config", f"model_reasoning_effort={effort}"]
    cmd.append("-")                   # read the prompt from stdin
    started = time.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", timeout=CODEX_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {"llm_status": "timeout", "command": cmd}
    (run_dir / "events.jsonl").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    meta = {"command": cmd, "returncode": proc.returncode,
            "seconds": round(time.time() - started, 1), "usage": codex_usage(proc.stdout)}
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return {"llm_status": "codex_error", "error": " / ".join(tail)[:300], **meta}
    if not response_path.exists() or not response_path.read_text(encoding="utf-8").strip():
        return {"llm_status": "no_output", **meta}
    return {"llm_status": "ok", "text": response_path.read_text(encoding="utf-8"), **meta}


def codex_usage(events: str) -> dict:
    """Token usage reported in Codex's JSONL events (last one wins), if any."""
    usage = {}
    for line in (events or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return usage


def call_anthropic(prompt: str, run_dir: Path, model: str, effort: str | None) -> dict:
    """One Anthropic API call (needs ANTHROPIC_API_KEY or `ant auth login`)."""
    import anthropic

    client = anthropic.Anthropic(max_retries=4)
    extra = {}
    if model in FALLBACK_MODELS:
        # if a safety classifier declines, the API retries on a fallback model
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=INSTRUCTIONS,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort or "medium",
                           "format": {"type": "json_schema", "schema": pm.answer_schema()}},
            **extra,
        )
    except anthropic.BadRequestError as exc:
        return {"llm_status": f"bad_request: {exc.message}"[:200]}
    except anthropic.RateLimitError:
        return {"llm_status": "rate_limited"}
    except anthropic.APIStatusError as exc:
        return {"llm_status": f"api_error_{exc.status_code}"}
    except anthropic.APIConnectionError:
        return {"llm_status": "connection_error"}
    meta = {"model": response.model, "request_id": response._request_id,
            "usage": {"input_tokens": response.usage.input_tokens,
                      "output_tokens": response.usage.output_tokens}}
    if response.stop_reason == "refusal":
        return {"llm_status": "refusal", **meta}
    if response.stop_reason == "max_tokens":
        return {"llm_status": "truncated", **meta}
    text = next((b.text for b in response.content if b.type == "text"), "")
    (run_dir / "response.json").write_text(text, encoding="utf-8")
    return {"llm_status": "ok", "text": text, **meta}


def extract_one(record: dict, out_dir: Path, args, schema_path: Path, workdir: str) -> dict:
    """Read one company's pages with the model, keep every artifact, and
    return the verified profile."""
    run_dir = output_paths(out_dir).codex_runs / record["IQ_COMPANY_ID"] / now_iso().replace(":", "")
    run_dir.mkdir(parents=True, exist_ok=True)
    pages_prompt, page_text = build_prompt(record)
    if args.backend == "codex":
        prompt = INSTRUCTIONS + "\n\n" + pages_prompt
        result = call_codex(prompt, run_dir, schema_path, workdir, args.model, args.effort)
    else:
        prompt = pages_prompt   # instructions go in the system prompt
        result = call_anthropic(prompt, run_dir, args.model or DEFAULT_ANTHROPIC_MODEL,
                                args.effort)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    text = result.pop("text", None)
    if result["llm_status"] == "ok":
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            result["llm_status"] = "invalid_json"
        else:
            names = name_variants(record["company_name"], record["website"])
            try:
                result["profile"] = verify(raw, page_text, names)
            except ValidationError as exc:   # wrong shape: rejected as a whole
                result["llm_status"] = "invalid_answer"
                result["shape_errors"] = [{"loc": ".".join(map(str, e["loc"])),
                                           "type": e["type"], "msg": e["msg"]}
                                          for e in exc.errors()][:50]
    run_info = {"backend": args.backend, "model": args.model or "", "effort": args.effort or "",
                "prompt_version": PROMPT_VERSION, "finished_at": now_iso(),
                **{k: v for k, v in result.items() if k != "profile"}}
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=1), encoding="utf-8")
    result["llm_run_dir"] = run_dir.relative_to(out_dir).as_posix()
    return result


# ---------------------------------------------------------------- outputs

def profile_record(record: dict, result: dict, args) -> dict:
    """Profile file contents: company ids, page sources, and the profile."""
    return {
        "IQ_COMPANY_ID": record["IQ_COMPANY_ID"],
        "company_name": record["company_name"],
        "website": record["website"],
        "scrape_status": record["status"],
        "scrape_method": record["method"],
        "scraped_at": record.get("scraped_at", ""),
        "pages": [{k: p.get(k, "") for k in ("page_id", "url", "category", "method",
                                              "snapshot", "fetched_at", "raw_html_file")}
                  for p in record["pages"]],
        "backend": args.backend,
        "model": args.model or result.get("model", ""),
        "prompt_version": PROMPT_VERSION,
        "input_sha256": input_fingerprint(record),
        "extracted_at": now_iso(),
        **result,
    }


def flatten(rec: dict) -> dict:
    """One matching-table row: only verified values are filled in."""
    urls = {p["page_id"]: p["url"] for p in rec["pages"]}
    profile = rec.get("profile") or unknown_profile(rec.get("llm_status", ""))
    row = {"IQ_COMPANY_ID": rec["IQ_COMPANY_ID"], "scrape_status": rec["scrape_status"],
           "llm_status": rec.get("llm_status", ""),
           "evidence_quality": profile["evidence_quality"],
           "matching_summary": profile["matching_summary"]}
    for field in FIELDS:
        record = profile[field]
        row[field] = "; ".join(pm.verified_values(record))
        row[f"{field}__status"] = record["status"]
        row[f"{field}__sources"] = " | ".join(urls[s] for s in pm.source_pages(record)
                                              if s in urls)
    row["masking_fixes"] = "; ".join(profile.get("masking_fixes", []))
    row["notes"] = profile["notes"]
    row["all_source_urls"] = " | ".join(urls.values())
    row["backend"] = rec.get("backend", "")
    row["extracted_at"] = rec.get("extracted_at", "")
    return row


def validation_report(profiles: list[dict]) -> pd.DataFrame:
    """Per column: how many companies have it stated / unknown / unverified,
    how many items the model proposed and how many passed, and why the rest
    were dropped (counts per rule)."""
    rows = []
    for field in FIELDS:
        row = {"field": field, "stated": 0, "unknown": 0, "unverified": 0,
               "items_proposed": 0, "items_passed": 0}
        reasons: dict[str, int] = {}
        for rec in profiles:
            record = (rec.get("profile") or unknown_profile(""))[field]
            row[record["status"]] = row.get(record["status"], 0) + 1
            for part in record.get("items", record.get("evidence", [])):
                row["items_proposed"] += 1
                row["items_passed"] += part["verified"]
                for issue in part["issues"]:
                    reasons[issue["type"]] = reasons.get(issue["type"], 0) + 1
            for issue in record["issues"]:
                reasons[issue["type"]] = reasons.get(issue["type"], 0) + 1
        row["pass_rate"] = (round(row["items_passed"] / row["items_proposed"], 3)
                            if row["items_proposed"] else None)
        row["dropped_because"] = "; ".join(f"{k}: {v}" for k, v in sorted(reasons.items()))
        rows.append(row)
    # Profile-level problems (currently: notes dropped for financial language)
    notes_issues: dict[str, int] = {}
    for rec in profiles:
        for issue in (rec.get("profile") or {}).get("issues", []):
            notes_issues[issue["type"]] = notes_issues.get(issue["type"], 0) + 1
    rows.append({"field": "notes", "dropped_because": "; ".join(
        f"{k}: {v}" for k, v in sorted(notes_issues.items()))})
    return pd.DataFrame(rows)


def write_tables(out_dir: Path, input_csv: str) -> None:
    profiles = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(output_paths(out_dir).profiles.glob("*.json"))]
    current = [p for p in profiles if is_current(p, load_page_text(out_dir, p["IQ_COMPANY_ID"]))]
    if len(current) < len(profiles):
        print(f"Note: {len(profiles) - len(current)} profiles are outdated (older prompt "
              "version, or page text changed since) and left out of the tables; the "
              "next run redoes them.")
    profiles = current
    if not profiles:
        print("No current profiles yet; nothing to tabulate.")
        return
    tables = output_paths(out_dir).tables
    tables.mkdir(parents=True, exist_ok=True)
    ids = load_companies(input_csv)
    rows = [flatten(r) for r in profiles]
    # Every row is validated (profile_schema.MatchingRow) before anything is written
    problems = []
    for rec, row in zip(profiles, rows):
        try:
            pm.MatchingRow.model_validate(
                row, context={"names": name_variants(rec["company_name"], rec["website"])})
        except ValidationError as exc:
            problems += [f"{rec['company_name']}: {e['msg']}" for e in exc.errors()]
    if problems:
        raise SystemExit("matching_inputs.csv not written; rows failed validation:\n  "
                         + "\n  ".join(problems[:30]))
    flat = pd.DataFrame(rows)
    matching = ids.merge(flat, on="IQ_COMPANY_ID", how="inner")
    assert not set(FINANCIAL_COLUMNS) & set(matching.columns)
    matching.to_csv(tables / "matching_inputs.csv", index=False)

    raw = pd.read_csv(input_csv, dtype=str)
    missing = [c for c in FINANCIAL_COLUMNS if c not in raw.columns]
    if missing:
        print(f"Note: input has no {missing}; financial_fields.csv not written.")
    else:
        fin = raw[["IQ_COMPANY_ID"] + FINANCIAL_COLUMNS]
        for rec in fin.to_dict("records"):
            pm.FinancialRow.model_validate(rec)   # numbers only, no other columns
        fin[fin["IQ_COMPANY_ID"].isin(matching["IQ_COMPANY_ID"])].to_csv(
            tables / "financial_fields.csv", index=False)

    report = validation_report(profiles)
    report.to_csv(tables / "validation_report.csv", index=False)
    print(f"\nSaved matching_inputs.csv ({len(matching)} companies), financial_fields.csv "
          f"and validation_report.csv in {tables}.")
    print("\nValidation by column (stated = at least one item backed by a quote found "
          "on the company's pages):")
    fields_only = report[report["field"] != "notes"].drop(columns="dropped_because")
    counts = ["stated", "unknown", "unverified", "items_proposed", "items_passed"]
    print(fields_only.astype({c: int for c in counts}).to_string(index=False))
    drops = report[report["dropped_because"] != ""][["field", "dropped_because"]]
    if not drops.empty:
        print("\nWhy items were dropped:")
        print(drops.to_string(index=False))


def reverify(out_dir: Path, ids: set[str]) -> None:
    """Re-apply verify() to each saved raw answer (step2_extract/codex_runs/<IQ>/<run>/response.json),
    archiving the previous profile. Used after changing the checks."""
    paths = output_paths(out_dir)
    history_dir = paths.profiles_history
    done = 0
    for path in sorted(paths.profiles.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec["IQ_COMPANY_ID"] not in ids or rec.get("llm_status") != "ok":
            continue
        record = json.loads((paths.page_text / path.name).read_text(encoding="utf-8"))
        if not is_current(rec, record):
            continue   # answer was made from other page text or format; needs a new run
        raw = json.loads((out_dir / rec["llm_run_dir"] / "response.json").read_text(encoding="utf-8"))
        page_text = build_prompt(record)[1]
        rec["profile"] = verify(raw, page_text, name_variants(record["company_name"],
                                                              record["website"]))
        rec["reverified_at"] = now_iso()
        history_dir.mkdir(exist_ok=True)
        path.replace(history_dir / f"{path.stem}_{now_iso().replace(':', '')}.json")
        path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        done += 1
    print(f"Re-verified {done} saved profiles (no model calls).")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--input", help="company list CSV (default: snapshot in data_manifest.json)")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--sic2", nargs="*", help="only these 2-digit SIC codes")
    p.add_argument("--tickers", nargs="*", help="only these tickers")
    p.add_argument("--limit", type=int, help="stop after N companies")
    p.add_argument("--refresh", action="store_true", help="redo existing profiles")
    p.add_argument("--backend", default="codex", choices=["codex", "anthropic"])
    p.add_argument("--model", help="model name (default: Codex's configured model, "
                                   f"or {DEFAULT_ANTHROPIC_MODEL} for anthropic)")
    p.add_argument("--effort", choices=["low", "medium", "high"],
                   help="reasoning effort (default: the backend's own default)")
    p.add_argument("--workers", type=int, default=2, help="companies processed in parallel")
    p.add_argument("--tables-only", action="store_true", help="only rebuild the CSVs")
    p.add_argument("--reverify", action="store_true",
                   help="re-run verification and masking on the saved model answers "
                        "(after a change to those checks); no model calls")
    p.add_argument("--dry-run", action="store_true",
                   help="write the prompts to prompts/ instead of calling the model")
    args = p.parse_args()

    input_csv = company_list(args.input)
    out_dir = Path(args.out).resolve()
    if args.tables_only:
        write_tables(out_dir, input_csv)
        return

    companies = load_companies(input_csv)
    if args.sic2:
        companies = companies[companies["target_sic2_code"].isin(args.sic2)]
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        companies = companies[companies["target_ciq_ticker"].str.upper().isin(wanted)]
    if args.limit:
        companies = companies.head(args.limit)

    paths = output_paths(out_dir)
    profiles_dir = paths.profiles
    profiles_dir.mkdir(parents=True, exist_ok=True)
    if args.reverify:
        reverify(out_dir, set(companies["IQ_COMPANY_ID"]))
        write_tables(out_dir, input_csv)
        return
    todo = []
    for iq_id in companies["IQ_COMPANY_ID"]:
        pages_path = paths.page_text / f"{iq_id}.json"
        if not pages_path.exists():
            continue  # not scraped yet
        out_path = profiles_dir / f"{iq_id}.json"
        if out_path.exists() and not args.refresh:
            old = json.loads(out_path.read_text(encoding="utf-8"))
            if (old.get("llm_status") in ("ok", "skipped")
                    and is_current(old, json.loads(pages_path.read_text(encoding="utf-8")))):
                continue   # done with the current prompt, format and page text
        todo.append((json.loads(pages_path.read_text(encoding="utf-8")), out_path))
    if not todo:
        print("Nothing to do: no scraped companies without a profile "
              "(run website_scrape/scrape_websites.py first, or pass --refresh).")
        write_tables(out_dir, input_csv)
        return

    paths.codex_runs.mkdir(parents=True, exist_ok=True)
    schema_path = paths.answer_schema
    schema_path.write_text(json.dumps(pm.answer_schema(), indent=1), encoding="utf-8")

    if args.dry_run:
        prompt_dir = paths.prompts_dry_run
        prompt_dir.mkdir(parents=True, exist_ok=True)
        words = 0
        for record, _ in todo:
            prompt = INSTRUCTIONS + "\n\n" + build_prompt(record)[0]
            words += len(prompt.split())
            (prompt_dir / f"{record['IQ_COMPANY_ID']}.txt").write_text(prompt, encoding="utf-8")
        print(f"Wrote {len(todo)} prompts to {prompt_dir} (~{words:,} words in total) "
              f"and the output schema to {schema_path}.")
        return

    if args.backend == "codex":
        find_codex()  # fail early with setup instructions
    workdir = tempfile.mkdtemp(prefix="codex_task3_")
    history_dir = paths.profiles_history

    out_of_quota = threading.Event()

    def run(record, out_path):
        if out_of_quota.is_set():
            return record, {"llm_status": "not_run"}
        # Thin sites are still profiled (what little they say is evidence);
        # unreadable ones get an all-unknown profile without a model call.
        if record.get("word_count", 0) < MIN_WORDS_FOR_LLM:
            result = {"llm_status": "skipped",
                      "profile": unknown_profile(f"website not readable ({record['status']})")}
        else:
            result = extract_one(record, out_dir, args, schema_path, workdir)
            # The signed-in account's usage limit: stop, rather than record an
            # error for every remaining company. The call's logs stay in codex_runs/.
            if (result["llm_status"] == "rate_limited" or (result["llm_status"] == "codex_error"
                    and "usage limit" in result.get("error", "").lower())):
                out_of_quota.set()
                return record, {**result, "llm_status": "not_run"}
        if out_path.exists():   # keep the earlier profile rather than overwrite it
            history_dir.mkdir(exist_ok=True)
            out_path.replace(history_dir / f"{out_path.stem}_{now_iso().replace(':', '')}.json")
        out_path.write_text(json.dumps(profile_record(record, result, args), indent=1,
                                       ensure_ascii=False), encoding="utf-8")
        return record, result

    print(f"Profiling {len(todo)} companies with {args.backend} ({args.workers} at a time)...")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run, r, o) for r, o in todo]
        for n, fut in enumerate(as_completed(futures), start=1):
            record, result = fut.result()
            if result["llm_status"] == "not_run":
                continue
            prof = result.get("profile")
            known = sum(prof[f]["status"] == "stated" for f in FIELDS) if prof else 0
            detail = f"  {result['error']}" if result.get("error") else ""
            print(f"[{n}/{len(todo)}] {record['company_name'][:40]:<40} "
                  f"{result['llm_status']:<11} {known}/{len(FIELDS)} fields stated{detail}")
    shutil.rmtree(workdir, ignore_errors=True)
    if out_of_quota.is_set():
        print("\nStopped: the model account's usage limit was reached. Run the same "
              "command again after it resets; finished companies are skipped.")

    write_tables(out_dir, input_csv)


if __name__ == "__main__":
    main()
