"""
Website scrape: crawl each company's website and save the raw and cleaned
text of every page read, with its URL, so anything built on it can cite
sources. No manual collection: every company is collected by a script, and
companies whose sites can't be read are marked as such.

Aziz's rule: the method must work for a PRIVATE target, so the only inputs
are the company name and website. No 10-Ks, investor-relations pages, or
financial data. The page parsing and text filters (financial figures,
headcount, tickers, filler) are in fetch_and_clean.py.

For each company it reads the homepage plus up to --max-pages - 1 pages on the
same site, chosen to cover different kinds of information:
  about      "About", "Who we are", "Our company"
  offerings  "Products", "Solutions", "Services", "Platform", "Brands", "Businesses"
  markets    "Industries", "Markets", "Customers", "Who we serve", "Applications"
  model      "Pricing", "Plans", "How it works", "Partners"

Each site is tried with up to four methods, stopping at the first that yields
enough text (adapted from the everlane-sustainability-analysis scraper):
  html      plain HTTP download (fast; no JavaScript)
  rendered  headless Chromium via Playwright (JavaScript sites)
  stealth   undetected-chromedriver, a real Chrome that passes most bot checks
            (sites that answer 403 / Cloudflare "Just a moment...")
  wayback   the most recent Internet Archive snapshot (sites that are down or
            still blocked); the snapshot date is recorded with each page
robots.txt is honored by every method: a site that disallows crawlers is
marked robots_disallowed and not fetched any other way. Every method checks
for bot-check pages (status 'blocked'; their text is never used), and a site
that can't be reached is retried at its www. and http:// addresses.

Everything is kept (in --out, default outputs-local/website_scrape/; see
output_paths()):
  raw_html/<IQ_ID>/<scrape time>/<method>/P<n>.html.gz
                       the pages exactly as downloaded, for every method tried
                       (including attempts that weren't used). Never edited.
  page_text/<IQ_ID>.json
                       per company: for every page used, its source URL, method,
                       fetch time, snapshot date, raw HTML file and checksum,
                         raw_title/raw_meta/raw_blocks  text before the filters
                         title/meta/blocks              text after the filters
                         removed       each sentence the filters dropped + why
  scrape_log.csv       one row per company: status, method, pages, words
Earlier records of a company move to page_text_history/ on --refresh.

The company list is the snapshot named in data_manifest.json (see
src/project_data.py); it is read, never modified.

Usage:
  python scrape_websites.py --sic2 35          # one industry group
  python scrape_websites.py --tickers KAI DE   # specific companies
  python scrape_websites.py                    # all companies
  python scrape_websites.py --refresh          # redo companies already 'ok'
  python scrape_websites.py --reparse          # rebuild text from saved HTML

Requirements: see requirements.txt. One-time: playwright install chromium.
Google Chrome must be installed for the stealth method.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

from fetch_and_clean import (  # also puts ../src on the import path
    LINK_EXCLUDE,
    THIN_WORDS,
    USER_AGENT,
    Fetcher,
    Renderer,
    RenderError,
    decode_html,
    extract_page,
    find_input,
    load_companies,
    same_site,
    url_candidates,
)
from project_data import OUTPUTS_LOCAL, REPO_ROOT

DEFAULT_OUT = OUTPUTS_LOCAL / "website_scrape"


def output_paths(out_dir: Path) -> SimpleNamespace:
    """Where the scrape writes, under the output folder (default
    outputs-local/website_scrape/)."""
    return SimpleNamespace(
        raw_html=out_dir / "raw_html",               # pages as downloaded
        page_text=out_dir / "page_text",             # raw + cleaned text per company
        page_text_history=out_dir / "page_text_history",
        scrape_log=out_dir / "scrape_log.csv",
        logs=out_dir / "logs",
    )

# Keywords that mark a link as describing one kind of information, with a
# weight for how directly it describes the business.
LINK_CATEGORIES = {
    "about": {
        "about": 5, "who-we-are": 5, "who we are": 5, "our-company": 5,
        "our company": 5, "what-we-do": 5, "what we do": 5, "overview": 3,
        "company": 3, "our-story": 2, "our story": 2, "profile": 2,
    },
    "offerings": {
        "products": 4, "solutions": 4, "services": 3, "capabilities": 3,
        "platform": 3, "businesses": 4, "our-businesses": 5, "brands": 3,
        "portfolio": 3, "offerings": 4, "technolog": 2, "divisions": 3,
        "segments": 3,
    },
    "markets": {
        "industries": 4, "markets": 4, "who-we-serve": 5, "who we serve": 5,
        "customers": 3, "clients": 3, "applications": 3, "sectors": 3,
    },
    "model": {
        "pricing": 4, "plans": 2, "how-it-works": 4, "how it works": 4,
        "partners": 2, "membership": 2,
    },
}
# Pages that say how and where the company sells and who its customers are.
# They compete with the categories above for the same page slots.
LINK_CATEGORIES.update({
    "channels": {
        "where-to-buy": 5, "where to buy": 5, "find-a-dealer": 5, "find a dealer": 5,
        "dealer": 4, "distributor": 4, "store-locator": 4, "store locator": 4,
        "resellers": 3, "retailers": 3, "partner-locator": 3,
    },
    "locations": {
        "locations": 4, "find-a-location": 4, "find a location": 4, "where-we-operate": 4,
        "global-presence": 4, "our-offices": 3, "service-area": 3, "offices": 2,
    },
    "customer_stories": {
        "case-studies": 4, "case studies": 4, "case-study": 4, "customer-stories": 4,
        "customer stories": 4, "success-stories": 4, "success stories": 4,
    },
})
CATEGORY_ORDER = ["about", "offerings", "markets", "model",
                  "channels", "locations", "customer_stories"]
# Words fetch_and_clean.LINK_EXCLUDE blocks (it comes from the first
# collection script) but the categories above need; removed before that check.
UNBLOCK = re.compile(r"dealers?|distributors?|locations?|where[- ]to[- ]buy", re.I)
# Not followed, besides fetch_and_clean.LINK_EXCLUDE: blogs, articles,
# company history, leadership, and translated copies of pages. (Case studies
# and customer stories are followed: they show who the customers are.)
EXTRA_EXCLUDE = re.compile(
    r"(?:^|[^a-z])(?:blogs|insights?|webinars?|podcasts?"
    r"|testimonials?|history|awards?|gallery|videos?|board|our-board|impact"
    r"|management|team|executives?)(?:$|[^a-z])", re.I)
INVESTOR_HOST = re.compile(r"^(?:ir|investors?|investor-relations)\.")
LOCALE_SEGMENT = re.compile(r"^([a-z]{2})(?:[-_][a-z]{2})?$")
NON_ENGLISH = {"fr", "de", "es", "it", "pt", "nl", "zh", "ja", "ko", "ru", "pl",
               "sv", "da", "fi", "no", "tr", "cs", "hu", "ar", "he", "cn", "jp",
               "kr", "br", "mx", "th", "vi", "id", "ro", "el", "uk"}

MAX_PAGE_WORDS = 2000          # cap per page (1,200 cut off 62 of 1,519 pages)
STEALTH_WAIT_SECONDS = 6       # time for JavaScript / bot checks to finish
STEALTH_SCROLLS = 4            # scrolls to trigger lazy-loaded content
# Text shown by bot-protection and error pages instead of the real site.
BLOCK_PAGE = re.compile(
    r"just a moment|checking your browser|verify you are human|attention required"
    r"|cf-browser-verification|access denied|403 forbidden|request blocked"
    r"|pardon our interruption|are you a robot"
    r"|something about your browser made us think you were a bot"
    r"|enable javascript and cookies to continue|request unsuccessful\. incapsula",
    re.I,
)
BLOCK_PAGE_MAX_WORDS = 100     # a real page can mention reCAPTCHA; a bot check is short
MAX_SNAPSHOT_AGE_YEARS = 2     # older archived pages are too stale to describe the business
# Errors after which the next form of the address is tried (www., http://)
CONNECTION_ERRORS = (requests.ConnectionError, requests.Timeout, RenderError)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BlockedError(Exception):
    """The site served a bot check or error page instead of its content."""


def is_block_page(parsed: dict) -> bool:
    """A bot check or error page served instead of the site (any method).
    Its text must never be used as the company's description."""
    text = " ".join([parsed["raw_title"], parsed["raw_meta"], *parsed["raw_blocks"]])
    return bool(BLOCK_PAGE.search(parsed["raw_title"])
                or (len(text.split()) < BLOCK_PAGE_MAX_WORDS and BLOCK_PAGE.search(text)))


