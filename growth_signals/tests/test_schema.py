import pytest

from schema import Event


def valid_record(**overrides):
    record = {
        "IQ_COMPANY_ID": "IQ1",
        "company_name": "Example Co.",
        "event_type": "new_contract",
        "direction": "positive",
        "event_date": "2024-06-01",
        "event_date_precision": "day",
        "retrieved_at": "2024-06-02T12:00:00Z",
        "source_url": "https://example.com/news/contract",
        "source_text": "Example Co. announced a new customer contract.",
        "confidence": 0.9,
        "extraction_method": "llm",
    }
    record.update(overrides)
    return record


def test_valid_event_round_trip():
    event = Event.from_dict(valid_record())
    assert event.to_dict()["event_type"] == "new_contract"
    assert event.signal_duration == "unknown"


def test_undated_event_requires_reason():
    with pytest.raises(ValueError, match="unknown_reason"):
        Event.from_dict(valid_record(event_date=None, event_date_precision="unknown"))


def test_rejects_invalid_confidence_and_url():
    with pytest.raises(ValueError, match="confidence"):
        Event.from_dict(valid_record(confidence=1.1))
    with pytest.raises(ValueError, match="absolute"):
        Event.from_dict(valid_record(source_url="/news/contract"))


def test_rejects_invalid_signal_duration():
    with pytest.raises(ValueError, match="signal_duration"):
        Event.from_dict(valid_record(signal_duration="permanent"))


def test_quarter_precision_and_new_fields_validate():
    event = Event.from_dict(valid_record(
        event_date="2026-09-30", event_date_precision="quarter",
        event_status="planned", via_ir_fallback=True))
    assert event.event_status == "planned"


def test_older_records_default_new_fields():
    event = Event.from_dict(valid_record())
    assert event.event_status == "unknown"
    assert event.via_ir_fallback is False


def test_rejects_unknown_event_status():
    with pytest.raises(ValueError, match="event_status"):
        Event.from_dict(valid_record(event_status="rumored"))


def test_version_1_records_still_load():
    event = Event.from_dict(valid_record(schema_version=1))
    assert event.supporting_text == ()


def test_new_event_types_require_schema_version_2():
    with pytest.raises(ValueError, match="schema_version 2"):
        Event.from_dict(valid_record(schema_version=1, event_type="acquisition"))
    assert Event.from_dict(valid_record(event_type="acquisition")).schema_version == 2


def test_supporting_text_round_trips_through_json_lists():
    event = Event.from_dict(valid_record(supporting_text=["Second sentence."]))
    assert event.to_dict()["supporting_text"] == ["Second sentence."]
    with pytest.raises(ValueError, match="supporting_text"):
        Event.from_dict(valid_record(supporting_text=[" "]))
