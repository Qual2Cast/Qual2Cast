"""
Fetching and text cleaning for the website scrape (used by scrape_websites.py).

Aziz's rule: the method must work for a PRIVATE target, so the only inputs are
the company's name and website. No 10-Ks, investor-relations pages, or
financial data. The filters here drop what only a public company would have
("NYSE: ABC", "publicly traded", dividends, investor links), the company's own
financial and size figures, deal history, founding dates, filler and site
chrome. Every dropped sentence or phrase is returned with the rule that dropped
it, so nothing is removed silently.

  Fetcher / Renderer   plain HTTP and headless-browser downloads (robots.txt honored)
  extract_page(html)   raw and cleaned title / meta / text blocks, links, removals
  clean_block_logged   the sentence filters, with a reason for each removal
  load_companies       the non-financial columns of the company list

Split out of the first collection script (pre-v0/scraps/collect_descriptions_v0/),
which is kept unchanged for reference.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4.dammit import UnicodeDammit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project_data import normalize_sic_codes, snapshot_path  # noqa: E402

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
CONTENT_CONTAINERS = {"html", "body", "main", "article"}
TEXT_TAGS = ["h1", "h2", "h3", "h4", "p", "li"]
# Containers read only when they hold text but no other blocks (see extract_page)
LEAF_TAGS = ["div", "section", "td", "th", "dd", "dt", "blockquote", "figcaption"]

# Sentences that are filler rather than a description of the business
# (values statements, careers, charity, site chrome). Matched per sentence,
# so a good paragraph only loses its "Contact us today." ending.
FILLER = re.compile(
    r"(?:\b(?:core values|our values|guiding (?:behaviou?rs|principles)"
    # workplace diversity statements only: "financial inclusion" describes a product
    r"|ethical standards|work ethic|respectful|\bDEI\b|diverse workforce"
    r"|diversity(?:,| and| &) (?:equity|inclusion)|equity(?:,| and| &) inclusion"
    r"|inclusive (?:workplace|culture)"
    r"|our (?:people|employees|culture)|employees? (?:live|work)|team members?"
    r"|careers?|join (?:our|the) team|we(?:'| a)re hiring"
    r"|charit\w*|donat\w*|volunteer\w*|give back|giving back|grants? to fund"
    r"|cookies?|all rights reserved|copyright"
    # newsletter sign-ups only: "subscribe to our software" is a business model
    r"|subscribe to (?:our |the )?(?:newsletter|blog|updates|mailing list|emails?)"
    r"|newsletter|sign up for (?:our |the )?(?:newsletter|updates|emails?)"
    r"|contact (?:us|a representative|our team)"
    r"|couldn.t find what you|try again with|search terms"
    r"|leadership team|our leaders|board of directors"
    r"|press releases?|read more|learn more about|click here"
    r"|opens in a new (?:window|tab)|opens an external (?:website|site))\b|©)",   # screen-reader link text
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

# Size and growth figures (adapted from Riya's collect_descriptions_2.py):
# market share, growth rates, the company's own revenue, deal values, and
# "90% of Fortune 100 companies". Sentences containing these are dropped.
# Revenue only counts as the company's own ("grow revenue with prepaid
# cards" is product copy), and bare "million" is left alone ("analyzes over
# 5 million data points" is a product spec).
SCALE_FIGURE = re.compile(
    r"\b(?:our|annual|total|record|net) revenues?\b"
    # "service bookings" and employee "turnover" are not finances
    r"|\b(?:net|annual|total) sales\b|\b(?:annual|our|total) turnover\b"
    r"|\b(?:our|record|total) (?:backlog|bookings)\b"
    r"|\bmarket share\b|\bmarket cap\w*|\bfree cash\b"
    # the company's own growth; customer results ("54% increase in online
    # visibility") are product claims and stay
    r"|\b(?:grew|growth of|increased|increase of|declined?|decrease of)\s+(?:by\s+)?"
    r"\d[\d.,]*\s*(?:%|percent)"
    r"|\d[\d.,]*\s*(?:%|percent)\s+of (?:our|total) (?:revenue|sales)"
    r"|year[- ]over[- ]year|\bCAGR\b|organic growth|record (?:year|quarter|results)"
    r"|\d[\d.,]*\s*(?:%|percent)\s+of\s+(?:the\s+|all\s+|our\s+)?(?:[\w-]+\s+){0,3}"
    r"(?:industry|market|customers|companies|clients|banks|hospitals|airlines"
    r"|utilities|manufacturers|operators)\b"
    r"|undisclosed (?:amount|sum|terms|price)|purchase price"
    r"|(?:transaction|deal|enterprise) value",
    re.I,
)
# Counts that show how big the company is ("45 manufacturing plants", "more
# than 125 countries", "thousands of customers") become "multiple ...", so
# the rest of the sentence (who it sells through, where) is kept. Product
# facts (patents, units, square feet) stay, as before.
_WRITTEN = (r"(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
            r"|fifteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
            r"|dozens of|hundreds of|thousands of|millions of|a dozen|a hundred|a thousand)")
SIZE_COUNT = re.compile(
    r"\b(?:(?:more than|over|nearly|almost|approximately|about|around|some|up to)\s+)?"
    r"(?:\d[\d,.]*\s*\+?|" + _WRITTEN + r")\s+"
    r"((?:[a-z-]+\s+){0,2}?(?:facilities|plants|factories|locations|offices|branches"
    r"|stores|sites|warehouses|countries|customers|clients|subsidiaries"
    r"|operating companies|divisions)\b)",
    re.I,
)
# Ownership and deal history ("acquired by Capital Southwest", "[the
# company] acquires UniMac", "a subsidiary of Parent Corp"): it names parents
# and targets, which identifies the company. A proper name must follow, so
# "sold to industries worldwide" and "customer acquisition" are kept.
_CAP = r"(?-i:[A-Z\[])"
DEAL_EVENT = re.compile(
    r"\b(?:acquired|purchased) by\s+(?:the\s+)?" + _CAP
    + r"|\bmerged? with\b|\bmerger\b"
    # "buys" is left out: headlines like "Your CTV Buys Might Be Fake"
    r"|\b(?:officially\s+)?(?:acquires|acquired)\s+(?:the\s+)?" + _CAP
    + r"|\b(?:acquires|acquired|acquisition of)\s+(?:the\s+)?(?:\w+\s+)?"
      r"(?:assets|business|operations|stake|interest|shares) (?:of|in)\b"
    r"|\bacquisitions? of\s+(?:the\s+)?" + _CAP
    + r"|\b(?:division|subsidiary|unit|portfolio company) of\s+(?:the\s+)?" + _CAP
    + r"|\bjoin(?:s|ed)? the " + _CAP + r"[\w-]* (?:family|group)\b"
    r"|\bowned by\s+(?:the\s+)?" + _CAP,
    re.I,
)
# Founding years and history dates identify a company too. They are cut
# inline ("Founded in 1919, the company makes ..." -> "the company makes
# ...", "In 1895, ..."), keeping the rest of the sentence.
FOUNDING_YEAR = re.compile(
    r"(?:,\s*)?\b(?:founded|established|incorporated|formed|started)\s+(?:in\s+)?"
    r"(?:1[5-9]|20)\d\d\b,?"
    r"|(?:,\s*)?\bsince\s+(?:1[5-9]|20)\d\d\b,?"
    r"|\bdating back to\s+(?:the\s+)?(?:1[5-9]|20)\d\d'?s?\b,?",
    re.I,
)
_MONTH = (r"(?:January|February|March|April|May|June|July|August|September"
          r"|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?")
HISTORY_DATE = re.compile(
    r"\b" + _MONTH + r"\s+(?:\d{1,2},?\s+)?(?:1[5-9]|20)\d\d\b\s*[–—-]?"
    r"|\b(?:in|during|by|from|until|through)\s+(?:the\s+)?(?:early\s+|late\s+|mid-?)?"
    r"(?:1[5-9]|20)\d\d'?s?\b,?",
    re.I,
)

# Tickers of every company in the list (filled in by load_companies). One in
# parentheses, "(CSWC)", is cut unless it abbreviates the words just before
# it ("information technology (IT)", "Space Alternated Phase Shift (SAPS)").
KNOWN_TICKERS: set[str] = set()
PAREN_CAPS = re.compile(r"\(\s*([A-Z]{2,5})\s*\)")


def _is_acronym(token: str, words: list[str]) -> bool:
    """Is `token` an abbreviation of the words just before it?
    "Dedicated Outdoor Air Systems (DOAS)" -> True,
    "Capital Southwest (CSWC)" -> False."""
    t = token.lower()
    for i, w in enumerate(words):
        if w[0].lower() != t[0]:
            continue
        letters = iter("".join(words[i:]).lower())
        if all(ch in letters for ch in t):  # t is a subsequence
            return True
    return False


def bare_tickers(text: str) -> list[re.Match]:
    """"(ABCD)" matches that are known tickers, not abbreviations."""
    found = []
    for m in PAREN_CAPS.finditer(text):
        words = re.findall(r"[A-Za-z]+", text[max(0, m.start() - 100):m.start()])[-6:]
        if m.group(1) in KNOWN_TICKERS and not _is_acronym(m.group(1), words):
            found.append(m)
    return found


# Phrases cut out inline ("a publicly traded management company" ->
# "a management company"), keeping the rest of the sentence.
PUBLIC_PHRASE = re.compile(r",?\s*\bpublicly[ -]traded\b", re.I)
# Sentences that are about the stock rather than the business are dropped.
PUBLIC_COMPANY = re.compile(
    r"stock exchange|stock ticker|ticker symbol|stock symbol|trading symbol"
    r"|under the symbol|listed on (?:the )?(?:NYSE|NASDAQ|Nasdaq|New York)"
    # The company's own listing and investors only. Investors as customers
    # ("customize investor experiences") and public companies as clients stay.
    r"|(?:became|is|as|is now) a public company|shareholders?|stockholders?"
    r"|share price|began trading|initial public offering|\bIPO\b"
    r"|market capitali[sz]ation|our investors"
    r"|investor (?:relations|day|presentations?|events?|news|cent(?:er|re)s?|kit"
    r"|resources|information|overview|contacts?|updates)"
    r"|financial (?:results|reports?|information|statements|highlights)"
    r"|\bfinancials\b|dividends?|earnings|conference call|quarterly results"
    r"|fiscal (?:year|quarter)|succession plan|\bCFO\b"
    r"|minutes? delayed|Source:\s*(?:LSEG|Refinitiv|Nasdaq|NYSE|FactSet|Morningstar|S&P)",
    re.I,
)
# Statements about the company's own finances rather than its business.
FINANCE_TALK = re.compile(
    r"(?<!non-)(?<!not-for-)\bprofits?\b|profitab(?:le growth|ility)|cash flow|balance sheet"
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
THIN_WORDS = 150             # below this, try rendering / flag for review
REQUEST_PAUSE_SECONDS = 1.0  # be gentle with company servers
TIMEOUT_SECONDS = 20
RENDER_WAIT_MS = 2500        # time for JavaScript to fill in the page


def normalize_url(website: str) -> str:
    website = website.strip()
    if not re.match(r"^https?://", website, re.I):
        website = "https://" + website
    return website


def url_candidates(website: str) -> list[str]:
    """The given site first, then a www. version, then plain http, for sites
    whose certificate or https setup is broken (from Riya's scraper)."""
    first = normalize_url(website)
    bare = re.sub(r"^https?://", "", first, flags=re.I)
    candidates = [first]
    if not bare.lower().startswith("www."):
        candidates.append("https://www." + bare)
    candidates.append("http://" + bare)
    return list(dict.fromkeys(candidates))


def decode_html(resp: requests.Response) -> str:
    """Page text decoded from its bytes. requests assumes ISO-8859-1 when the
    header names no charset, which garbles UTF-8 pages; UnicodeDammit also
    reads the page's own <meta charset>."""
    ctype = resp.headers.get("Content-Type", "")
    declared = [resp.encoding] if "charset" in ctype.lower() and resp.encoding else []
    return UnicodeDammit(resp.content, declared, is_html=True).unicode_markup or ""


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def same_site(url: str, base: str) -> bool:
    """Same host, ignoring 'www.'. Other subdomains (myaccount., shop.) don't count."""
    return _host(url) == _host(base)


def _is_boilerplate(tag) -> bool:
    # Page-level containers are never boilerplate: many themes put words like
    # "menu" or "header" in <body>'s classes ("mobile-menu-design-classic"),
    # which would otherwise delete the whole page.
    if tag.name in CONTENT_CONTAINERS or tag.get("role") == "main":
        return False
    attrs = " ".join([tag.get("id") or "", " ".join(tag.get("class") or []),
                      tag.get("role") or ""])
    if not attrs.strip() or not BOILERPLATE_ATTR.search(attrs):
        return False
    # Same for app wrappers like <div id="root" class="search-bar-rendered">:
    # anything holding the page's main content is not boilerplate.
    return not tag.find(["main", "article", "h1"])


# Split on sentence ends, but not after abbreviations like "U.S." or "U.K."
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])(?<!\b[A-Z]\.[A-Z]\.)(?<!\b[A-Z]\.)\s+")


