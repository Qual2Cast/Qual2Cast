"""Versioned, source-preserving private-target text transformation.

Removes detected public-market sentences and disallowed pages. It does not
assert that regex filtering proves all remaining prose admissible or factual.
"""

import re, hashlib
from urllib.parse import urlsplit

POLICY_VERSION = "private-evidence-2026-10-19-v4"
ERROR_TITLE = re.compile(
    r"^(?:404\b|page not found\b|request unavailable\b|access denied\b)", re.I
)
PUBLIC_MARKERS = re.compile(
    r"\b(?:went public|public company governance|public stock|(?:going|go|goes) private|take[ -]private|share repurchase|publicly[ -](?:traded|listed|held)|stock (?:price|exchange|quote|market)|share price|shareholders?|stockholders?|nasdaq|nyse|ticker|investor relations|earnings (?:call|release)|annual report|quarterly results|market capitali[sz]ation|initial public offering|form 10-[kq]|sec filings?|s&p\s*500|reports? (?:first|second|third|fourth) quarter)\b",
    re.I,
)
DISALLOWED_PATH = re.compile(
    r"(?:^|[/.-])(?:ir|investors?|investor-relations|privacy|cookie|terms|legal)(?:[/.-]|$)",
    re.I,
)


def allowed_page(url, category=""):
    u = urlsplit(url if "://" in url else "https://" + url)
    return (
        u.scheme in ("http", "https")
        and category
        not in ("investor", "investor_site", "investor_relations", "privacy", "legal")
        and not DISALLOWED_PATH.search(u.netloc + u.path)
    )


def clean_text(text):
    retained = []
    removed = []
    for line in str(text).splitlines():
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", line.strip()):
            if not sentence:
                continue
            hit = PUBLIC_MARKERS.search(sentence)
            if hit:
                removed.append(
                    {
                        "text": sentence,
                        "reason": "public_market_marker",
                        "marker": hit.group(),
                    }
                )
            else:
                retained.append(sentence)
    return "\n".join(retained), removed


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_document(company_id, page):
    url = page.get("url", "")
    raw = "\n".join(
        [page.get("title", ""), page.get("meta", "")] + page.get("blocks", [])
    )
    error_page = bool(ERROR_TITLE.search(page.get("title", "").strip()))
    keep = (
        allowed_page(url, page.get("category", ""))
        and not page.get("block_page", False)
        and not error_page
    )
    text, removed = (
        clean_text(raw)
        if keep
        else (
            "",
            [
                {
                    "reason": "error_page_title"
                    if error_page
                    else "disallowed_or_blocked_page",
                    "text_sha256": digest(raw),
                }
            ],
        )
    )
    return {
        "company_id": company_id,
        "source_id": company_id + ":" + page["page_id"],
        "source_url": url,
        "category": page.get("category"),
        "fetched_at": page.get("fetched_at"),
        "text": text,
        "raw_cleaned_text_sha256": digest(raw),
        "text_sha256": digest(text),
        "eligible": bool(text),
        "removed": removed,
        "policy_version": POLICY_VERSION,
    }
