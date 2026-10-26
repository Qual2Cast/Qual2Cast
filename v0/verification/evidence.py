"""
Evidence retrieval for verifying facet fills: what the company's own website
and the open web say about it, beyond the pages the website scrape saved.

This module only collects and labels evidence; it judges nothing. A verifier
(Riya's website verifier, or verify_with_evidence.py here as a stand-in)
reads the labelled lines and cites them, the same way the facet fill cites
saved page lines ("P1.3"):

  P1.3   saved scrape page 1, line 3       (outputs-local/website_scrape/page_text)
  W2.4   same-site page 2 fetched here, line 4  (deeper crawl of the company's site)
  S3.1   web search result 3, its snippet

Two sources:
1. Deeper crawl of the company's own site (no API key needed). The scrape
   kept at most 3 pages, mostly home and about pages, and it skips links to
   locations, dealers, distributors and news on purpose (LINK_EXCLUDE). For
   verification those pages are exactly what settles geography, channels and
   recent changes, so this crawl looks for them. robots.txt is honoured
   through the scrape's own Fetcher.
2. Web search through an API (Serper = Google results, Brave or Tavily; the
   key comes from SERPER_API_KEY, BRAVE_API_KEY or TAVILY_API_KEY in the
   environment or the repo's .env). Queries are built from the company's
   name and website only, never a ticker. Results from investor-relations,
   SEC, stock-quote and market-data sites are dropped (Aziz's rule), and so
   are earnings and results pages unless allow_public_only=True: a private
   company has none of them, so evidence from them would overstate how well
   verification works for a real target.

Every result is ranked by source type, most trusted first: the company's own
site, press releases, news and trade press, reference works, then company
databases. The 20-company check (verification_notes.md) found the databases
the least reliable (craft.co gave APi Group 5 employees next to $7.9B of
revenue), so they only add support and are listed last.

Text kept as evidence never carries the company's financial or size figures:
lines are dropped with the scrape's own filters (facets._figures). Unlike
the scrape, deal and history sentences are kept ("completed the sale of its
annuity business"), since out-of-date facts are a main error the
verification has to catch.

Every query, raw API response and fetched page is saved under
outputs-local/comps/evidence/<IQ_ID>/<time>/.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))                     # v0/
import facets as fc  # noqa: E402  (puts website_scrape/ and src/ on the path)
from fetch_and_clean import (SIZE_COUNT, USER_AGENT, Fetcher, extract_page, same_site,  # noqa: E402
                             url_candidates)
from project_data import OUTPUTS_LOCAL, REPO_ROOT  # noqa: E402

EVIDENCE_OUT = OUTPUTS_LOCAL / "comps" / "evidence"
SAVED_PAGES = OUTPUTS_LOCAL / "website_scrape" / "page_text"

MAX_CRAWL_PAGES = 6          # same-site pages fetched per company, beyond the saved ones
MAX_LINES_PER_PAGE = 25      # longest pages are cut; the first lines carry the substance
MAX_RESULTS_PER_QUERY = 6
MIN_LINE_WORDS = 5

# ---------------------------------------------------------------- source rules

# Never used: public-company-only sources and market data.
BLOCKED_DOMAINS = {
    "sec.gov", "edgar-online.com", "edgar.tools", "q4cdn.com", "q4ir.com", "gcs-web.com",
    "annualreports.com", "finance.yahoo.com", "marketscreener.com", "stockanalysis.com",
    "seekingalpha.com", "nasdaq.com", "nyse.com", "macrotrends.net", "morningstar.com",
    "morningstar.com.au", "zacks.com", "fool.com", "marketbeat.com", "tipranks.com",
    "simplywall.st", "finviz.com", "barchart.com", "earningswhispers.com", "quartr.com",
    "webull.com", "insidermonkey.com", "stocklight.com", "ycharts.com", "roic.ai",
    "gurufocus.com", "investing.com", "wallstreetzen.com", "stocktitan.net",
    "nemo.money", "coinbase.com", "chartmill.com", "validea.com", "base.report",
    "fundamentei.com", "ajbell.co.uk", "multiples.vc", "finnomena.com", "renaissancecapital.com",
}
BLOCKED_HOST_PREFIX = re.compile(r"^(?:ir|investors?|investor-relations|shareholders?)\.", re.I)
BLOCKED_PATH = re.compile(
    r"/(?:investors?|investor-relations|ir|sec-filings?|financials?|stock|quote|shareholders?"
    r"|annual-reports?|earnings)(?:/|$|[-_.?])", re.I)
# Pages only a public company has; dropped unless allow_public_only=True.
PUBLIC_ONLY_TITLE = re.compile(
    r"\b(?:earnings|quarterly results|(?:first|second|third|fourth) quarter\b.*\bresults"
    r"|fiscal (?:year )?\d{4} results|q[1-4] \d{4}|10-k|10-q|8-k|annual report|investor day"
    r"|earnings call|transcript|dividend|share repurchase|stock price|shares?\b.*\bprice)",
    re.I)

PRESS_WIRES = {"businesswire.com", "prnewswire.com", "globenewswire.com", "accesswire.com",
               "newswire.ca", "einpresswire.com", "prweb.com"}
REFERENCE = {"wikipedia.org", "britannica.com"}
DATABASES = {"crunchbase.com", "pitchbook.com", "craft.co", "zoominfo.com", "dnb.com",
             "owler.com", "cbinsights.com", "globaldata.com", "americancompanies.com",
             "rocketreach.co", "apollo.io", "bloomberg.com/profile", "privsource.com",
             "tracxn.com", "cbinsights.com", "dealroom.co", "komo.ai", "simplify.jobs",
             "partner.io", "umbrex.com", "glassdoor.com", "indeed.com", "linkedin.com"}
SOURCE_RANK = {"company_site": 0, "press_release": 1, "news": 2, "reference": 3, "database": 4}


def host(url: str) -> str:
    h = urlparse(url).netloc.lower().split(":")[0]
    return h[4:] if h.startswith("www.") else h


def _domain_in(h: str, domains: set[str]) -> bool:
    return any(h == d or h.endswith("." + d) for d in domains if "/" not in d)


def blocked(url: str, title: str = "", allow_public_only: bool = False) -> str:
    """Why a result is dropped ('' if kept)."""
    h = host(url)
    if _domain_in(h, BLOCKED_DOMAINS):
        return "blocked_domain"
    if BLOCKED_HOST_PREFIX.match(urlparse(url).netloc.lower().removeprefix("www.")):
        return "investor_host"
    if BLOCKED_PATH.search(urlparse(url).path):
        return "investor_path"
    if not allow_public_only and PUBLIC_ONLY_TITLE.search(title or ""):
        return "public_company_only"
    return ""


def source_type(url: str, company_website: str) -> str:
    h = host(url)
    if h == host(fc_normalize(company_website)) or h.endswith("." + host(fc_normalize(company_website))):
        return "company_site"
    if _domain_in(h, PRESS_WIRES):
        return "press_release"
    if _domain_in(h, REFERENCE):
        return "reference"
    if _domain_in(h, DATABASES) or any(d in url for d in DATABASES if "/" in d):
        return "database"
    return "news"


def fc_normalize(website: str) -> str:
    return website if re.match(r"^https?://", website or "", re.I) else "https://" + (website or "")


# Counts the scrape's SIZE_COUNT misses ("over 42,000 patients in 22 states",
# found in Addus's saved pages) and rank claims ("the 11th largest writer").
# They are rewritten the way the scrape rewrites site counts, so the rest of
# the line (who, where) stays as evidence.
EXTRA_COUNT = re.compile(
    r"\b(?:(?:more than|over|nearly|almost|approximately|about|around|some|up to)\s+)?"
    r"\d[\d,.]*\s*\+?\s+((?:[a-z-]+\s+){0,2}?(?:patients|people|employees|team members|members"
    r"|users|consumers|households|states|provinces|cities|markets|restaurants|units|homes|beds"
    r"|vehicles|trucks|agents|brokers|partners|professionals|caregivers|dealers|distributors"
    r"|franchisees|brands|schools|hospitals|policies|policyholders)\b)", re.I)
RANK = re.compile(r"\b(?:the\s+)?\d+(?:st|nd|rd|th)[- ]largest\b", re.I)


def clean_line(text: str) -> str:
    """A line as kept for evidence: whitespace squeezed; '' if it carries a
    financial, headcount or ticker figure (the scrape's filters) or is too
    short; other counts become "multiple ..." and ranks "one of the largest"."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text.split()) < MIN_LINE_WORDS or fc._figures(text):
        return ""
    text = RANK.sub("one of the largest", text)
    text = SIZE_COUNT.sub(r"multiple \1", text)
    return EXTRA_COUNT.sub(r"multiple \1", text)


# ---------------------------------------------------------------- search queries

LEGAL_SUFFIX = re.compile(
    r",?\s+(?:inc\.?|incorporated|corp\.?|corporation|co\.?|company|holdings?|group|ltd\.?"
    r"|limited|llc|l\.l\.c\.|plc|lp|l\.p\.|s\.a\.|n\.v\.|ag)$", re.I)


def search_name(company_name: str) -> str:
    """The name people search for: legal suffixes dropped ("Addus HomeCare
    Corporation" -> "Addus HomeCare"; "The Wendy's Company" -> "Wendy's")."""
    name = re.sub(r"^the\s+", "", company_name.strip(), flags=re.I)
    for _ in range(3):
        shorter = LEGAL_SUFFIX.sub("", name).strip(" ,")
        if shorter == name or not shorter:
            break
        name = shorter
    return name


# One query per question the saved pages rarely answer. {n} is the search
# name in quotes. Which facets each one serves is recorded with its results.
QUERIES = [
    ("overview", "{n} company products services customers", ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F10"]),
    ("footprint", "{n} locations countries headquarters operations", ["F8", "F9"]),
    ("channels", "{n} sold through distributors dealers retailers customers", ["F4", "F11"]),
    ("regulation", "{n} regulated license regulatory approval", ["F12"]),
    ("changes", "{n} sold OR divested OR acquired OR acquisition OR spin-off", ["F1", "F2", "F10"]),
]


def build_queries(company_name: str, website: str) -> list[dict]:
    n = f'"{search_name(company_name)}"'
    return [{"id": qid, "query": q.format(n=n), "facets": facets} for qid, q, facets in QUERIES]


# ---------------------------------------------------------------- search providers

def _env_key(name: str) -> str:
    key = os.environ.get(name, "")
    env_file = REPO_ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == name:
                key = v.strip().strip('"').strip("'")
    return key


def pick_provider(name: str | None = None) -> tuple[str, str]:
    """(provider, key): the named one, else the first with a key set."""
    keys = {"serper": "SERPER_API_KEY", "brave": "BRAVE_API_KEY", "tavily": "TAVILY_API_KEY"}
    for p in ([name] if name else list(keys)):
        key = _env_key(keys[p])
        if key:
            return p, key
    return "", ""


def call_search(provider: str, key: str, query: str, n: int = MAX_RESULTS_PER_QUERY) -> dict:
    """One search; returns the provider's raw JSON."""
    import requests
    neg = " ".join(f"-site:{d}" for d in ("sec.gov", "finance.yahoo.com", "seekingalpha.com"))
    if provider == "serper":
        r = requests.post("https://google.serper.dev/search", timeout=30,
                          headers={"X-API-KEY": key, "Content-Type": "application/json"},
                          json={"q": f"{query} {neg}", "num": n, "gl": "us", "hl": "en"})
    elif provider == "brave":
        r = requests.get("https://api.search.brave.com/res/v1/web/search", timeout=30,
                         headers={"X-Subscription-Token": key, "Accept": "application/json"},
                         params={"q": f"{query} {neg}", "count": n, "country": "us"})
    elif provider == "tavily":
        r = requests.post("https://api.tavily.com/search", timeout=30,
                          headers={"Authorization": f"Bearer {key}"},
                          json={"query": query, "max_results": n, "search_depth": "basic",
                                "exclude_domains": sorted(BLOCKED_DOMAINS)[:100]})
    else:
        raise ValueError(f"unknown search provider {provider!r}")
    r.raise_for_status()
    return r.json()


def parse_results(provider: str, raw: dict) -> list[dict]:
    """title, url, snippet, date from any provider's response."""
    if provider == "serper":
        items = [{"title": x.get("title", ""), "url": x.get("link", ""),
                  "snippet": x.get("snippet", ""), "date": x.get("date", "")}
                 for x in raw.get("organic", [])]
    elif provider == "brave":
        items = [{"title": x.get("title", ""), "url": x.get("url", ""),
                  "snippet": re.sub(r"<[^>]+>", "", x.get("description", "")),
                  "date": x.get("page_age", "") or x.get("age", "")}
                 for x in raw.get("web", {}).get("results", [])]
    elif provider == "tavily":
        items = [{"title": x.get("title", ""), "url": x.get("url", ""),
                  "snippet": x.get("content", ""), "date": x.get("published_date", "")}
                 for x in raw.get("results", [])]
    else:
        raise ValueError(provider)
    return [i for i in items if i["url"]]


# ---------------------------------------------------------------- same-site crawl

# Links worth following for verification, best first. Unlike the scrape's
# LINK_EXCLUDE, locations, dealers, distributors and news are wanted here.
CRAWL_PRIORITY = [
    ("products", re.compile(r"product|solution|offering|brands?|portfolio|catalog|menu", re.I)),
    ("services", re.compile(r"service|capabilit|what-we-do", re.I)),
    ("markets", re.compile(r"industr|market|sector|who-we-serve|customers?|clients?", re.I)),
    ("footprint", re.compile(r"location|where-we|office|branch|global|countr|region|find-a|store-locator", re.I)),
    ("channels", re.compile(r"dealer|distributor|where-to-buy|partner|reseller|retailer|agent|broker", re.I)),
    ("about", re.compile(r"about|company|who-we-are|our-story|overview", re.I)),
    ("news", re.compile(r"news|press|announcement", re.I)),
]
CRAWL_SKIP = re.compile(
    r"(?:^|[^a-z])(?:investors?|ir|sec-filings?|annual-reports?|shareholders?|stockholders?|stock"
    r"|financials?|earnings|careers?|jobs|privacy|terms|legal|cookies?|log-?in|sign-?in"
    r"|my-?account|account|cart|checkout|search|subscribe)(?:$|[^a-z])|\.(?:pdf|jpg|png|zip)$",
    re.I)


def pick_links(links: list[tuple[str, str]], base: str, already: set[str], k: int) -> list[tuple[str, str]]:
    """Up to k (kind, url) same-site links, one or two per kind in CRAWL_PRIORITY order."""
    seen, per_kind, picked = set(already), {}, []
    for kind, rx in CRAWL_PRIORITY:
        for text, href in links:
            url = urljoin(base, href).split("#")[0].rstrip("/")
            if (not url.startswith("http") or not same_site(url, base) or url in seen
                    or CRAWL_SKIP.search(urlparse(url).path) or blocked(url)):
                continue
            if rx.search(urlparse(url).path) or rx.search(text or ""):
                if per_kind.get(kind, 0) >= 2:
                    break
                seen.add(url)
                per_kind[kind] = per_kind.get(kind, 0) + 1
                picked.append((kind, url))
        if len(picked) >= k:
            break
    return picked[:k]


def crawl_site(website: str, saved_urls: set[str], fetcher=None, k: int = MAX_CRAWL_PAGES,
               log_dir: Path | None = None) -> list[dict]:
    """Same-site pages beyond the saved ones: the homepage's links, ranked by
    CRAWL_PRIORITY. Each page: url, kind, title, lines (raw blocks with
    figures dropped), status."""
    fetcher = fetcher or Fetcher(USER_AGENT)
    pages, home = [], None
    for url in url_candidates(website):
        try:
            if not fetcher.allowed(url):
                return [{"url": url, "kind": "home", "status": "robots_disallowed", "lines": []}]
            final, html = fetcher.get_html(url)
            home = (final, extract_page(html))
            break
        except Exception as exc:                      # noqa: BLE001  (logged, next candidate)
            pages.append({"url": url, "kind": "home", "status": f"error: {exc}"[:200], "lines": []})
    if not home:
        return pages
    base, page = home
    norm = {u.rstrip("/") for u in saved_urls}
    if base.rstrip("/") not in norm:
        pages.append(_page_record(base, "home", page))
    for kind, url in pick_links(page["links"], base, norm | {base.rstrip("/")}, k):
        try:
            if not fetcher.allowed(url):
                pages.append({"url": url, "kind": kind, "status": "robots_disallowed", "lines": []})
                continue
            final, html = fetcher.get_html(url)
            pages.append(_page_record(final, kind, extract_page(html)))
        except Exception as exc:                      # noqa: BLE001
            pages.append({"url": url, "kind": kind, "status": f"error: {exc}"[:200], "lines": []})
    if log_dir:
        (log_dir / "crawl.json").write_text(json.dumps(pages, indent=1, ensure_ascii=False), encoding="utf-8")
    return pages


def _page_record(url: str, kind: str, page: dict) -> dict:
    # raw blocks: the scrape's cleaning drops deal and history sentences,
    # which are what reveal a sold or added business; figures still go
    lines = [x for x in (clean_line(b) for b in [page.get("raw_title", ""), page.get("raw_meta", "")]
                         + page.get("raw_blocks", [])) if x]
    status = "ok" if not re.search(r"\b(?:404|page not found|no longer exists)\b",
                                   page.get("raw_title", ""), re.I) else "not_found_page"
    return {"url": url, "kind": kind, "status": status if lines else "empty",
            "title": page.get("raw_title", ""), "lines": list(dict.fromkeys(lines))[:MAX_LINES_PER_PAGE]}


# ---------------------------------------------------------------- the evidence bundle

@dataclass
class Evidence:
    IQ_COMPANY_ID: str
    company_name: str
    website: str
    lines: dict[str, str] = field(default_factory=dict)       # label -> text
    sources: dict[str, dict] = field(default_factory=dict)    # "P1"/"W2"/"S3" -> url, type, title, date
    dropped: list[dict] = field(default_factory=list)          # results removed, with the reason
    log_dir: str = ""

    def text(self, kinds: str = "PWS") -> str:
        """The evidence as the verifier reads it, grouped by source, best-ranked
        source first within each kind."""
        out = []
        for sid, src in self.sources.items():
            if sid[0] not in kinds:
                continue
            head = f'<source id="{sid}" type="{src["type"]}" url="{src["url"]}"' + (
                f' date="{src["date"]}"' if src.get("date") else "") + ">"
            body = [f"[{lab}] {t}" for lab, t in self.lines.items() if lab.split(".")[0] == sid]
            if body:
                out.append("\n".join([head, *body, "</source>"]))
        return "\n\n".join(out)

    def subset(self, kinds: str) -> dict[str, str]:
        return {k: v for k, v in self.lines.items() if k[0] in kinds}


def saved_pages(iq_id: str) -> list[dict]:
    path = SAVED_PAGES / f"{iq_id}.json"
    return json.loads(path.read_text(encoding="utf-8")).get("pages", []) if path.exists() else []


def gather(iq_id: str, company_name: str, website: str, *, provider: str | None = None,
           crawl: bool = True, search: bool = True, allow_public_only: bool = False,
           fetcher=None, searcher=None, out_root: Path = EVIDENCE_OUT) -> Evidence:
    """All evidence for one company: saved pages (P), same-site crawl (W),
    web search (S). searcher(provider, key, query) -> raw JSON can be passed
    in (tests); otherwise call_search."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    log_dir = out_root / iq_id / stamp
    log_dir.mkdir(parents=True, exist_ok=True)
    ev = Evidence(iq_id, company_name, website, log_dir=str(log_dir))

    # P: the saved pages, labelled exactly as the facet fill labels them
    record = {"IQ_COMPANY_ID": iq_id, "company_name": company_name, "website": website,
              "pages": saved_pages(iq_id)}
    _, p_lines = fc.build_prompt(record, True)
    for p in record["pages"]:
        ev.sources[p["page_id"]] = {"url": p["url"], "type": "company_site", "title": p.get("title", ""),
                                    "date": "", "kind": "saved_page"}
    ev.lines.update(p_lines)

    # W: the company's own site, pages the scrape didn't keep
    if crawl:
        pages = crawl_site(website, {s["url"] for s in ev.sources.values()}, fetcher=fetcher, log_dir=log_dir)
        seen = {t.lower() for t in ev.lines.values()}
        w = 0
        for pg in pages:
            fresh = [t for t in pg["lines"] if t.lower() not in seen]
            if pg["status"] != "ok" or not fresh:
                if pg["status"] != "ok":
                    ev.dropped.append({"url": pg["url"], "reason": pg["status"]})
                continue
            w += 1
            sid = f"W{w}"
            ev.sources[sid] = {"url": pg["url"], "type": "company_site", "title": pg.get("title", ""),
                               "date": "", "kind": f"crawl:{pg['kind']}"}
            for i, t in enumerate(fresh, start=1):
                ev.lines[f"{sid}.{i}"] = t
                seen.add(t.lower())

    # S: web search, ranked by source type, then by query order
    if search:
        provider, key = pick_provider(provider)
        if not provider and searcher is None:
            ev.dropped.append({"url": "", "reason": "no_search_api_key"})
        else:
            hits, log = [], []
            for q in build_queries(company_name, website):
                try:
                    raw = (searcher or call_search)(provider, key, q["query"])
                except Exception as exc:              # noqa: BLE001
                    log.append({**q, "provider": provider, "error": str(exc)[:300]})
                    continue
                log.append({**q, "provider": provider, "raw": raw})
                for r in parse_results(provider, raw):
                    hits.append({**r, "query": q["id"], "facets": q["facets"]})
            (log_dir / "search.json").write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
            kept, seen_urls = [], set()
            for h in hits:
                url = h["url"].split("#")[0]
                why = blocked(url, h["title"], allow_public_only)
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                if why:
                    ev.dropped.append({"url": url, "reason": why})
                    continue
                snippet = clean_line(h["snippet"])
                if not snippet:
                    ev.dropped.append({"url": url, "reason": "snippet_empty_or_figures"})
                    continue
                kept.append({**h, "url": url, "snippet": snippet, "type": source_type(url, website)})
            kept.sort(key=lambda h: SOURCE_RANK[h["type"]])
            for i, h in enumerate(kept, start=1):
                sid = f"S{i}"
                ev.sources[sid] = {"url": h["url"], "type": h["type"], "title": h["title"],
                                   "date": h.get("date", ""), "kind": f"search:{h['query']}"}
                ev.lines[f"{sid}.1"] = h["snippet"]
    (log_dir / "evidence.json").write_text(json.dumps(asdict(ev), indent=1, ensure_ascii=False), encoding="utf-8")
    return ev


def main() -> None:
    import argparse
    import pandas as pd
    p = argparse.ArgumentParser(description="Collect verification evidence for companies.")
    p.add_argument("--tickers", nargs="+", required=True)
    p.add_argument("--provider", choices=["serper", "brave", "tavily"])
    p.add_argument("--no-crawl", action="store_true")
    p.add_argument("--no-search", action="store_true")
    args = p.parse_args()
    from universe import build_universe
    companies, _ = build_universe()
    rows = companies[companies["target_ciq_ticker"].str.upper().isin({t.upper() for t in args.tickers})]
    for c in rows.itertuples():
        ev = gather(c.IQ_COMPANY_ID, c.target_company_name, c.target_ciq_website, provider=args.provider,
                    crawl=not args.no_crawl, search=not args.no_search)
        kinds = {k: sum(1 for s in ev.sources if s[0] == k) for k in "PWS"}
        print(f"{c.target_ciq_ticker:<6} sources P{kinds['P']} W{kinds['W']} S{kinds['S']}  "
              f"lines {len(ev.lines)}  dropped {len(ev.dropped)}  -> {ev.log_dir}")


if __name__ == "__main__":
    main()
