"""
Collect business descriptions from company websites.

Aziz's rule for this project: the method must work for a PRIVATE target, so the
only inputs allowed are the company's name and its website. No 10-Ks, annual
reports, or stock prices. This script therefore builds each company's
description from its own website only:

  1. the homepage (title, meta description, main text)
  2. up to --max-extra-pages pages on the same site that describe the business,
     taking an "About"-type page and a "Products/Solutions"-type page in turn

Investor-relations pages, press releases, careers, legal pages, PDFs and the
like are skipped. Filler text (company values, careers, charity, cookie
notices) is dropped. So that a public company's description looks like a
private company's would and carries no financial information:
  - sentences that reveal public status are removed (tickers, exchanges,
    "publicly traded", shareholders, IPOs/SPACs/spin-offs, S&P 500 / Russell /
    Fortune 500 membership, SEC filings); "(CSWC)"-style bare tickers are cut
  - sentences with financial or size figures are removed: money in digits or
    words, revenue/sales/backlog, growth rates, market share, deal terms, and
    counts of facilities, countries, customers, units, square feet or staff
  - the company's own name, its abbreviations and ticker become [COMPANY],
    and URLs/domain names are removed (turn off with --keep-names)
  - a last check lists anything suspicious that's left (percentages, large
    numbers, "acquired", founding years, ...) in the leak_flags column for a
    person to review. Brand and product names are NOT masked.

Every dropped sentence is logged with the rule that removed it
(dropped_sentences.csv), and descriptions.csv records the share of words each
company lost to the filters, so over-aggressive rules can be spotted by SIC.

Sites that build their text with JavaScript come back nearly empty from a
plain download. If Playwright and its Chromium browser are installed, those
are re-loaded in a headless browser and extracted again (see README for the
one-time setup).

Only NON-financial columns from the company list are carried into the output.

Outputs (in --out, default ./descriptions_output_v2):
  descriptions.csv           one row per company: IDs, ticker, SIC, website,
                             pages used, method, status, word count, share of
                             words dropped by filters, fetch time, excerpt,
                             leak_flags (possible leftovers to review)
  text/<IQ_ID>_<TICKER>.txt  the full collected description
  raw/<IQ_ID>_<TICKER>/      the raw HTML of every page used, plus index.json
                             (URL and fetch time), so results can be rebuilt
                             from a fixed snapshot
  dropped_sentences.csv      every sentence removed by a filter, with the rule

Usage examples:
  # small test: the 2-digit SIC 35 companies (~38, a few minutes)
  python collect_descriptions.py --sic2 35

  # re-run only the companies that weren't 'ok' last time
  python collect_descriptions.py --sic2 35

  # start over for these companies, ignoring earlier results
  python collect_descriptions.py --sic2 35 --refresh

  # everything (~560 companies, roughly 1-2 hours with Playwright) - also
  # what the VS Code Run button does
  python collect_descriptions.py

  # only the 38 companies from Yifan's first run
  python collect_descriptions.py --pilot

Requirements: pip install requests beautifulsoup4 pandas
Optional (JavaScript sites): pip install playwright && playwright install chromium
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4.dammit import UnicodeDammit

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
# Two groups, so the extra pages are one of each kind rather than two
# "about" variants (/about and /about/overview).
ABOUT_KEYWORDS = {
    "about": 5, "who-we-are": 5, "who we are": 5, "our-company": 5,
    "our company": 5, "company": 3, "overview": 3, "what-we-do": 5,
    "what we do": 5, "our-story": 2, "our story": 2,
}
OFFER_KEYWORDS = {
    "products": 4, "solutions": 4, "services": 3, "capabilities": 3,
    "industries": 2, "markets": 2, "brands": 2, "businesses": 3,
}
# Links never followed: investor relations (not available for private
# companies) and pages that rarely describe what the company does.
# Matched against the link text and URL path only, never the domain name.
LINK_EXCLUDE = re.compile(
    r"(?:^|[^a-z])(?:investors?|ir|sec-filings?|annual-reports?|shareholders?"
    r"|stockholders?|stock|financials?|earnings|esg|sustainab\w*|careers?|jobs"
    r"|news\w*|press|media|blog|events?|contact\w*|privacy|terms|legal|cookies?"
    r"|log-?in|sign-?in|my-?account|account|cart|support|faqs?|locations?"
    r"|dealers?|distributors?|warrant\w*|downloads?|search|leadership"
    r"|governance|values|culture|community)(?:$|[^a-z])|\.pdf",
    re.I,
)
# Non-English copies of the site (/fr/, /de-de/, ...).
FOREIGN_LOCALE_PATH = re.compile(
    r"^/(?:fr|de|es|it|pt|ja|jp|zh|cn|ko|kr|nl|pl|ru|sv|tr|cs|da|fi|no|hu)"
    r"(?:[-_][a-z]{2})?(?:/|$)",
    re.I,
)

# Page elements that are navigation or boilerplate rather than content.
# <header> is handled separately: only the site header is removed, not the
# <header> inside a section, which usually holds the page's main headline.
BOILERPLATE_TAGS = ["script", "style", "noscript", "svg", "nav", "footer",
                    "form", "aside", "iframe", "button", "template"]
# Matched against WHOLE class / id tokens, so "hero-banner" or a body class
# like "has-sticky-menu" no longer count as boilerplate.
BOILERPLATE_TOKEN = re.compile(
    r"^(?:cookie[\w-]*|[\w-]*cookie|consent[\w-]*|gdpr[\w-]*"
    r"|(?:[\w]+-)?menu|menu-[\w-]+|navbar[\w-]*|nav|nav-[\w-]+|site-nav[\w-]*"
    r"|(?:site-)?footer[\w-]*|breadcrumbs?|modal[\w-]*|popup[\w-]*"
    r"|newsletter[\w-]*|social(?:-[\w-]+)?|share(?:-[\w-]+)?|skip-link"
    r"|site-header|global-header|search(?:-[\w-]+)?)$",
    re.I,
)
# ARIA roles that mark site chrome.
BOILERPLATE_ROLES = {"navigation", "banner", "contentinfo", "search", "dialog",
                     "menu", "menubar"}
# Never removed, whatever their classes say.
NEVER_STRIP = {"html", "body", "main", "article"}
# A tag holding more than this share of the page's words is content, not
# chrome, even if its class looks like boilerplate.
MAX_BOILERPLATE_SHARE = 0.5

TEXT_TAGS = ["h1", "h2", "h3", "h4", "p", "li", "td", "dd", "blockquote",
             "figcaption"]
# Page builders (Elementor, Wix, Squarespace) often put copy straight into
# <div>s. A div/section with no block-level children is read as one block.
LEAF_CONTAINER_TAGS = ["div", "section"]
BLOCK_TAGS = TEXT_TAGS + ["div", "section", "ul", "ol", "table", "article",
                          "header", "h5", "h6"]

# Sentences that are filler rather than a description of the business
# (values statements, careers, charity, site chrome). Matched per sentence,
# so a good paragraph only loses its "Contact us today." ending.
# Careers/diversity phrases are written narrowly so a staffing company's
# "we place nurses in careers across 40 states" survives.
FILLER = re.compile(
    r"(?:\b(?:core values|our values|guiding (?:behaviou?rs|principles)"
    r"|ethical standards|work ethic|diversity,? (?:equity|and inclusion)"
    r"|equity and inclusion|respectful"
    r"|our (?:people|employees|culture)|employees? (?:live|work)"
    r"|careers? (?:at|with) (?:us|our)|(?:our|explore|view|open) careers?"
    r"|join (?:our|the) team|we(?:'| a)re hiring"
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

# Company size and performance in any form: amounts in words, growth rates,
# market share, deal terms, and counts of facilities, countries, customers,
# units or staff ("53 facilities in five countries", "shipped 10,800 units",
# "a 184,000 square foot plant", "ten thousand employees").
_WRITTEN = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
            r"|fifteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
            r"|several|dozens of|hundreds of|thousands of|a dozen|a hundred|a thousand)")
_QTY = r"(?:\d[\d,.]*\s*\+?|" + _WRITTEN + r")"
SCALE_FIGURE = re.compile(
    r"\b(?:million|billion|trillion)s?\b"
    r"|\brevenues?\b(?!\s+(?:cycle|management|assurance|optimi[sz]ation|recognition))"
    r"|\b(?:net|annual|total) sales\b|\bturnover\b|\bebitda\b|\bbacklog\b|\bbookings\b"
    r"|\bmarket share\b|\bmarket cap\w*|\bfree cash\b|\bvaluation\b"
    r"|\b(?:grew|growth of|increased|increase of|declined?|decrease of)\s+(?:by\s+)?"
    r"\d[\d.,]*\s*(?:%|percent)"
    r"|\d[\d.,]*\s*(?:%|percent)\s+(?:growth|increase|decline|of (?:our|total|its) )"
    r"|year[- ]over[- ]year|\bCAGR\b|organic growth|record (?:year|quarter|results)"
    r"|\d[\d.,]*\s*(?:%|percent)\s+of\s+(?:the\s+|all\s+|our\s+)?(?:[\w-]+\s+){0,3}"
    r"(?:industry|market|customers|companies|clients|banks|hospitals|airlines"
    r"|utilities|manufacturers|operators)\b"
    r"|undisclosed (?:amount|sum|terms|price)|purchase price"
    r"|(?:transaction|deal|enterprise) value"
    r"|\b" + _QTY + r"\s+(?:[a-z-]+\s+){0,2}(?:facilities|plants|factories|locations"
    r"|offices|branches|stores|sites|warehouses|countries|customers|clients|units"
    r"|installations|square[- ]f(?:oo|ee)t|sq\.?\s*ft|acres|employees|associates"
    r"|team members|staff|workers|colleagues|engineers|technicians|brands"
    r"|subsidiaries|operating companies|divisions|patents|models)\b",
    re.I,
)

# Specific ownership and deal events ("acquired by Capital Southwest",
# "[COMPANY] acquires Rhino Products", "a subsidiary of Parent Corp"). These
# name parents and targets and trace the company's history, which identifies
# it. Generic phrases ("acquisition opportunities", "customer acquisition")
# are kept, since for some businesses buying companies IS the business model.
_CAP = r"(?-i:[A-Z\[])"  # a proper name (or [COMPANY]) follows, case-sensitive
DEAL_EVENT = re.compile(
    r"\bacquired by\b|\bpurchased by\b|\bsold to\b|\bmerged? with\b|\bmerger\b"
    r"|\b(?:officially\s+)?(?:acquires|acquired|buys|bought)\s+(?:the\s+)?" + _CAP
    + r"|\b(?:acquires|acquired|buys|bought|acquisition of)\s+(?:the\s+)?(?:\w+\s+)?"
      r"(?:assets|business|operations|stake|interest|shares) (?:of|in)\b"
    r"|\bacquisitions? of\s+(?:the\s+)?" + _CAP
    + r"|\b(?:division|subsidiary|unit|portfolio company) of\s+(?:the\s+)?" + _CAP
    + r"|\bjoin(?:s|ed)? the " + _CAP + r"[\w-]* (?:family|group)\b"
    r"|\bowned by\b|\bownership of the\b",
    re.I,
)
# Where the company is headquartered.
HEADQUARTERS = re.compile(r"\bheadquarter\w*|\bcorporate (?:office|campus)\b|\bHQ\b", re.I)
# Founding years are cut inline ("Founded in 1919, the company makes ..." ->
# "the company makes ..."), keeping the rest of the sentence.
FOUNDING_YEAR = re.compile(
    r"(?:,\s*)?\b(?:founded|established|incorporated|formed|started)\s+(?:in\s+)?"
    r"(?:1[5-9]|20)\d\d\b,?"
    r"|(?:,\s*)?\bsince\s+(?:1[5-9]|20)\d\d\b,?"
    r"|\bdating back to\s+(?:the\s+)?(?:1[5-9]|20)\d\d'?s?\b,?",
    re.I,
)
# Dates in company-history timelines are cut inline too: "In 1895, ...",
# "beginning in 1965", "June 30, 2025 – ...", "during the 1940's".
_MONTH = (r"(?:January|February|March|April|May|June|July|August|September"
          r"|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?")
HISTORY_DATE = re.compile(
    r"\b" + _MONTH + r"\s+(?:\d{1,2},?\s+)?(?:1[5-9]|20)\d\d\b\s*[–—-]?"
    r"|\b(?:in|during|by|from|until|through)\s+(?:the\s+)?(?:early\s+|late\s+|mid-?)?"
    r"(?:1[5-9]|20)\d\d'?s?\b,?",
    re.I,
)

# Phrases cut out inline ("a publicly traded management company" ->
# "a management company"), keeping the rest of the sentence.
PUBLIC_PHRASE = re.compile(r",?\s*\bpublicly[ -]traded\b", re.I)
# Sentences that are about the stock rather than the business are dropped.
# "investors", "dividends" and "earnings" only count in stock-market phrases,
# so a lender's "we help real estate investors" survives.
PUBLIC_COMPANY = re.compile(
    r"stock exchange|stock ticker|ticker symbol|stock symbol|trading symbol"
    r"|under the symbol|listed on (?:the )?(?:NYSE|NASDAQ|Nasdaq|New York)"
    r"|became a public company|public compan(?:y|ies)|shareholders?|stockholders?"
    r"|share price|began trading|initial public offering|\bIPO\b"
    r"|market capitali[sz]ation"
    r"|investor relations|investor (?:day|presentation|deck|update)"
    r"|(?:our|for) investors\b"
    r"|financial (?:results|reports?|information|statements|highlights)"
    r"|\bfinancials\b|(?:declares?|declared|quarterly|pays?|paid|cash) dividends?"
    r"|earnings (?:call|release|report|per share)|\bEPS\b"
    r"|conference call|quarterly results"
    r"|fiscal (?:year|quarter)|succession plan|\bCFO\b"
    r"|minutes? delayed|Source:\s*(?:LSEG|Refinitiv|Nasdaq|NYSE|FactSet|Morningstar|S&P)"
    # exchanges named on their own, and listing events
    r"|\bNYSE\b|\bNASDAQ\b|New York Stock Exchange|London Stock Exchange|\bTSX\b"
    r"|opening bell|closing bell|went public|going public|go public"
    r"|\bSPAC\b|special purpose acquisition|business combination"
    r"|spun[ -]off|spin[ -]?off|split[ -]off|carve[ -]out"
    # indexes and rankings that only public/large companies appear in
    r"|S&P\s*(?:500|400|600|1500|SmallCap|MidCap)|\bRussell\s*\d{3,4}"
    r"|Dow Jones|Fortune\s*(?:500|1000|100|Global)|Forbes Global|Global 2000"
    # securities filings
    r"|\bForm\s*(?:10-?K|10-?Q|8-?K|20-?F|S-1)\b|\b(?:10-?K|10-?Q|8-?K)\b"
    r"|(?-i:\bSEC\b)|Securities and Exchange Commission|proxy statement|annual report",
    re.I,
)
# Statements about the company's own finances rather than its business.
# "profit" and "margin" only count with a qualifier, so "margin lending"
# or "profit-sharing plans" (a product) survive.
FINANCE_TALK = re.compile(
    r"\b(?:our|record|net|operating) profits?\b"
    r"|profitab(?:le growth|ility)|cash flow|balance sheet"
    r"|liquidity position|stakeholder value"
    r"|\b(?:gross|operating|ebitda|profit|net) margins?\b"
    r"|maximi[sz]e (?:their |our )?returns",
    re.I,
)
# Site chrome and legal text: addresses, phone numbers, emails, promotion
# terms, product-filter widgets, trade-show booths, dated news headlines,
# and questions ("Looking for brochures?").
# A street address must be followed by a comma or suite number, and a ZIP
# must follow a real state code, so "4 Wheel Drive tractors", "3 Way valves"
# and "UL 60950" are not mistaken for addresses.
_STATES = (r"A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]"
           r"|N[CDEHJMVY]|O[HKR]|PA|PR|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY]")
SITE_CHROME = re.compile(
    r"\b\d{1,5}\s+(?:[A-Z][\w.'-]*\s+){0,4}(?:Street|St\.?|Road|Rd\.?|Drive|Dr\.?"
    r"|Way|Lane|Ln\.?|Highway|Hwy\.?|Avenue|Ave\.?|Boulevard|Blvd\.?|Parkway|Pkwy\.?)"
    r"(?:\s*,|\s+(?:Suite|Ste\.?|#)\s*\w+)"
    r"|\b(?:" + _STATES + r")\s+\d{5}(?:-\d{4})?\b|\bSuite\s+\d+|\bP\.?\s?O\.? Box\b"
    r"|\b\d{3}[-.]\d{3}[-.]\d{4}\b|\S+@\S+\.[a-z]{2,}"
    # promotion / legal terms (case-insensitive: "Eligible Products")
    r"|(?i:terms (?:&|and) conditions|promo(?:tion)? code|\boffer (?:valid|not valid|has no|details)"
    r"|\beligib(?:le|ility)\b|purchase period|cannot be combined|without notice"
    r"|first come, first served|invoic(?:ed|e of)|U\.S\. dollars|submit the form"
    r"|\b\d+% (?:off|discount)|\bdiscount (?:off|on)\b|qualifying purchases)"
    r"|\(\d[\d,]*\s+items?\)|Not selected:|\bBooth\s*#"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\s*:",
)

# The 38 companies in Yifan's first run, used only with --pilot, so this
# version can be compared with that run. Without options, every company runs.
PILOT_TICKERS = [
    "AAON", "ACMR", "ALG", "ALH", "ASTE", "WHD", "CGEH", "PMTS", "CXT", "CRCT",
    "CSW", "DE", "DGII", "BOOM", "ERII", "ESAB", "FLOC", "FLS", "GENC", "GGG",
    "HAYW", "ISSC", "ITT", "KAI", "LNN", "NTAP", "PBI", "PSIX", "PRLB", "RBC",
    "RHLD", "SPXC", "GRC", "TKR", "TTC", "VECO", "ZBRA", "LII",
]

MIN_BLOCK_WORDS = 5          # drop short fragments like "Learn more"
MAX_SAME_OPENING = 3         # max blocks starting with the same three words
MAX_WORDS = 1500             # cap per company
THIN_WORDS = 150             # below this, try rendering / flag for review
EXCERPT_WORDS = 250
REQUEST_PAUSE_SECONDS = 1.0  # be gentle with company servers
TIMEOUT_SECONDS = 20
RENDER_WAIT_MS = 2500        # time for JavaScript to fill in the page


def url_candidates(website: str) -> list[str]:
    """The given site first, then a www. version, then plain http, for sites
    whose certificate or https setup is broken."""
    website = website.strip()
    if re.match(r"^https?://", website, re.I):
        first = website
        bare = re.sub(r"^https?://", "", website, flags=re.I)
    else:
        first = "https://" + website
        bare = website
    candidates = [first]
    if not bare.lower().startswith("www."):
        candidates.append("https://www." + bare)
    candidates.append("http://" + bare)
    seen, out = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def same_site(url: str, base: str) -> bool:
    """Same host, ignoring 'www.'. Other subdomains (myaccount., shop.) don't count."""
    return _host(url) == _host(base)


