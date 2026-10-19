"""Discover candidate News, Press, Careers, and Jobs pages.

This first milestone operates on saved HTML. Network fetching will be added by
reusing the existing fetching layer without changing `website_scrape/`.
"""

from __future__ import annotations

import argparse
import html as html_lib
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
    r"/(?:news|newsroom|press(?:-releases?)?|media|media-center|press-center|"
    r"updates?|blogs?|articles?|stories)/.+"
    r"|/news-releases/news-release-details/[^/?#]+/?$"
    r"|/news/news-details/\d{4}/.+/default\.aspx$",
    re.I,
)
NEXT_LINK_TEXT = re.compile(r"^(?:next|older|more news|next page|»|>)$", re.I)
MONTH_DATE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:\.)?"
    r"\s+(\d{1,2}),\s+(\d{4})\b",
    re.I,
)
MONTH_NUMBERS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


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
    if re.search(r"(?:^|/)lien-release(?:\.|/|$)", parsed.path, re.I):
        return None
    if re.search(
        r"(?:^|/)(?:media-assets?|media-library|events-and-presentations)(?:/|$)",
        parsed.path,
        re.I,
    ):
        return None
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
        visible_text = " ".join(anchor.stripped_strings)
        aria_label = anchor.get("aria-label", "")
        anchor_text = " ".join(part for part in (visible_text, aria_label) if part)
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
    parsed = datetime(
        int(match.group(3)), MONTH_NUMBERS[match.group(1).lower()[:3]], int(match.group(2))
    ).date()
    return parsed.isoformat(), "day"


def publication_date_from_html(html: str) -> tuple[str | None, str]:
    """Read an explicit article date from standard metadata or time markup."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for key, value in (
        ("property", "article:published_time"),
        ("name", "date"),
        ("name", "publish-date"),
        ("itemprop", "datePublished"),
    ):
        tag = soup.find("meta", attrs={key: re.compile(f"^{re.escape(value)}$", re.I)})
        if tag and tag.get("content"):
            candidates.append(tag["content"])
    for tag in soup.find_all("time"):
        candidates.append(tag.get("datetime") or " ".join(tag.stripped_strings))
    for value in candidates:
        value = value.strip()
        iso = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
        if iso:
            return iso.group(1), "day"
        parsed, precision = date_from_text(value)
        if parsed:
            return parsed, precision
    visible_text = " ".join(soup.stripped_strings)
    parsed, precision = date_from_text(visible_text[:2500])
    if parsed:
        return parsed, precision
    return None, "unknown"


def discover_listing_next_url(html: str, base_url: str) -> str | None:
    """Return one same-site listing continuation URL, without guessing pagination."""
    soup = BeautifulSoup(html, "html.parser")
    base_key = canonical_url(base_url)

    def _usable(href: str | None) -> str | None:
        if not href or urlparse(href).scheme.lower() in EXCLUDED_SCHEMES:
            return None
        absolute = canonical_url(urljoin(base_url, href))
        if absolute == base_key or not same_registered_host(absolute, base_url):
            return None
        return absolute

    for tag in soup.find_all("link", href=True):
        rel = tag.get("rel", [])
        if isinstance(rel, str):
            rel = rel.split()
        if "next" in {item.lower() for item in rel}:
            usable = _usable(tag.get("href"))
            if usable:
                return usable
    for anchor in soup.find_all("a", href=True):
        rel = anchor.get("rel", [])
        if isinstance(rel, str):
            rel = rel.split()
        text = " ".join(anchor.stripped_strings).strip()
        if "next" not in {item.lower() for item in rel} and not NEXT_LINK_TEXT.match(text):
            continue
        usable = _usable(anchor.get("href"))
        if usable:
            return usable
    return None


def is_article_url(url: str) -> bool:
    """Return whether a URL has the shape of a specific article, not a listing."""
    path = urlparse(url).path.rstrip("/")
    if re.search(r"/news/news-details/\d{4}/.+/default\.aspx$", path, re.I):
        return True
    basename = path.rsplit("/", 1)[-1].lower()
    if basename in {"default.aspx", "index.html", "index.htm", "news", "press", "blog", "blogs"}:
        return False
    if re.search(r"/news-releases/news-release-details/[^/]+$", path, re.I):
        return True
    return bool(ARTICLE_PATH.search(path))


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
                or not is_article_url(absolute)):
            continue
        visible_text = " ".join(anchor.stripped_strings)
        aria_label = anchor.get("aria-label", "")
        anchor_text = " ".join(part for part in (visible_text, aria_label) if part)
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


def wordpress_posts_api_url(html: str, base_url: str, limit: int) -> str | None:
    """Return a bounded latest-posts endpoint only when the page declares WP API."""
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("link", href=True):
        rel = link.get("rel", [])
        if isinstance(rel, str):
            rel = rel.split()
        if "https://api.w.org/" not in rel:
            continue
        api_root = urljoin(base_url, link["href"])
        if not same_registered_host(api_root, base_url):
            continue
        return urljoin(api_root.rstrip("/") + "/", "wp/v2/posts") + (
            f"?per_page={max(1, min(limit, 20))}&orderby=date&order=desc"
            "&_fields=date,link,title"
        )
    return None


def articles_from_wordpress_api(payload: str, api_url: str,
                                source_category: str) -> list[dict[str, str | None]]:
    """Parse first-party WordPress latest-post metadata into article candidates."""
    try:
        rows = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(rows, list):
        return []
    articles: dict[str, dict[str, str | None]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        link = row.get("link")
        date = row.get("date")
        title = row.get("title", {})
        if not isinstance(link, str) or not same_registered_host(link, api_url):
            continue
        iso = re.match(r"^(\d{4}-\d{2}-\d{2})", date or "")
        if not iso:
            continue
        rendered = title.get("rendered", "") if isinstance(title, dict) else ""
        anchor_text = BeautifulSoup(html_lib.unescape(rendered), "html.parser").get_text(
            " ", strip=True)
        canonical = canonical_url(link)
        articles.setdefault(canonical, {
            "url": canonical,
            "source_category": source_category,
            "anchor_text": anchor_text,
            "published_date": iso.group(1),
            "published_date_precision": "day",
            "discovered_from": api_url,
        })
    return sorted(
        articles.values(),
        key=lambda item: (item["published_date"] or "", item["url"]),
        reverse=True,
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
