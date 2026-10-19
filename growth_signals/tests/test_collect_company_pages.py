import json

from fetch_adapter import FetchFailed, FetchedPage
from collect_company_pages import (
    collect_company,
    choose_event_pages,
    official_ir_url,
    write_company_record,
)


def fetched(url, html, method="html", final_url=None):
    return FetchedPage(
        requested_url=url,
        final_url=final_url or url,
        source_url=url,
        snapshot="",
        fetched_at="2026-10-18T19:00:00Z",
        method=method,
        html=html,
        attempts=({"method": method, "status": "ok"},),
    )


def test_choose_event_pages_prefers_category_coverage():
    pages = [
        {"url": "https://example.com/news/a", "category": "news", "anchor_text": "A"},
        {"url": "https://example.com/news/b", "category": "news", "anchor_text": "B"},
        {"url": "https://example.com/careers", "category": "careers", "anchor_text": "Careers"},
    ]
    chosen = choose_event_pages(pages, 2)
    assert {page["category"] for page in chosen} == {"news", "careers"}


def test_official_ir_url_uses_same_company_domain():
    assert official_ir_url("https://www.example.com/") == "https://ir.example.com/"


def test_collect_company_saves_home_and_event_pages(tmp_path, monkeypatch):
    homepage = """
    <html><head><title>Example</title></head><body>
    <a href="/news">News</a><a href="/careers">Careers</a>
    </body></html>
    """
    event_html = "<html><head><title>News</title></head><body><p>New contract announced for hospital software.</p></body></html>"

    def fake_fetch(url, clients, **kwargs):
        if url == "https://example.com":
            return fetched(url, homepage)
        return fetched(url, event_html)

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
    monkeypatch.setattr("collect_company_pages.fetch_text_payload", fake_fetch)
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path, max_event_pages=2)
    assert record["status"] == "ok"
    assert record["event_page_count"] == 2
    assert [page["category"] for page in record["pages"]] == ["home", "news", "careers"]
    assert all(page["raw_html_sha256"] for page in record["pages"])


def test_collect_company_fetches_dated_articles(tmp_path, monkeypatch):
    homepage = '<html><body><a href="/news">News</a></body></html>'
    landing = '''<html><body><a href="/news/new-contract">
    New contract announced September 22, 2026</a></body></html>'''
    article = "<html><body><p>The company signed a new hospital contract.</p></body></html>"

    def fake_fetch(url, clients, **kwargs):
        if url == "https://example.com":
            return fetched(url, homepage)
        if url == "https://example.com/news":
            return fetched(url, landing)
        return fetched(url, article)

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
    monkeypatch.setattr("collect_company_pages.fetch_text_payload", fake_fetch)
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path, max_event_pages=1, max_articles=2)
    assert record["article_count"] == 1
    saved = record["pages"][-1]
    assert saved["category"] == "article"
    assert saved["published_date"] == "2026-09-22"


def test_article_body_date_overrides_future_date_in_link_text(tmp_path, monkeypatch):
    homepage = '<html><body><a href="/news">News</a></body></html>'
    landing = '''<html><body><a href="/news/results-call">
    Results call November 5, 2026</a></body></html>'''
    article = "<html><body><p>DALLAS, Oct. 12, 2026 (NEWSWIRE) — The call was announced.</p></body></html>"

    def fake_fetch(url, clients, **kwargs):
        if url == "https://example.com":
            return fetched(url, homepage)
        if url == "https://example.com/news":
            return fetched(url, landing)
        return fetched(url, article)

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path, max_event_pages=1, max_articles=1)
    assert record["pages"][-1]["published_date"] == "2026-10-12"


def test_collect_company_uses_declared_wordpress_api_for_latest_articles(
        tmp_path, monkeypatch):
    homepage = '<html><body><a href="/news">News</a></body></html>'
    landing = '''<html><head>
      <link rel="https://api.w.org/" href="https://example.com/wp-json/">
      </head><body></body></html>'''
    api_payload = '''[{"date":"2026-10-13T05:30:52",
      "link":"https://example.com/latest-release/",
      "title":{"rendered":"Latest release"}}]'''
    article = '''<html><head>
      <meta property="article:published_time" content="2026-10-13T05:30:52Z">
      </head><body><p>The company launched a new service.</p></body></html>'''

    def fake_fetch(url, clients, **kwargs):
        if url == "https://example.com":
            return fetched(url, homepage)
        if url == "https://example.com/news":
            return fetched(url, landing)
        if "/wp-json/wp/v2/posts" in url:
            return fetched(url, api_payload)
        return fetched(url, article)

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
    monkeypatch.setattr("collect_company_pages.fetch_text_payload", fake_fetch)
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path, max_event_pages=1, max_articles=1)
    assert record["status"] == "ok"
    assert record["event_page_count"] == 2
    assert record["article_count"] == 1
    assert [page["category"] for page in record["pages"]] == [
        "home", "news", "archive_api", "article"]
    assert record["pages"][-1]["published_date"] == "2026-10-13"


def test_direct_press_release_is_saved_as_article(tmp_path, monkeypatch):
    homepage = '<html><body><a href="/press-releases/new-product">Press release</a></body></html>'
    article = '''<html><head>
    <meta property="article:published_time" content="2026-08-14T09:30:00Z">
    </head><body><p>The company launched a new platform.</p></body></html>'''

    def fake_fetch(url, clients, **kwargs):
        if url == "https://example.com":
            return fetched(url, homepage)
        return fetched(url, article)

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path, max_event_pages=1, max_articles=0)
    assert record["article_count"] == 1
    assert record["pages"][1]["category"] == "article"
    assert record["pages"][1]["published_date"] == "2026-08-14"


