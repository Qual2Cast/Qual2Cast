from collect_events import discover_event_pages


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
