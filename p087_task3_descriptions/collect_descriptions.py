"""
Collect business descriptions from company websites.

Aziz's rule for this project: the method must work for a PRIVATE target, so the
only inputs allowed are the company's name and its website. No 10-Ks, annual
reports, or stock prices. This script therefore builds each company's
description from its own website only:

  1. the homepage (title, meta description, main text)
  2. up to --max-extra-pages pages on the same site that describe the business
     ("About", "Who we are", "Products", "Solutions", ...)

Investor-relations pages, press releases, careers, legal pages, PDFs and the
like are skipped. Filler text (company values, careers, charity, cookie
notices) is dropped, and mentions that only a public company would have
("NYSE: ABC", "publicly traded", "shareholders") are removed, so a public
company's description looks like a private company's would.

Sites that build their text with JavaScript come back nearly empty from a
plain download. If Playwright is installed, those are re-loaded in a headless
browser and extracted again (see README for the one-time setup).

Only NON-financial columns from the company list are carried into the output.

Outputs (in --out, default ./descriptions_output):
  descriptions.csv           one row per company: IDs, ticker, SIC, website,
                             pages used, method, status, word count, excerpt
  text/<IQ_ID>_<TICKER>.txt  the full collected description

Usage examples:
  # small test: the 2-digit SIC 35 companies (~38, a few minutes)
  python collect_descriptions.py --sic2 35

  # re-run only the companies that weren't 'ok' last time
  python collect_descriptions.py --sic2 35

  # start over for these companies, ignoring earlier results
  python collect_descriptions.py --sic2 35 --refresh

  # everything (~560 companies, roughly 30-60 minutes)
  python collect_descriptions.py

Requirements: pip install requests beautifulsoup4 pandas
Optional (JavaScript sites): pip install playwright && playwright install chromium
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1hhacI53Ya8af_PFjpP7Nqf77SgGDy6Lyu9WqMT8HH-s/export?format=csv&gid=0"
)

NON_FINANCIAL_COLUMNS = [
    "IQ_COMPANY_ID",
    "target_company_name",
    "target_ciq_ticker",
    "target_ciq_exchange",
    "target_ciq_website",
    "target_sic2_code",
    "target_sic3_code",
    "target_sic4_code",
    "target_primary_sic_industry",
]

USER_AGENT = (
    "Mozilla/5.0 (compatible; RationalAI-research/1.0; "
    "student research project, company descriptions)"
)
# A standard browser Accept header. A narrow one makes some servers answer
# "406 Not Acceptable".
ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

# Links worth following, scored by how well they describe the business.
LINK_KEYWORDS = {
    "about": 5, "who-we-are": 5, "who we are": 5, "our-company": 5,
    "our company": 5, "company": 3, "overview": 3, "what-we-do": 5,
    "what we do": 5, "our-story": 2, "our story": 2,
    "products": 4, "solutions": 4, "services": 3, "capabilities": 3,
    "industries": 2, "markets": 2, "brands": 2, "businesses": 3,
}
# Links never followed: investor relations (not available for private
# companies) and pages that rarely describe what the company does.
LINK_EXCLUDE = re.compile(
    r"(?:^|[^a-z])(?:investors?|ir|sec-filings?|annual-reports?|shareholders?"
    r"|stockholders?|stock|financials?|earnings|esg|sustainab\w*|careers?|jobs"
    r"|news\w*|press|media|blog|events?|contact\w*|privacy|terms|legal|cookies?"
    r"|log-?in|sign-?in|my-?account|account|cart|support|faqs?|locations?"
    r"|dealers?|distributors?|warrant\w*|downloads?|search|leadership"
    r"|governance|values|culture|community)(?:$|[^a-z])|\.pdf",
    re.I,
)
# Page elements that are navigation or boilerplate rather than content.
BOILERPLATE_TAGS = ["script", "style", "noscript", "svg", "nav", "header",
                    "footer", "form", "aside", "iframe", "button", "template"]
BOILERPLATE_ATTR = re.compile(
    r"cookie|consent|banner|menu|navbar|nav-|footer|breadcrumb|modal"
    r"|popup|newsletter|social|skip-link|site-header|global-header"
    r"|(?<![a-z])search",
    re.I,
)
TEXT_TAGS = ["h1", "h2", "h3", "h4", "p", "li"]

# Sentences that are filler rather than a description of the business
# (values statements, careers, charity, site chrome). Matched per sentence,
# so a good paragraph only loses its "Contact us today." ending.
FILLER = re.compile(
    r"(?:\b(?:core values|our values|guiding (?:behaviou?rs|principles)"
    r"|ethical standards|work ethic|diversity|inclusion|respectful"
    r"|our (?:people|employees|culture)|employees? (?:live|work)|team members?"
    r"|careers?|join (?:our|the) team|we(?:'| a)re hiring"
    r"|charit\w*|donat\w*|volunteer\w*|give back|giving back|grants? to fund"
    r"|cookies?|all rights reserved|copyright"
    r"|subscribe|newsletter|sign up|contact (?:us|a representative|our team)"
    r"|couldn.t find what you|try again with|search terms"
    r"|leadership team|our leaders|board of directors"
    r"|press releases?|read more|learn more about|click here)\b|©)",
    re.I,
)
# Mentions that reveal a company is publicly traded. Sentences containing
# these are removed; "(NYSE: ABC)"-style tags are deleted inline.
TICKER_TAG = re.compile(
    r"\(?\s*\b(?:NYSE(?: American)?|NASDAQ|Nasdaq(?:GS|GM|CM)?|AMEX|OTC(?:QX|QB|PK)?|TSX)"
    r"\s*[:\-]\s*[A-Z][A-Z.\-]{0,6}\s*\)?",
)
# Sentences with financial figures or headcount are dropped, so descriptions
# stay non-financial (e.g. "a $1.4B global company with 5,000 associates",
# "yearly shipments exceed $100 million").
_NUM = r"\d[\d,.]*\s*\+?"
_SCALE = r"(?:k|m|mm|bn?|billion|million|thousand|trillion)\b"
FINANCIAL_FIGURE = re.compile(
    r"(?:[$€£¥]|\b(?:US\$|USD|EUR|GBP)\s?)\s*\d"           # $1.4B, USD 300
    r"|\b" + _NUM + r"\s*" + _SCALE + r"\s*(?:in\s+)?(?:dollars|USD|revenues?|sales)"
    r"|\b(?:revenues?|sales|net sales|turnover|ebitda|profit|earnings|backlog)"
    r"\s+(?:of|exceed\w*|over|above|top\w*|reach\w*|surpass\w*|grew to|was|were|is)"
    r"\s+(?:about\s+|approximately\s+|nearly\s+|more than\s+)?" + _NUM
    + r"|\b" + _NUM + r"\s*(?:[a-z\-]+\s+){0,2}"
      r"(?:employees|associates|team members|teammates|people|staff|workers"
      r"|colleagues|professionals|engineers|doers|personnel)\b",
    re.I,
)

# Phrases cut out inline ("a publicly traded management company" ->
# "a management company"), keeping the rest of the sentence.
PUBLIC_PHRASE = re.compile(r",?\s*\bpublicly[ -]traded\b", re.I)
# Sentences that are about the stock rather than the business are dropped.
PUBLIC_COMPANY = re.compile(
    r"stock exchange|stock ticker|ticker symbol|stock symbol|trading symbol"
    r"|under the symbol|listed on (?:the )?(?:NYSE|NASDAQ|Nasdaq|New York)"
    r"|became a public company|public compan(?:y|ies)|shareholders?|stockholders?"
    r"|share price|began trading|initial public offering|\bIPO\b"
    r"|market capitali[sz]ation|(?<!institutional )\binvestors?\b"
    r"|financial (?:results|reports?|information|statements|highlights)"
    r"|\bfinancials\b|dividends?|earnings|conference call|quarterly results"
    r"|fiscal (?:year|quarter)|succession plan|\bCFO\b"
    r"|minutes? delayed|Source:\s*(?:LSEG|Refinitiv|Nasdaq|NYSE|FactSet|Morningstar|S&P)",
    re.I,
)
# Statements about the company's own finances rather than its business.
FINANCE_TALK = re.compile(
    r"\bprofits?\b|profitab(?:le growth|ility)|cash flow|balance sheet"
    r"|liquidity position|stakeholder value|\bmargins?\b"
    r"|maximi[sz]e (?:their |our )?returns",
    re.I,
)
# Site chrome and legal text: addresses, phone numbers, emails, promotion
# terms, product-filter widgets, trade-show booths, dated news headlines,
# and questions ("Looking for brochures?").
SITE_CHROME = re.compile(
    r"\b\d{1,5}\s+(?:[A-Z][\w.'-]*\s+){0,4}(?:Street|St\.?|Road|Rd\.?|Drive|Dr\.?"
    r"|Way|Lane|Ln|Highway|Hwy|Avenue|Ave\.?|Boulevard|Blvd|Parkway|Pkwy)\b"
    r"|\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b|\bSuite\s+\d+|\bP\.?\s?O\.? Box\b"
    r"|\b\d{3}[-.]\d{3}[-.]\d{4}\b|\S+@\S+\.[a-z]{2,}"
    # promotion / legal terms (case-insensitive: "Eligible Products")
    r"|(?i:terms (?:&|and) conditions|promo(?:tion)? code|\boffer (?:valid|not valid|has no|details)"
    r"|\beligib(?:le|ility)\b|purchase period|cannot be combined|without notice"
    r"|first come, first served|invoic(?:ed|e of)|U\.S\. dollars|submit the form"
    r"|\b\d+% (?:off|discount)|\bdiscount (?:off|on)\b|qualifying purchases)"
    r"|\(\d[\d,]*\s+items?\)|Not selected:|\bBooth\s*#"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\s*:",
)

MIN_BLOCK_WORDS = 5          # drop short fragments like "Learn more"
MAX_SAME_OPENING = 3         # max blocks starting with the same three words
MAX_WORDS = 1500             # cap per company
THIN_WORDS = 150             # below this, try rendering / flag for review
EXCERPT_WORDS = 250
REQUEST_PAUSE_SECONDS = 1.0  # be gentle with company servers
TIMEOUT_SECONDS = 20
RENDER_WAIT_MS = 2500        # time for JavaScript to fill in the page


def normalize_url(website: str) -> str:
    website = website.strip()
    if not re.match(r"^https?://", website, re.I):
        website = "https://" + website
    return website


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def same_site(url: str, base: str) -> bool:
    """Same host, ignoring 'www.'. Other subdomains (myaccount., shop.) don't count."""
    return _host(url) == _host(base)