def _attr_tokens(tag) -> list[str]:
    tokens = list(tag.get("class") or [])
    if tag.get("id"):
        tokens.append(tag["id"])
    return tokens


def _looks_like_boilerplate(tag) -> bool:
    if tag.name in NEVER_STRIP:
        return False
    if (tag.get("role") or "").lower() in BOILERPLATE_ROLES:
        return True
    return any(BOILERPLATE_TOKEN.match(t) for t in _attr_tokens(tag))


def _is_site_header(tag) -> bool:
    """A <header> outside main/article/section is the site header; one inside
    them is a page or section heading and is kept."""
    return tag.find_parent(["main", "article", "section"]) is None


# Split on sentence ends, but not after abbreviations like "U.S." or "U.K."
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])(?<!\b[A-Z]\.[A-Z]\.)(?<!\b[A-Z]\.)\s+")

# Order matters only for which rule a dropped sentence is logged under.
DROP_RULES = [
    ("public_company", lambda s: PUBLIC_COMPANY.search(s)),
    ("filler", lambda s: FILLER.search(s)),
    ("financial_figure", lambda s: FINANCIAL_FIGURE.search(s)),
    ("finance_talk", lambda s: FINANCE_TALK.search(s)),
    ("scale_figure", lambda s: SCALE_FIGURE.search(s)),
    ("deal_event", lambda s: DEAL_EVENT.search(s)),
    ("headquarters", lambda s: HEADQUARTERS.search(s)),
    ("site_chrome", lambda s: SITE_CHROME.search(s)),
    ("cta_question", lambda s: _is_cta_question(s)),
]