class StealthBrowser:
    """Real Chrome driven by undetected-chromedriver (slow; passes most bot
    checks). Adapted from the everlane-sustainability-analysis scraper."""

    method = "stealth"

    def __init__(self, robots_from: Fetcher, headless: bool = True,
                 chrome_version: int | None = None):
        self.robots_from = robots_from
        self.headless = headless
        self.chrome_version = chrome_version
        self.driver = None

    @staticmethod
    def available() -> bool:
        try:
            import undetected_chromedriver  # noqa: F401
            return True
        except ImportError:
            return False

    def allowed(self, url: str) -> bool:
        return self.robots_from.allowed(url)

    def _start(self):
        import undetected_chromedriver as uc
        options = uc.ChromeOptions()
        options.add_argument("--window-size=1366,900")
        options.add_argument("--lang=en-US")
        if self.headless:
            options.add_argument("--headless=new")
        self.driver = uc.Chrome(options=options, version_main=self.chrome_version)
        self.driver.set_page_load_timeout(45)

    def get_html(self, url: str) -> tuple[str, str]:
        if self.driver is None:
            self._start()
        try:
            self.driver.get(url)
            time.sleep(STEALTH_WAIT_SECONDS)
            if BLOCK_PAGE.search(self.driver.title or ""):
                time.sleep(STEALTH_WAIT_SECONDS)  # some checks clear on their own
            # Scroll to load lazy content, stopping when the page stops growing
            last = self.driver.execute_script("return document.body.scrollHeight")
            for _ in range(STEALTH_SCROLLS):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
                height = self.driver.execute_script("return document.body.scrollHeight")
                if height == last:
                    break
                last = height
            html = self.driver.page_source
        except Exception as exc:  # timeouts, DNS errors, crashed tab
            raise RenderError(str(exc).splitlines()[0][:150]) from exc
        if BLOCK_PAGE.search(self.driver.title or "") or (
                len(html) < 5000 and BLOCK_PAGE.search(html)):
            raise BlockedError("bot check or error page")
        return self.driver.current_url, html

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            # uc calls quit() again on garbage collection, which errors on Windows
            self.driver.quit = lambda: None


