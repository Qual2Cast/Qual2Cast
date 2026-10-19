from extract_events import extract_page_events, extract_record, signal_duration


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


def test_announced_completed_acquisition_is_not_a_product_launch():
    record = record_with([
        "Progress today announced it completed its acquisition of a data platform business."
    ])
    events, _ = extract_record(record)
    assert events == []


def test_month_abbreviation_stays_with_evidence_sentence():
    evidence = (
        "BURLINGTON, Mass., Sept. 30, 2026 -- The company announced a new platform."
    )
    record = record_with([evidence])
    events, _ = extract_record(record)
    assert len(events) == 1
    assert events[0].source_text == evidence


def test_explicit_introducing_product_title_is_a_launch():
    record = record_with([])
    record["pages"][0]["raw_title"] = "Introducing Paylocity Ignite AI"
    events, _ = extract_record(record)
    assert len(events) == 1
    assert events[0].event_type == "product_launch"
    assert events[0].source_text == "Introducing Paylocity Ignite AI"


def test_introducing_the_named_pass_is_a_launch():
    evidence = "Introducing the Wingstop Wing Pass"
    events, _ = extract_record(record_with([evidence]))
    assert len(events) == 1
    assert events[0].event_type == "product_launch"


def test_announces_named_rewards_card_is_a_launch():
    evidence = "Wingstop Announces the Game Day Punch Card"
    events, _ = extract_record(record_with([evidence]))
    assert len(events) == 1
    assert events[0].event_type == "product_launch"


def test_flavor_arrives_nationwide_is_a_launch():
    evidence = "The unexpected SOUR THEN SWEET wing flavor arrives nationwide Oct. 27."
    events, _ = extract_record(record_with([evidence]))
    assert len(events) == 1
    assert events[0].event_type == "product_launch"


def test_named_new_products_launching_nationwide_are_a_launch():
    evidence = (
        "Original Lemon Pepper is joined by new Lemon Pepper Chili Crunch and "
        "Lemon Pepper Chili Glaze, launching nationwide Sept. 15."
    )
    events, _ = extract_record(record_with([evidence]))
    assert len(events) == 1
    assert events[0].event_type == "product_launch"


def test_nationwide_staff_availability_is_not_a_product_launch():
    events, _ = extract_record(record_with([
        "New leadership positions are available nationwide."
    ]))
    assert events == []


def test_future_product_plan_without_launch_action_is_not_a_launch():
    events, _ = extract_record(record_with([
        "The company is considering a new rewards card for next year."
    ]))
    assert events == []


def test_prnewswire_original_content_url_is_not_event_evidence():
    events, _ = extract_record(record_with([
        "View original content to download multimedia: "
        "https://www.prnewswire.com/news-releases/company-announces-the-rewards-card.html"
    ]))
    assert events == []


def test_limited_time_article_marks_launch_temporary():
    record = record_with([
        "The new flavor arrives nationwide Oct. 27.",
        "Available for a limited time only at participating locations.",
    ])
    events, _ = extract_record(record)
    assert len(events) == 1
    assert events[0].signal_duration == "temporary"


def test_platform_launch_is_durable_without_temporary_marker():
    events, _ = extract_record(record_with([
        "The company launched a new payroll platform for hospitals."
    ]))
    assert len(events) == 1
    assert events[0].signal_duration == "durable"


def test_named_ai_launch_embedded_throughout_platform_is_durable():
    record = record_with([
        "Introducing Paylocity Ignite AI",
        "It is embedded throughout the platform, bringing data and automation into work.",
    ])
    events, _ = extract_record(record)
    assert len(events) == 1
    assert events[0].signal_duration == "durable"


def test_non_product_event_duration_is_unknown():
    assert signal_duration(
        "new_contract", "Signed a service agreement.", "Limited-time wording."
    ) == "unknown"


def test_undated_match_is_retained_with_reason():
    record = record_with(["The company is hiring 25 engineers."], date=None)
    events = extract_page_events(record, record["pages"][0])
    assert len(events) == 1
    assert events[0].event_date is None
    assert events[0].event_date_precision == "unknown"
    assert events[0].unknown_reason


def test_headline_present_tense_signs_agreement_is_a_contract_event():
    record = record_with([
        "Wingstop Inc. Signs 35 Unit Franchise Development Agreement With Sizzling Platter"
    ])
    events, _ = extract_record(record)
    assert len(events) == 1
    assert events[0].event_type == "new_contract"


def test_non_article_pages_are_not_extracted():
    record = record_with(["The company launched a new platform."])
    page = {**record["pages"][0], "category": "careers"}
    assert extract_page_events(record, page) == []


def test_duplicate_evidence_is_deduplicated():
    sentence = "The company launched a new payroll platform."
    record = record_with([sentence, sentence])
    events, _ = extract_record(record)
    assert len(events) == 1


