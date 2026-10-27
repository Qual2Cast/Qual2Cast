"""Source-bound business split and company-level evaluation adapter.

Example (from the repository root):
    python v0/business_split.py --tickers PCTY NWSA CSL AFG BOC BUKS

The company's Capital IQ ID remains the sole matching/valuation ID. Outputs,
including evidence, prompts, raw answers, and decisions, stay in outputs-local/.
This experiment does not modify the existing facets, matches, or valuations.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from io import StringIO
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import fill_facets as ff  # noqa: E402
from verification import evidence as evm  # noqa: E402


EXIT_EVENT = re.compile(
    r"\b(?:completed (?:the )?(?:previously announced )?sale|closing of the sale|divest(?:ed|iture) of|spun off|ceased operations|"
    r"closed (?:its |our |the )?[\w -]{0,60}(?:business|division|unit)|"
    r"sold (?:its |our |the )[\w -]{0,60}(?:business|division|unit|subsidiary|stake))\b",
    re.IGNORECASE,
)
GENERIC_WORDS = {"business", "businesses", "division", "group", "operations",
                 "product", "products", "service", "services", "technology",
                 "technologies", "company", "and", "the", "of", "for"}
CURRENT_EVIDENCE_MAX_AGE = timedelta(days=730)
STRONG_SOURCES = {"company_site", "press_release", "annual_report", "saved_page"}


@dataclass(frozen=True)
class EvidenceLine:
    label: str
    text: str
    url: str
    published: date | None = None
    observed: date | None = None
    source_kind: str = "saved_page"


@dataclass(frozen=True)
class LineCheck:
    business_id: str
    status: str  # current, exited, or unknown
    cites: tuple[str, ...] = ()
    event_date: date | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class PairCheck:
    left: str
    right: str
    different_offering: bool | None
    different_customers: bool | None
    different_process: bool | None
    different_channels: bool | None
    different_economics: bool | None
    shared_platform: bool | None
    cites: tuple[str, ...] = ()


def _name_in_text(name: str, text: str) -> bool:
    """Check a specific line name, not generic words such as 'business'."""
    def stem(word: str) -> str:
        return word[:6].removesuffix("s") if len(word) >= 5 else word[:6]

    terms = {stem(w) for w in re.findall(r"[a-z]{4,}", name.lower())
             if w not in GENERIC_WORDS}
    words = {stem(w) for w in re.findall(r"[a-z]{4,}", text.lower())}
    return bool(terms & words)


def _shared_business_terms(left: str, right: str) -> bool:
    """Recognize a common business domain, not a shared generic word."""
    def terms(name: str) -> set[str]:
        return {word[:6] for word in re.findall(r"[a-z]{5,}", name.lower())
                if word not in GENERIC_WORDS and word not in
                {"commercial", "general", "specialty", "integrated", "management"}}
    return bool(terms(left) & terms(right))


def _cited(check_cites: tuple[str, ...], evidence: Mapping[str, EvidenceLine]) -> list[EvidenceLine]:
    return [evidence[label] for label in check_cites if label in evidence and evidence[label].text.strip()]


def line_status(name: str, check: LineCheck | None,
                evidence: Mapping[str, EvidenceLine], as_of: date) -> str:
    """An exit needs an explicit, dated, completed event for this line.

    A signed agreement, an undated historical mention, or silence does not
    remove a business. Positive current evidence must also be cited.
    """
    if check is None:
        return "unresolved"
    cited = _cited(check.cites, evidence)
    names = (name, *check.aliases)
    if check.status == "current":
        if any(item.source_kind in STRONG_SOURCES and not EXIT_EVENT.search(item.text)
               and any(_name_in_text(n, item.text) for n in names)
               and (item.published or item.observed)
               and as_of - CURRENT_EVIDENCE_MAX_AGE <= (item.published or item.observed) <= as_of
               for item in cited):
            return "current"
    if check.status == "exited":
        if any(item.source_kind in STRONG_SOURCES and EXIT_EVENT.search(item.text)
               and any(_name_in_text(n, item.text) for n in names)
               and item.published and item.published <= as_of
               and (check.event_date is None or check.event_date <= item.published)
               for item in cited):
            return "exited"
    return "unresolved"


def pair_status(pair: PairCheck | None, evidence: Mapping[str, EvidenceLine],
                explicit_business_list: bool = False) -> str:
    """A different offering plus customer or process evidence supports a split."""
    if pair is None or not _cited(pair.cites, evidence):
        return "unresolved"
    if (pair.different_offering is True
            and (pair.different_customers is True or pair.different_process is True)
            and pair.shared_platform is not True):
        return "distinct"
    if (explicit_business_list and pair.different_offering is True
            and pair.different_process is True and pair.shared_platform is not True):
        return "distinct"
    if (pair.shared_platform is True and pair.different_customers is False
            and pair.different_economics is not True):
        return "related"
    return "unresolved"


def review_businesses(businesses: list[dict], checks: list[LineCheck],
                      pairs: list[PairCheck], evidence: Mapping[str, EvidenceLine],
                      as_of: date, *, scrape_status: str = "ok") -> dict:
    """Return a parent-company decision and an audit trail without mutating input.

    ``businesses`` are proposals, not separate legal entities. The company
    remains the valuation unit. Only verified exits leave the current-line
    list; unresolved proposals remain visible for further evidence gathering.
    """
    ids = [b["business_id"] for b in businesses]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate business_id")
    by_id = {c.business_id: c for c in checks}
    statuses = {b["business_id"]: line_status(b["business"], by_id.get(b["business_id"]),
                                                evidence, as_of) for b in businesses}
    # A thin page or an unconfirmed historical exit cannot erase an operating
    # line. Retain it in the best-effort company scope until an exit is proved.
    active = [business_id for business_id in ids if statuses[business_id] != "exited"]
    unresolved = [business_id for business_id in ids if statuses[business_id] == "unresolved"]
    exited = [business_id for business_id in ids if statuses[business_id] == "exited"]

    pair_results: dict[str, str] = {}
    links = {business_id: business_id for business_id in active}

    def root(business_id: str) -> str:
        while links[business_id] != business_id:
            business_id = links[business_id]
        return business_id

    by_pair = {frozenset((p.left, p.right)): p for p in pairs}
    names_by_id = {b["business_id"]: (b["business"], *by_id[b["business_id"]].aliases)
                   for b in businesses}
    business_names = {b["business_id"]: b["business"] for b in businesses}
    for i, left in enumerate(active):
        for right in active[i + 1:]:
            pair = by_pair.get(frozenset((left, right)))
            cited = set(pair.cites) if pair else set()
            both_lines_cited = (bool(cited.intersection(by_id[left].cites))
                                and bool(cited.intersection(by_id[right].cites)))
            shared = set(by_id[left].cites).intersection(by_id[right].cites)
            explicit_list = any(
                label in evidence and evidence[label].source_kind in STRONG_SOURCES
                and re.search(r"\b(?:two|three|four|five|[2-9]) businesses\b", evidence[label].text, re.I)
                and any(_name_in_text(n, evidence[label].text) for n in names_by_id[left])
                and any(_name_in_text(n, evidence[label].text) for n in names_by_id[right])
                for label in shared)
            verdict = pair_status(pair, evidence, explicit_list) if both_lines_cited else "unresolved"
            if _shared_business_terms(business_names[left], business_names[right]):
                # Different workflows within the same general business are
                # products/roles, not separate parent-company entities.
                verdict = "related"
            pair_results[f"{left}|{right}"] = verdict

    # A related chain cannot merge two lines for which there is direct
    # evidence of different businesses (A~B, A~C, but B!=C).
    for key, verdict in pair_results.items():
        if verdict != "related":
            continue
        left, right = key.split("|")
        left_group = {x for x in active if root(x) == root(left)}
        right_group = {x for x in active if root(x) == root(right)}
        conflict = any(pair_results.get(f"{min(x, y)}|{max(x, y)}") == "distinct"
                       or pair_results.get(f"{max(x, y)}|{min(x, y)}") == "distinct"
                       for x in left_group for y in right_group)
        if not conflict:
            links[root(right)] = root(left)

    has_proven_split = any(verdict == "distinct" for verdict in pair_results.values())
    groups: dict[str, list[str]] = {}
    for business_id in active:
        groups.setdefault(root(business_id) if has_proven_split else "whole_company", []).append(business_id)
    ambiguous_pairs = [key for key, verdict in pair_results.items() if verdict == "unresolved"]
    # A transitive related link must not override an explicit distinct pair.
    contradictions = [key for key, verdict in pair_results.items()
                      if verdict == "distinct" and len({root(x) for x in key.split("|")}) == 1]
    external_coverage = all(any(evidence[label].source_kind != "saved_page"
                                for label in by_id[business_id].cites if label in evidence)
                            for business_id in active)
    decision = "multiple_businesses" if len(groups) > 1 else "one_business"
    evidence_gaps = list(unresolved)
    if scrape_status != "ok" and not external_coverage:
        evidence_gaps.append("thin_source_pages")
    evidence_gaps.extend(contradictions)
    return {"company_decision": decision, "as_of": as_of.isoformat(),
            "scrape_status": scrape_status, "thin_pages": scrape_status != "ok",
            "line_status": statuses, "current": active, "exited": exited,
            "unresolved": unresolved, "groups": list(groups.values()),
            "pair_status": pair_results, "ambiguous_pairs": ambiguous_pairs,
            "contradictions": contradictions, "evidence_gaps": evidence_gaps,
            "provisional": bool(evidence_gaps)}


def review_prompt(company: str, as_of: date, businesses: list[dict], evidence_text: str) -> str:
    """A source-bound LLM stage; the deterministic checks above decide the result."""
    candidates = "\n".join(f"{b['business_id']}: {b['business']}" for b in businesses)
    return f"""Review proposed business lines for {company} as of {as_of.isoformat()}.
