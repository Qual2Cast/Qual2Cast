import pytest

from extract_events import event_status, extract_page_events, extract_record, signal_duration


def record_with(blocks, date="2026-09-22", company_name="Example Co."):
    return {
        "IQ_COMPANY_ID": "IQ1",
        "company_name": company_name,
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
    assert [event.event_type for event in events] == ["acquisition"]


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
    events, _ = extract_record(record_with([evidence], company_name="Wingstop Inc."))
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
    ], company_name="Wingstop Inc.")
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
    record = record_with([headline], company_name="Wingstop Inc.")
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
    assert [event.event_type for event in events] == ["customer_loss"]
    assert events[0].supporting_text == (
        "The company experienced elevated customer churn in the period.",)


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


def page_with(page_id, blocks, **extra):
    return {
        "page_id": page_id,
        "category": "article",
        "published_date": "2026-09-22",
        "published_date_precision": "day",
        "fetched_at": "2026-09-23T12:00:00Z",
        "source_url": f"https://example.com/news/{page_id.lower()}",
        "raw_title": f"Article {page_id}",
        "raw_meta": "",
        "raw_blocks": blocks,
        **extra,
    }


def types_for(blocks, company_name="Example Co."):
    events, _ = extract_record(record_with(blocks, company_name=company_name))
    return [event.event_type for event in events]


@pytest.mark.parametrize("sentence", [
    "This month's releases include the introduction of Paylocity Retirement.",
    "The national launch of Club Wingstop marked an important milestone.",
    "Fans get two new additions: Hot Honey Mustard Dip and Sprite Strawberry Rodeo.",
    "To complement the flavor, Example Co. is introducing Chamoy Ranch, a savory twist.",
    "The new Answer & Insight Agent allows you to analyze data.",
    "New recruiting agents automate repetitive processes.",
    "Wingstop is bringing bold flavor with its newest limited-time flavor, Sweet Heat Chamoy.",
])
def test_noun_and_sentence_initial_launch_forms_are_product_launches(sentence):
    assert types_for([sentence]) == ["product_launch"]


@pytest.mark.parametrize("sentence", [
    "The release of Q2 results is scheduled for July.",
    "With this appointment, Erik is a new addition to the Board.",
    "New risks and uncertainties arise from time to time.",
])
def test_launch_noun_forms_do_not_match_results_board_or_risk_language(sentence):
    assert types_for([sentence]) == []


@pytest.mark.parametrize("sentence", [
    "102 Net New Openings in Second Quarter, 16% Unit Growth",
    "Wingstop plans to expand its reach to 100 locations across Canada.",
    "The company opened two distribution centers in Ohio.",
])
def test_openings_counts_and_base_form_expand_are_market_expansion(sentence):
    assert types_for([sentence]) == ["market_expansion"]


def test_metric_definition_mentioning_openings_is_not_expansion():
    assert types_for([
        "Changes in domestic AUV are primarily driven by increases in same store sales "
        "and are also influenced by opening new restaurants.",
        "Herc Rentals operates 607 locations across North America.",
    ]) == []


@pytest.mark.parametrize("sentence", [
    "Our focus on customers, expanding our salesforce, and execution continues.",
    "The company grew its sales team in the quarter.",
    "Example Co. will add 300 new jobs at the plant.",
    "The plant will create hundreds of new jobs.",
    "Example Co. is hiring field technicians across Texas.",
])
def test_sales_force_growth_and_numbered_additions_are_hiring(sentence):
    assert types_for([sentence]) == ["hiring"]


@pytest.mark.parametrize("sentence", [
    "We remain committed to creating an environment where employees feel empowered.",
    "Our recruiters are always on the hunt for talented and committed employees.",
])
def test_workplace_award_language_is_not_hiring(sentence):
    assert types_for([sentence]) == []


@pytest.mark.parametrize("sentence", [
    "Example Co. announced it will lay off 200 employees.",
    "Example Co. is cutting about 5% of its workforce.",
    "The plan includes a workforce reduction across corporate functions.",
])
def test_future_and_percentage_layoffs_are_layoffs(sentence):
    assert types_for([sentence]) == ["layoff"]


def test_raised_rating_and_positive_outlook_are_credit_positive():
    assert types_for([
        "Moody's raised its rating on Example Co. to Ba2.",
        "Fitch revised the outlook to positive.",
    ]) == ["credit_positive"]