def _is_boilerplate(tag) -> bool:
    attrs = " ".join([tag.get("id") or "", " ".join(tag.get("class") or []),
                      tag.get("role") or ""])
    return bool(attrs.strip()) and bool(BOILERPLATE_ATTR.search(attrs))


# Split on sentence ends, but not after abbreviations like "U.S." or "U.K."
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])(?<!\b[A-Z]\.[A-Z]\.)(?<!\b[A-Z]\.)\s+")


def _is_cta_question(sentence: str) -> bool:
    """Short marketing questions ("Looking for brochures?"). Longer chunks that
    happen to end in '?' usually carry product text, so they're kept."""
    return sentence.rstrip().endswith("?") and len(sentence.split()) <= 15


def clean_block(text: str, min_words: int = MIN_BLOCK_WORDS) -> str:
    """Drop filler and public-company sentences; return '' if too little is left."""
    text = TICKER_TAG.sub(" ", text)
    text = PUBLIC_PHRASE.sub("", text)
    sentences = SENTENCE_SPLIT.split(text)
    kept = [s for s in sentences
            if not PUBLIC_COMPANY.search(s) and not FILLER.search(s)
            and not FINANCIAL_FIGURE.search(s) and not FINANCE_TALK.search(s)
            and not SITE_CHROME.search(s) and not _is_cta_question(s)]
    text = re.sub(r"\s+", " ", " ".join(kept)).strip()
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text).strip()
    return text if len(text.split()) >= min_words else ""