def _is_cta_question(sentence: str) -> bool:
    """Short marketing questions ("Looking for brochures?"). Longer chunks that
    happen to end in '?' usually carry product text, so they're kept."""
    return sentence.rstrip().endswith("?") and len(sentence.split()) <= 15


SENTENCE_RULES = [
    ("public_company", PUBLIC_COMPANY.search),
    ("filler", FILLER.search),
    ("financial_figure", FINANCIAL_FIGURE.search),
    ("finance_talk", FINANCE_TALK.search),
    ("scale_figure", SCALE_FIGURE.search),
    ("deal_event", DEAL_EVENT.search),
    ("site_chrome", SITE_CHROME.search),
    ("cta_question", _is_cta_question),
]


def clean_block_logged(text: str, min_words: int = MIN_BLOCK_WORDS) -> tuple[str, list[dict]]:
    """clean_block, plus a record of everything removed and the rule that
    removed it: [{"text": ..., "reason": ...}]."""
    removed = [{"text": m.group(0).strip(), "reason": "ticker_tag"}
               for m in TICKER_TAG.finditer(text)]
    text = TICKER_TAG.sub(" ", text)
    for m in reversed(bare_tickers(text)):
        removed.append({"text": m.group(0), "reason": "bare_ticker"})
        text = text[:m.start()] + " " + text[m.end():]
    # cut inline, keeping the rest of the sentence
    for reason, rule, repl in [("public_phrase", PUBLIC_PHRASE, ""),
                               ("founding_year", FOUNDING_YEAR, " "),
                               ("history_date", HISTORY_DATE, " "),
                               ("size_count", SIZE_COUNT, r"multiple \1")]:
        removed += [{"text": m.group(0).strip(" ,"), "reason": reason}
                    for m in rule.finditer(text)]
        text = rule.sub(repl, text)
    kept = []
    for s in SENTENCE_SPLIT.split(text):
        reason = next((name for name, rule in SENTENCE_RULES if rule(s)), None)
        if reason:
            removed.append({"text": s.strip(), "reason": reason})
        else:
            kept.append(s)
    text = re.sub(r"\s+", " ", " ".join(kept)).strip()
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text).strip()
    if text and len(text.split()) < min_words:
        removed.append({"text": text, "reason": "too_short_after_cleaning"})
        text = ""
    return text, removed