def test_raised_guidance_is_not_credit_positive():
    assert types_for(["The company raised its full-year revenue guidance."]) == ["guidance_raised"]


def test_forbearance_and_chapter_11_are_credit_stress():
    assert types_for([
        "Example Co. entered into a forbearance agreement with its lenders.",
        "Example Co. filed for Chapter 11 bankruptcy protection.",
    ]) == ["credit_stress"]


def test_block_repeated_on_three_pages_is_not_evidence():
    teaser = "New agents save time and increase accuracy across payroll."
    record = record_with([])
    record["pages"] = [page_with(f"P{n}", [f"Unrelated update {n}.", teaser]) for n in (1, 2, 3)]
    events, audit = extract_record(record)
    assert events == []
    assert audit["repeated_blocks_excluded"] == 1


def test_block_on_two_pages_is_still_evidence():
    teaser = "New agents save time and increase accuracy across payroll."
    record = record_with([])
    record["pages"] = [page_with(f"P{n}", [teaser]) for n in (1, 2)]
    events, _ = extract_record(record)
    assert [event.event_type for event in events] == ["product_launch", "product_launch"]


def test_about_block_for_partner_company_is_skipped_but_own_is_kept():
    record = record_with([
        "About Mondelez International: The company launched a new snack platform.",
        "About Example Co.: Example Co. launched a new payroll platform.",
    ])
    events, _ = extract_record(record)
    assert [event.source_text for event in events] == [
        "About Example Co.: Example Co. launched a new payroll platform."]


def test_event_status_marks_planned_completed_and_unknown():
    assert event_status("Wingstop plans to expand its reach to 100 locations.") == "planned"
    assert event_status("The Company opened 3 previously planned greenfield locations.") == "completed"
    assert event_status("We are expanding our salesforce.") == "unknown"
    events, _ = extract_record(record_with(["Example Co. will add 300 new jobs."]))
    assert events[0].event_status == "planned"


def test_ir_fallback_flag_is_carried_to_events_and_audit():
    record = record_with([])
    record["pages"] = [page_with("P1", ["Example Co. launched a new payroll platform."],
                                 via_ir_fallback=True)]
    events, audit = extract_record(record)
    assert events[0].via_ir_fallback is True
    assert audit["pages"][0]["via_ir_fallback"] is True


def test_financing_agreements_are_not_customer_contracts():
    assert types_for([
        "Example Co. entered into a new credit agreement with its bank group.",
        "Example Co. signed a merger agreement with Acme.",
    ]) == []


def test_generic_open_apis_and_churn_marketing_are_not_events():
    assert types_for([
        "A platform with open APIs to your current systems streamlines operations.",
        "Brands feel the pain by way of rising service costs, or worse, customer churn.",
    ]) == []


def test_a_lost_customer_in_advice_prose_is_not_customer_loss():
    assert types_for([
        "That experience turns a routine call into a lost customer.",
        "Example Co. lost its largest customer contract in March.",
    ]) == ["customer_loss"]


def test_undated_insights_page_is_skipped_but_dated_one_is_not():
    record = record_with([])
    undated = page_with("P1", ["Example Co. launched a new payroll platform."],
                        published_date=None, published_date_precision="unknown",
                        source_url="https://example.com/insights/how-to-choose")
    dated = page_with("P2", ["Example Co. launched a new payroll platform."],
                      source_url="https://example.com/insights/launch")
    record["pages"] = [undated, dated]
    events, audit = extract_record(record)
    assert [event.source_url for event in events] == ["https://example.com/insights/launch"]
    assert audit["pages"][0]["status"] == "skipped_undated_marketing_page"


def test_other_named_company_action_is_rejected_with_reason():
    record = record_with([
        "In mid-2025, Telstra launched Dynamic 5G, a business slicing service.",
        "Mondelez International launched a new snack platform.",
    ])
    events, audit = extract_record(record)
    assert events == []
    reasons = [item["reason"] for item in audit["pages"][0]["rejected"]]
    assert reasons == ["other_actor: Telstra", "other_actor: Mondelez International"]


