from extract_events import extract_page_events, extract_record


def record_with(blocks, date="2026-09-22"):
    return {
        "IQ_COMPANY_ID": "IQ1",
        "company_name": "Example Co.",
        "pages": [{
            "page_id": "P4",
            "category": "article",
            "published_date": date,
            "published_date_precision": "day" if date else "unknown",
            "fetched_at": "2026-09-23T12:00:00Z",
            "source_url": "https://example.com/news/item",
            "raw_title": "Example company update",
            "raw_meta": "",
            "raw_blocks": blocks,
        }],
    }


def test_extracts_action_plus_object_with_exact_evidence():
    record = record_with([
        "Example Co. launched a new payroll platform for regional hospitals.",
        "It also signed a three-year contract with a healthcare network.",
    ])
    events, audit = extract_record(record)
    assert [event.event_type for event in events] == ["product_launch", "new_contract"]
    assert events[0].event_date == "2026-09-22"
    assert events[0].source_text == record["pages"][0]["raw_blocks"][0]
    assert audit["event_count"] == 2


def test_abstains_on_marketing_growth_and_generic_careers_language():
    record = record_with([
        "Our flexible solutions fuel growth and inspire confident leadership.",
        "Don't just land a job. Launch your career with us.",
        "We help clients improve hiring and employee engagement.",
    ])
    events, audit = extract_record(record)
    assert events == []
    assert audit["pages"][0]["status"] == "abstained_no_rule_match"


def test_reducing_data_entry_for_employees_is_not_a_layoff():
    record = record_with([
        "Configured rules can help categorize transactions, reducing repetitive data entry and supporting consistent information for employees."
    ])
    events, _ = extract_record(record)
    assert events == []


def test_explicit_introducing_product_title_is_a_launch():
    record = record_with([])
    record["pages"][0]["raw_title"] = "Introducing Paylocity Ignite AI"
    events, _ = extract_record(record)
    assert len(events) == 1
    assert events[0].event_type == "product_launch"
    assert events[0].source_text == "Introducing Paylocity Ignite AI"


def test_undated_match_is_retained_with_reason():
    record = record_with(["The company is hiring 25 engineers."], date=None)
    events = extract_page_events(record, record["pages"][0])
    assert len(events) == 1
    assert events[0].event_date is None
    assert events[0].event_date_precision == "unknown"
    assert events[0].unknown_reason


def test_non_article_pages_are_not_extracted():
    record = record_with(["The company launched a new platform."])
    page = {**record["pages"][0], "category": "careers"}
    assert extract_page_events(record, page) == []


def test_duplicate_evidence_is_deduplicated():
    sentence = "The company launched a new payroll platform."
    record = record_with([sentence, sentence])
    events, _ = extract_record(record)
    assert len(events) == 1
