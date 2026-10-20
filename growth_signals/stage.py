"""One interface for the teammate's rules, LLM extraction and their agreement.

Historical features require capture by the cutoff, not only an old date printed
on a page. The separate extraction benchmark can retain public-company pages.
"""

from datetime import date, datetime
import re
from pipeline.llm import object_schema, enum_schema
from matching.private_evidence import allowed_page, clean_text
from .schema import Event, EVENT_TYPES
from .extract_events import (
    extract_record,
    article_blocks,
    repeated_blocks,
    sentences,
    DIRECTIONS,
    ELIGIBLE_PAGE_CATEGORIES,
)
from .build_features import build_company_features

EVENT_SCHEMA = object_schema(
    {
        "events": {
            "type": "array",
            "items": object_schema(
                {
                    "event_type": enum_schema(sorted(EVENT_TYPES)),
                    "sentence_ids": {"type": "array", "items": {"type": "string"}},
                    "event_status": enum_schema(["completed", "planned", "unknown"]),
                    "signal_duration": enum_schema(["temporary", "durable", "unknown"]),
                }
            ),
        }
    }
)


class GrowthStage:
    METHODS = ("rules", "llm", "hybrid")

    def __init__(self, llm=None):
        self.llm = llm

    def _llm(self, record):
        events, audits = [], []
        excluded = repeated_blocks(record)
        for page in record.get("pages", []):
            if page.get("category") not in ELIGIBLE_PAGE_CATEGORIES:
                continue
            if self.llm is None:
                audits.append(
                    {"page_id": page["page_id"], "status": "llm_not_configured"}
                )
                continue
            parts = [
                s for b in article_blocks(record, page, excluded) for s in sentences(b)
            ]
            cards = {str(i): s for i, s in enumerate(parts)}
            answer = self.llm.complete(
                "growth_events_v1",
                {
                    "company": record["company_name"],
                    "category": page["category"],
                    "published_date": page.get("published_date"),
                    "sentences": cards,
                },
                EVENT_SCHEMA,
                "Extract concrete events involving this company, not industry commentary, customer activities, "
                "awards/rankings, definitions, general strategy or navigation. A dividend is not a product launch. "
                "A transaction being terminated is not a customer loss. Distinguish planned and completed events. "
                "Exclude events explicitly from an earlier reporting period. Careers/job pages may only yield "
                "hiring or layoff. Return at most one entry per event_type, cite exact sentence IDs; "
                "return an empty events list when none are supported. Do not predict growth.",
            )
            audit = {
                "page_id": page["page_id"],
                "status": answer["status"],
                "request_id": answer.get("request_id"),
                "rejected_events": 0,
            }
            seen = set()
            for row in (answer.get("data") or {}).get("events", []):
                kind, ids = row["event_type"], row["sentence_ids"]
                if (
                    not ids
                    or any(s not in cards for s in ids)
                    or kind in seen
                    or (
                        page["category"] in ("careers", "jobs")
                        and kind not in ("hiring", "layoff")
                    )
                ):
                    audit["rejected_events"] += 1
                    continue
                seen.add(kind)
                day = page.get("published_date")
                event = Event(
                    IQ_COMPANY_ID=record["IQ_COMPANY_ID"],
                    company_name=record["company_name"],
                    event_type=kind,
                    direction=DIRECTIONS[kind],
                    event_date=day,
                    event_date_precision=page.get("published_date_precision", "day")
                    if day
                    else "unknown",
                    retrieved_at=page["fetched_at"],
                    source_url=page["source_url"],
                    source_text=cards[ids[0]],
                    supporting_text=tuple(cards[s] for s in ids[1:]),
                    confidence=0.5,
                    extraction_method="llm",
                    unknown_reason=None
                    if day
                    else "No publication date; no inferred date.",
                    signal_duration=row["signal_duration"],
                    event_status=row["event_status"],
                    via_ir_fallback=bool(page.get("via_ir_fallback", False)),
                ).validate()
                events.append(event)
            audits.append(audit)
        return events, {
            "pages": audits,
            "confidence_note": "Fixed bookkeeping value 0.5; not calibrated probability",
        }

    def run(
        self,
        record,
        method="rules",
        cutoff="2026-10-19",
        target_mode="private",
        require_capture_by_cutoff=True,
    ):
        if method not in self.METHODS or target_mode not in (
            "private",
            "public_benchmark",
        ):
            raise ValueError("Unknown growth method or evidence policy")
        if record is None:
            return {
                "status": "missing_event_pages",
                "events": [],
                "features": [],
                "excluded_pages": [],
                "forecast": None,
                "method": method,
            }
        day = date.fromisoformat(cutoff)
        accepted, rejected = [], []
        for page in record.get("pages", []):
            reason = None
            url = page.get("source_url", "")
            if target_mode == "private" and (
                page.get("via_ir_fallback")
                or not allowed_page(url, page.get("category", ""))
                or re.search(r"(^|[./-])(ir|investor|investors)([./-]|$)", url, re.I)
                or re.search(
                    r"earnings|financial.results|quarterly.results|10-k|10-q", url, re.I
                )
            ):
                reason = "private_target_public_market_page"
            try:
                capture_day = datetime.fromisoformat(
                    page["fetched_at"].replace("Z", "+00:00")
                ).date()
            except (ValueError, KeyError):
                capture_day = None
            if require_capture_by_cutoff and (capture_day is None or capture_day > day):
                reason = "not_captured_by_cutoff"
            if reason:
                rejected.append(
                    {
                        "page_id": page.get("page_id"),
                        "source_url": url,
                        "reason": reason,
                    }
                )
            else:
                if target_mode == "private":
                    page = {**page}
                    for field in ("raw_title", "raw_meta"):
                        page[field] = clean_text(page.get(field, ""))[0]
                    page["raw_blocks"] = [
                        clean_text(b)[0] for b in page.get("raw_blocks", [])
                    ]
                accepted.append(page)
        filtered = {**record, "pages": accepted}
        if method in ("rules", "hybrid"):
            rules, rule_audit = extract_record(filtered)
        if method in ("llm", "hybrid"):
            generated, llm_audit = self._llm(filtered)
        if method == "rules":
            events, audit = rules, rule_audit
        elif method == "llm":
            events, audit = generated, llm_audit
        else:
            # Conservative agreement arm; a union would accumulate false positives.
            allowed = {(e.source_url, e.event_type) for e in generated}
            events = [e for e in rules if (e.source_url, e.event_type) in allowed]
            audit = {
                "rules": rule_audit,
                "llm": llm_audit,
                "combination": "article/type intersection",
            }
        llm_statuses = [
            p["status"]
            for p in (llm_audit.get("pages", []) if method != "rules" else [])
        ]
        status = (
            "incomplete_llm_run"
            if any(s != "ok" for s in llm_statuses)
            else "no_eligible_pages"
            if not accepted
            else "extracted"
        )
        return {
            "status": status,
            "method": method,
            "target_mode": target_mode,
            "events": [e.to_dict() for e in events],
            "features": build_company_features(events, day),
            "audit": audit,
            "eligible_pages": len(accepted),
            "excluded_pages": rejected,
            "forecast": None,
            "date_basis": "Publication date proxy; not verified transaction effective date",
            "coverage_note": "Missing pages/events do not imply no growth; no calibrated forecast or valuation adjustment",
        }
