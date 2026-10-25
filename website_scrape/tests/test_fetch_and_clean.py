"""
Tests for the website scrape's text filters and fetching helpers
(fetch_and_clean.py, scrape_websites.py). Each case is a problem found while
building the scrape; the tests keep it from coming back after a rule change.

Run from website_scrape/:  python -m pytest tests -q
"""

import pytest

import fetch_and_clean as fc


# ---------------------------------------------------------------- page-text filters

@pytest.mark.parametrize("sentence", [
    "Our solutions digitize operations and customize investor experiences.",
    "Your fastest option is to subscribe to any of our most popular products directly.",
    "We serve clients from well-established public companies to private businesses and nonprofits.",
    "Prepaid programs provide flexible payment solutions supporting budgeting, inclusion and convenience.",
])
def test_filters_keep_business_sentences(sentence):
    assert fc.clean_block(sentence)


@pytest.mark.parametrize("sentence", [
    "Access company updates, financial information, and investor resources.",
    "Subscribe to our newsletter for the latest updates.",
    "We are committed to diversity, equity and inclusion across our workforce.",
    "The company became a public company in 2019.",
    "Opens in a new window Opens an external website.",
])
def test_filters_drop_stock_and_site_chrome(sentence):
    assert not fc.clean_block(sentence)


# ---------------------------------------------------------------- filters from Riya's scraper

@pytest.mark.parametrize("sentence", [
    # false hits of the original rules, all quotes from the SIC 35 audit
    "Kadant brand products and services are sold to industries worldwide through our subsidiaries.",
    "Grow revenue, build customer loyalty, and increase retail store traffic with prepaid cards.",
    "Our image recognition software analyzes over 5 million data points in more than 1,000 dimensions.",
    "We focus on customer acquisition and retention for growing brands.",
    # false hits found in the full-list dry run
    "Our agent handles after-hours leads, inbound calls, and service bookings.",
    "We have maintained a small company feel with low turnover.",
    "Your CTV Buys Might Be Fake iPod Touch Sessions.",
    "Clients saw a 54% increase in online visibility within months.",
])
def test_size_and_deal_filters_keep_business_sentences(sentence):
    assert fc.clean_block(sentence) == sentence


@pytest.mark.parametrize("sentence, reason", [
    ("Company acquires UniMac, the global brand leader in on-premises laundry.", "deal_event"),
    ("The business was acquired by Capital Southwest in a recent transaction.", "deal_event"),
    ("We work with more than 90% of Fortune 100 companies from our target industries.", "scale_figure"),
    ("We hold a leading market share in commercial refrigeration equipment.", "scale_figure"),
])
def test_size_and_deal_filters_drop_identifying_sentences(sentence, reason):
    text, removed = fc.clean_block_logged(sentence)
    assert text == "" and removed[0]["reason"] == reason


def test_size_counts_and_dates_are_cut_inline():
    assert (fc.clean_block("Sold through distributors and dealers in more than 125 countries.")
            == "Sold through distributors and dealers in multiple countries.")
    assert (fc.clean_block("The company operates 45 manufacturing plants across North America.")
            == "The company operates multiple manufacturing plants across North America.")
    assert (fc.clean_block("RBC Bearings has been manufacturing bearings for aerospace customers since 1919.")
            == "RBC Bearings has been manufacturing bearings for aerospace customers.")
    text, removed = fc.clean_block_logged("Founded in 1950, the company makes industrial pumps and valves.")
    assert text == "the company makes industrial pumps and valves."
    assert removed[0]["reason"] == "founding_year"


def test_bare_tickers_are_cut_but_acronyms_stay(monkeypatch):
    monkeypatch.setattr(fc, "KNOWN_TICKERS", {"CSWC", "IT"})
    assert (fc.clean_block("Capital Southwest (CSWC) lends to middle-market companies.")
            == "Capital Southwest lends to middle-market companies.")
    kept = "We provide information technology (IT) services to hospitals."
    assert fc.clean_block(kept) == kept                           # IT abbreviates the words before
    kept = "Our Space Alternated Phase Shift (SAPS) technology cleans wafers."
    assert fc.clean_block(kept) == kept                           # not a known ticker


def test_url_candidates_try_www_then_http():
    assert fc.url_candidates("example.com") == [
        "https://example.com", "https://www.example.com", "http://example.com"]
    assert fc.url_candidates("https://www.example.com") == [
        "https://www.example.com", "http://www.example.com"]