class WaybackFetcher:
    """Most recent Internet Archive snapshot of each page. Used last, for sites
    that are down or block every other method."""

    method = "wayback"

    def __init__(self, robots_from: Fetcher):
        self.robots_from = robots_from
        self.session = robots_from.session
        self.snapshots: dict[str, tuple[str, str]] = {}

    def allowed(self, url: str) -> bool:
        return self.robots_from.allowed(url)

    def source_for(self, url: str) -> tuple[str, str]:
        """(archive URL to cite, snapshot timestamp) for a page fetched here."""
        return self.snapshots.get(url, (url, ""))

    def get_html(self, url: str) -> tuple[str, str]:
        time.sleep(1.0)
        # Asking for today's date redirects to the closest (latest) capture and
        # follows redirects the site itself made; "id_" returns the page as
        # originally captured, without the archive's toolbar.
        today = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        resp = self.session.get(f"https://web.archive.org/web/{today}id_/{url}", timeout=40)
        resp.raise_for_status()
        match = re.search(r"/web/(\d{14})id_/(.+)$", resp.url)
        if not match:
            raise RenderError("no archived snapshot")
        ts, original = match.groups()
        if int(today[:4]) - int(ts[:4]) > MAX_SNAPSHOT_AGE_YEARS:
            raise RenderError(f"latest snapshot too old ({ts[:8]})")
        self.snapshots[original] = (f"https://web.archive.org/web/{ts}/{original}", ts)
        return original, decode_html(resp)