They all belong to one legal company. The question is whether current operations
contain distinct economic businesses, not how many products, brands, legal
subsidiaries, regions or reporting segments are named.

For each candidate, mark current only with a cited recent source directly
describing it. Mark exited only with a cited, dated statement that a sale,
spin-off or closure was completed; an agreement or old mention is insufficient.
Otherwise mark unknown. Never treat absence from a webpage as an exit.

For every pair of current candidates, compare offering, customers/end markets,
production or technology, distribution, economics or regulation, and any shared
platform. Related product lines serving the same customers through the same
platform or channels are one business. Distinct products and customers plus
another operational difference may justify separate businesses. Cite evidence
for both sides of each comparison. If a fact is not supported, use null.
Do not infer business size or weights from the order of the list.

Candidates:\n{candidates}\n\nEvidence:\n{evidence_text or '(none)'}"""


def review_schema(business_ids: list[str]) -> dict:
    """JSON schema compatible with the existing Claude structured-output call."""
    nullable_bool = {"type": ["boolean", "null"]}
    line = {"type": "object", "additionalProperties": False,
            "required": ["business_id", "status", "cites", "event_date", "aliases"],
            "properties": {"business_id": {"type": "string", "enum": business_ids},
                           "status": {"type": "string", "enum": ["current", "exited", "unknown"]},
                           "cites": {"type": "array", "items": {"type": "string"}},
                           "event_date": {"type": ["string", "null"]},
                           "aliases": {"type": "array", "items": {"type": "string"}}}}
    pair = {"type": "object", "additionalProperties": False,
            "required": ["left", "right", "different_offering", "different_customers",
                         "different_process", "different_channels", "different_economics",
                         "shared_platform", "cites"],
            "properties": {"left": {"type": "string", "enum": business_ids},
                           "right": {"type": "string", "enum": business_ids},
                           **{name: nullable_bool for name in
                              ("different_offering", "different_customers", "different_process",
                               "different_channels", "different_economics", "shared_platform")},
                           "cites": {"type": "array", "items": {"type": "string"}}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["checks", "pairs"],
            "properties": {"checks": {"type": "array", "items": line},
                           "pairs": {"type": "array", "items": pair}}}


def parse_review(raw: dict, business_ids: list[str]) -> tuple[list[LineCheck], list[PairCheck]]:
    """Reject duplicated/foreign IDs; keep bad dates unresolved."""
    valid = set(business_ids)
    checks: list[LineCheck] = []
    for item in raw["checks"]:
        if item["business_id"] not in valid or item["business_id"] in {c.business_id for c in checks}:
            raise ValueError("foreign or duplicate business check")
        try:
            event_date = date.fromisoformat(item["event_date"]) if item["event_date"] else None
        except ValueError:
            event_date = None
        checks.append(LineCheck(item["business_id"], item["status"], tuple(item["cites"]),
                                event_date, tuple(item["aliases"])))
    pairs: list[PairCheck] = []
    seen: set[frozenset[str]] = set()
    for item in raw["pairs"]:
        key = frozenset((item["left"], item["right"]))
        if len(key) != 2 or not key <= valid or key in seen:
            raise ValueError("invalid or duplicate pair")
        seen.add(key)
        pairs.append(PairCheck(item["left"], item["right"],
                               *(item[name] for name in
                                 ("different_offering", "different_customers", "different_process",
                                  "different_channels", "different_economics", "shared_platform")),
                               tuple(item["cites"])))
    return checks, pairs


def evidence_from_bundle(bundle: object, observed_on: date,
                         saved_page_dates: Mapping[str, date] | None = None) -> dict[str, EvidenceLine]:
    """Adapt Yiming's saved P/W/S evidence bundle without re-fetching pages.

    P page dates can be passed from ``page_text/<IQ_ID>.json``. Without them,
    currentness remains unresolved. W pages were fetched during the evidence
    run. Search snippets stay weak until their underlying source is fetched.
    """
    result = {}
    for label, text in bundle.lines.items():
        source = bundle.sources.get(label.split(".")[0], {})
        raw_date = source.get("date", "")
        try:
            published = date.fromisoformat(raw_date[:10])
        except ValueError:
            try:
                published = parsedate_to_datetime(raw_date).date()
            except (TypeError, ValueError, IndexError):
                published = None
        kind = source.get("kind", "")
        source_kind = ("saved_page" if kind == "saved_page" else
                       source.get("type", "company_site") if kind in ("reviewed_web", "fetched_web") else
                       "company_site" if kind.startswith("crawl:") else "search_snippet")
        if kind == "saved_page":
            observed = (saved_page_dates or {}).get(label.split(".")[0])
        elif kind in ("reviewed_web", "fetched_web"):
            try:
                observed = date.fromisoformat(source["reviewed_on"][:10])
            except (KeyError, ValueError):
                observed = None
        else:
            observed = observed_on if kind.startswith("crawl:") else None
        result[label] = EvidenceLine(label, text, source.get("url", ""), published,
                                     observed, source_kind)
    return result


DEFAULT_OUT = REPO / "outputs-local" / "research" / "business-structure" / "real-split-20261027"
DEFAULT_GOLD = REPO / "outputs-local" / "research" / "business-structure" / "facet_gold_labels.csv"
COMPANIES = REPO / "data-local" / "snapshots" / "company_list_v3_websites_fixed.csv"
FACETS_REPO_PATH = "outputs-local/comps/facets/tables/facets.csv"
MAX_EVIDENCE_LINES = 72


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def read_facets() -> list[dict]:
    path = REPO / FACETS_REPO_PATH
    if path.exists():
        return read_csv(path)
    # Some local checkouts omit saved outputs although they exist on main.
    result = subprocess.run(["git", "show", f"origin/main:{FACETS_REPO_PATH}"],
                            cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True)
    return list(csv.DictReader(StringIO(result.stdout)))


def split_schema() -> dict:
    nullable_bool = {"type": ["boolean", "null"]}
    line = {"type": "object", "additionalProperties": False,
            "required": ["business_id", "business", "status", "cites", "event_date", "aliases", "reason"],
            "properties": {
                "business_id": {"type": "string"}, "business": {"type": "string"},
                "status": {"type": "string", "enum": ["current", "exited", "unknown"]},
                "cites": {"type": "array", "items": {"type": "string"}},
                "event_date": {"type": ["string", "null"]},
                "aliases": {"type": "array", "items": {"type": "string"}},
                "reason": {"type": "string"}}}
    pair = {"type": "object", "additionalProperties": False,
            "required": ["left", "right", "different_offering", "different_customers",
                         "different_process", "different_channels", "different_economics",
                         "shared_platform", "cites", "reason"],
            "properties": {
                "left": {"type": "string"}, "right": {"type": "string"},
                **{name: nullable_bool for name in
                   ("different_offering", "different_customers", "different_process",
                    "different_channels", "different_economics", "shared_platform")},
                "cites": {"type": "array", "items": {"type": "string"}},
                "reason": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["businesses", "pairs"],
            "properties": {"businesses": {"type": "array", "items": line},
                           "pairs": {"type": "array", "items": pair}}}


def grouping_schema(ids: list[str]) -> dict:
    group = {"type": "object", "additionalProperties": False,
             "required": ["name", "members", "cites"],
             "properties": {"name": {"type": "string"},
                            "members": {"type": "array", "items": {"type": "string", "enum": ids}},
                            "cites": {"type": "array", "items": {"type": "string"}}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["groups"], "properties": {"groups": {"type": "array", "items": group}}}


def grouping_prompt(company: dict, decision: dict, ev: evm.Evidence) -> str:
    current = [b for b in decision["businesses"] if b["business_id"] in decision["current"]]
    candidates = "\n".join(f"{b['business_id']}: {b['business']}" for b in current)
    return f"""Group the current activities of {company['target_company_name']} into broad
