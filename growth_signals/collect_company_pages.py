"""Collect News, Press, Careers, and Jobs pages for company growth signals."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
WEBSITE_SCRAPE_DIR = REPO_ROOT / "website_scrape"
if str(WEBSITE_SCRAPE_DIR) not in sys.path:
    sys.path.insert(0, str(WEBSITE_SCRAPE_DIR))

from fetch_and_clean import find_input, load_companies  # noqa: E402

from collect_events import (
    discover_article_links,
    discover_event_pages,
    date_from_text,
    is_article_url,
    publication_date_from_html,
)
from fetch_adapter import (
    FetchFailed,
    build_clients,
    close_clients,
    fetch_page,
    raw_text_fields,
    save_raw_page,
)

DEFAULT_OUT = REPO_ROOT / "outputs-local" / "growth_signals"
CATEGORY_PRIORITY = {"press": 0, "news": 1, "careers": 2, "jobs": 3}


def canonical_url(url: str) -> str:
    """Normalize a final URL so redirects to the same page are saved once."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def output_paths(output_root: Path) -> dict[str, Path]:
    return {
        "raw_html": output_root / "raw_html",
        "page_records": output_root / "page_records",
        "page_records_history": output_root / "page_records_history",
    }


def choose_event_pages(discovered: list[dict], max_event_pages: int) -> list[dict]:
    """Choose a deterministic mix, preferring one page per category."""
    ordered = sorted(
        discovered,
        key=lambda item: (CATEGORY_PRIORITY.get(item["category"], 99), item["url"]),
    )
    chosen, covered = [], set()
    for item in ordered:
        if item["category"] not in covered:
            chosen.append(item)
            covered.add(item["category"])
            if len(chosen) == max_event_pages:
                return chosen
    for item in ordered:
        if item not in chosen:
            chosen.append(item)
            if len(chosen) == max_event_pages:
                break
    return chosen


def page_record(page, metadata: dict, page_id: str, category: str,
                extra: dict | None = None) -> dict:
    record = {
        "page_id": page_id,
        "category": category,
        **metadata,
        **raw_text_fields(page.html),
    }
    if extra:
        record.update(extra)
    return record


def collect_company(company: dict, clients: list, output_root: Path,
                    max_event_pages: int = 4, max_articles: int = 5) -> dict:
    """Collect a homepage plus selected growth-signal pages for one company."""
    company_id = company["IQ_COMPANY_ID"]
    name = company["target_company_name"]
    website = company["target_ciq_website"]
    collected_at = now_iso()
    record = {
        "schema_version": 1,
        "IQ_COMPANY_ID": company_id,
        "company_name": name,
        "website": website,
        "collected_at": collected_at,
        "status": "error",
        "discovered_event_pages": [],
        "discovered_articles": [],
        "pages": [],
        "errors": [],
    }

    try:
        home = fetch_page(website, clients)
    except FetchFailed as exc:
        record["status"] = "homepage_failed"
        record["errors"].append({"url": website, "attempts": exc.attempts})
        return record

    home_metadata = save_raw_page(home, output_root, company_id, "P1")
    record["pages"].append(page_record(home, home_metadata, "P1", "home"))
    seen_final_urls = {canonical_url(home.final_url)}
    discovered = discover_event_pages(home.html, home.final_url)
    record["discovered_event_pages"] = discovered
    selected = choose_event_pages(discovered, max_event_pages)
    article_candidates: dict[str, dict] = {}

    for selected_page in selected:
        page_id = f"P{len(record['pages']) + 1}"
        try:
            page = fetch_page(selected_page["url"], clients)
        except FetchFailed as exc:
            record["errors"].append({
                "url": selected_page["url"],
                "category": selected_page["category"],
                "attempts": exc.attempts,
            })
            continue
        final_key = canonical_url(page.final_url)
        if final_key in seen_final_urls:
            continue
        seen_final_urls.add(final_key)
        metadata = save_raw_page(page, output_root, company_id, page_id)
        direct_article = (
            selected_page["category"] in {"news", "press"}
            and is_article_url(page.final_url)
        )
        if direct_article:
            published_date, precision = publication_date_from_html(page.html)
            if not published_date:
                raw = raw_text_fields(page.html)
                published_date, precision = date_from_text(
                    " ".join(raw["raw_blocks"][:5]))
            record["pages"].append(page_record(page, metadata, page_id, "article", {
                "article_source_category": selected_page["category"],
                "published_date": published_date,
                "published_date_precision": precision,
                "discovered_from": home.final_url,
            }))
        else:
            record["pages"].append(page_record(
                page, metadata, page_id, selected_page["category"]))
        if selected_page["category"] in {"news", "press"} and not direct_article:
            for article in discover_article_links(
                    page.html, page.final_url, selected_page["category"]):
                article_candidates.setdefault(article["url"], article)

    articles = sorted(
        article_candidates.values(),
        key=lambda item: (item["published_date"] is not None,
                          item["published_date"] or "", item["url"]),
        reverse=True,
    )[:max_articles]
    record["discovered_articles"] = articles
    for article in articles:
        page_id = f"P{len(record['pages']) + 1}"
        try:
            page = fetch_page(article["url"], clients)
        except FetchFailed as exc:
            record["errors"].append({
                "url": article["url"],
                "category": "article",
                "attempts": exc.attempts,
            })
            continue
        final_key = canonical_url(page.final_url)
        if final_key in seen_final_urls:
            continue
        seen_final_urls.add(final_key)
        metadata = save_raw_page(page, output_root, company_id, page_id)
        record["pages"].append(page_record(page, metadata, page_id, "article", {
            "article_source_category": article["source_category"],
            "published_date": article["published_date"],
            "published_date_precision": article["published_date_precision"],
            "discovered_from": article["discovered_from"],
        }))

    event_page_count = sum(page["category"] != "home" for page in record["pages"])
    record["article_count"] = sum(
        page["category"] == "article" for page in record["pages"])
    if event_page_count:
        record["status"] = "ok" if not record["errors"] else "partial"
    else:
        record["status"] = "no_event_pages" if not record["errors"] else "event_pages_failed"
    record["event_page_count"] = event_page_count
    return record


