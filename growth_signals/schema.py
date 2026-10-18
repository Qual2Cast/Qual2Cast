"""Validated records for the growth-signals pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

SCHEMA_VERSION = 1

EVENT_DIRECTIONS = {"positive", "negative", "neutral", "unknown"}
EVENT_DATE_PRECISIONS = {"day", "month", "year", "unknown"}
EXTRACTION_METHODS = {"rule", "llm", "human_review", "unknown"}
EVENT_TYPES = {
    "new_contract",
    "customer_loss",
    "product_launch",
    "market_expansion",
    "hiring",
    "layoff",
    "credit_positive",
    "credit_stress",
}


def _parse_date(value: str | None) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"event_date must be ISO YYYY-MM-DD, got {value!r}") from exc


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"retrieved_at must be an ISO timestamp, got {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("retrieved_at must include a timezone")
    return parsed


@dataclass(frozen=True)
class Event:
    IQ_COMPANY_ID: str
    company_name: str
    event_type: str
    direction: str
    event_date: str | None
    event_date_precision: str
    retrieved_at: str
    source_url: str
    source_text: str
    confidence: float
    extraction_method: str
    unknown_reason: str | None = None
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> "Event":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if not self.IQ_COMPANY_ID.strip():
            raise ValueError("IQ_COMPANY_ID is required")
        if not self.company_name.strip():
            raise ValueError("company_name is required")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type: {self.event_type}")
        if self.direction not in EVENT_DIRECTIONS:
            raise ValueError(f"unknown direction: {self.direction}")
        if self.event_date_precision not in EVENT_DATE_PRECISIONS:
            raise ValueError(f"unknown event_date_precision: {self.event_date_precision}")
        if self.extraction_method not in EXTRACTION_METHODS:
            raise ValueError(f"unknown extraction_method: {self.extraction_method}")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.source_text.strip():
            raise ValueError("source_text is required")
        parsed_url = urlparse(self.source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError(f"source_url must be an absolute HTTP(S) URL: {self.source_url!r}")
        _parse_timestamp(self.retrieved_at)
        event_date = _parse_date(self.event_date)
        if event_date is None:
            if self.event_date_precision != "unknown":
                raise ValueError("an undated event must use event_date_precision='unknown'")
            if not (self.unknown_reason or "").strip():
                raise ValueError("an undated event requires unknown_reason")
        elif self.event_date_precision == "unknown":
            raise ValueError("a dated event must state day, month, or year precision")
        return self

    @property
    def parsed_event_date(self) -> date | None:
        return _parse_date(self.event_date)

    @classmethod
    def from_dict(cls, record: dict) -> "Event":
        allowed = set(cls.__dataclass_fields__)
        extra = set(record) - allowed
        if extra:
            raise ValueError(f"unexpected event fields: {sorted(extra)}")
        try:
            event = cls(**record)
        except TypeError as exc:
            raise ValueError(f"invalid event record: {exc}") from exc
        return event.validate()

    def to_dict(self) -> dict:
        self.validate()
        return asdict(self)


def read_events_jsonl(path: Path) -> list[Event]:
    events = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                events.append(Event.from_dict(record))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return events


def write_events_jsonl(events: Iterable[Event], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