def test_site_suffix_in_html_title_does_not_duplicate_body_headline():
    headline = "Wingstop Inc. Signs 35 Unit Franchise Development Agreement"
    record = record_with([headline])
    record["pages"][0]["raw_title"] = headline + " – Investor Relations"
    events, _ = extract_record(record)
    assert len(events) == 1
    assert events[0].source_text == headline


def test_partnership_purchase_order_and_contract_extension_are_contracts():
    phrases = [
        "The company announced a new partnership with Walmart.",
        "Example Co. received a purchase order from the Department of Defense.",
        "The parties executed a master services agreement.",
        "The company extended its existing contract with the customer.",
    ]
    for phrase in phrases:
        events, _ = extract_record(record_with([phrase]))
        assert [event.event_type for event in events] == ["new_contract"], phrase


def test_canceled_subscription_and_churn_are_customer_loss():
    events, _ = extract_record(record_with([
        "A key account canceled its subscription.",
        "The company experienced elevated customer churn in the period.",
    ]))
    assert [event.event_type for event in events] == ["customer_loss", "customer_loss"]


def test_rollout_shipping_and_debut_are_product_launches():
    phrases = [
        "Example Co. today rolled out a new mobile app.",
        "The company began shipping its next-generation device.",
        "Example Co. debuted a new analytics dashboard.",
    ]
    for phrase in phrases:
        events, _ = extract_record(record_with([phrase]))
        assert [event.event_type for event in events] == ["product_launch"], phrase


def test_store_plant_and_expanded_into_are_market_expansion():
    phrases = [
        "Example Co. opened 50 new restaurants this year.",
        "The company opened a new store in Austin.",
        "Example Co. expanded into Europe.",
        "The company is opening a manufacturing plant in Ohio.",
    ]
    for phrase in phrases:
        events, _ = extract_record(record_with([phrase]))
        assert [event.event_type for event in events] == ["market_expansion"], phrase


def test_acquisition_to_expand_footprint_is_not_market_expansion():
    events, _ = extract_record(record_with([
        "Example Co. acquired a competitor to expand its footprint."
    ]))
    assert events == []


def test_headcount_additions_and_consultant_hiring_are_hiring():
    phrases = [
        "We are hiring implementation consultants.",
        "Example Co. added 150 employees in the first half.",
        "We are now hiring for multiple open roles.",
        "The company created 40 new jobs in Tennessee.",
        "The company is expanding its workforce by 10 percent.",
    ]
    for phrase in phrases:
        events, _ = extract_record(record_with([phrase]))
        assert [event.event_type for event in events] == ["hiring"], phrase


def test_generic_open_positions_line_is_not_hiring():
    events, _ = extract_record(record_with([
        "Join our team: 12 open positions on the careers page."
    ]))
    assert events == []


def test_past_tense_cuts_rif_and_furlough_are_layoffs():
    phrases = [
        "Example Co. cut 120 jobs at its Midwest plant.",
        "The company eliminated 50 positions.",
        "Example Co. announced a reduction in force.",
        "The firm furloughed hundreds of workers.",
    ]
    for phrase in phrases:
        events, _ = extract_record(record_with([phrase]))
        assert [event.event_type for event in events] == ["layoff"], phrase


def test_rating_upgrade_and_credit_facility_amendment_are_credit_positive():
    phrases = [
        "S&P upgraded the company's credit rating to BBB.",
        "Example Co. amended and extended its credit facility.",
    ]
    for phrase in phrases:
        events, _ = extract_record(record_with([phrase]))
        assert [event.event_type for event in events] == ["credit_positive"], phrase


def test_note_issuance_without_rating_action_is_not_credit_positive():
    events, _ = extract_record(record_with([
        "The company issued $500 million of senior notes."
    ]))
    assert events == []


def test_downgrade_going_concern_and_missed_payment_are_credit_stress():
    phrases = [
        "Moody's downgraded the company's credit rating to B2.",
        "The auditor raised substantial doubt about going concern.",
        "The company missed an interest payment.",
        "Lenders waived the covenant breach.",
    ]
    for phrase in phrases:
        events, _ = extract_record(record_with([phrase]))
        assert [event.event_type for event in events] == ["credit_stress"], phrase


def test_careers_page_extracts_hiring_but_not_product_language():
    record = record_with(["The company is hiring 25 engineers."])
    record["pages"][0]["category"] = "careers"
    events, _ = extract_record(record)
    assert [event.event_type for event in events] == ["hiring"]
    launch_record = record_with(["The company launched a new payroll platform."])
    launch_record["pages"][0]["category"] = "careers"
    assert extract_record(launch_record)[0] == []