def clean_title(title: str) -> str:
    title = TICKER_TAG.sub(" ", title)
    title = re.sub(r"\(\s*[A-Z]{2,5}\s*\)", " ", title)  # bare tickers like "(CEPL)"
    title = re.sub(r"\s+", " ", title).strip(" |-–—:")
    return title if re.search(r"[A-Za-z]{2}", title) else ""


def extract_page(html: str) -> dict:
    """Pull the title, meta description, main text blocks and links from a page."""
    soup = BeautifulSoup(html, "html.parser")
    links = [(a.get_text(" ", strip=True), a["href"])
             for a in soup.find_all("a", href=True)]
    title = clean_title(soup.title.get_text(" ", strip=True)) if soup.title else ""
    meta = ""
    for attrs in ({"name": "description"}, {"property": "og:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            meta = clean_block(tag["content"].strip(), min_words=3)
            break

    for tag in soup(BOILERPLATE_TAGS):
        tag.decompose()
    for tag in soup.find_all(_is_boilerplate):
        if not tag.decomposed:
            tag.decompose()

    blocks = []
    for tag in soup.find_all(TEXT_TAGS):
        # skip containers whose text is already captured by a child block
        if tag.find(TEXT_TAGS):
            continue
        text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))
        if len(text.split()) < MIN_BLOCK_WORDS:
            continue
        text = clean_block(text)
        if text:
            blocks.append(text)
    return {"title": title, "meta": meta, "blocks": blocks, "links": links}