def _is_cta_question(sentence: str) -> bool:
    """Short marketing questions ("Looking for brochures?"). Longer chunks that
    happen to end in '?' usually carry product text, so they're kept."""
    return sentence.rstrip().endswith("?") and len(sentence.split()) <= 15


# Tickers of every company in the input list, filled in by main(). Any of
# them in parentheses ("(CSWC)") is removed wherever it appears.
KNOWN_TICKERS: set[str] = set()
PAREN_CAPS = re.compile(r"\(\s*([A-Z]{2,5})\s*\)")


def _is_acronym(token: str, words: list[str]) -> bool:
    """Is `token` an abbreviation of the words just before it?
    "Dedicated Outdoor Air Systems (DOAS)" -> True,
    "Capital Southwest (CSWC)" -> False (a ticker)."""
    t = token.lower()
    for i, w in enumerate(words):
        if w[0].lower() != t[0]:
            continue
        letters = iter("".join(words[i:]).lower())
        if all(ch in letters for ch in t):  # t is a subsequence
            return True
    return False


def strip_bare_tickers(text: str) -> str:
    """Remove "(ABCD)" when it is a known ticker or not an abbreviation of the
    preceding words. A false hit only loses a parenthesis, not the sentence."""
    def repl(m):
        tok = m.group(1)
        if tok in KNOWN_TICKERS:
            return " "
        words = re.findall(r"[A-Za-z]+", text[max(0, m.start() - 100):m.start()])[-6:]
        return m.group(0) if _is_acronym(tok, words) else " "
    return PAREN_CAPS.sub(repl, text)