def link_score(text: str, url: str) -> tuple[str, int] | None:
    """(category, score) for a link worth following, or None."""
    parsed = urlparse(url)
    haystack = f"{text} {parsed.netloc} {parsed.path}".lower()
    if (LINK_EXCLUDE.search(UNBLOCK.sub(" ", haystack)) or EXTRA_EXCLUDE.search(parsed.path)
            or re.search(r"[\[\]{}<>\s]", parsed.path)):
        return None
    for segment in parsed.path.lower().split("/"):
        match = LOCALE_SEGMENT.match(segment)
        if match and match.group(1) in NON_ENGLISH:
            return None  # translated copy of a page
    best = None
    for category in CATEGORY_ORDER:
        score = sum(w for k, w in LINK_CATEGORIES[category].items() if k in haystack)
        if score and (best is None or score > best[1]):
            best = (category, score)
    if best is None:
        return None
    # prefer short, top-level paths like /about over deep product pages
    score = best[1] - parsed.path.strip("/").count("/")
    return (best[0], score) if score > 0 else None


CORE_CATEGORIES = {"about", "offerings", "markets", "model"}


def next_page(candidates: dict, covered: set[str]) -> str | None:
    """Best unvisited link, preferring a category no page has covered yet.
    Until one core page (about / offerings / markets / model) is picked, only
    core pages are considered, so channels, locations and case studies compete
    for the remaining slot(s) without pushing out the main description."""
    if not candidates:
        return None
    pool = candidates
    if not covered & CORE_CATEGORIES:
        core = {u: c for u, c in candidates.items() if c[0] in CORE_CATEGORIES}
        pool = core or candidates
    def key(item):
        url, (category, score) = item
        return (category not in covered, score, -len(url))
    return max(pool.items(), key=key)[0]


def is_investor_host(url: str) -> bool:
    """ir.example.com, investors.example.com, investor-relations.example.com"""
    return bool(INVESTOR_HOST.match(urlparse(url).netloc.lower()))