def pick_extra_pages(links, base_url: str, limit: int) -> list[str]:
    scored = {}
    for text, href in links:
        url = urljoin(base_url, href).split("#")[0].rstrip("/")
        if not url.startswith("http") or not same_site(url, base_url):
            continue
        if url.rstrip("/") == base_url.rstrip("/"):
            continue
        parsed = urlparse(url)
        haystack = f"{text} {parsed.netloc} {parsed.path}".lower()
        if LINK_EXCLUDE.search(haystack):
            continue
        score = sum(w for k, w in LINK_KEYWORDS.items() if k in haystack)
        # prefer short, top-level paths like /about over deep product pages
        depth = parsed.path.strip("/").count("/")
        score -= depth
        if score > 0:
            scored[url] = max(score, scored.get(url, 0))
    return [u for u, _ in sorted(scored.items(), key=lambda x: -x[1])][:limit]


def build_description(pages: list[dict]) -> str:
    """Combine pages into one text: title/meta first, then unique blocks."""
    parts, seen = [], set()
    openings: dict[str, int] = {}

    def add(text: str):
        key = text.lower()
        if not text or key in seen:
            return
        # Cap long repetitive lists (e.g. 40 "Alamo Group acquires ..." lines)
        # at 3 blocks that start with the same three words.
        opening = " ".join(key.split()[:3])
        openings[opening] = openings.get(opening, 0) + 1
        if openings[opening] > MAX_SAME_OPENING:
            return
        seen.add(key)
        parts.append(text)

    home = pages[0]
    add(home["title"])
    add(home["meta"])
    # about/product pages first (they describe the business), then homepage
    for page in pages[1:] + pages[:1]:
        for block in page["blocks"]:
            add(block)
    words = " ".join(parts).split()
    return " ".join(words[:MAX_WORDS])


class Fetcher:
    """Plain HTTP downloads (fast; doesn't run JavaScript)."""

    method = "html"

    def __init__(self, user_agent: str):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": ACCEPT,
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.robots: dict[str, robotparser.RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if root not in self.robots:
            rp = robotparser.RobotFileParser()
            try:
                resp = self.session.get(root + "/robots.txt", timeout=10)
                rp.parse(resp.text.splitlines() if resp.ok else [])
            except requests.RequestException:
                rp.parse([])
            self.robots[root] = rp
        return self.robots[root].can_fetch(self.session.headers["User-Agent"], url)

    def get_html(self, url: str) -> tuple[str, str]:
        time.sleep(REQUEST_PAUSE_SECONDS)
        resp = self.session.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=True)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "")
        looks_like_html = resp.text.lstrip()[:200].lower().startswith(("<!doctype", "<html"))
        if "html" not in ctype.lower() and not (not ctype and looks_like_html):
            raise ValueError(f"not an HTML page ({ctype or 'no content type'})")
        return resp.url, resp.text


