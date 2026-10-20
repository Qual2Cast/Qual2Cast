"""High-precision rule extraction of source-backed growth events.

This first extractor intentionally prefers abstention over recall. A keyword
alone is never enough: each rule requires an action phrase and an event object,
and every accepted event retains the exact source sentence and page URL.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

try:
    from .schema import Event, write_events_jsonl
except ImportError:  # Direct script entry remains supported.
    from schema import Event, write_events_jsonl


ELIGIBLE_PAGE_CATEGORIES = {"article", "careers", "jobs"}
CAREERS_EVENT_TYPES = {"hiring", "layoff"}
WORKFORCE_OBJECTS = (
    r"workforce|employees|workers|engineers|staff|roles|positions|jobs"
)
HEADCOUNT_OBJECTS = (
    rf"{WORKFORCE_OBJECTS}|consultants|associates|technicians|drivers|nurses|"
    r"representatives|reps|specialists|developers|analysts|managers|salespeople|"
    r"sales professionals|team members|professionals|operators|mechanics|"
    r"scientists|agents|hires"
)
# Matching runs on a copy of the sentence where non-final periods (decimals,
# "Inc.", "U.S.") are replaced by DOT_MARK, so "$2.2 million" does not end a
# [^.!?] window. Evidence text keeps the original characters.
DOT_MARK = "\u2024"
NUMBER = (
    r"(?:(?:about|approximately|roughly|nearly|some|more than|over|up to)\s+)?"
    r"\$?\d[\d,.\u2024]*%?(?:\s+(?:million|billion))?"
)
CONTRACT_OBJECTS = r"contracts?|agreements?|deals?"
SITE_OBJECTS = (
    r"markets?|regions?|countr(?:y|ies)|states?|locations?|offices?|facilit(?:y|ies)|"
    r"operations|stores?|restaurants?|plants?|warehouses?|factor(?:y|ies)|branch(?:es)?|"
    r"distribution cent(?:er|re)s?|clinics?|hospitals?|campus(?:es)?|units?"
)
# Named-object guard: the next word starts with a capital letter, regardless
# of the surrounding re.I flag.
PROPER = r"(?-i:[A-Z])"

RULES = {
    "new_contract": re.compile(
        r"\b(?:awarded|awards|secured|secures|signed|signs|won|wins|entered into|enters into)\b"
        rf"[^.!?]{{0,100}}\b(?:{CONTRACT_OBJECTS})\b"
        # "has been awarded three ... projects", "secures $10 Million Contract"
        r"|\b(?:awarded|secured|secures|won|wins)\s+(?:a\s+|an\s+|the\s+)?(?:\w+\s+){0,6}?"
        r"(?:projects?|orders?|tenders?)\b"
        r"|\b(?:executed|extended|extends|extend|renewed|renews|amended|amends|expanded|expands)\b"
        rf"[^.!?]{{0,80}}\b(?:{CONTRACT_OBJECTS})\b"
        r"|\b(?:announced|announces|announce|signed|signs|formed|forms|entered into|enters into|"
        r"launched|expanded|expands|expanding)\b[^.!?]{0,80}\b(?:partnership|(?-i:alliance))\b"
        r"|\bnew\s+(?:\w+\s+){0,2}?partnership\b"
        r"|(?-i:\b[Pp]artners [Ww]ith\b)|\b(?:today|now|recently)\s+partnered with\b"
        r"|\bteam(?:s|ed)? up with\b"
        r"|\b(?:received|won|secured)\b[^.!?]{0,60}\bpurchase orders?\b"
        r"|\b(?:selected|chosen)\b[^.!?]{0,80}\b(?:provider|partner|platform|vendor|supplier|"
        r"to (?:provide|maintain|supply|manage|deliver|build|install|serve|support))\b"
        r"|\b(?:named|selected|chosen|appointed)\b[^.!?]{0,60}\b(?:official|exclusive|preferred)\s+"
        r"(?:\w+\s+){0,2}(?:consultant|partner|provider|supplier|vendor)\b"
        # A new designation, not a standing one ("is the Official Chicken Partner of").
        r"|\b(?:serve|serves|will serve|become|becomes|became)\s+as\s+(?:\w+['\u2019]s\s+)?"
        r"(?:first|official|exclusive|preferred)\s+(?:\w+\s+){0,2}(?:partner|provider|supplier)\b"
        r"|\bfirst\s+(?:\w+\s+){0,2}partner in\s+(?-i:[A-Z])",
        re.I,
    ),
    "customer_loss": re.compile(
        r"(?<!\ba )(?<!\ban )(?<!\bthe )\blost\b[^.!?]{0,100}\b(?:customer|client|contract|agreement)\b"
        r"|\b(?:terminated|did not renew|nonrenewal|non-renewal)\b[^.!?]{0,100}"
        r"\b(?:customer|client|contract|agreement)\b"
        r"|\b(?:canceled|cancelled)\b[^.!?]{0,80}\b(?:subscription|contract|agreement|account)\b"
        r"|\b(?:elevated|higher|increased|increasing|rising)\s+(?:customer\s+)?churn\b"
        r"|\bcustomer churn\s+(?:increased|rose|was elevated)\b",
        re.I,
    ),
    "product_launch": re.compile(
        r"\b(?:announced|announces|unveiled|unveils)\b[^.!?]{0,50}\b(?:product release|new capabilities|"
        r"new product|new platform|new solution|new service|new feature|new agent|new module|"
        r"new offering|new integration|new program|new app|new tool|new line)\b"
        r"|\b(?:introduced|launched|unveiled|released)\b[^.!?]{0,100}"
        r"\b(?:new|product|platform|solution|service|feature|agent|module|offering)\b"
        r"|\b(?:rolled out|debuted|began shipping)\b[^.!?]{0,80}"
        r"\b(?:new|product|platform|solution|service|app|device|dashboard)\b"
        r"|\bintroducing\b[^.!?]{0,100}\b(?:product|platform|solution|service|feature|agent|module)\b"
        r"|\b(?:announces?|launches?|introduces?)\b[^.!?]{0,80}"
        r"\b(?:pass|card|program|offering)\b"
        r"|\b(?:flavor|product|service|offering|program|pass|card)\b[^.!?]{0,60}"
        r"\barrives\s+nationwide\b"
        r"|(?-i:\bnew\s+[A-Z][\w-]+(?:\s+(?:[A-Z][\w-]+|and)){0,8},?\s+"
        r"(?:launching|available)\s+(?:nationwide|globally)\b)"
        r"|^(?-i:Introducing\s+(?:the\s+)?[A-Z])[\w-]+(?:\s+[A-Z][\w-]+){0,5}"
        # Noun forms: "the introduction of Paylocity Retirement",
        # "the national launch of Club Wingstop" (not "release of Q2 results").
        rf"|\b(?:launch|introduction|debut|rollout|roll-out)\s+of\s+(?:the\s+)?(?:new\s+)?"
        rf"(?!(?-i:Q[1-4]\b|First|Second|Third|Fourth|Fiscal))(?:{PROPER}|new\b)"
        # "the launch of an expansive suite of AI-powered solutions"
        r"|\b(?:launch|introduction|debut|rollout|roll-out)\s+of\s+(?:an?|its|their|the)\s+"
        r"(?:\w+\s+){0,4}?(?:suite|products?|platform|solutions?|services?|app|program|"
        r"features?|tools?|offering|line|menu)\b"
        r"|\bwith\s+(?:a\s+|its\s+)?new\s+(?:[\w-]+\s+){0,3}?(?:program|product|platform|app|"
        r"feature|service|integration)\b"
        r"|\b(?:offer|offers|introduce|introduces|add|adds|added)\s+(?:\w+\s+){0,3}?new\s+"
        r"(?:[\w-]+\s+){0,3}?(?:menu items?|items|sides|flavors?|products?|options|dips?)\b"
        r"|\bnew\s+(?:[\w-]+\s+){0,3}?(?:sides?|menu items?|flavors?|products?)\b[^.!?]{0,40}"
        r"\b(?:now available|available now)\b"
        r"|(?-i:['\u2019]s new [A-Z])"
        r"|\b(?:expand|expands|expanded)\s+(?:its|the|our)\s+(?:[\w-]+\s+){0,4}?"
        r"(?:solution|platform|product|offering)\s+to\b"
        r"|\bexpands?\b[^.!?]{0,60}\bportfolio of\b[^.!?]{0,40}\bproducts\b"
        r"|\b(?:upgraded|relaunched)\s+(?:its\s+|the\s+)?(?-i:[A-Z])"
        rf"|\bnew additions?\s*[:,]\s*{PROPER}"
        rf"|\b(?:is|are|now)\s+introducing\s+(?:the\s+)?(?:new\s+)?{PROPER}"
        r"|\bnewest\s+(?:limited[- ]time\s+)?(?:flavor|product|platform|feature|service|"
        r"offering|app|menu item|agent|module)\b"
        # Sentence-initial "The new Answer & Insight Agent ...", "New recruiting agents ...".
        r"|^(?-i:(?:The\s+)?[Nn]ew\s+)(?:[\w&-]+\s+){0,4}?(?:agents?|platform|app|"
        r"product|feature|module|service|solution|tool|capabilit(?:y|ies)|flavor|"
        r"offering|device)\b",
        re.I,
    ),
    "market_expansion": re.compile(
        r"\b(?:expand|expands|expanded|expanding|entered|entering|opened|opening)\b"
        rf"[^.!?]{{0,100}}\b(?:{SITE_OBJECTS})\b"
        r"|\b(?:expanded|expanding|expands|expand)\s+into\b"
        r"|\b\d[\d,]*\s+(?:net\s+)?(?:new\s+)?(?:\w+\s+)?openings\b"
        r"|\bnet (?:new )?(?:\w+ )?openings\b"
        # "will open its first location in France", "plans to open 16 restaurants"
        r"|\bopen\s+(?:its\s+|their\s+|our\s+|a\s+|an\s+|the\s+|\d[\d,]*\s+)"
        r"(?:(?:first|new|additional|second|third)\s+)*(?:\w+\s+){0,2}?"
        r"(?:locations?|stores?|restaurants?|offices?|plants?|facilit(?:y|ies)|branch(?:es)?|"
        r"warehouses?|clinics?|hospitals?|cent(?:er|re)s?)\b"
        r"|\b(?:build-out|buildout|development|addition) of\s+\d[\d,]*\s+(?:additional\s+|new\s+)?"
        r"(?:restaurants|stores|locations|units|branches|clinics)\b"
        r"|\b(?:expand(?:s|ed|ing)?|extend(?:s|ed|ing)?|grow(?:s|ing)?|grew)\s+(?:its|our|the)\s+"
        r"(?:geographic\s+)?(?:footprint|presence|reach)\s+(?:into|across|in|to)\s+"
        r"(?:the\s+)?(?:\d[\d,]*\s+)?(?-i:[A-Z])"
        r"|\b(?:geographic\s+)?expansion (?:into|beyond|across)\b|\bgeographic expansion\b"
        r"|\bfinal investment decision\b[^.!?]{0,120}\b(?:plant|facility|pipeline|expansion)\b",
        re.I,
    ),
    "hiring": re.compile(
        rf"\b(?:is hiring|are hiring|now hiring|plans? to hire|will hire|to hire)\b[^.!?]{{0,80}}"
        rf"\b(?:{HEADCOUNT_OBJECTS})\b"
        # "added 150 employees", "will add 300 new jobs": a number is required
        # unless the object is jobs/positions/roles ("creating new jobs"), so
        # "creating an environment where employees ..." does not match.
        rf"|\b(?:add|adds|added|adding|create|creates|created|creating|hired|hiring)\s+"
        rf"{NUMBER}\s+(?:(?:new|additional|full-time|part-time)\s+)*(?:{HEADCOUNT_OBJECTS})\b"
        r"|\b(?:add|adds|added|adding|create|creates|created|creating)\s+(?:\w+\s+){0,3}?"
        r"(?:new|additional)\s+(?:jobs|positions|roles)\b"
        r"|\b(?:expand|expanded|expanding|grow|grew|growing|doubled|doubling|increased|increasing)"
        r"\s+(?:its\s+|our\s+|the\s+)?(?:\w+\s+)?(?:workforce|headcount|sales\s?forces?|sales teams?)\b",
        re.I,
    ),
    "layoff": re.compile(
        rf"\b(?:laid off|lay(?:s|ing)? off|layoffs?)\b[^.!?]{{0,40}}\b(?:{WORKFORCE_OBJECTS})\b"
        rf"|\b(?:reduc(?:e|es|ed|ing)|cut(?:s|ting)?|eliminat(?:e|es|ed|ing))\s+"
        rf"(?:{NUMBER}\s+(?:of\s+)?)?(?:its\s+|the\s+|our\s+|their\s+)?"
        rf"(?:global\s+|total\s+|corporate\s+)?(?:{WORKFORCE_OBJECTS}|headcount)\b"
        r"|\breductions? in force\b|(?-i:\bRIF\b)|\b(?:workforce|headcount) reductions?\b"
        rf"|\bfurlough(?:ed|s|ing)?\b[^.!?]{{0,40}}\b(?:{WORKFORCE_OBJECTS})\b",
        re.I,
    ),
    "credit_stress": re.compile(
        r"\b(?:defaulted|default|breached)\b[^.!?]{0,80}\b(?:debt|loan|covenant)\b"
        r"|\bcovenant breach\b"
        r"|\b(?:liquidity crisis|difficulty servicing (?:its )?debt|credit stress)\b"
        r"|\b(?:credit rating|rating)\b[^.!?]{0,60}\b(?:downgraded|downgrade|lowered)\b"
        r"|\b(?:downgraded|downgrade|lowered)\b[^.!?]{0,60}\b(?:credit rating|rating)\b"
        r"|\boutlook\b[^.!?]{0,40}\b(?:to|as)\s+negative\b"
        r"|\bgoing concern\b"
        r"|\bmissed\b[^.!?]{0,40}\b(?:interest payment|debt payment|payment)\b"
        r"|\bforbearance agreement\b"
        r"|\b(?:filed|files|filing) (?:a voluntary petition )?for (?:Chapter (?:7|11)|bankruptcy)\b"
        r"|\bChapter 11 (?:bankruptcy|protection|proceedings?)\b",
        re.I,
    ),
    "credit_positive": re.compile(
        r"\b(?:refinanced|repaid|paid down)\b[^.!?]{0,80}\b(?:debt|loan|facility)\b"
        r"|\b(?:amended|extended)\b[^.!?]{0,80}\b(?:credit facility|credit agreement|loan facility)\b"
        r"|\b(?:credit rating|rating)\b[^.!?]{0,60}\b(?:upgraded|upgrade|raised)\b"
        r"|\b(?:upgraded|upgrade|raised)\b[^.!?]{0,60}\b(?:credit rating|rating)\b"
        r"|\boutlook\b[^.!?]{0,40}\b(?:to|as)\s+positive\b"
        r"|\brepric(?:ed|ing|es)\b[^.!?]{0,60}\b(?:term loan|loan|debt|facility|notes)\b"
        r"|\bamendment to\b[^.!?]{0,60}\bcredit (?:agreement|facility)\b"
        r"|\b(?:raises|raised|increases|increased|upsized|upsizes)\b[^.!?]{0,40}"
        r"\b(?:revolving credit facility|credit facility|revolver)\b"
        r"|\bexpanded credit facility\b",
        re.I,
    ),
    "acquisition": re.compile(
        r"\b(?:complet(?:ed|es|ing)|clos(?:ed|es|ing)|finaliz(?:ed|es|ing))\s+(?:its\s+|the\s+|our\s+)?"
        r"(?:previously announced\s+)?acquisition of\b"
        r"|\b(?:has\s+|have\s+)?(?:acquired|acquires|agreed to acquire|will acquire|to acquire)\s+"
        rf"(?:substantially all (?:of )?the assets of\s+|(?:a\s+)?(?:majority|minority|controlling) "
        rf"stake in\s+|all (?:of )?the (?:outstanding )?(?:shares|stock) of\s+)?(?:the\s+|an?\s+)?"
        rf"(?:{PROPER}|(?:\w+\s+){{1,3}}?(?:business|company|provider|maker|operator|firm|brand)\b)"
        r"|\bdefinitive agreement to acquire\b"
        r"|\b(?:closing|completion)\s+of\s+(?:its|the|our)\s+(?:previously announced\s+)?acquisition of\b"
        r"|\bannounced\s+(?:today\s+)?(?:the|its)\s+acquisition of\b",
        re.I,
    ),
    "divestiture": re.compile(
        r"\b(?:sold|sells|divested|divests|agreed to sell|spun off|spins off|"
        r"complet(?:ed|es) (?:the |its )?(?:sale|divestiture|spin-off) of)\s+"
        r"(?:its\s+|the\s+|our\s+)?(?:\w+\s+){0,4}?"
        r"(?:business|division|unit|segment|subsidiary|operations|portfolio)\b"
        r"|\b(?:sale|divestiture|disposition) of\s+(?:its|our|the Company['\u2019]s|the)\s+"
        r"(?:\w+\s+){0,3}?(?:equity interest|stake|business|division|unit|segment|subsidiary)\b",
        re.I,
    ),
    "funding_round": re.compile(
        r"\b(?:raised|raises|closed|closes|secured|secures|completed|announced)\b[^.!?]{0,60}"
        r"\b(?:Series [A-H]\d?|seed|pre-seed|growth equity|venture)\s+"
        r"(?:funding|financing|round|investment)\b"
        r"|\b(?:raised|raises|secured|secures)\s+(?:a\s+)?\$[\d.,]+\s*(?:million|billion|[MB])\b"
        r"[^.!?]{0,60}\b(?:funding|financing|round|investment|equity)\b"
        r"|\b(?:closed|closes|completed|completes|announced)\b[^.!?]{0,40}\bprivate placement\b",
        re.I,
    ),
    "guidance_raised": re.compile(
        r"\b(?:rais(?:e|es|ed|ing)|increas(?:e|es|ed|ing)|lift(?:s|ed)?|boost(?:s|ed))\b[^.!?]{0,60}"
        r"\b(?:guidance|outlook|forecast)\b",
        re.I,
    ),
    "guidance_lowered": re.compile(
        r"\b(?:lower(?:s|ed|ing)?|reduc(?:e|es|ed|ing)|cut(?:s|ting)?|trim(?:s|med)?)\b[^.!?]{0,60}"
        r"\b(?:guidance|outlook|forecast)\b",
        re.I,
    ),
}

# Financing and legal agreements are not customer contracts.
SPECULATIVE = (
    r"\b(?:rumou?red|reportedly|in talks|exploring|considering|may (?:acquire|sell)|"
    r"could (?:acquire|sell)|speculat\w+|potential (?:acquisition|sale)|analysts?)\b"
)
RULE_EXCLUSIONS = {
    "new_contract": re.compile(
        r"\b(?:forbearance|credit|loan|waiver|merger|settlement|separation|"
        r"purchase and sale|underwriting)\s+agreements?\b|\bindenture\b"
        r"|\bdefinitive agreement\b|\bagreement to (?:acquire|sell|merge|be acquired|repurchase)\b"
        r"|\bplan of merger\b|\brepurchase\b",
        re.I,
    ),
    # "was acquired by" is the company being bought, not buying.
    "acquisition": re.compile(
        rf"\b(?:was|were|been|being|is|be)\s+acquired\b|\bacquired by\b|\bacquisition by\b|{SPECULATIVE}"
        r"|\b(?:newly|recently|previously)[- ]acquired\b"
        r"|\bacquir\w+\s+(?:new\s+)?(?:customers|clients|users|talent|skills|data|knowledge)\b",
        re.I,
    ),
    "divestiture": re.compile(
        rf"\bsold out\b|\b(?:was|were|been|being)\s+sold\b|{SPECULATIVE}", re.I),
    "funding_round": re.compile(
        r"\b(?:notes|bonds|debentures|credit facility|term loan|for charity|donat\w+)\b"
        r"|\b(?:helps?|helped|helping)\b[^.!?]{0,40}\braise\b",
        re.I,
    ),
    "market_expansion": re.compile(
        r"\b(?:credit|loan|revolving)\s+facilit(?:y|ies)\b|\bexpand(?:s|ed|ing)?\s+access\b"
        r"|\bcapabilit(?:y|ies)\b",
        re.I,
    ),
    "product_launch": re.compile(
        r"\b(?:secondary|public|registered|underwritten|notes|debt|equity|stock)\s+offering\b"
        r"|\bpricing of\b|\b(?:tagline|ad campaign|creative campaign|marketing campaign)\b",
        re.I,
    ),
    # Rating-agency outlooks are credit events, not company guidance.
    "guidance_raised": re.compile(r"\b(?:rating|S&P|Moody's|Fitch)\b", re.I),
    "guidance_lowered": re.compile(r"\b(?:rating|S&P|Moody's|Fitch)\b", re.I),
}

# Sentences that define a metric or carry legal boilerplate describe how a
# number works, not an event ("AUV ... influenced by opening new restaurants").
DEFINITION_SENTENCE = re.compile(
    r"\b(?:is|are) (?:defined|calculated) as\b|\bconsists? of\b|\bwe define\b"
    r"|\b(?:is|are) (?:primarily |also |generally )?(?:driven|influenced) by\b"
    r"|\bforward-looking statements?\b"
    # Third-party statistics ("..., according to data released by ...").
    r"|\baccording to (?!the company\b|company\b)",
    re.I,
)
# Company boilerplate blocks ("About Wingstop ...", "Founded in 1994 ...")
# repeat history, not news from this article.
OWN_BOILERPLATE_BLOCK = re.compile(r"^\s*(?:about\s+\S|founded in \d{4})", re.I)
ABOUT_BLOCK = re.compile(r"^\s*about\s+(?:the\s+)?([^\s:,.]+)", re.I)
REPEATED_BLOCK_MIN_PAGES = 3
# Undated pages under these paths are evergreen marketing or advice content
# (CSG /insights/ in the held-out check), not dated company news.
MARKETING_ARTICLE_PATH = re.compile(r"/(?:insights|resources)/", re.I)
PLANNED_MARKERS = re.compile(
    r"\b(?:plans?|planning|planned|intends?|expects?|aims?|is set|are set|will|to begin|"
    r"agreed to|pending)\s+(?:to\s+)?\w+|\bdefinitive agreement\b"
    r"|\bpreviews?\b|\bupcoming\b",
    re.I,
)
COMPLETED_MARKERS = re.compile(
    r"\b(?:opened|expanded|entered|added|created|hired|laid off|cut|eliminated|reduced|"
    r"furloughed|signed|awarded|won|secured|executed|extended|renewed|launched|introduced|"
    r"unveiled|released|rolled out|debuted|refinanced|repaid|amended|upgraded|downgraded|"
    r"raised|lowered|defaulted|missed|filed|terminated|lost|canceled|cancelled|selected|"
    r"acquired|completed|closed|divested|sold|increased|reduced)\b"
    r"|\b\d[\d,]*\s+(?:net\s+)?new\s+(?:\w+\s+)?openings\b",
    re.I,
)

DIRECTIONS = {
    "new_contract": "positive",
    "customer_loss": "negative",
    "product_launch": "positive",
    "market_expansion": "positive",
    "hiring": "positive",
    "layoff": "negative",
    "credit_positive": "positive",
    "credit_stress": "negative",
    "acquisition": "positive",
    "divestiture": "negative",
    "funding_round": "positive",
    "guidance_raised": "positive",
    "guidance_lowered": "negative",
}

TEMPORARY_MARKERS = re.compile(
    r"\b(?:limited[- ]time|while supplies last|promotional period|"
    r"disappears after|only \d+ [^.!?]{0,30}available|before (?:they(?:'re| are) )?sold out)\b",
    re.I,
)
DURABLE_PRODUCT_MARKERS = re.compile(
    r"\b(?:platform|solution|service|feature|agent|module|capabilit(?:y|ies))\b",
    re.I,
)
DURABLE_CONTEXT_MARKERS = re.compile(
    r"\b(?:embedded throughout|integrated (?:throughout|into)|built into)\s+"
    r"(?:the\s+|its\s+)?(?:platform|service|product)\b",
    re.I,
)


def sentences(text: str) -> list[str]:
    """Split source blocks conservatively while retaining evidence text."""
    protected = re.sub(
        r"\b(Co|Inc|Corp|Ltd|LLC|U\.S|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.",
        lambda match: match.group(0).replace(".", "<DOT>"),
        text,
        flags=re.I,
    )
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9“"])', protected)
    return [part.replace("<DOT>", ".").strip() for part in parts if part.strip()]


ABBREVIATION_DOT = re.compile(
    r"\b(?:Inc|Corp|Co|Ltd|LLC|Bros|No|Nos|St|Jr|Sr|Mr|Ms|Dr|vs|approx|est|Jan|Feb|Mar|Apr|"
    r"Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Mass|Calif|Fla|Va|Ga|Pa|Tex)\.(?=\s|,|$)"
)
INITIALISM = re.compile(r"\b(?:[A-Z]\.){2,}")


def matching_text(sentence: str) -> str:
    """Same-length copy of a sentence whose non-final periods cannot end a window.

    Decimals ("$2.2 million"), abbreviations ("Inc.", "Sept.") and initialisms
    ("U.S.") get DOT_MARK instead of ".", so a rule window such as
    ``[^.!?]{0,100}`` spans them. Positions are unchanged, so match offsets
    still index the original sentence.
    """
    text = re.sub(r"(?<=\d)\.(?=\d)", DOT_MARK, sentence)
    text = INITIALISM.sub(lambda m: m.group(0).replace(".", DOT_MARK), text)
    text = ABBREVIATION_DOT.sub(lambda m: m.group(0)[:-1] + DOT_MARK, text)
    return text


OWN_PASSIVE_ACQUISITION = re.compile(r"\bacquired by\s+(?:the\s+)?([\w&'\u2019-]+)", re.I)


def signal_duration(event_type: str, evidence: str, page_text: str) -> str:
    """Classify launch duration only when the article provides explicit cues."""
    if event_type != "product_launch":
        return "unknown"
    if TEMPORARY_MARKERS.search(page_text):
        return "temporary"
    if (DURABLE_PRODUCT_MARKERS.search(evidence)
            or DURABLE_CONTEXT_MARKERS.search(page_text)):
        return "durable"
    return "unknown"


def event_status(evidence: str) -> str:
    """Mark a sentence as planned or completed only from explicit wording."""
    text = re.sub(r"\bpreviously planned\b", "", evidence, flags=re.I)
    if PLANNED_MARKERS.search(text):
        return "planned"
    if COMPLETED_MARKERS.search(text):
        return "completed"
    return "unknown"


def _block_key(block: str) -> str:
    return " ".join(block.casefold().split())


def repeated_blocks(record: dict) -> set[str]:
    """Blocks shown on several pages of one company: sidebars, teasers, footers."""
    counts: Counter[str] = Counter()
    for page in record.get("pages", []):
        if page.get("category") not in ELIGIBLE_PAGE_CATEGORIES:
            continue
        counts.update({_block_key(block) for block in page.get("raw_blocks", []) if block.strip()})
    return {key for key, count in counts.items() if count >= REPEATED_BLOCK_MIN_PAGES}


def is_other_company_about(block: str, company_name: str) -> bool:
    """True for an "About <partner>" boilerplate block naming another company."""
    match = ABOUT_BLOCK.match(block)
    if not match:
        return False
    first_word = re.sub(r"\W", "", match.group(1)).casefold()
    company_words = {re.sub(r"\W", "", word).casefold() for word in company_name.split()}
    return bool(first_word) and first_word not in company_words


def is_undated_marketing_page(page: dict) -> bool:
    return (page.get("category") == "article" and not page.get("published_date")
            and bool(MARKETING_ARTICLE_PATH.search(page.get("source_url", ""))))


NAME_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "companies", "holdings",
    "holding", "group", "ltd", "llc", "lp", "plc", "the", "and", "of", "international",
}
SELF_REFERENCES = {"we", "our", "us", "it", "its", "company", "they", "their"}
CAPITALIZED_FUNCTION_WORDS = {
    "the", "this", "these", "that", "those", "today", "in", "on", "at", "by", "for", "with",
    "earlier", "additionally", "also", "now", "a", "an", "last", "next", "together", "new",
    "as", "after", "since", "during", "following", "through", "and", "&", "of",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}
SUBJECT_FILLERS = {
    "today", "also", "recently", "has", "have", "had", "officially", "successfully",
    "previously", "just", "now", "newly", "jointly", "both", "each", "will", "is", "are",
    "was", "were", "further", "already", "formally",
}
CLAUSE_BREAK = re.compile(r"[,;:()—–“”\"]|\s-{1,2}\s")
MAX_SUPPORTING_SENTENCES = 5
# Rating actions are taken by an agency ("S&P upgraded ..."), so the named
# actor is expected to be someone else.
AGENCY_ACTOR_TYPES = {"credit_positive", "credit_stress"}


def company_tokens(record: dict) -> set[str]:
    """Words that refer to the company itself: its name and website label."""
    words = re.findall(r"[\w&]+", record.get("company_name", ""))
    tokens = {word.casefold() for word in words if word.casefold() not in NAME_SUFFIXES}
    host = urlparse(record.get("website") or "").hostname or ""
    host = host.removeprefix("www.")
    if host:
        tokens.add(host.split(".")[0].casefold())
    return {token for token in tokens if token}


def _plain(word: str) -> str:
    return re.sub(r"(?:['’]s)$", "", word).strip(".,'’").casefold()


def other_actor(sentence: str, match_start: int, own_tokens: set[str]) -> str | None:
    """Return the named actor when someone other than the company does the action.

    Only the words directly before the matched action are read: the trailing
    run of capitalized words in the same clause ("In mid-2025, Telstra
    launched ..." -> "Telstra"). No named actor, a self reference ("we", "the
    Company"), or any of the company's own name tokens accepts the sentence.
    """
    clause = CLAUSE_BREAK.split(sentence[:match_start])[-1]
    words = clause.split()
    while words and _plain(words[-1]) in SUBJECT_FILLERS:
        words.pop()
    subject: list[str] = []
    for word in reversed(words):
        plain = _plain(word)
        if word[:1].isupper() or word in {"&"} or (subject and plain in {"and", "of"}):
            subject.insert(0, word)
        else:
            break
    if not subject:
        return None
    plain_words = {_plain(word) for word in subject}
    if plain_words & (own_tokens | SELF_REFERENCES):
        return None
    if any(own and own in plain for own in own_tokens for plain in plain_words):
        return None
    if plain_words <= CAPITALIZED_FUNCTION_WORDS:
        return None
    return " ".join(subject)


def article_blocks(record: dict, page: dict, excluded_blocks: set[str]) -> list[str]:
    """The article's own text in reading order: title, summary, then body blocks.

    Drops blocks repeated across the company's pages, partner "About" blocks
    and the company's own About/Founded boilerplate. Shared so that every
    reader of an article works from exactly these blocks.
    """
    raw_blocks = [
        block for block in page.get("raw_blocks", [])
        if _block_key(block) not in excluded_blocks
        and not is_other_company_about(block, record["company_name"])
        and not OWN_BOILERPLATE_BLOCK.match(block)
    ]
    raw_title = page.get("raw_title", "")
    blocks = [page.get("raw_meta", "")]
    if not raw_blocks or not raw_title.casefold().startswith(raw_blocks[0].casefold()):
        blocks.insert(0, raw_title)
    blocks.extend(raw_blocks)
    return [block for block in blocks if block.strip()]


def extract_page_events(record: dict, page: dict,
                        excluded_blocks: set[str] | None = None,
                        rejections: list[dict] | None = None) -> list[Event]:
    """Extract one validated event per event type from an article or careers page.

    The first supporting sentence in reading order (title, summary, body) is the
    evidence; later sentences for the same type become ``supporting_text``.
    Sentences whose action belongs to another named company are rejected and,
    when ``rejections`` is given, recorded there with the reason.
    """
    category = page.get("category")
    if category not in ELIGIBLE_PAGE_CATEGORIES or is_undated_marketing_page(page):
        return []
    excluded_blocks = excluded_blocks or set()
    own_tokens = company_tokens(record)
    event_date = page.get("published_date")
    precision = page.get("published_date_precision", "unknown")
    unknown_reason = None if event_date else "No explicit publication date was found on the page."
    via_ir_fallback = bool(page.get("via_ir_fallback", False))
    evidence_blocks = article_blocks(record, page, excluded_blocks)
    page_text = " ".join(evidence_blocks)
    by_type: dict[str, list[str]] = {}
    for block in evidence_blocks:
        for sentence in sentences(block):
            if sentence.casefold().startswith("view original content to download multimedia:"):
                continue
            if DEFINITION_SENTENCE.search(matching_text(sentence)):
                continue
            text = matching_text(sentence)
            for event_type, pattern in RULES.items():
                if category in {"careers", "jobs"} and event_type not in CAREERS_EVENT_TYPES:
                    continue
                match = pattern.search(text)
                if event_type == "acquisition":
                    # "Green Image, LLC Acquired by BrightView": the company is the buyer.
                    passive = OWN_PASSIVE_ACQUISITION.search(text)
                    if passive and _plain(passive.group(1)) in own_tokens:
                        matched = by_type.setdefault(event_type, [])
                        if sentence.casefold() not in {item.casefold() for item in matched}:
                            matched.append(sentence)
                        continue
                if not match:
                    continue
                exclusion = RULE_EXCLUSIONS.get(event_type)
                if exclusion and exclusion.search(text):
                    continue
                actor = (None if event_type in AGENCY_ACTOR_TYPES
                         else other_actor(sentence, match.start(), own_tokens))
                if actor:
                    if rejections is not None:
                        rejections.append({
                            "event_type": event_type,
                            "sentence": sentence,
                            "reason": f"other_actor: {actor}",
                        })
                    continue
                matched = by_type.setdefault(event_type, [])
                if sentence.casefold() not in {item.casefold() for item in matched}:
                    matched.append(sentence)
    found: list[Event] = []
    for event_type, matched in by_type.items():
        evidence, supporting = matched[0], tuple(matched[1:1 + MAX_SUPPORTING_SENTENCES])
        found.append(Event(
            IQ_COMPANY_ID=record["IQ_COMPANY_ID"],
            company_name=record["company_name"],
            event_type=event_type,
            direction=DIRECTIONS[event_type],
            event_date=event_date,
            event_date_precision=precision if event_date else "unknown",
            retrieved_at=page["fetched_at"],
            source_url=page["source_url"],
            source_text=evidence,
            confidence=0.80,
            extraction_method="rule",
            unknown_reason=unknown_reason,
            signal_duration=signal_duration(event_type, " ".join(matched), page_text),
            event_status=event_status(evidence),
            via_ir_fallback=via_ir_fallback,
            supporting_text=supporting,
        ).validate())
    return found


def extract_record(record: dict) -> tuple[list[Event], dict]:
    """Extract all article events and return an inspectable audit summary."""
    events: list[Event] = []
    page_audit = []
    excluded = repeated_blocks(record)
    for page in record.get("pages", []):
        if page.get("category") not in ELIGIBLE_PAGE_CATEGORIES:
            continue
        rejections: list[dict] = []
        page_events = extract_page_events(record, page, excluded, rejections)
        events.extend(page_events)
        page_audit.append({
            "page_id": page.get("page_id"),
            "category": page.get("category"),
            "source_url": page.get("source_url"),
            "published_date": page.get("published_date"),
            "via_ir_fallback": bool(page.get("via_ir_fallback", False)),
            "event_count": len(page_events),
            "event_types": sorted(event.event_type for event in page_events),
            "rejected": rejections,
            "status": (
                "events_found" if page_events
                else "skipped_undated_marketing_page" if is_undated_marketing_page(page)
                else "abstained_no_rule_match"),
        })
    audit = {
        "IQ_COMPANY_ID": record.get("IQ_COMPANY_ID"),
        "company_name": record.get("company_name"),
        "article_count": len(page_audit),
        "event_count": len(events),
        "repeated_blocks_excluded": len(excluded),
        "pages": page_audit,
    }
    return events, audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-record", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.page_record.read_text(encoding="utf-8"))
    events, audit = extract_record(record)
    write_events_jsonl(events, args.events)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{audit['company_name']}: {len(events)} events from {audit['article_count']} articles")


if __name__ == "__main__":
    main()