def test_homepage_failure_is_recorded(tmp_path, monkeypatch):
    failure = FetchFailed("https://example.com", [{"method": "html", "status": "http_403"}])
    monkeypatch.setattr("collect_company_pages.fetch_page", lambda url, clients: (_ for _ in ()).throw(failure))
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path)
    assert record["status"] == "homepage_failed"
    assert record["pages"] == []
    assert record["errors"][0]["attempts"][0]["status"] == "http_403"


def test_redirected_event_pages_are_deduplicated(tmp_path, monkeypatch):
    homepage = '''<html><body>
    <a href="/news">News</a><a href="/content/news">More news</a>
    </body></html>'''
    event_html = "<html><body><p>New customer contract announced.</p></body></html>"

    def fake_fetch(url, clients, **kwargs):
        if url == "https://example.com":
            return fetched(url, homepage)
        return fetched(
            url,
            event_html,
            final_url="https://example.com/company/news/",
        )

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path, max_event_pages=2)
    assert record["status"] == "ok"
    assert record["event_page_count"] == 1
    assert [page["category"] for page in record["pages"]] == ["home", "news"]


def test_collect_company_follows_one_listing_next_page(tmp_path, monkeypatch):
    homepage = '<html><body><a href="/news">News</a></body></html>'
    landing = '''<html><body>
    <a href="/news/older-item">Older item September 1, 2026</a>
    <link rel="next" href="/news/page/2">
    </body></html>'''
    page_two = '''<html><body>
    <a href="/news/newer-item">Newer item October 1, 2026</a>
    </body></html>'''
    article = "<html><body><p>The company signed a new hospital contract.</p></body></html>"

    def fake_fetch(url, clients, **kwargs):
        if url == "https://example.com":
            return fetched(url, homepage)
        if url == "https://example.com/news":
            return fetched(url, landing)
        if url == "https://example.com/news/page/2":
            return fetched(url, page_two)
        return fetched(url, article)

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path, max_event_pages=1, max_articles=2)
    assert {item["url"] for item in record["discovered_articles"]} == {
        "https://example.com/news/older-item",
        "https://example.com/news/newer-item",
    }
    assert record["article_count"] == 2


def test_collect_company_follows_listing_pages_up_to_limit(tmp_path, monkeypatch):
    homepage = '<html><body><a href="/news">News</a></body></html>'
    listings = {
        "https://example.com/news": '<a href="/news/item-1">One September 1, 2026</a>'
                                    '<link rel="next" href="/news/archive/2">',
        "https://example.com/news/archive/2": '<a href="/news/item-2">Two August 1, 2026</a>'
                                              '<link rel="next" href="/news/archive/3">',
        "https://example.com/news/archive/3": '<a href="/news/item-3">Three July 1, 2026</a>'
                                              '<link rel="next" href="/news/archive/4">',
    }
    requested = []

    def fake_fetch(url, clients, **kwargs):
        requested.append(url)
        if url == "https://example.com":
            return fetched(url, homepage)
        if url in listings:
            return fetched(url, f"<html><body>{listings[url]}</body></html>")
        return fetched(url, "<html><body><p>Article.</p></body></html>")

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path, max_event_pages=1,
                             max_articles=10, max_listing_pages=3)
    assert len(record["discovered_articles"]) == 3
    assert "https://example.com/news/archive/4" not in requested


def test_pages_found_through_ir_fallback_are_tagged(tmp_path, monkeypatch):
    homepage = '<html><body><a href="/careers">Careers</a></body></html>'
    ir_home = '<html><body><a href="/news">News</a></body></html>'
    landing = '<html><body><a href="/news/new-plant">New plant October 1, 2026</a></body></html>'

    def fake_fetch(url, clients, content_validator=None, **kwargs):
        pages = {
            "https://example.com": homepage,
            "https://ir.example.com/": ir_home,
            "https://ir.example.com/news": landing,
        }
        html = pages.get(url, "<html><body><p>Article.</p></body></html>")
        if content_validator and not content_validator(html, url):
            raise FetchFailed(url, [])
        return fetched(url, html)

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
    company = {
        "IQ_COMPANY_ID": "IQ1",
        "target_company_name": "Example Co.",
        "target_ciq_website": "https://example.com",
    }
    record = collect_company(company, [], tmp_path, max_event_pages=2)
    flags = {page["category"]: page["via_ir_fallback"] for page in record["pages"]}
    assert flags == {"home": False, "ir_home": True, "careers": False,
                     "news": True, "article": True}
    assert record["ir_fallback_article_count"] == 1


def test_previous_company_record_moves_to_history(tmp_path):
    original = {"IQ_COMPANY_ID": "IQ1", "collected_at": "2026-10-18T18:00:00Z", "status": "ok"}
    updated = {"IQ_COMPANY_ID": "IQ1", "collected_at": "2026-10-18T19:00:00Z", "status": "partial"}
    write_company_record(original, tmp_path)
    current = write_company_record(updated, tmp_path)
    history = tmp_path / "page_records_history/IQ1_20261018T180000Z.json"
    assert json.loads(current.read_text())["status"] == "partial"
    assert json.loads(history.read_text())["status"] == "ok"
