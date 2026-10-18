import json

from fetch_adapter import FetchFailed, FetchedPage
from collect_company_pages import collect_company, choose_event_pages, write_company_record


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


def test_collect_company_saves_home_and_event_pages(tmp_path, monkeypatch):
    homepage = """
    <html><head><title>Example</title></head><body>
    <a href="/news">News</a><a href="/careers">Careers</a>
    </body></html>
    """
    event_html = "<html><head><title>News</title></head><body><p>New contract announced for hospital software.</p></body></html>"

    def fake_fetch(url, clients):
        if url == "https://example.com":
            return fetched(url, homepage)
        return fetched(url, event_html)

    monkeypatch.setattr("collect_company_pages.fetch_page", fake_fetch)
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

    def fake_fetch(url, clients):
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


def test_previous_company_record_moves_to_history(tmp_path):
    original = {"IQ_COMPANY_ID": "IQ1", "collected_at": "2026-10-18T18:00:00Z", "status": "ok"}
    updated = {"IQ_COMPANY_ID": "IQ1", "collected_at": "2026-10-18T19:00:00Z", "status": "partial"}
    write_company_record(original, tmp_path)
    current = write_company_record(updated, tmp_path)
    history = tmp_path / "page_records_history/IQ1_20261018T180000Z.json"
    assert json.loads(current.read_text())["status"] == "partial"
    assert json.loads(history.read_text())["status"] == "ok"