def write_company_record(record: dict, output_root: Path) -> Path:
    paths = output_paths(output_root)
    paths["page_records"].mkdir(parents=True, exist_ok=True)
    destination = paths["page_records"] / f"{record['IQ_COMPANY_ID']}.json"
    if destination.exists():
        paths["page_records_history"].mkdir(parents=True, exist_ok=True)
        old = json.loads(destination.read_text(encoding="utf-8"))
        stamp = old.get("collected_at", "unknown").replace(":", "").replace("-", "")
        archived = paths["page_records_history"] / f"{destination.stem}_{stamp}.json"
        suffix = 1
        while archived.exists():
            archived = paths["page_records_history"] / f"{destination.stem}_{stamp}_{suffix}.json"
            suffix += 1
        destination.replace(archived)
    destination.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="company list CSV; defaults to required snapshot")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--tickers", nargs="*", help="only these tickers")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-event-pages", type=int, default=4)
    parser.add_argument("--max-articles", type=int, default=5)
    parser.add_argument(
        "--methods",
        nargs="*",
        default=["html", "rendered", "stealth", "wayback"],
        choices=["html", "rendered", "stealth", "wayback"],
    )
    parser.add_argument("--stealth-headful", action="store_true")
    parser.add_argument("--chrome-version", type=int)
    args = parser.parse_args()

    companies = load_companies(find_input(args.input))
    if args.tickers:
        wanted = {ticker.upper() for ticker in args.tickers}
        companies = companies[companies["target_ciq_ticker"].str.upper().isin(wanted)]
    if args.limit:
        companies = companies.head(args.limit)
    if companies.empty:
        raise SystemExit("No companies match the requested filters.")

    clients = build_clients(
        args.methods,
        stealth_headless=not args.stealth_headful,
        chrome_version=args.chrome_version,
    )
    try:
        total = len(companies)
        for index, company in enumerate(companies.to_dict("records"), start=1):
            label = f"[{index}/{total}] {company['target_ciq_ticker']:<6} {company['target_company_name']}"
            record = collect_company(
                company, clients, args.out, args.max_event_pages, args.max_articles)
            path = write_company_record(record, args.out)
            print(f"{label}  {record['status']} ({record.get('event_page_count', 0)} event pages) -> {path}")
    finally:
        close_clients(clients)


if __name__ == "__main__":
    main()