def clean_block(text: str, min_words: int = MIN_BLOCK_WORDS,
                log: list | None = None) -> str:
    """Drop filler and public-company sentences; return '' if too little is left.
    If `log` is given, (rule, sentence) is appended for every dropped sentence."""
    text = TICKER_TAG.sub(" ", text)
    text = strip_bare_tickers(text)
    text = PUBLIC_PHRASE.sub("", text)
    text = FOUNDING_YEAR.sub(" ", text)
    text = HISTORY_DATE.sub(" ", text)
    kept = []
    for s in SENTENCE_SPLIT.split(text):
        rule = next((name for name, test in DROP_RULES if test(s)), None)
        if rule is None:
            kept.append(s)
        elif log is not None and s.strip():
            log.append((rule, s.strip()))
    text = re.sub(r"\s+", " ", " ".join(kept)).strip()
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text).strip()
    return text if len(text.split()) >= min_words else ""


MASK = "[COMPANY]"
# One trailing legal/generic suffix: ", Inc.", " Holdings", " International"...
_NAME_SUFFIX = re.compile(
    r",?\s+(?:Inc\.?|Incorporated|Corporation|Corp\.?|Company|Co\.?|Holdings?"
    r"|Group|Ltd\.?|Limited|LLC|L\.?P\.?|plc|N\.?V\.?|S\.?A\.?|AG|SE|Industries"
    r"|Technologies|International|Enterprises|Management|Instruments|Brands"
    r"|Worldwide)\.?$",
    re.I,
)
# Generic words that must not be masked on their own, even when a company's
# name starts with them ("Energy Recovery", "Power Solutions").
GENERIC_NAME_WORDS = {
    "advanced", "alliance", "american", "applied", "capital", "central", "data",
    "digital", "energy", "first", "general", "global", "great", "innovative",
    "international", "national", "north", "pacific", "power", "precision",
    "premier", "smart", "solutions", "southern", "standard", "systems",
    "united", "universal", "western", "eastern", "new", "the", "best", "home",
}
URL_OR_DOMAIN = re.compile(
    r"\b(?:https?://|www\.)\S+"
    r"|\b[\w-]+\.(?:com|net|org|io|us|ca|eu|co\.uk|co\.za|com\.au)\b",
    re.I,
)


