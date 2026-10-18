"""Discover candidate News, Press, Careers, and Jobs pages.

This first milestone operates on saved HTML. Network fetching will be added by
reusing the existing fetching layer without changing `website_scrape/`.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

PAGE_PATTERNS = {
    "news": re.compile(r"(?:^|[\W_])(?:news|updates?)(?:$|[\W_])", re.I),
    "press": re.compile(r"(?:^|[\W_])(?:press|media|releases?)(?:$|[\W_])", re.I),
    "careers": re.compile(r"(?:^|[\W_])(?:careers?|join[-_ ]?us)(?:$|[\W_])", re.I),
    "jobs": re.compile(r"(?:^|[\W_])(?:jobs?|open[-_ ]?positions?|vacancies)(?:$|[\W_])", re.I),
}
EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}
ARTICLE_PATH = re.compile(
    r"/(?:news|newsroom|press(?:-releases?)?|media|updates?|blogs?|articles?)/[^/?#]+/?$",
    re.I,
)
MONTH_DATE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(\d{4})\b",
    re.I,
)


def canonical_url(url: str) -> str:
    """Drop fragments and normalize a URL for deterministic deduplication."""
    parsed = urlparse(url)
    normalized_path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if normalized_path != "/":
        normalized_path = normalized_path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), normalized_path,
                       parsed.params, parsed.query, ""))


def same_registered_host(candidate: str, base_url: str) -> bool:
    """Conservative same-host check; subdomains of the base host are allowed."""
    candidate_host = (urlparse(candidate).hostname or "").lower().removeprefix("www.")
    base_host = (urlparse(base_url).hostname or "").lower().removeprefix("www.")
    return bool(candidate_host and base_host and
                (candidate_host == base_host or candidate_host.endswith("." + base_host)))


def classify_event_page(url: str, anchor_text: str = "") -> str | None:
    parsed = urlparse(url)
    haystack = f"{parsed.netloc} {parsed.path} {anchor_text}".replace("/", " ").replace("-", " ")
    for category in ("careers", "jobs", "press", "news"):
        if PAGE_PATTERNS[category].search(haystack):
            return category
    return None


def discover_event_pages(html: str, base_url: str) -> list[dict[str, str]]:
    """Return unique same-site candidate pages with their discovery evidence."""
    soup = BeautifulSoup(html, "html.parser")
    discovered: dict[str, dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href:
            continue
        if urlparse(href).scheme.lower() in EXCLUDED_SCHEMES:
            continue
        absolute = canonical_url(urljoin(base_url, href))
        if not same_registered_host(absolute, base_url):
            continue
        anchor_text = " ".join(anchor.stripped_strings)
        category = classify_event_page(absolute, anchor_text)
        if category is None:
            continue
        discovered.setdefault(absolute, {
            "url": absolute,
            "category": category,
            "anchor_text": anchor_text,
        })
    return sorted(discovered.values(), key=lambda item: (item["category"], item["url"]))


def date_from_text(text: str) -> tuple[str | None, str]:
    """Return an ISO publication date found in link text, without guessing."""
    match = MONTH_DATE.search(text)
    if not match:
        return None, "unknown"
    parsed = datetime.strptime(match.group(0), "%B %d, %Y").date()
    return parsed.isoformat(), "day"


def discover_article_links(html: str, base_url: str,
                           source_category: str) -> list[dict[str, str | None]]:
    """Discover dated, same-site article links from a News or Press landing page."""
    soup = BeautifulSoup(html, "html.parser")
    discovered: dict[str, dict[str, str | None]] = {}
    base_key = canonical_url(base_url)
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href or urlparse(href).scheme.lower() in EXCLUDED_SCHEMES:
            continue
        absolute = canonical_url(urljoin(base_url, href))
        if (absolute == base_key or not same_registered_host(absolute, base_url)
                or not ARTICLE_PATH.search(urlparse(absolute).path)):
            continue
        anchor_text = " ".join(anchor.stripped_strings)
        published_date, precision = date_from_text(anchor_text)
        discovered.setdefault(absolute, {
            "url": absolute,
            "source_category": source_category,
            "anchor_text": anchor_text,
            "published_date": published_date,
            "published_date_precision": precision,
            "discovered_from": base_url,
        })
    return sorted(
        discovered.values(),
        key=lambda item: (item["published_date"] is None,
                          item["published_date"] or "", item["url"]),
        reverse=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True, help="Saved homepage HTML")
    parser.add_argument("--base-url", required=True, help="Homepage URL used to resolve links")
    parser.add_argument("--output", type=Path, required=True, help="JSON output path")
    args = parser.parse_args()

    pages = discover_event_pages(args.html.read_text(encoding="utf-8"), args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pages, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
