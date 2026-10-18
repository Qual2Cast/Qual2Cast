import gzip
import hashlib

import pytest

from fetch_adapter import FetchFailed, FetchedPage, fetch_page, raw_text_fields, save_raw_page


class FakeClient:
    def __init__(self, method, result=None, allowed=True):
        self.method = method
        self.result = result
        self.is_allowed = allowed

    def allowed(self, url):
        return self.is_allowed

    def get_html(self, url):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_fetch_falls_back_and_records_attempts():
    html = "<html><head><title>Company news</title></head><body><p>New contract announced today.</p></body></html>"
    page = fetch_page("https://example.com/news", [
        FakeClient("html", RuntimeError("blocked")),
        FakeClient("rendered", ("https://example.com/news", html)),
    ])
    assert page.method == "rendered"
    assert [attempt["status"] for attempt in page.attempts] == ["error:RuntimeError", "ok"]


def test_robots_disallow_stops_all_methods():
    with pytest.raises(FetchFailed) as caught:
        fetch_page("https://example.com/careers", [
            FakeClient("html", allowed=False),
            FakeClient("rendered", ("https://example.com/careers", "<html></html>")),
        ])
    assert caught.value.attempts == [{"method": "html", "status": "robots_disallowed"}]


def test_raw_page_is_saved_outside_website_scrape(tmp_path):
    html = "<html><body><p>We are hiring twenty engineers this month.</p></body></html>"
    page = FetchedPage(
        requested_url="https://example.com/jobs",
        final_url="https://example.com/jobs",
        source_url="https://example.com/jobs",
        snapshot="",
        fetched_at="2026-10-18T18:30:00Z",
        method="html",
        html=html,
        attempts=({"method": "html", "status": "ok"},),
    )
    metadata = save_raw_page(page, tmp_path, "IQ1", "P1")
    saved = tmp_path / "raw_html/IQ1/20261018T183000Z/html/P1.html.gz"
    assert saved.exists()
    with gzip.open(saved, "rt", encoding="utf-8") as stream:
        assert stream.read() == html
    assert metadata["raw_html_sha256"] == hashlib.sha256(html.encode()).hexdigest()
    assert "website_scrape" not in metadata["raw_html_file"]


def test_raw_text_keeps_hiring_and_financial_stress():
    html = """
    <html><head><title>Careers update</title></head><body>
    <p>We are hiring engineers after receiving a new customer contract.</p>
    <p>The company is experiencing difficulty servicing its debt.</p>
    </body></html>
    """
    fields = raw_text_fields(html)
    combined = " ".join([fields["raw_title"], fields["raw_meta"], *fields["raw_blocks"]])
    assert "hiring engineers" in combined
    assert "servicing its debt" in combined
