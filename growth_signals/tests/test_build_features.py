from datetime import date

from build_features import build_company_features
from schema import Event


def event(event_date, event_type="hiring", direction="positive", confidence=0.8,
          signal_duration="unknown"):
    precision = "day" if event_date else "unknown"
    return Event(
        IQ_COMPANY_ID="IQ1",
        company_name="Example Co.",
        event_type=event_type,
        direction=direction,
        event_date=event_date,
        event_date_precision=precision,
        retrieved_at="2025-01-02T00:00:00Z",
        source_url="https://example.com/news/item",
        source_text="Supporting source text for the event.",
        confidence=confidence,
        extraction_method="rule",
        unknown_reason="No date on source" if not event_date else None,
        signal_duration=signal_duration,
    )


def test_cutoff_excludes_future_events_and_counts_windows():
    rows = build_company_features([
        event("2024-12-31", confidence=1.0),
        event("2024-01-02", event_type="new_contract", confidence=0.5),
        event("2023-12-31", event_type="layoff", direction="negative"),
        event("2025-01-01", event_type="product_launch"),
        event(None),
    ], date(2024, 12, 31))
    row = rows[0]
    assert row["hiring_365d_count"] == 1
    assert row["new_contract_365d_count"] == 1
    assert row["layoff_365d_count"] == 0
    assert row["product_launch_365d_count"] == 0
    assert row["evidence_365d_count"] == 2
    assert row["evidence_730d_count"] == 3
    assert row["undated_event_count"] == 1
    assert row["mean_confidence_365d"] == 0.75


def test_rejects_conflicting_company_names_for_same_id():
    first = event("2024-01-01")
    second = Event(**{**first.to_dict(), "company_name": "Different Co."})
    try:
        build_company_features([first, second], date(2024, 12, 31))
    except ValueError as exc:
        assert "conflicting company names" in str(exc)
    else:
        raise AssertionError("expected conflicting names to fail")


def test_product_launch_duration_counts_remain_separate():
    rows = build_company_features([
        event("2024-12-01", "product_launch", signal_duration="temporary"),
        event("2024-11-01", "product_launch", signal_duration="durable"),
        event("2024-10-01", "product_launch"),
    ], date(2024, 12, 31))
    row = rows[0]
    assert row["product_launch_365d_count"] == 3
    assert row["product_launch_temporary_365d_count"] == 1
    assert row["product_launch_durable_365d_count"] == 1
    assert row["product_launch_unknown_duration_365d_count"] == 1
