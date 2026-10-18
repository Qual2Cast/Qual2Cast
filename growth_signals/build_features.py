"""Aggregate dated growth events into leakage-safe company features."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from schema import EVENT_TYPES, Event, read_events_jsonl

WINDOW_DAYS = (365, 730, 1095)


def _feature_names() -> list[str]:
    names = ["IQ_COMPANY_ID", "company_name", "cutoff_date", "undated_event_count"]
    for days in WINDOW_DAYS:
        for event_type in sorted(EVENT_TYPES):
            names.append(f"{event_type}_{days}d_count")
        names.extend([
            f"positive_{days}d_count",
            f"negative_{days}d_count",
            f"evidence_{days}d_count",
            f"mean_confidence_{days}d",
        ])
    return names


FEATURE_NAMES = _feature_names()


def build_company_features(events: list[Event], cutoff_date: date) -> list[dict]:
    """Build one feature row per company using no event after `cutoff_date`."""
    by_company: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        event.validate()
        by_company[event.IQ_COMPANY_ID].append(event)

    rows = []
    for company_id in sorted(by_company):
        company_events = by_company[company_id]
        company_names = {event.company_name for event in company_events}
        if len(company_names) != 1:
            raise ValueError(f"conflicting company names for {company_id}: {sorted(company_names)}")
        row = {
            "IQ_COMPANY_ID": company_id,
            "company_name": next(iter(company_names)),
            "cutoff_date": cutoff_date.isoformat(),
            "undated_event_count": sum(event.parsed_event_date is None for event in company_events),
        }
        for days in WINDOW_DAYS:
            start_date = cutoff_date - timedelta(days=days - 1)
            eligible = [event for event in company_events
                        if event.parsed_event_date is not None
                        and start_date <= event.parsed_event_date <= cutoff_date]
            for event_type in sorted(EVENT_TYPES):
                row[f"{event_type}_{days}d_count"] = sum(
                    event.event_type == event_type for event in eligible)
            row[f"positive_{days}d_count"] = sum(event.direction == "positive" for event in eligible)
            row[f"negative_{days}d_count"] = sum(event.direction == "negative" for event in eligible)
            row[f"evidence_{days}d_count"] = len(eligible)
            row[f"mean_confidence_{days}d"] = (
                sum(event.confidence for event in eligible) / len(eligible) if eligible else "")
        rows.append(row)
    return rows


def write_feature_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FEATURE_NAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--cutoff-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = build_company_features(read_events_jsonl(args.events), args.cutoff_date)
    write_feature_csv(rows, args.output)


if __name__ == "__main__":
    main()