def name_variants(name: str, website: str = "") -> list[str]:
    """Ways a company refers to itself: "The Gorman-Rupp Company",
    "Gorman-Rupp", "Power Solutions International" -> also "PSI",
    "CPI Card Group Inc." -> also "CPI". If the website's domain starts with
    the name's first word ("Capstone" -> capstoneenergyplus.com), that word
    alone is a variant too, which catches rebrands. Longest first."""
    full = re.sub(r"\s+", " ", name).strip()
    base = re.sub(r"^The\s+", "", full)
    # strip legal/generic suffixes one at a time, keeping every form:
    # "Power Solutions International, Inc." -> "Power Solutions International"
    # -> "Power Solutions"
    forms = [full, base]
    current = base
    while True:
        shorter = _NAME_SUFFIX.sub("", current).strip(" ,.")
        shorter = re.sub(r"\s*(?:&|and)$", "", shorter).strip(" ,.")  # "Deere &"
        if not shorter or shorter == current:
            break
        forms.append(shorter)
        current = shorter
    variants = set(forms)
    for form in forms:
        words = re.findall(r"[A-Za-z][\w'-]*", form)
        initials = "".join(w[0] for w in words if w[0].isupper())
        if len(initials) >= 3:
            variants.add(initials)  # "Power Solutions International" -> "PSI"
        if words and len(words[0]) >= 3 and words[0].isupper():
            variants.add(words[0])  # leading acronym: "CPI", "ITT", "AAON"
    first = re.findall(r"[A-Za-z][\w'-]*", base)[:1]
    label = _host(website if "://" in website else "https://" + website).split(".")[0]
    if (first and len(first[0]) >= 4 and first[0].lower() not in GENERIC_NAME_WORDS
            and label.startswith(first[0].lower().replace("-", ""))):
        variants.add(first[0])
    return sorted((v for v in variants if len(v) >= 3), key=len, reverse=True)


_ACCENTS = {"a": "aàáâãäå", "e": "eèéêë", "i": "iìíîï", "o": "oòóôõöø",
            "u": "uùúûü", "n": "nñ", "c": "cç", "y": "yýÿ"}


