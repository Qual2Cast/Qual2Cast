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


class RecordingClient(FakeClient):
    def get_html(self, url):
        self.received_url = url
        return super().get_html(url)


def test_fetch_falls_back_and_records_attempts():
    html = "<html><head><title>Company news</title></head><body><p>New contract announced today.</p></body></html>"
    page = fetch_page("https://example.com/news", [
        FakeClient("html", RuntimeError("blocked")),
        FakeClient("rendered", ("https://example.com/news", html)),
    ])
    assert page.method == "rendered"
    assert [attempt["status"] for attempt in page.attempts] == ["error:RuntimeError", "ok"]


def test_cloudflare_cookie_challenge_triggers_fallback():
    challenge = '''<html><body><script>document.cookie = "cf_bypass=1; Path=/";</script>
    <p>For the best experience, enable JavaScript.</p></body></html>'''
    content = "<html><body><p>We are hiring implementation consultants.</p></body></html>"
    page = fetch_page("https://example.com/careers", [
        FakeClient("html", ("https://example.com/careers/", challenge)),
        FakeClient("rendered", ("https://example.com/careers/", content)),
    ])
    assert page.method == "rendered"
    assert [attempt["status"] for attempt in page.attempts] == [
        "error:BlockedError", "ok"
    ]


def test_fetch_normalizes_a_domain_without_a_scheme():
    client = RecordingClient(
        "html",
        ("https://www.example.com/", "<html><body><p>Company news.</p></body></html>"),
    )
    page = fetch_page("www.example.com", [client])
    assert client.received_url == "https://www.example.com"
    assert page.requested_url == "www.example.com"


def test_cloudflare_script_marker_does_not_reject_real_content():
    content = '''<html><head><title>Company newsroom</title></head><body>
    <script src="/cdn-cgi/challenge-platform/script.js"></script>
    <p>The company announced a new customer contract for its software platform.</p>
    <p>The agreement expands service into additional healthcare markets.</p>
    <p>Implementation work begins this quarter with a broader launch next year.</p>
    </body></html>'''
    page = fetch_page("https://example.com/news", [
        FakeClient("rendered", ("https://example.com/news", content)),
    ])
    assert page.method == "rendered"


def test_content_validator_can_reject_dynamic_shell_and_fallback():
    shell = "<html><body><div id='news-items'></div></body></html>"
    rendered = "<html><body><a href='/news/item'>Company news</a></body></html>"
    page = fetch_page(
        "https://example.com/news",
        [
            FakeClient("html", ("https://example.com/news", shell)),
            FakeClient("rendered", ("https://example.com/news", rendered)),
        ],
        content_validator=lambda html, final_url: "Company news" in html,
    )
    assert page.method == "rendered"
    assert [attempt["status"] for attempt in page.attempts] == [
        "error:ContentRejected", "ok"
    ]


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
