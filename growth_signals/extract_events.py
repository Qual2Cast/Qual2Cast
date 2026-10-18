"""High-precision rule extraction of source-backed growth events.

This first extractor intentionally prefers abstention over recall. A keyword
alone is never enough: each rule requires an action phrase and an event object,
and every accepted event retains the exact source sentence and page URL.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from schema import Event, write_events_jsonl


RULES = {
    "new_contract": re.compile(
        r"\b(?:awarded|secured|signed|won|entered into)\b[^.!?]{0,100}"
        r"\b(?:contract|agreement|deal)\b"
        r"|\bselected\b[^.!?]{0,80}\b(?:provider|partner|platform)\b",
        re.I,
    ),
    "customer_loss": re.compile(
        r"\b(?:lost|terminated|did not renew|nonrenewal|non-renewal)\b[^.!?]{0,100}"
        r"\b(?:customer|client|contract|agreement)\b",
        re.I,
    ),
    "product_launch": re.compile(
        r"\b(?:announced|introduced|launched|unveiled|released)\b[^.!?]{0,100}"
        r"\b(?:new|product|platform|solution|service|feature|agent|module|offering)\b"
        r"|\bintroducing\b[^.!?]{0,100}\b(?:product|platform|solution|service|feature|agent|module)\b"
        r"|^(?-i:Introducing\s+[A-Z])[\w-]+(?:\s+[A-Z][\w-]+){0,5}",
        re.I,
    ),
    "market_expansion": re.compile(
        r"\b(?:expanded|expanding|entered|entering|opened|opening)\b[^.!?]{0,100}"
        r"\b(?:market|region|country|countries|location|office|facility|operations)\b",
        re.I,
    ),
    "hiring": re.compile(
        r"\b(?:is hiring|are hiring|plans? to hire|will hire|adding)\b[^.!?]{0,80}"
        r"\b(?:employees|workers|engineers|staff|roles|positions|jobs)\b",
        re.I,
    ),
    "layoff": re.compile(
        r"\b(?:laid off|layoffs?)\b[^.!?]{0,40}"
        r"\b(?:workforce|employees|workers|staff|roles|positions|jobs)\b"
        r"|\b(?:reducing|cutting|eliminating)\b\s+(?:its\s+|the\s+)?"
        r"(?:workforce|employees|workers|staff|roles|positions|jobs)\b",
        re.I,
    ),
    "credit_stress": re.compile(
        r"\b(?:defaulted|default|breached)\b[^.!?]{0,80}\b(?:debt|loan|covenant)\b"
        r"|\b(?:liquidity crisis|difficulty servicing (?:its )?debt|credit stress)\b",
        re.I,
    ),
    "credit_positive": re.compile(
        r"\b(?:refinanced|repaid|paid down)\b[^.!?]{0,80}\b(?:debt|loan|facility)\b"
        r"|\b(?:credit rating|rating)\b[^.!?]{0,60}\b(?:upgraded|upgrade)\b",
        re.I,
    ),
}

DIRECTIONS = {
    "new_contract": "positive",
    "customer_loss": "negative",
    "product_launch": "positive",
    "market_expansion": "positive",
    "hiring": "positive",
    "layoff": "negative",
    "credit_positive": "positive",
    "credit_stress": "negative",
}


def sentences(text: str) -> list[str]:
    """Split source blocks conservatively while retaining evidence text."""
    protected = re.sub(
        r"\b(Co|Inc|Corp|Ltd|LLC|U\.S)\.",
        lambda match: match.group(0).replace(".", "<DOT>"),
        text,
        flags=re.I,
    )
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return [part.replace("<DOT>", ".").strip() for part in parts if part.strip()]


def extract_page_events(record: dict, page: dict) -> list[Event]:
    """Extract validated events from one dated article page."""
    if page.get("category") != "article":
        return []
    event_date = page.get("published_date")
    precision = page.get("published_date_precision", "unknown")
    unknown_reason = None if event_date else "No explicit publication date was found in the listing link."
    found: list[Event] = []
    seen: set[tuple[str, str]] = set()
    evidence_blocks = [page.get("raw_title", ""), page.get("raw_meta", "")]
    evidence_blocks.extend(page.get("raw_blocks", []))
    for block in evidence_blocks:
        for sentence in sentences(block):
            for event_type, pattern in RULES.items():
                if not pattern.search(sentence):
                    continue
                key = (event_type, sentence.casefold())
                if key in seen:
                    continue
                seen.add(key)
                found.append(Event(
                    IQ_COMPANY_ID=record["IQ_COMPANY_ID"],
                    company_name=record["company_name"],
                    event_type=event_type,
                    direction=DIRECTIONS[event_type],
                    event_date=event_date,
                    event_date_precision=precision if event_date else "unknown",
                    retrieved_at=page["fetched_at"],
                    source_url=page["source_url"],
                    source_text=sentence,
                    confidence=0.80,
                    extraction_method="rule",
                    unknown_reason=unknown_reason,
                ).validate())
    return found


def extract_record(record: dict) -> tuple[list[Event], dict]:
    """Extract all article events and return an inspectable audit summary."""
    events: list[Event] = []
    page_audit = []
    for page in record.get("pages", []):
        if page.get("category") != "article":
            continue
        page_events = extract_page_events(record, page)
        events.extend(page_events)
        page_audit.append({
            "page_id": page.get("page_id"),
            "source_url": page.get("source_url"),
            "published_date": page.get("published_date"),
            "event_count": len(page_events),
            "status": "events_found" if page_events else "abstained_no_rule_match",
        })
    audit = {
        "IQ_COMPANY_ID": record.get("IQ_COMPANY_ID"),
        "company_name": record.get("company_name"),
        "article_count": len(page_audit),
        "event_count": len(events),
        "pages": page_audit,
    }
    return events, audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-record", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.page_record.read_text(encoding="utf-8"))
    events, audit = extract_record(record)
    write_events_jsonl(events, args.events)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{audit['company_name']}: {len(events)} events from {audit['article_count']} articles")


if __name__ == "__main__":
    main()
