"""Adapter from growth signals to the existing website fetch methods.

The adapter deliberately does not call ``website_scrape.crawl`` because that
crawler excludes News and Careers links and applies company-description
filters. It reuses only the download clients, robots.txt behavior, bot-page
detection, and source metadata.
"""

from __future__ import annotations

import gzip
import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
WEBSITE_SCRAPE_DIR = REPO_ROOT / "website_scrape"
if str(WEBSITE_SCRAPE_DIR) not in sys.path:
    sys.path.insert(0, str(WEBSITE_SCRAPE_DIR))

from fetch_and_clean import (  # noqa: E402
    Fetcher,
    Renderer,
    USER_AGENT,
    extract_page,
    normalize_url,
)
from scrape_websites import (  # noqa: E402
    BlockedError,
    StealthBrowser,
    WaybackFetcher,
    is_block_page,
)


CHALLENGE_MARKERS = (
    'document.cookie = "cf_bypass=1',
    "cf-chl-",
    "__cf_chl_",
    "challenge-platform",
    "checking your browser",
    "verify you are human",
)


class FetchFailed(RuntimeError):
    """No configured client returned a usable page."""

    def __init__(self, url: str, attempts: list[dict]):
        self.url = url
        self.attempts = attempts
        summary = " | ".join(f"{a['method']}:{a['status']}" for a in attempts)
        super().__init__(f"could not fetch {url}: {summary}")


@dataclass(frozen=True)
class FetchedPage:
    requested_url: str
    final_url: str
    source_url: str
    snapshot: str
    fetched_at: str
    method: str
    html: str
    attempts: tuple[dict, ...]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_clients(
    methods: Iterable[str] = ("html", "rendered", "stealth", "wayback"),
    *,
    user_agent: str = USER_AGENT,
    stealth_headless: bool = True,
    chrome_version: int | None = None,
) -> list:
    """Create clients in fallback order using the website-scrape classes."""
    fetcher = Fetcher(user_agent)
    clients = []
    for method in methods:
        if method == "html":
            clients.append(fetcher)
        elif method == "rendered":
            if Renderer.available():
                clients.append(Renderer(user_agent, robots_from=fetcher))
        elif method == "stealth":
            if StealthBrowser.available():
                clients.append(StealthBrowser(
                    fetcher,
                    headless=stealth_headless,
                    chrome_version=chrome_version,
                ))
        elif method == "wayback":
            clients.append(WaybackFetcher(fetcher))
        else:
            raise ValueError(f"unknown fetch method: {method}")
    if not clients:
        raise ValueError("no requested fetch methods are available")
    return clients


def fetch_page(url: str, clients: Iterable) -> FetchedPage:
    """Fetch one event page, trying each client and rejecting bot pages."""
    fetch_url = normalize_url(url)
    attempts = []
    for client in clients:
        method = getattr(client, "method", type(client).__name__)
        try:
            if not client.allowed(fetch_url):
                attempts.append({"method": method, "status": "robots_disallowed"})
                break
            final_url, html = client.get_html(fetch_url)
            lowered_html = html.lower()
            if any(marker in lowered_html for marker in CHALLENGE_MARKERS):
                raise BlockedError("Cloudflare or browser verification page")
            if is_block_page(extract_page(html)):
                raise BlockedError("bot check or error page")
            source_url, snapshot = (
                client.source_for(final_url)
                if hasattr(client, "source_for")
                else (final_url, "")
            )
            attempts.append({"method": method, "status": "ok"})
            return FetchedPage(
                requested_url=url,
                final_url=final_url,
                source_url=source_url,
                snapshot=snapshot,
                fetched_at=now_iso(),
                method=method,
                html=html,
                attempts=tuple(attempts),
            )
        except Exception as exc:
            attempts.append({
                "method": method,
                "status": f"error:{type(exc).__name__}",
                "message": str(exc).splitlines()[0][:200],
            })
    raise FetchFailed(url, attempts)


def raw_page_path(output_root: Path, company_id: str, fetched_at: str,
                  method: str, page_id: str) -> Path:
    timestamp = fetched_at.replace(":", "").replace("-", "")
    return output_root / "raw_html" / company_id / timestamp / method / f"{page_id}.html.gz"


def save_raw_page(page: FetchedPage, output_root: Path, company_id: str,
                  page_id: str) -> dict:
    """Save original HTML under growth-signals outputs and return provenance."""
    path = raw_page_path(output_root, company_id, page.fetched_at, page.method, page_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = page.html.encode("utf-8")
    with gzip.open(path, "wb") as stream:
        stream.write(data)
    try:
        stored_path = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        stored_path = str(path.resolve())
    return {
        "requested_url": page.requested_url,
        "final_url": page.final_url,
        "source_url": page.source_url,
        "snapshot": page.snapshot,
        "fetched_at": page.fetched_at,
        "method": page.method,
        "raw_html_file": stored_path,
        "raw_html_sha256": hashlib.sha256(data).hexdigest(),
        "attempts": list(page.attempts),
    }


def raw_text_fields(html: str) -> dict:
    """Return unfiltered text required by growth-signal extraction."""
    parsed = extract_page(html)
    return {
        "raw_title": parsed["raw_title"],
        "raw_meta": parsed["raw_meta"],
        "raw_blocks": parsed["raw_blocks"],
    }


def close_clients(clients: Iterable) -> None:
    for client in clients:
        close = getattr(client, "close", None)
        if close:
            close()