economic businesses. Return only JSON. Every ID must occur in exactly one group.
Use the company's own description of its operating hierarchy. Several products,
subsidiaries or processes inside one broad business belong in one group, even
when their immediate customers or workflows differ. Separate genuinely different
businesses if the cited sources show distinct offerings plus distinct customers
or operating processes. Do not use financial figures. Cite source lines for
each group's name and membership. Do not add or remove an activity.

Activities:\n{candidates}\n\nSources:\n{evidence_block(ev)}"""


def apply_grouping(decision: dict, raw: dict, ev: evm.Evidence) -> dict:
    active = set(decision["current"])
    groups = raw["groups"]
    members = [item for group in groups for item in group["members"]]
    if set(members) != active or len(members) != len(active) or not groups:
        raise ValueError("grouping must partition all current lines")
    line_cites = {b["business_id"]: b["cites"] for b in decision["businesses"]}
    for group in groups:
        if not group["cites"]:
            group["cites"] = list(dict.fromkeys(
                label for member in group["members"] for label in line_cites[member]))
    if any(not group["name"].strip() or not group["cites"]
           or not set(group["cites"]) <= set(ev.lines) for group in groups):
        raise ValueError("grouping needs a name and cited source lines")
    decision["groups"] = [group["members"] for group in groups]
    decision["business_groups"] = [[group["name"]] for group in groups]
    decision["group_evidence"] = [group["cites"] for group in groups]
    decision["company_decision"] = ("multiple_businesses" if len(groups) > 1
                                    else "one_business")
    return decision


def saved_page_dates(iq_id: str) -> dict[str, date]:
    path = evm.SAVED_PAGES / f"{iq_id}.json"
    if not path.exists():
        return {}
    pages = json.loads(path.read_text(encoding="utf-8")).get("pages", [])
    dates = {}
    for page in pages:
        try:
            dates[page["page_id"]] = date.fromisoformat(page["fetched_at"][:10])
        except (KeyError, ValueError):
            pass
    return dates


def bundle_date(ev: evm.Evidence, fallback: date) -> date:
    try:
        return date.fromisoformat(Path(ev.log_dir).name[:10])
    except (TypeError, ValueError):
        return fallback


def latest_evidence(root: Path, iq_id: str) -> evm.Evidence | None:
    paths = sorted((root / iq_id).glob("*/evidence.json"))
    return evm.Evidence(**json.loads(paths[-1].read_text(encoding="utf-8"))) if paths else None


def fetched_search_pages(ev: evm.Evidence, *, limit: int = 4) -> list[dict]:
    """Search results identify URLs; only fetched pages become strong evidence."""
    fetcher = evm.Fetcher(evm.USER_AGENT)
    pages = []
    seen = {source["url"].rstrip("/") for sid, source in ev.sources.items()
            if not sid.startswith("S") and source.get("url")}
    for source_id, source in ev.sources.items():
        if not source_id.startswith("S") or source.get("type") not in ("company_site", "press_release"):
            continue
        url = source["url"]
        if url.rstrip("/") in seen or evm.blocked(url, source.get("title", "")):
            continue
        seen.add(url.rstrip("/"))
        try:
            if not fetcher.allowed(url):
                ev.dropped.append({"url": url, "reason": "robots_disallowed"})
                continue
            final, html = fetcher.get_html(url)
            page = evm._page_record(final, "search", evm.extract_page(html))
            if page["status"] != "ok" or not page["lines"]:
                ev.dropped.append({"url": url, "reason": page["status"]})
                continue
            pages.append({"url": final, "title": source.get("title", ""),
                          "type": source["type"], "published": source.get("date", ""),
                          "reviewed_on": date.today().isoformat(),
                          "lines": page["lines"][:15]})
            if len(pages) >= limit:
                break
        except Exception as exc:
            ev.dropped.append({"url": url, "reason": f"fetch_error: {type(exc).__name__}"})
    return pages


def get_evidence(company: dict, out: Path, *, crawl: bool,
                 base_run: Path | None = None,
                 web_sources: dict[str, list[dict]] | None = None,
                 search_provider: str | None = None) -> evm.Evidence:
    iq_id = company["IQ_COMPANY_ID"]
    ticker = company["target_ciq_ticker"]
    baseline = base_run / "calls" / ticker / "evidence.json" if base_run else None
    cached = (evm.Evidence(**json.loads(baseline.read_text(encoding="utf-8")))
              if baseline and baseline.exists() else latest_evidence(out / "evidence", iq_id))
    if cached:
        ev = cached
    else:
        # Earlier team evidence for a few hard cases can be reused read-only.
        ev = latest_evidence(evm.EVIDENCE_OUT, iq_id)
        if ev is None:
            ev = evm.gather(iq_id, company["target_company_name"],
                            company["target_ciq_website"], crawl=crawl, search=False,
                            out_root=out / "evidence")
    ev = evm.Evidence(**ev.__dict__)  # Never mutate a teammate's cached bundle.
    ev.lines, ev.sources = dict(ev.lines), dict(ev.sources)
    searched = []
    if search_provider:
        search_ev = evm.gather(iq_id, company["target_company_name"],
                               company["target_ciq_website"], crawl=False, search=True,
                               provider=search_provider, out_root=out / "search")
        searched = fetched_search_pages(search_ev)
        ev.dropped.extend(search_ev.dropped)
    additions = [(item, "reviewed_web") for item in (web_sources or {}).get(ticker, [])]
    additions.extend((item, "fetched_web") for item in searched)
    for index, (item, kind) in enumerate(additions, start=1):
        if not item.get("url") or not item.get("lines") or (kind == "reviewed_web" and not item.get("reviewed_on")):
            raise ValueError(f"Incomplete web source for {ticker}")
        source_id = f"X{index}"
        ev.sources[source_id] = {
            "url": item["url"], "date": item.get("published", ""),
            "title": item.get("title", ""), "type": item.get("type", "company_site"),
            "kind": kind, "reviewed_on": item.get("reviewed_on", "")}
        for line_number, line in enumerate(item["lines"], start=1):
            ev.lines[f"{source_id}.{line_number}"] = line
    return ev


def evidence_block(ev: evm.Evidence) -> str:
    """A bounded, source-diverse input; save the full bundle separately."""
    selected = []
    for source_id, source in sorted(ev.sources.items(), key=lambda x: x[0][0] != "X"):
        if source_id.startswith("S"):
            continue  # A snippet alone is not proof of a line or exit.
        lines = [(label, text) for label, text in ev.lines.items()
                 if label.split(".")[0] == source_id]
        priority = [x for x in lines if any(word in x[1].lower() for word in
                    ("sold", "sale", "divest", "spin-off", "business", "product",
                     "service", "customer", "platform", "market"))]
        first = list(dict.fromkeys(priority + lines))[:10]
        for label, text in first:
            selected.append((label, text, source))
            if len(selected) >= MAX_EVIDENCE_LINES:
                break
        if len(selected) >= MAX_EVIDENCE_LINES:
            break
    return "\n".join(f"[{label}] {text} (source: {src['url']}; "
                     f"published: {src.get('date') or 'unknown'}; "
                     f"reviewed: {src.get('reviewed_on') or 'unknown'})"
                     for label, text, src in selected) or "(No usable source lines)"


def prompt(company: dict, facet: dict, ev: evm.Evidence, as_of: date) -> str:
    hypothesis = "\n".join(f"{name}: {facet.get(name, '')}" for name in
                           ("offering_description", "primary_products", "primary_services",
                            "customer_segment", "end_markets", "revenue_model", "specialization"))
    return f"""Classify the CURRENT businesses of one company as of {as_of.isoformat()}.