def save_raw(raw_dir: Path, page_id: str, html: str) -> tuple[str, str]:
    """Store a page exactly as downloaded; return (repo-relative path, sha256)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    data = html.encode("utf-8")
    path = raw_dir / f"{page_id}.html.gz"
    with gzip.open(path, "wb") as f:
        f.write(data)
    return path.relative_to(REPO_ROOT).as_posix(), hashlib.sha256(data).hexdigest()


def text_fields(parsed: dict) -> dict:
    """A page's text, from extract_page(): raw (before the filters), what the
    filters removed, and processed (what later steps read, capped at
    MAX_PAGE_WORDS). A bot check or error page keeps its raw text but no
    processed text."""
    blocked = is_block_page(parsed)
    blocks, words = [], 0
    for block in [] if blocked else parsed["blocks"]:
        n = len(block.split())
        if words + n > MAX_PAGE_WORDS:
            break
        blocks.append(block)
        words += n
    meta = "" if blocked else parsed["meta"]
    return {
        "raw_title": parsed["raw_title"],
        "raw_meta": parsed["raw_meta"],
        "raw_blocks": parsed["raw_blocks"],
        "removed": parsed["removed"],
        "block_page": blocked,
        "title": "" if blocked else parsed["title"],
        "meta": meta,
        "blocks": blocks,
        "blocks_cut_at_word_cap": 0 if blocked else len(parsed["blocks"]) - len(blocks),
        "word_count": words + len(meta.split()),
    }


def reparse(paths: SimpleNamespace, ids: set[str]) -> None:
    """Rebuild page text from the saved raw HTML (after a parser or filter
    change): same pages, same sources, no downloads. Earlier records move to
    page_text_history/."""
    done = 0
    for path in sorted(paths.page_text.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["IQ_COMPANY_ID"] not in ids or not record["pages"]:
            continue
        old_words = record["word_count"]
        for page in record["pages"]:
            with gzip.open(REPO_ROOT / page["raw_html_file"], "rt", encoding="utf-8") as f:
                page.update(text_fields(extract_page(f.read())))
        record["word_count"] = sum(p["word_count"] for p in record["pages"])
        if record["pages"][0]["block_page"]:
            record["status"] = "blocked"    # the homepage was a bot check
        elif record["status"] in ("ok", "thin_content", "blocked"):
            record["status"] = "ok" if record["word_count"] >= THIN_WORDS else "thin_content"
        record["reparsed_at"] = now_iso()
        paths.page_text_history.mkdir(parents=True, exist_ok=True)
        stamp = record.get("reparsed_at").replace(":", "")
        path.replace(paths.page_text_history / f"{path.stem}_before_reparse_{stamp}.json")
        # (the archived copy is the pre-reparse version; it was read above)
        path.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        done += 1
        if done % 100 == 0:
            print(f"  re-parsed {done} companies (last: {record['company_name'][:30]}, "
                  f"{old_words} -> {record['word_count']} words)")
    print(f"Re-parsed {done} companies from saved raw HTML (no downloads).")


def crawl(client, website: str, max_pages: int, raw_dir: Path) -> dict:
    """Read the homepage and up to max_pages - 1 related pages with `client`,
    saving each page's raw HTML under raw_dir. If the site can't be reached,
    its www. and http:// addresses are tried too."""
    candidates_urls = url_candidates(website)
    for n, url in enumerate(candidates_urls, start=1):
        if not client.allowed(url):
            return {"status": "robots_disallowed", "pages": []}
        try:
            final_url, html = client.get_html(url)
            break
        except CONNECTION_ERRORS:
            if n == len(candidates_urls):
                raise
    if is_investor_host(final_url):
        # Aziz's rule: no investor-relations pages, even when the main domain
        # redirects there (a private company wouldn't have them)
        return {"status": "investor_site", "final_url": final_url, "pages": [],
                "word_count": 0}
    home_root = final_url.split("#")[0].rstrip("/")
    pages, visited, covered = [], {home_root, url.rstrip("/")}, {"home"}
    candidates: dict[str, tuple[str, int]] = {}

    saved: set[str] = set()

    def add_page(page_url: str, category: str, html: str):
        saved.add(page_url.split("#")[0].split("?")[0].rstrip("/"))
        page_id = f"P{len(pages) + 1}"
        raw_file, raw_sha = save_raw(raw_dir, page_id, html)
        parsed = extract_page(html)
        # archived pages are cited by their archive URL and snapshot date
        source_url, snapshot = (client.source_for(page_url) if hasattr(client, "source_for")
                                else (page_url, ""))
        pages.append({
            "page_id": page_id,
            "url": source_url,
            "category": category,
            "method": client.method,
            "snapshot": snapshot,
            "fetched_at": now_iso(),
            "raw_html_file": raw_file,
            "raw_html_sha256": raw_sha,
            **text_fields(parsed),
        })
        for text, href in parsed["links"]:
            link = urljoin(page_url, href).split("#")[0].split("?")[0].rstrip("/")
            if (not link.startswith("http") or not same_site(link, final_url)
                    or link in visited):
                continue
            scored = link_score(text, link)
            if scored and scored[1] > candidates.get(link, ("", 0))[1]:
                candidates[link] = scored

    add_page(final_url, "home", html)
    if pages[0]["block_page"]:
        raise BlockedError("bot check or error page")   # raw HTML is kept; try the next method
    while len(pages) < max_pages:
        link = next_page(candidates, covered)
        if link is None:
            break
        category = candidates.pop(link)[0]
        visited.add(link)
        if not client.allowed(link):
            continue
        try:
            fetched_url, sub_html = client.get_html(link)
        except (requests.RequestException, ValueError, RenderError, BlockedError):
            continue  # one bad sub-page shouldn't sink the company
        landed = fetched_url.split("#")[0].split("?")[0].rstrip("/")
        if landed in saved or is_investor_host(fetched_url):
            continue  # redirected to a page we already have, or to investor relations
        if is_block_page(extract_page(sub_html)):
            continue  # a bot check on this sub-page only
        visited.add(landed)
        add_page(fetched_url, category, sub_html)
        covered.add(category)

    words = sum(p["word_count"] for p in pages)
    return {
        "status": "ok" if words >= THIN_WORDS else "thin_content",
        "final_url": final_url,
        "pages": pages,
        "word_count": words,
    }