def clean_block(text: str, min_words: int = MIN_BLOCK_WORDS) -> str:
    """Drop filler and public-company sentences; return '' if too little is left."""
    return clean_block_logged(text, min_words)[0]


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
    raw_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    title = clean_title(raw_title)
    raw_meta, meta, removed = "", "", []
    for attrs in ({"name": "description"}, {"property": "og:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            raw_meta = tag["content"].strip()
            meta, removed = clean_block_logged(raw_meta, min_words=3)
            break

    for tag in soup(BOILERPLATE_TAGS):
        # ASP.NET sites wrap the whole page in one <form>; keep any
        # "boilerplate" element that holds the page's main content.
        if tag.decomposed or tag.find(["main", "article", "h1"]):
            continue
        tag.decompose()
    for tag in soup.find_all(_is_boilerplate):
        if not tag.decomposed:
            tag.decompose()

    blocks, raw_blocks, seen = [], [], set()
    for tag in soup.find_all(TEXT_TAGS + LEAF_TAGS):
        if tag.name in TEXT_TAGS:
            # skip containers whose text is already captured by a child block
            if tag.find(TEXT_TAGS):
                continue
        # Text in other containers (card layouts built from <div>/<span>):
        # only "leaf" containers, with no block elements inside, that aren't
        # already part of a heading, paragraph or list item.
        elif tag.find(TEXT_TAGS + LEAF_TAGS) or tag.find_parent(TEXT_TAGS):
            continue
        text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))
        if len(text.split()) < MIN_BLOCK_WORDS or text.lower() in seen:
            continue
        seen.add(text.lower())
        raw_blocks.append(text)
        text, dropped = clean_block_logged(text)
        removed += dropped
        if text:
            blocks.append(text)
    # raw_* and removed record the text before cleaning and what the filters took out
    return {"title": title, "meta": meta, "blocks": blocks, "links": links,
            "raw_title": raw_title, "raw_meta": raw_meta, "raw_blocks": raw_blocks,
            "removed": removed}


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
        looks_like_html = resp.content[:200].lstrip().lower().startswith((b"<!doctype", b"<html"))
        if "html" not in ctype.lower() and not (not ctype and looks_like_html):
            raise ValueError(f"not an HTML page ({ctype or 'no content type'})")
        return resp.url, decode_html(resp)


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


def find_input(given: str | None) -> str:
    """Use --input if given, else the snapshot named in data_manifest.json
    (data-local/snapshots/...), checked against its checksum."""
    if given:
        return given
    return str(snapshot_path())


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
    KNOWN_TICKERS.update(t.strip().upper() for t in df["target_ciq_ticker"].dropna()
                         if 2 <= len(t.strip()) <= 5)
    # zero-padded 4-digit SIC, 2/3-digit derived from it (BrightView: 0700, not 700)
    return normalize_sic_codes(df[NON_FINANCIAL_COLUMNS])