Return only JSON matching the supplied schema. Do not use tools, outside knowledge,
financial data, or an uncited assumption. The old whole-company profile below
is a HYPOTHESIS and may contain sold businesses. Use the cited source lines
to verify every proposed line. Propose ECONOMIC BUSINESS LINES, not each
product, service, brand, geography, channel, or revenue stream. Consolidate
related offerings that share customers and a platform into one candidate;
describe the component products in its reason. Do not turn every field of the
prior profile into a candidate. Keep an old separately operated business as
a candidate until a dated completed exit verifies its removal. Distinguish
an operating business from a minority portfolio investment or an internal
support function. Use at most four
current distinct candidates plus historical exit candidates, six total, with
unique B1, B2, ... IDs. One legal company remains one company throughout.

Mark a line current only when a recent source affirmatively describes current
operations; mark exited only with a completed, dated sale/spin-off/closure.
An agreement or silence on a thin page is not an exit. Otherwise use unknown.
Supply exact evidence labels in cites. Use YYYY-MM-DD for a known event_date;
the source publication date may anchor an announcement made "today". Use null
when the exact event date is unknown.
For every pair of current lines, compare offering, customers, process,
channels, economics, and shared platform. Cite supporting lines for BOTH.
Use null for unsupported dimensions. Different offerings and customers plus
another operating difference support distinct businesses. Shared customers
and platform can make several products one business. No invented weights.

