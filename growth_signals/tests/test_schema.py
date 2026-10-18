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


def test_undated_event_requires_reason():
    with pytest.raises(ValueError, match="unknown_reason"):
        Event.from_dict(valid_record(event_date=None, event_date_precision="unknown"))


def test_rejects_invalid_confidence_and_url():
    with pytest.raises(ValueError, match="confidence"):
        Event.from_dict(valid_record(confidence=1.1))
    with pytest.raises(ValueError, match="absolute"):
        Event.from_dict(valid_record(source_url="/news/contract"))