def company_list(given: str | None) -> str:
    """--input if given, else the snapshot named in data_manifest.json."""
    return find_input(given)


def failure_status(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f"http_{exc.response.status_code}"
    if isinstance(exc, BlockedError):
        return "blocked"
    return f"error: {type(exc).__name__}: {exc}"[:200]


def collect(clients: list, website: str, max_pages: int, raw_root: Path) -> dict:
    """Try each method in turn; keep the first result with enough text, or else
    the one with the most text. Raw HTML from every attempt is kept."""
    best, attempts, details = None, [], []
    for client in clients:
        raw_dir = raw_root / client.method
        try:
            result = crawl(client, website, max_pages, raw_dir)
        except Exception as exc:
            result = {"status": failure_status(exc), "pages": [], "word_count": 0}
        attempts.append(f"{client.method}:{result['status']}")
        details.append({
            "method": client.method, "status": result["status"],
            "word_count": result.get("word_count", 0),
            "raw_html_dir": (raw_dir.relative_to(REPO_ROOT).as_posix() if raw_dir.is_relative_to(REPO_ROOT) else str(raw_dir.resolve())) if raw_dir.exists() else "",
        })
        if result["status"] in ("robots_disallowed", "investor_site"):
            best = result   # other methods would land on the same page
            break
        if best is None or result.get("word_count", 0) > best.get("word_count", 0):
            best = result
        if result["status"] == "ok":
            break
    best["attempts"] = " | ".join(attempts)
    best["attempt_details"] = details
    best["method"] = best["pages"][0]["method"] if best["pages"] else ""
    return best


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--input", help="company list CSV (default: snapshot in data_manifest.json)")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--sic2", nargs="*", help="only these 2-digit SIC codes")
    p.add_argument("--tickers", nargs="*", help="only these tickers")
    p.add_argument("--limit", type=int, help="stop after N companies")
    p.add_argument("--max-pages", type=int, default=3, help="pages per company, incl. homepage")
    p.add_argument("--refresh", action="store_true", help="re-collect companies already 'ok'")
    p.add_argument("--methods", nargs="*", default=["html", "rendered", "stealth", "wayback"],
                   choices=["html", "rendered", "stealth", "wayback"],
                   help="methods to try, in this order")
    p.add_argument("--stealth-headful", action="store_true",
                   help="show the stealth Chrome window (passes more bot checks)")
    p.add_argument("--chrome-version", type=int,
                   help="major Chrome version, if undetected-chromedriver guesses wrong")
    p.add_argument("--user-agent", default=USER_AGENT)
    p.add_argument("--reparse", action="store_true",
                   help="rebuild page text from the saved raw HTML (after a parser or "
                        "filter change); no downloads")
    args = p.parse_args()

    companies = load_companies(company_list(args.input))
    if args.sic2:
        companies = companies[companies["target_sic2_code"].isin(args.sic2)]
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        companies = companies[companies["target_ciq_ticker"].str.upper().isin(wanted)]
    if args.limit:
        companies = companies.head(args.limit)
    if companies.empty:
        sys.exit("No companies match the filters.")

    out_dir = Path(args.out).resolve()
    paths = output_paths(out_dir)
    pages_dir = paths.page_text
    history_dir = paths.page_text_history
    pages_dir.mkdir(parents=True, exist_ok=True)
    if args.reparse:
        reparse(paths, set(companies["IQ_COMPANY_ID"]))
        write_scrape_log(paths)
        return

    fetcher = Fetcher(args.user_agent)
    clients = []
    for name in args.methods:
        if name == "html":
            clients.append(fetcher)
        elif name == "rendered":
            if Renderer.available():
                clients.append(Renderer(args.user_agent, robots_from=fetcher))
            else:
                print("Note: Playwright isn't installed; skipping 'rendered'.")
        elif name == "stealth":
            if StealthBrowser.available():
                clients.append(StealthBrowser(fetcher, headless=not args.stealth_headful,
                                              chrome_version=args.chrome_version))
            else:
                print("Note: undetected-chromedriver isn't installed; skipping 'stealth'.")
        elif name == "wayback":
            clients.append(WaybackFetcher(fetcher))

    total = len(companies)
    try:
        for n, company in enumerate(companies.to_dict("records"), start=1):
            iq_id, ticker = company["IQ_COMPANY_ID"], company["target_ciq_ticker"]
            label = f"[{n}/{total}] {ticker:<6} {company['target_company_name'][:40]}"
            path = pages_dir / f"{iq_id}.json"
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
                if old.get("status") == "ok" and not args.refresh:
                    print(f"{label}  (already collected)")
                    continue
                # keep the earlier record rather than overwrite it
                history_dir.mkdir(exist_ok=True)
                stamp = old.get("scraped_at", "unknown").replace(":", "")
                path.replace(history_dir / f"{iq_id}_{stamp}.json")
            scraped_at = now_iso()
            raw_root = paths.raw_html / iq_id / scraped_at.replace(":", "")
            result = collect(clients, company["target_ciq_website"], args.max_pages, raw_root)
            record = {
                "IQ_COMPANY_ID": iq_id,
                "company_name": company["target_company_name"],
                "website": company["target_ciq_website"],
                "status": result["status"],
                "method": result["method"],
                "attempts": result["attempts"],
                "attempt_details": result["attempt_details"],
                "scraped_at": scraped_at,
                "max_pages": args.max_pages,
                "word_count": result.get("word_count", 0),
                "pages": result["pages"],
            }
            path.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"{label}  {record['status']}  {record['method'] or '-'}  "
                  f"{len(record['pages'])} pages  {record['word_count']} words")
    finally:
        for client in clients:
            if hasattr(client, "close"):
                client.close()

    write_scrape_log(paths)


def write_scrape_log(paths: SimpleNamespace) -> None:
    """scrape_log.csv for every company scraped so far, not just this run."""
    rows = []
    for path in sorted(paths.page_text.glob("*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        rows.append({
            "IQ_COMPANY_ID": r["IQ_COMPANY_ID"], "company_name": r["company_name"],
            "website": r["website"], "status": r["status"], "method": r["method"],
            "attempts": r["attempts"], "pages": len(r["pages"]),
            "word_count": r["word_count"],
            "page_urls": " | ".join(pg["url"] for pg in r["pages"]),
            "scraped_at": r["scraped_at"],
        })
    log = pd.DataFrame(rows)
    log.to_csv(paths.scrape_log, index=False)
    print("\nAll companies scraped so far, by status:")
    print(log["status"].value_counts().to_string())
    print(f"\nSaved {paths.scrape_log} and {len(rows)} page files.")


if __name__ == "__main__":
    main()