@pytest.mark.parametrize("sentence", [
    "Example Co. launched a new payroll platform.",
    "Example's team launched a new payroll platform.",
    "We launched a new payroll platform.",
    "The Company opened two new distribution centers.",
    "Today, the company launched a new payroll platform.",
    "Example Co. and Acme signed a three-year contract.",
])
def test_company_self_references_keep_the_event(sentence):
    assert len(types_for([sentence])) == 1


def test_website_label_counts_as_the_company():
    record = record_with(["Herc Rentals opened 3 new branches in Texas."],
                         company_name="Herc Holdings Inc.")
    record["website"] = "https://www.hercrentals.com/"
    events, _ = extract_record(record)
    assert [event.event_type for event in events] == ["market_expansion"]


def test_rating_agency_actor_is_expected_for_credit_events():
    assert types_for(["S&P upgraded the company's credit rating to BBB."]) == ["credit_positive"]


def test_one_event_per_article_and_type_keeps_supporting_sentences():
    events, _ = extract_record(record_with([
        "Example Co. launched a new payroll platform.",
        "Example Co. also launched a new expense module.",
        "Example Co. signed a contract with a hospital network.",
    ]))
    assert [event.event_type for event in events] == ["product_launch", "new_contract"]
    assert events[0].source_text == "Example Co. launched a new payroll platform."
    assert events[0].supporting_text == ("Example Co. also launched a new expense module.",)


@pytest.mark.parametrize("sentence", [
    "Example Co. completed its acquisition of Domo's data platform business.",
    "Example Co. acquired Grayscale, a recruiting software provider.",
    "Example Co. has entered into a definitive agreement to acquire Acme Corp.",
    "Example Co. agreed to acquire a regional rental business.",
])
def test_company_acquisitions_are_acquisitions(sentence):
    assert types_for([sentence]) == ["acquisition"]


@pytest.mark.parametrize("sentence", [
    "Example Co. was acquired by Acme Corp. in 2021.",
    "Example Co. is reportedly in talks to acquire Acme.",
    "The platform helps teams acquire new customers faster.",
    "Proceeds were used to acquire rental equipment.",
    "Example Co. announced the September release for its newly-acquired Domo platform.",
])
def test_being_acquired_rumors_and_customer_acquisition_are_not_acquisitions(sentence):
    assert "acquisition" not in types_for([sentence])


@pytest.mark.parametrize("sentence", [
    "Example Co. completed the sale of its studio entertainment business.",
    "Example Co. divested its European packaging unit.",
])
def test_business_sales_are_divestitures(sentence):
    assert types_for([sentence]) == ["divestiture"]


@pytest.mark.parametrize("sentence", [
    "The limited-edition flavor sold out in two days.",
    "BrightView issued and sold 500,000 shares of preferred stock.",
    "The division was sold by its former owner in 2019.",
])
def test_sold_out_share_sales_and_passive_sales_are_not_divestitures(sentence):
    assert "divestiture" not in types_for([sentence])


@pytest.mark.parametrize("sentence", [
    "Example Co. raised a $40 million Series B funding round led by Acme Ventures.",
    "Example Co. closed $25 million in growth equity financing.",
    "Example Co. secured $12 million in new equity funding.",
    "Example Co. completed a private placement of common shares.",
])
def test_equity_raises_are_funding_rounds(sentence):
    assert types_for([sentence]) == ["funding_round"]


@pytest.mark.parametrize("sentence", [
    "Example Co. closed a $500 million offering of senior notes.",
    "Our platform helps founders raise seed funding faster.",
    "Employees raised $50,000 for charity.",
])
def test_debt_offerings_and_customer_or_charity_raises_are_not_funding_rounds(sentence):
    assert "funding_round" not in types_for([sentence])


def test_raised_and_lowered_company_guidance():
    assert types_for(["Example Co. is raising its full-year financial guidance."]) == [
        "guidance_raised"]
    assert types_for(["Example Co. lowered its 2026 revenue outlook."]) == ["guidance_lowered"]


def test_rating_outlook_and_reiterated_guidance_are_not_guidance_events():
    assert types_for(["S&P raised its rating outlook on Example Co."]) == ["credit_positive"]
    assert types_for(["Example Co. reiterated its full-year guidance."]) == []


def test_new_events_are_written_as_schema_version_2():
    events, _ = extract_record(record_with(["Example Co. acquired Acme Corp."]))
    assert events[0].to_dict()["schema_version"] == 2
