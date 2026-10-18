from collect_events import (
    date_from_text,
    discover_article_links,
    discover_event_pages,
    is_article_url,
    publication_date_from_html,
)


def test_discovers_deduplicated_same_site_event_pages():
    html = """
    <a href="/news/">Latest news</a>
    <a href="/news/#top">News again</a>
    <a href="https://careers.example.com/jobs">Open positions</a>
    <a href="https://other.example.org/press">External press</a>
    <a href="mailto:jobs@example.com">Email recruiting</a>
    """
    pages = discover_event_pages(html, "https://www.example.com")
    assert pages == [
        {"url": "https://careers.example.com/jobs", "category": "careers", "anchor_text": "Open positions"},
        {"url": "https://www.example.com/news", "category": "news", "anchor_text": "Latest news"},
    ]


def test_anchor_text_can_identify_a_generic_link():
    pages = discover_event_pages(
        '<a href="/company/updates-page">Press releases</a>',
        "https://example.com",
    )
    assert pages[0]["category"] == "press"


def test_discovers_dated_same_site_articles():
    html = '''
    <a href="/resources/learn/blogs/new-product/">New product launch blog September 22, 2026</a>
    <a href="/resources/learn/blogs/">All blogs</a>
    <a href="https://other.example/news/item">External article October 1, 2026</a>
    '''
    articles = discover_article_links(
        html, "https://www.example.com/resources/learn/blogs/", "news")
    assert articles == [{
        "url": "https://www.example.com/resources/learn/blogs/new-product",
        "source_category": "news",
        "anchor_text": "New product launch blog September 22, 2026",
        "published_date": "2026-09-22",
        "published_date_precision": "day",
        "discovered_from": "https://www.example.com/resources/learn/blogs/",
    }]


def test_date_from_text_does_not_guess_when_missing():
    assert date_from_text("Company launches a product") == (None, "unknown")


def test_reads_explicit_publication_date_metadata():
    html = '<meta property="article:published_time" content="2026-08-14T09:30:00Z">'
    assert publication_date_from_html(html) == ("2026-08-14", "day")


def test_reads_abbreviated_date_from_top_of_article():
    html = '<html><body><p>BURLINGTON, Mass., Sept. 30, 2026 (NEWSWIRE)</p></body></html>'
    assert publication_date_from_html(html) == ("2026-09-30", "day")


def test_reads_other_month_abbreviations():
    assert date_from_text("Oct. 01, 2026") == ("2026-10-01", "day")


def test_specific_press_release_url_is_an_article_but_listing_is_not():
    assert is_article_url(
        "https://example.com/news-releases/news-release-details/new-product")
    assert not is_article_url("https://example.com/news/default.aspx")