Company: {company['target_company_name']}
Website: {company['target_ciq_website']}
Prior profile (unverified):\n{hypothesis}

Current source lines:\n{evidence_block(ev)}"""


def parse_decision(raw: dict, ev: evm.Evidence, iq_id: str, as_of: date) -> dict:
    businesses = raw["businesses"]
    ids = [b["business_id"] for b in businesses]
    if not 1 <= len(ids) <= 6 or len(ids) != len(set(ids)):
        raise ValueError("invalid number or duplicate business IDs")
    known_labels = set(ev.lines)
    for business in businesses:
        if not set(business["cites"]) <= known_labels:
            raise ValueError("business cites unknown evidence")
    for pair in raw["pairs"]:
        if not set(pair["cites"]) <= known_labels:
            raise ValueError("pair cites unknown evidence")
    checks_raw = {"checks": [{k: b[k] for k in
                              ("business_id", "status", "cites", "event_date", "aliases")}
                             for b in businesses], "pairs": [
        {k: p[k] for k in ("left", "right", "different_offering", "different_customers",
                          "different_process", "different_channels", "different_economics",
                          "shared_platform", "cites")}
        for p in raw["pairs"]]}
    checks, pairs = parse_review(checks_raw, ids)
    evidence = evidence_from_bundle(ev, bundle_date(ev, as_of), saved_page_dates(iq_id))
    scrape_path = evm.SAVED_PAGES / f"{iq_id}.json"
    scrape = json.loads(scrape_path.read_text(encoding="utf-8")) if scrape_path.exists() else {}
    decision = review_businesses(businesses, checks, pairs, evidence, as_of,
                                    scrape_status=scrape.get("status", "missing"))
    decision["IQ_COMPANY_ID"] = iq_id
    decision["businesses"] = businesses
    decision["business_groups"] = [[next(b["business"] for b in businesses
                                          if b["business_id"] == x) for x in group]
                                   for group in decision["groups"]]
    return decision


def run_one(company: dict, facet: dict, out: Path, *, model: str, as_of: date,
            crawl: bool, workdir: str, schema_path: Path, recheck: bool,
            base_run: Path | None = None,
            web_sources: dict[str, list[dict]] | None = None,
            search_provider: str | None = None) -> dict:
    ticker, iq_id = company["target_ciq_ticker"], company["IQ_COMPANY_ID"]
    path = out / "companies" / f"{ticker}.json"
    if path.exists() and not recheck:
        return json.loads(path.read_text(encoding="utf-8"))
    folder = out / "calls" / ticker
    folder.mkdir(parents=True, exist_ok=True)
    try:
        raw_path = folder / "response.json"
        if recheck and raw_path.exists():
            ev = evm.Evidence(**json.loads((folder / "evidence.json").read_text(encoding="utf-8")))
            result = {"llm_status": "ok", "usage":
                      json.loads(path.read_text(encoding="utf-8")).get("usage", {})}
        else:
            ev = get_evidence(company, out, crawl=crawl, base_run=base_run,
                              web_sources=web_sources, search_provider=search_provider)
            p = prompt(company, facet, ev, as_of)
            (folder / "prompt.txt").write_text(p, encoding="utf-8")
            (folder / "evidence.json").write_text(json.dumps(ev.__dict__, indent=2), encoding="utf-8")
            result = ff.call_codex(p, folder, schema_path, workdir, model, "low")
        if result["llm_status"] != "ok":
            output = {"ticker": ticker, "IQ_COMPANY_ID": iq_id,
                      "company_decision": "model_error", "error": result.get("error", ""),
                      "usage": result.get("usage", {})}
        else:
            decision = parse_decision(json.loads(raw_path.read_text(encoding="utf-8")), ev, iq_id, as_of)
            if decision["company_decision"] == "multiple_businesses" and len(decision["groups"]) > 2:
                grouping_dir = folder / "grouping"
                grouping_dir.mkdir(exist_ok=True)
                grouping_answer = grouping_dir / "response.json"
                grouping_schema_path = grouping_dir / "schema.json"
                grouping_schema_path.write_text(
                    json.dumps(grouping_schema(decision["current"]), indent=2), encoding="utf-8")
                group_prompt = grouping_prompt(company, decision, ev)
                (grouping_dir / "prompt.txt").write_text(group_prompt, encoding="utf-8")
                if not grouping_answer.exists():
                    grouped = ff.call_codex(group_prompt, grouping_dir, grouping_schema_path,
                                            workdir, model, "low")
                    if grouped["llm_status"] != "ok":
                        raise RuntimeError(f"grouping failed: {grouped.get('error', '')}")
                try:
                    decision = apply_grouping(
                        decision, json.loads(grouping_answer.read_text(encoding="utf-8")), ev)
                except ValueError as exc:
                    decision["grouping_issue"] = str(exc)
            if decision["company_decision"] == "one_business" and len(decision["current"]) > 1:
                # Keep one business, but do not reuse stale v0 wording that
                # can still name a documented divestiture (AZZ is an example).
                if "group_evidence" not in decision:
                    decision["business_groups"] = [[b["business"] for b in decision["businesses"]
                                                    if b["business_id"] in decision["current"]]]
                    decision["fallback_to_one_business"] = True
            output = {"ticker": ticker, **decision, "usage": result.get("usage", {})}
    except Exception as exc:  # Keep a per-company error; do not lose the run.
        output = {"ticker": ticker, "IQ_COMPANY_ID": iq_id,
                  "company_decision": "processing_error", "error": f"{type(exc).__name__}: {exc}"[:300]}
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        history = out / "history"
        history.mkdir(parents=True, exist_ok=True)
        previous = history / f"{ticker}_{len(list(history.glob(ticker + '_*.json'))) + 1}.json"
        path.replace(previous)
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    return output


def write_summary(out: Path, results: list[dict], gold: dict[str, dict], facets: dict[str, dict]) -> None:
    rows = []
    for result in results:
        ticker = result["ticker"]
        g = gold.get(ticker, {})
        old_category = g.get("haiku_value", "").split(":", 1)[0].strip()
        reference = ("multiple_businesses" if old_category == "diversified" else
                     "one_business" if old_category in ("niche specialist", "related lines") else "")
        reference = reference if g.get("label", "").lower().strip() == "correct" else ""
        rows.append({"ticker": ticker, "IQ_COMPANY_ID": result["IQ_COMPANY_ID"],
                     "decision": result["company_decision"],
                     "groups": " | ".join(" + ".join(x) for x in result.get("business_groups", [])),
                     "current_lines": len(result.get("current", [])),
                     "exited_lines": len(result.get("exited", [])),
                     "unresolved_lines": len(result.get("unresolved", [])),
                     "gold_F10_label": g.get("label", ""),
                     "reference_split": reference,
                     "reference_agreement": (result["company_decision"] == reference)
                     if reference and result["company_decision"] in
                     ("one_business", "multiple_businesses") else "",
                     "v0_F10": facets[result["IQ_COMPANY_ID"]].get("specialization_category", ""),
                     "error": result.get("error", "")})
    with (out / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    determined = [r for r in rows if r["decision"] in ("one_business", "multiple_businesses")]
    scored = [r for r in rows if r["reference_agreement"] != ""]
    report = {"companies": len(rows), "determined": len(determined),
              "needs_evidence": sum(r["decision"] == "needs_evidence" for r in rows),
              "errors": sum(r["decision"].endswith("error") for r in rows),
              "multiple_businesses": sum(r["decision"] == "multiple_businesses" for r in rows),
              "one_business": sum(r["decision"] == "one_business" for r in rows),
              "gold_correct_F10_reference_cases": sum(bool(r["reference_split"]) for r in rows),
              "scored_reference_cases": len(scored),
              "agreement_on_scored_reference_cases":
                  round(sum(r["reference_agreement"] for r in scored) / len(scored), 3) if scored else None,
              "warning": "F10 labels are an older-run proxy, not independent split gold. "
                         "Abstentions are excluded from reference agreement; count coverage separately."}
    (out / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def write_comparison(out: Path, base_run: Path) -> None:
    baseline = {row["ticker"]: row for row in read_csv(base_run / "summary.csv")}
    rows = []
    for revised in read_csv(out / "summary.csv"):
        old = baseline[revised["ticker"]]
        rows.append({"ticker": revised["ticker"], "website_only": old["decision"],
                     "search_assisted": revised["decision"],
                     "website_exits": old["exited_lines"],
                     "search_exits": revised["exited_lines"],
                     "reference_split": revised["reference_split"],
                     "website_agreement": old["reference_agreement"],
                     "search_agreement": revised["reference_agreement"]})
    with (out / "comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def scope_context(decision: dict, evidence: evm.Evidence) -> str:
    """Whole-company scope for the existing v0 peer judge."""
    if decision.get("company_decision") not in ("one_business", "multiple_businesses"):
        return ""
    lines = [f"Business structure as of {decision['as_of']}: "
             f"{decision['company_decision'].replace('_', ' ')}."]
    for group in decision.get("business_groups", []):
        lines.append(f"- current business: {' + '.join(group)}")
    for business in decision["businesses"]:
        status = decision["line_status"][business["business_id"]]
        if status != "exited":
            continue
        urls = []
        for label in business["cites"]:
            source = evidence.sources.get(label.split(".")[0], {})
            url = source.get("url", "")
            if url and url not in urls:
                urls.append(url)
        lines.append(f"- exited: {business['business']} "
                     f"[{' ; '.join(urls[:2]) or 'source unavailable'}]")
    lines.append("Evaluate the whole company, not a matching division in isolation.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tickers", nargs="*", help="Default: all 40 F10 Sheet tickers")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--gold-csv", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 10, 27))
    parser.add_argument("--no-crawl", action="store_true")
    parser.add_argument("--base-run", type=Path,
                        help="Reuse the exact P/W evidence from an earlier run")
    parser.add_argument("--web-sources", type=Path,
                        help="JSON manifest of manually opened and reviewed source pages")
    parser.add_argument("--search-provider", choices=("serper", "brave", "tavily"),
                        help="Search API to discover pages, then fetch them; snippets are not evidence")
    parser.add_argument("--recheck", action="store_true",
                        help="Reapply updated rules to saved raw model responses")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    gold_rows = ([r for r in read_csv(args.gold_csv) if r.get("facet_id") == "F10"]
                 if args.gold_csv.exists() else [])
    gold = {r["ticker"]: r for r in gold_rows}
    if not gold_rows and not args.tickers:
        raise SystemExit("Provide --tickers or a local F10 reference CSV")
    tickers = args.tickers or [r["ticker"] for r in gold_rows]
    if args.limit:
        tickers = tickers[:args.limit]
    companies = {r["target_ciq_ticker"]: r for r in read_csv(COMPANIES)}
    facets = {r["IQ_COMPANY_ID"]: r for r in read_facets()
              if r.get("business_id") == "B1"}
    missing = [t for t in tickers if t not in companies or companies[t]["IQ_COMPANY_ID"] not in facets]
    if missing:
        raise SystemExit(f"Missing company or v0 profile: {missing}")
    web_sources = json.loads(args.web_sources.read_text(encoding="utf-8")) if args.web_sources else {}
    if args.search_provider and not evm.pick_provider(args.search_provider)[0]:
        raise SystemExit(f"Missing {args.search_provider} API key; use --web-sources for reviewed pages")
    schema_path = args.out / "answer_schema.json"
    schema_path.write_text(json.dumps(split_schema(), indent=2), encoding="utf-8")
    (args.out / "run_manifest.json").write_text(json.dumps({
        "as_of": args.as_of.isoformat(), "model": args.model, "tickers": tickers,
        "company_snapshot": "company_list_v3", "facet_source": FACETS_REPO_PATH,
        "evidence": "saved pages and bounded same-site crawl; no search snippets",
        "base_run": str(args.base_run) if args.base_run else None,
        "web_sources": str(args.web_sources) if args.web_sources else None,
        "search_provider": args.search_provider,
        "note": "The 40 F10 labels are an older-run reference, not split gold."}, indent=2),
        encoding="utf-8")
    results = []
    with tempfile.TemporaryDirectory(prefix="business-split-") as workdir:
        for i, ticker in enumerate(tickers, start=1):
            company = companies[ticker]
            result = run_one(company, facets[company["IQ_COMPANY_ID"]], args.out,
                             model=args.model, as_of=args.as_of,
                             crawl=not args.no_crawl, workdir=workdir,
                             schema_path=schema_path, recheck=args.recheck,
                             base_run=args.base_run, web_sources=web_sources,
                             search_provider=args.search_provider)
            results.append(result)
            print(f"{i}/{len(tickers)} {ticker}: {result['company_decision']}", flush=True)
            write_summary(args.out, results, gold, facets)
            if args.base_run:
                write_comparison(args.out, args.base_run)
    print(f"Results: {args.out.name}/summary.csv")


if __name__ == "__main__":
    main()