class RenderError(Exception):
    pass


class Renderer:
    """Headless-browser downloads (slower; runs the page's JavaScript)."""

    method = "rendered"

    def __init__(self, user_agent: str, robots_from: Fetcher):
        self.user_agent = user_agent
        self.robots_from = robots_from
        self._pw = self._browser = self._page = None

    @staticmethod
    def available() -> bool:
        try:
            import playwright.sync_api  # noqa: F401
            return True
        except ImportError:
            return False

    def allowed(self, url: str) -> bool:
        return self.robots_from.allowed(url)

    def _start(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        context = self._browser.new_context(
            user_agent=self.user_agent, locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
        self._page = context.new_page()

    def get_html(self, url: str) -> tuple[str, str]:
        if self._page is None:
            self._start()
        time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            resp = self._page.goto(url, wait_until="domcontentloaded",
                                   timeout=TIMEOUT_SECONDS * 1000)
            self._page.wait_for_timeout(RENDER_WAIT_MS)
        except Exception as exc:  # timeouts, DNS errors, etc.
            raise RenderError(str(exc).splitlines()[0]) from exc
        if resp is not None and resp.status >= 400:
            raise RenderError(f"HTTP {resp.status}")
        return self._page.url, self._page.content()

    def close(self):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()


def collect_one(client, website: str, max_extra: int) -> dict:
    """Collect one company's description with `client` (Fetcher or Renderer)."""
    url = normalize_url(website)
    if not client.allowed(url):
        return {"status": "robots_disallowed"}
    final_url, html = client.get_html(url)
    home = extract_page(html)
    pages, used = [home], [final_url]
    for extra in pick_extra_pages(home["links"], final_url, max_extra):
        if not client.allowed(extra):
            continue
        try:
            pages.append(extract_page(client.get_html(extra)[1]))
            used.append(extra)
        except (requests.RequestException, ValueError, RenderError):
            continue  # one bad sub-page shouldn't sink the company
    text = build_description(pages)
    n = len(text.split())
    return {
        "final_url": final_url,
        "pages_used": " | ".join(used),
        "method": client.method,
        "text": text,
        "word_count": n,
        "status": "ok" if n >= THIN_WORDS else "thin_content",
    }


def collect_with_fallback(fetcher, renderer, website: str, max_extra: int) -> dict:
    """Plain download first; re-try in the headless browser if the result is
    thin or the server refused the plain request."""
    try:
        result = collect_one(fetcher, website, max_extra)
    except requests.HTTPError as exc:
        result = {"status": f"http_{exc.response.status_code}"}
    except Exception as exc:
        result = {"status": f"error: {type(exc).__name__}: {exc}"[:200]}

    needs_render = (result["status"] == "thin_content"
                    or result["status"].startswith(("http_4", "error")))
    if renderer is None or not needs_render:
        return result
    try:
        rendered = collect_one(renderer, website, max_extra)
    except Exception:
        return result  # keep the plain result and its status
    # keep whichever version found more text
    if rendered.get("word_count", 0) > result.get("word_count", 0):
        return rendered
    return result


def find_input(given: str | None) -> str:
    """Use --input if given, else a downloaded copy of the sheet in this folder."""
    if given:
        return given
    for pattern in ("company list for interns*.csv", "company_list*.csv"):
        matches = sorted(Path(".").glob(pattern))
        if matches:
            print(f"Using company list: {matches[0]}")
            return str(matches[0])
    return SHEET_CSV_URL


def load_companies(source: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(source, dtype=str)
    except Exception as exc:
        if source.startswith("http"):
            sys.exit(
                f"Couldn't download the company list ({exc}).\n"
                "The sheet needs a Columbia sign-in, so download it yourself:\n"
                "  open the sheet -> File -> Download -> Comma-separated values (.csv)\n"
                "and put the file in this folder (or pass --input path/to/file.csv)."
            )
        raise
    missing = [c for c in NON_FINANCIAL_COLUMNS if c not in df.columns]
    if missing:
        sys.exit(f"Input is missing expected columns: {missing}")
    return df[NON_FINANCIAL_COLUMNS]


def safe_name(ticker: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "-", ticker.strip().upper())


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--input",
                   help="CSV path or URL (default: a downloaded 'company list for "
                        "interns*.csv' in this folder, else the Google Sheet link)")
    p.add_argument("--out", default="descriptions_output")
    p.add_argument("--sic2", nargs="*", help="only these 2-digit SIC codes")
    p.add_argument("--tickers", nargs="*", help="only these tickers")
    p.add_argument("--limit", type=int, help="stop after N companies")
    p.add_argument("--max-extra-pages", type=int, default=2,
                   help="about/products pages to read besides the homepage")
    p.add_argument("--refresh", action="store_true",
                   help="re-collect companies already marked ok")
    p.add_argument("--no-render", action="store_true",
                   help="don't use the headless browser even if installed")
    p.add_argument("--user-agent", default=USER_AGENT)
    args = p.parse_args()

    companies = load_companies(find_input(args.input))
    if args.sic2:
        companies = companies[companies["target_sic2_code"].isin(args.sic2)]
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        companies = companies[companies["target_ciq_ticker"].str.upper().isin(wanted)]
    if args.limit:
        companies = companies.head(args.limit)
    if companies.empty:
        sys.exit("No companies match the filters.")

    out_dir = Path(args.out)
    text_dir = out_dir / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "descriptions.csv"

    previous, earlier_rows = {}, pd.DataFrame()
    if csv_path.exists():
        earlier_rows = pd.read_csv(csv_path, dtype=str).fillna("")
        if not args.refresh:
            previous = {r["IQ_COMPANY_ID"]: r for r in earlier_rows.to_dict("records")
                        if r.get("status") == "ok"}

    fetcher = Fetcher(args.user_agent)
    renderer = None
    if not args.no_render:
        if Renderer.available():
            renderer = Renderer(args.user_agent, robots_from=fetcher)
        else:
            print("Note: Playwright isn't installed, so JavaScript-heavy sites may come")
            print("back as 'thin_content'. To fix: pip install playwright && "
                  "playwright install chromium\n")

    rows = []
    total = len(companies)
    try:
        for n, company in enumerate(companies.to_dict("records"), start=1):
            iq_id, ticker = company["IQ_COMPANY_ID"], company["target_ciq_ticker"]
            label = f"[{n}/{total}] {ticker:<6} {company['target_company_name'][:40]}"
            if iq_id in previous:
                rows.append(previous[iq_id])
                print(f"{label}  (already collected)")
                continue

            row = {**company, "final_url": "", "pages_used": "", "method": "",
                   "status": "", "word_count": 0, "excerpt": "", "text_file": ""}
            result = collect_with_fallback(fetcher, renderer,
                                           company["target_ciq_website"],
                                           args.max_extra_pages)
            text = result.pop("text", "")
            row.update(result)
            if text:
                fname = f"{iq_id}_{safe_name(ticker)}.txt"
                (text_dir / fname).write_text(text, encoding="utf-8")
                row["text_file"] = f"text/{fname}"
                row["excerpt"] = " ".join(text.split()[:EXCERPT_WORDS])
            rows.append(row)
            method = f" ({row['method']})" if row["method"] == "rendered" else ""
            print(f"{label}  {row['status']}{method}  {row['word_count']} words")
    finally:
        if renderer:
            renderer.close()

    result = pd.DataFrame(rows)
    if not earlier_rows.empty:
        untouched = earlier_rows[~earlier_rows["IQ_COMPANY_ID"].isin(result["IQ_COMPANY_ID"])]
        combined = pd.concat([untouched.astype(str), result.astype(str)], ignore_index=True)
    else:
        combined = result
    combined.to_csv(csv_path, index=False)

    print("\nThis run, by status:")
    print(result["status"].value_counts().to_string())
    print(f"\nSaved {csv_path} and {len(list(text_dir.glob('*.txt')))} text files.")
    print("Rows that still aren't 'ok' need a manual look: copy the description")
    print("from the company's website by hand.")


if __name__ == "__main__":
    main()