def test_pages_without_a_declared_charset_decode_as_utf8():
    import requests
    resp = requests.Response()
    resp._content = "<html><body><p>Café équipement — 3 products</p></body></html>".encode("utf-8")
    resp.headers["Content-Type"] = "text/html"
    resp.encoding = "ISO-8859-1"                                  # what requests would guess
    assert "Café équipement —" in fc.decode_html(resp)


def test_browser_certificate_error_page_means_try_the_next_address():
    import scrape_websites as s1
    chrome = ("<html><head><title>Privacy error</title></head><body><h1>Your connection is not "
              "private</h1><p>Attackers might be trying to steal your information from "
              "www.englewoodlab.com</p><p>NET::ERR_CERT_AUTHORITY_INVALID</p></body></html>")
    assert s1.CERT_ERROR_PAGE.search(chrome)
    assert s1.text_fields(fc.extract_page(chrome))["block_page"]     # never kept as text
    assert not s1.CERT_ERROR_PAGE.search("<html><head><title>Data privacy services</title></head>"
                                         "<body><p>We fix privacy errors in your records.</p></body></html>")


@pytest.mark.parametrize("url, english", [
    ("http://www.englewoodlab.com/ko/home", "http://www.englewoodlab.com/en/home"),
    ("https://example.com/de-de/about", "https://example.com/en/about"),
    ("https://example.com/en/home", None),
    ("https://example.com/about", None),
    ("https://example.com/", None),
])
def test_homepage_in_another_language_has_an_english_address(url, english):
    import scrape_websites as s1
    assert s1.english_version(url) == english


class FakeClient:
    """Serves fixed pages by URL, like a fetch client."""
    method = "html"

    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def allowed(self, url):
        return True

    def get_html(self, url):
        import scrape_websites as s1
        self.asked.append(url)
        if url not in self.pages:
            raise s1.RenderError("unreachable")
        final, html = self.pages[url]
        return final, html


def test_crawl_skips_the_certificate_error_and_uses_the_english_homepage(tmp_path, monkeypatch):
    import scrape_websites as s1
    monkeypatch.setattr(s1, "save_raw", lambda raw_dir, page_id, html: ("", ""))   # no files
    chrome = "<html><head><title>Privacy error</title></head><body>NET::ERR_CERT_AUTHORITY_INVALID</body></html>"
    korean = "<html><head><title>Home</title></head><body><p>잉글우드랩에 오신 것을 환영합니다</p></body></html>"
    english = ("<html><head><title>Englewood LAB</title></head><body>"
               + "<p>We research, develop and manufacture skincare and cosmetics for beauty brands.</p>" * 10
               + "</body></html>")
    client = FakeClient({"https://www.englewoodlab.com": ("https://www.englewoodlab.com/", chrome),
                         "http://www.englewoodlab.com": ("http://www.englewoodlab.com/ko/home", korean),
                         "http://www.englewoodlab.com/en/home": ("http://www.englewoodlab.com/en/home", english)})
    result = s1.crawl(client, "www.englewoodlab.com", 1, tmp_path)
    assert client.asked[:3] == ["https://www.englewoodlab.com", "http://www.englewoodlab.com",
                                "http://www.englewoodlab.com/en/home"]
    assert result["pages"][0]["url"] == "http://www.englewoodlab.com/en/home"
    assert "manufacture skincare and cosmetics" in " ".join(result["pages"][0]["blocks"])


def test_bot_check_pages_are_never_used_as_text():
    import scrape_websites as s1
    wall = fc.extract_page("<html><head><title>Pardon Our Interruption</title></head><body>"
                           "<p>As you were browsing something about your browser made us think "
                           "you were a bot.</p></body></html>")
    fields = s1.text_fields(wall)
    assert fields["block_page"] and fields["blocks"] == [] and fields["word_count"] == 0
    # a real page that mentions reCAPTCHA in its footer is kept
    real = fc.extract_page("<html><head><title>Healthcare staffing</title></head><body>"
                           + "<p>We place travel nurses and allied health professionals at hospitals "
                             "and clinics across the country every single week.</p>" * 12
                           + "<p>This site is protected by reCAPTCHA and the Google Privacy Policy.</p>"
                             "</body></html>")
    assert not s1.text_fields(real)["block_page"]