def _name_pattern(name: str) -> str:
    """Regex for a name that ignores accents either way: the list may say
    "Cafe Pumps" while the site says "Café Pumps", or the reverse."""
    out = []
    for ch in name:
        base = unicodedata.normalize("NFKD", ch)[0]
        key = base.lower()
        if key in _ACCENTS:
            chars = _ACCENTS[key].upper() if base.isupper() else _ACCENTS[key]
            out.append(f"[{chars}]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def mask_identity(text: str, name: str, ticker: str, website: str = "") -> str:
    """Replace the company's own name and ticker with [COMPANY] and drop URLs
    and domain names. Case-sensitive, so a descriptive name like "Energy
    Recovery" doesn't mask the phrase "energy recovery devices". Multi-word
    names are also matched run together, any case ("Proto Labs" ->
    "Protolabs")."""
    for v in name_variants(name, website):
        text = re.sub(r"(?<![\w-])" + _name_pattern(v) + r"(?:'s|’s)?(?![\w-])", MASK, text)
        joined = re.sub(r"[\s-]+", "", v)
        if joined != v and len(joined) >= 6:
            text = re.sub(r"(?<![\w-])" + _name_pattern(joined) + r"(?:'s|’s)?(?![\w-])",
                          MASK, text, flags=re.I)
    ticker = (ticker or "").strip()
    if len(ticker) >= 3:
        text = re.sub(r"(?<![\w-])" + re.escape(ticker) + r"(?![\w-])", MASK, text)
    text = URL_OR_DOMAIN.sub(" ", text)
    # final pass over the finished text, so nothing that reached it by another
    # route keeps a ticker tag or a history date
    text = TICKER_TAG.sub(" ", text)
    text = strip_bare_tickers(text)
    text = PUBLIC_PHRASE.sub("", text)
    text = FOUNDING_YEAR.sub(" ", text)
    text = HISTORY_DATE.sub(" ", text)
    text = re.sub(re.escape(MASK) + r"\s*[®™]", MASK, text)
    text = re.sub(r"(?:" + re.escape(MASK) + r"\s*){2,}", MASK + " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Last-pass check on the finished description. Nothing here is removed
# automatically (some hits are harmless, like "80% efficiency"); matches are
# listed in the leak_flags column for a person to look at.
LEAK_CHECK = re.compile(
    r"[$€£¥]\s*\d|\d[\d.,]*\s*(?:%|percent)\s+of\b"
    r"|\bpublic(?:ly)?\b(?!\s+(?:cloud|sector|works|safety|health|spaces?|transit"
    r"|utilit\w+|infrastructure|agenc\w+|schools?|buildings?|areas?|networks?|key))"
    r"|\b(?:share|stock)holders?\b|\bstock (?:price|market|exchange|symbol)\b"
    r"|\bacquir\w+|(?<!customer )\bacquisitions?\b"
    r"|\b(?:1[89]|20)\d\d\b(?!\s*(?:series|model|hours?|cfm|psi|rpm|mm|kw|w)\b)"
    r"|\bheadquarter\w*|\bparent company\b|\bmanager of\b|\boverseeing the operations\b"
    # another company's legal name ("GPGI, Inc."): parents, owners, partners
    r"|(?-i:\b[A-Z][\w&'-]*),?\s+(?-i:(?:Inc|Corp|LLC|Ltd|plc|GmbH|L\.P))\b",
    re.I,
)

# Pages served instead of the site when a bot check blocks the download
# (Imperva/Distil "Pardon Our Interruption", Cloudflare "Just a moment...",
# Akamai "Access Denied"). Their text must never be saved as a description.
BOT_WALL = re.compile(
    r"pardon our interruption|something about your browser made us think you were a bot"
    r"|just a moment\.\.\.|checking (?:if the site connection is secure|your browser)"
    r"|attention required!? \| cloudflare|verify (?:that )?you are (?:a )?human"
    r"|enable javascript and cookies to continue|access denied.{0,80}reference #"
    r"|request unsuccessful\. incapsula|are you a robot|captcha",
    re.I | re.S,
)


def leak_flags(text: str, limit: int = 8) -> str:
    hits, covered_to = [], -1
    for m in LEAK_CHECK.finditer(text):
        start, end = max(0, m.start() - 30), m.end() + 30
        if start <= covered_to:  # overlaps the previous snippet: extend it
            hits[-1] = (hits[-1][0], end)
        else:
            hits.append((start, end))
        covered_to = end
    return " || ".join(f"…{text[s:e].strip()}…" for s, e in hits[:limit])


def clean_title(title: str) -> str:
    title = TICKER_TAG.sub(" ", title)
    title = re.sub(r"\(\s*[A-Z]{2,5}\s*\)", " ", title)  # bare tickers like "(CEPL)"
    title = re.sub(r"\s+", " ", title).strip(" |-–—:")
    return title if re.search(r"[A-Za-z]{2}", title) else ""


def _remove_boilerplate(soup) -> None:
    for tag in soup(BOILERPLATE_TAGS):
        tag.decompose()
    for tag in soup.find_all("header"):
        if not tag.decomposed and _is_site_header(tag):
            tag.decompose()
    page_words = len(soup.get_text(" ", strip=True).split()) or 1
    for tag in soup.find_all(_looks_like_boilerplate):
        if tag.decomposed:
            continue
        share = len(tag.get_text(" ", strip=True).split()) / page_words
        if share > MAX_BOILERPLATE_SHARE:
            continue  # too much of the page to be chrome
        tag.decompose()


def _text_blocks(soup):
    """Text blocks in document order: text tags without nested text tags, and
    divs/sections with no block-level children (page-builder copy)."""
    for tag in soup.find_all(TEXT_TAGS + LEAF_CONTAINER_TAGS):
        if tag.name in TEXT_TAGS:
            if tag.find(TEXT_TAGS):
                continue  # a child block already captures this text
        elif tag.find(BLOCK_TAGS):
            continue      # not a leaf container
        yield re.sub(r"\s+", " ", tag.get_text(" ", strip=True))


def extract_page(html: str) -> dict:
    """Pull the title, meta description, main text blocks and links from a page.
    Also returns the sentences the filters removed and word counts."""
    soup = BeautifulSoup(html, "html.parser")
    links = [(a.get_text(" ", strip=True), a["href"])
             for a in soup.find_all("a", href=True)]
    dropped: list[tuple[str, str]] = []
    title = clean_title(soup.title.get_text(" ", strip=True)) if soup.title else ""
    # the title gets the same leak filters as the body text
    title = clean_block(title, min_words=1, log=dropped) if title else ""
    meta = ""
    for attrs in ({"name": "description"}, {"property": "og:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            meta = clean_block(tag["content"].strip(), min_words=3, log=dropped)
            break

    _remove_boilerplate(soup)

    blocks = []
    for text in _text_blocks(soup):
        if len(text.split()) < MIN_BLOCK_WORDS:
            continue
        text = clean_block(text, log=dropped)
        if text:
            blocks.append(text)
    return {"title": title, "meta": meta, "blocks": blocks, "links": links,
            "dropped": dropped}


def _link_score(haystack: str, keywords: dict) -> int:
    # strongest keyword, not the sum: a link whose text and path repeat
    # several keywords ("Company overview" -> /about/overview) shouldn't
    # outrank the plain /about page
    return max((w for k, w in keywords.items() if k in haystack), default=0)


def pick_extra_pages(links, base_url: str, limit: int) -> list[str]:
    """Best 'about'-type and best 'products'-type pages, alternating."""
    about, offer = {}, {}
    for text, href in links:
        url = urljoin(base_url, href).split("#")[0].split("?")[0].rstrip("/")
        if not url.startswith("http") or not same_site(url, base_url):
            continue
        if url == base_url.split("?")[0].rstrip("/"):
            continue
        parsed = urlparse(url)
        if FOREIGN_LOCALE_PATH.match(parsed.path):
            continue
        # link text and path only: the domain is the same for every link, and
        # a domain containing an excluded word would otherwise block them all
        haystack = f"{text} {parsed.path}".lower()
        if LINK_EXCLUDE.search(haystack):
            continue
        # prefer short, top-level paths like /about over deep product pages
        depth = parsed.path.strip("/").count("/")
        for group, keywords in ((about, ABOUT_KEYWORDS), (offer, OFFER_KEYWORDS)):
            score = _link_score(haystack, keywords) - depth
            if score > 0:
                group[url] = max(score, group.get(url, 0))
    ranked = [[u for u, _ in sorted(g.items(), key=lambda x: -x[1])]
              for g in (about, offer)]
    picked: list[str] = []
    while len(picked) < limit and any(ranked):
        for queue in ranked:
            while queue and queue[0] in picked:
                queue.pop(0)
            if queue and len(picked) < limit:
                picked.append(queue.pop(0))
    return picked


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
                if resp.status_code in (401, 403):
                    rp.disallow_all = True  # standard reading of a locked robots.txt
                else:
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
        head = resp.content[:200].lstrip().lower()
        looks_like_html = head.startswith((b"<!doctype", b"<html"))
        if "html" not in ctype.lower() and not (not ctype and looks_like_html):
            raise ValueError(f"not an HTML page ({ctype or 'no content type'})")
        # Decode from bytes: requests guesses ISO-8859-1 when the header has no
        # charset, which garbles UTF-8 pages. UnicodeDammit also reads the
        # page's own <meta charset>.
        declared = [resp.encoding] if "charset" in ctype.lower() and resp.encoding else []
        html = UnicodeDammit(resp.content, declared, is_html=True).unicode_markup
        return resp.url, html or ""


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
    def check() -> tuple[bool, str]:
        """Can a browser actually start? Importing Playwright isn't enough:
        if Chromium was never installed every launch fails."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return False, "Playwright isn't installed"
        try:
            with sync_playwright() as p:
                p.chromium.launch().close()
        except Exception as exc:
            first = (str(exc).strip().splitlines() or [type(exc).__name__])[0]
            return False, f"Playwright can't start Chromium ({first[:120]})"
        return True, ""

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
            try:
                self._start()
            except Exception as exc:
                raise RenderError(f"browser didn't start: {exc}") from exc
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


# Errors where a different URL variant (www., http://) may still work.
CONNECTION_ERRORS = (requests.ConnectionError, requests.Timeout, RenderError)


def _fetch_homepage(client, website: str) -> tuple[str, str]:
    last_exc: Exception | None = None
    for url in url_candidates(website):
        if not client.allowed(url):
            raise PermissionError("robots_disallowed")
        try:
            return client.get_html(url)
        except CONNECTION_ERRORS as exc:  # includes SSL errors
            last_exc = exc
    raise last_exc  # type: ignore[misc]


def collect_one(client, website: str, max_extra: int) -> dict:
    """Collect one company's description with `client` (Fetcher or Renderer)."""
    try:
        final_url, html = _fetch_homepage(client, website)
    except PermissionError:
        return {"status": "robots_disallowed"}
    home = extract_page(html)
    visible = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    # bot-check pages are short; a real homepage that merely mentions a
    # captcha on its contact form is not one
    if len(visible.split()) < 300 and BOT_WALL.search(visible):
        return {"final_url": final_url, "method": client.method,
                "status": "blocked_bot_check", "word_count": 0}
    pages, used = [home], [final_url]
    raw = [(final_url, html, _now())]
    for extra in pick_extra_pages(home["links"], final_url, max_extra):
        if not client.allowed(extra):
            continue
        try:
            extra_url, extra_html = client.get_html(extra)
        except (requests.RequestException, ValueError, RenderError):
            continue  # one bad sub-page shouldn't sink the company
        pages.append(extract_page(extra_html))
        used.append(extra)
        raw.append((extra_url, extra_html, _now()))
    text = build_description(pages)
    n = len(text.split())
    dropped = [d for p in pages for d in p["dropped"]]
    dropped_words = sum(len(s.split()) for _, s in dropped)
    seen_words = dropped_words + sum(len(b.split()) for p in pages for b in p["blocks"])
    return {
        "final_url": final_url,
        "pages_used": " | ".join(used),
        "method": client.method,
        "text": text,
        "word_count": n,
        "dropped_share": round(dropped_words / seen_words, 3) if seen_words else 0.0,
        "fetched_at": raw[0][2],
        "status": "ok" if n >= THIN_WORDS else "thin_content",
        "_raw": raw,
        "_dropped": dropped,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def collect_with_fallback(fetcher, renderer, website: str, max_extra: int) -> dict:
    """Plain download first; re-try in the headless browser if the result is
    thin or the server refused or failed the plain request (4xx, 5xx -
    e.g. Cloudflare challenges answer 403 or 503)."""
    try:
        result = collect_one(fetcher, website, max_extra)
    except requests.HTTPError as exc:
        result = {"status": f"http_{exc.response.status_code}"}
    except Exception as exc:
        result = {"status": f"error: {type(exc).__name__}: {exc}"[:200]}

    needs_render = (result["status"] in ("thin_content", "blocked_bot_check")
                    or result["status"].startswith(("http_4", "http_5", "error")))
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


def save_raw(raw_dir: Path, raw: list[tuple[str, str, str]]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for i, (url, html, fetched_at) in enumerate(raw):
        name = f"page_{i}.html"
        (raw_dir / name).write_text(html, encoding="utf-8")
        index.append({"file": name, "url": url, "fetched_at": fetched_at})
    (raw_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")


def merge_csv(path: Path, new_rows: pd.DataFrame, rerun_ids: set[str]) -> pd.DataFrame:
    """Replace the rows of companies re-run this time; keep everyone else's."""
    if path.exists():
        old = pd.read_csv(path, dtype=str).fillna("")
        old = old[~old["IQ_COMPANY_ID"].isin(rerun_ids)]
        return pd.concat([old.astype(str), new_rows.astype(str)], ignore_index=True)
    return new_rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--input",
                   help="CSV path or URL (default: a downloaded 'company list for "
                        "interns*.csv' in this folder, else the Google Sheet link)")
    # different default from the original script's "descriptions_output", so
    # this version never writes into (or reuses rows from) the old results
    p.add_argument("--out", default="descriptions_output_v2")
    p.add_argument("--sic2", nargs="*", help="only these 2-digit SIC codes")
    p.add_argument("--tickers", nargs="*", help="only these tickers")
    p.add_argument("--pilot", action="store_true",
                   help="only Yifan's 38 companies (PILOT_TICKERS); by default "
                        "every company in the list runs")
    p.add_argument("--all", action="store_true", help=argparse.SUPPRESS)  # now the default
    p.add_argument("--limit", type=int, help="stop after N companies")
    p.add_argument("--max-extra-pages", type=int, default=2,
                   help="about/products pages to read besides the homepage")
    p.add_argument("--refresh", action="store_true",
                   help="re-collect companies already marked ok")
    p.add_argument("--no-render", action="store_true",
                   help="don't use the headless browser even if installed")
    p.add_argument("--user-agent", default=USER_AGENT)
    p.add_argument("--keep-names", action="store_true",
                   help="don't replace the company's own name/ticker with [COMPANY]")
    args = p.parse_args()

    companies = load_companies(find_input(args.input))
    # every ticker in the full list, before filtering, for strip_bare_tickers
    KNOWN_TICKERS.update(t.strip().upper() for t in companies["target_ciq_ticker"].dropna()
                         if 2 <= len(t.strip()) <= 5 and t.strip().isalpha())
    if args.pilot:
        args.tickers = PILOT_TICKERS
    if args.sic2:
        companies = companies[companies["target_sic2_code"].isin(args.sic2)]
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        companies = companies[companies["target_ciq_ticker"].str.upper().isin(wanted)]
    if args.limit:
        companies = companies.head(args.limit)
    if companies.empty:
        sys.exit("No companies match the filters.")
    print(f"Running {len(companies)} companies.")

    out_dir = Path(args.out)
    text_dir = out_dir / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "descriptions.csv"
    dropped_path = out_dir / "dropped_sentences.csv"

    previous = {}
    if csv_path.exists() and not args.refresh:
        earlier = pd.read_csv(csv_path, dtype=str).fillna("")
        previous = {r["IQ_COMPANY_ID"]: r for r in earlier.to_dict("records")
                    if r.get("status") == "ok"}

    fetcher = Fetcher(args.user_agent)
    renderer = None
    if not args.no_render:
        ok, why = Renderer.check()
        if ok:
            renderer = Renderer(args.user_agent, robots_from=fetcher)
        else:
            print(f"Note: {why}, so JavaScript-heavy sites may come back as")
            print("'thin_content'. To fix: pip install playwright && "
                  "playwright install chromium\n")

    rows, dropped_rows, rerun_ids = [], [], set()
    total = len(companies)
    try:
        for n, company in enumerate(companies.to_dict("records"), start=1):
            iq_id, ticker = company["IQ_COMPANY_ID"], company["target_ciq_ticker"]
            label = f"[{n}/{total}] {ticker:<6} {company['target_company_name'][:40]}"
            if iq_id in previous:
                rows.append(previous[iq_id])
                print(f"{label}  (already collected)")
                continue
            rerun_ids.add(iq_id)

            row = {**company, "final_url": "", "pages_used": "", "method": "",
                   "status": "", "word_count": 0, "dropped_share": "",
                   "fetched_at": "", "excerpt": "", "text_file": "", "raw_dir": "",
                   "leak_flags": ""}
            result = collect_with_fallback(fetcher, renderer,
                                           company["target_ciq_website"],
                                           args.max_extra_pages)
            text = result.pop("text", "")
            if text and not args.keep_names:
                text = mask_identity(text, company["target_company_name"], ticker,
                                     company["target_ciq_website"])
            row["leak_flags"] = leak_flags(text)
            raw = result.pop("_raw", [])
            dropped = result.pop("_dropped", [])
            row.update(result)
            stem = f"{iq_id}_{safe_name(ticker)}"
            if text:
                (text_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
                row["text_file"] = f"text/{stem}.txt"
                row["excerpt"] = " ".join(text.split()[:EXCERPT_WORDS])
            if raw:
                save_raw(out_dir / "raw" / stem, raw)
                row["raw_dir"] = f"raw/{stem}"
            for rule, sentence in dropped:
                dropped_rows.append({"IQ_COMPANY_ID": iq_id, "ticker": ticker,
                                     "target_sic2_code": company["target_sic2_code"],
                                     "rule": rule, "sentence": sentence})
            rows.append(row)
            method = f" ({row['method']})" if row["method"] == "rendered" else ""
            print(f"{label}  {row['status']}{method}  {row['word_count']} words")
    finally:
        if renderer:
            renderer.close()

        # Save whatever was collected, even if the run was interrupted.
        if rows:
            result_df = pd.DataFrame(rows)
            combined = merge_csv(csv_path, result_df, set(result_df["IQ_COMPANY_ID"]))
            combined.to_csv(csv_path, index=False)
            dropped_df = pd.DataFrame(dropped_rows, columns=[
                "IQ_COMPANY_ID", "ticker", "target_sic2_code", "rule", "sentence"])
            merge_csv(dropped_path, dropped_df, rerun_ids).to_csv(dropped_path, index=False)

    print("\nThis run, by status:")
    print(result_df["status"].value_counts().to_string())

    share = pd.to_numeric(result_df["dropped_share"], errors="coerce")
    if share.notna().any():
        by_sic = share.groupby(result_df["target_sic2_code"]).mean().sort_values(ascending=False)
        print("\nShare of words removed by the filters, by 2-digit SIC (check any outlier):")
        print(by_sic.round(3).to_string())

    flagged = (result_df["leak_flags"].fillna("") != "").sum() if "leak_flags" in result_df else 0
    if flagged:
        print(f"\n{flagged} description(s) have possible leftover identifying or "
              "financial details; see the leak_flags column.")

    print(f"\nSaved {csv_path}, {dropped_path} and "
          f"{len(list(text_dir.glob('*.txt')))} text files.")
    print("Rows that still aren't 'ok' need a manual look: copy the description")
    print("from the company's website by hand.")


if __name__ == "__main__":
    main()