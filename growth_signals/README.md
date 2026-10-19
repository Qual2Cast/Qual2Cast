# Growth signals

This directory is the growth-signals pipeline for dated company events. It is
separate from `website_scrape/`, which describes what a company does for the
comparable-company model. This pipeline records what changed, when it changed,
and where the evidence came from.

## Scope

The first event taxonomy is intentionally small:

- `new_contract`, `customer_loss`
- `product_launch`, `market_expansion`
- `hiring`, `layoff`
- `credit_positive`, `credit_stress`

Every event has an observation date, source URL, retrieved timestamp,
supporting text, extraction confidence, and a stable company ID. Missing or
ambiguous facts are not guessed.

The current `website_scrape/` outputs are not modified. Shared fetching
utilities may be imported, but growth signals uses separate page-selection rules and
writes only under `outputs-local/growth_signals/`.

## Planned flow

```text
company name + website
        |
        v
News / Press / Careers page discovery
        |
        v
raw pages + dated source records
        |
        v
structured Event records
        |
        v
features at a historical cutoff date
        |
        v
future 3-year revenue-growth outcome
        |
        v
time-split model evaluation
```

## Implemented in this first milestone

- `schema.py`: validated event record and JSONL helpers.
- `fetch_adapter.py`: reuses the existing HTTP, rendered-browser, stealth,
  Wayback, robots.txt, and bot-page handling while saving separate raw pages.
- `collect_events.py`: deterministic discovery of News, Press, Careers, and
  Jobs links from saved HTML, plus latest-article metadata from a same-company
  WordPress API only when the page explicitly declares that endpoint.
- `collect_company_pages.py`: reads the company snapshot, fetches each
  homepage, discovers event pages and dated article links, saves raw HTML, and
  writes a company-level page record without overwriting prior records.
- `build_features.py`: converts dated event records into company features for
  a specified cutoff date without using future events.
- `build_outcomes.py`: computes exact one-, two-, and three-year revenue
  growth outcomes from a separate long-form annual revenue file. Missing years
  remain missing and are never replaced by a later observation.
- `extract_events.py`: high-precision rule extraction from article pages with
  exact source evidence and a per-article audit trail. It abstains when no
  explicit event phrase is present.
- `sample_evaluation.md`: evidence and remaining coverage gaps from the first
  five-company live pilot.
- `tests/`: schema, link-discovery, and look-ahead tests.

## Event JSONL format

One event per line:

```json
{
  "schema_version": 1,
  "IQ_COMPANY_ID": "IQ254957567",
  "company_name": "Paylocity Holding Corporation",
  "event_type": "hiring",
  "direction": "positive",
  "event_date": "2024-04-15",
  "event_date_precision": "day",
  "retrieved_at": "2024-04-20T14:30:00Z",
  "source_url": "https://example.com/careers",
  "source_text": "The company is hiring implementation consultants.",
  "confidence": 0.86,
  "extraction_method": "llm",
  "signal_duration": "durable",
  "unknown_reason": null
}
```

`event_date_precision` is explicit because some sources provide only a month
or year. Records with no usable event date should be retained with
`event_date` set to null and an `unknown_reason`, but they are excluded from
cutoff-based features.

`signal_duration` is `temporary`, `durable`, or `unknown`. The extractor uses
only explicit article evidence: limited-time/sold-out language marks a launch
temporary, while product objects such as platforms and services or explicit
integration into a platform mark it durable. Older records without this field
remain valid and default to `unknown`.

## Run tests

```bash
cd growth_signals
python -m pytest tests -q
```

## Fetch adapter

```python
from pathlib import Path

from fetch_adapter import build_clients, close_clients, fetch_page, raw_text_fields, save_raw_page

clients = build_clients(["html", "rendered", "wayback"])
try:
    page = fetch_page("https://example.com/news", clients)
    provenance = save_raw_page(
        page,
        Path("outputs-local/growth_signals"),
        company_id="IQ1",
        page_id="P1",
    )
    text = raw_text_fields(page.html)
finally:
    close_clients(clients)
```

Use `raw_title`, `raw_meta`, and `raw_blocks` for event extraction. The
existing cleaned fields are designed for company descriptions and may remove
dated hiring, financial stress, and other growth signals.

## Collect company pages

Run one company first:

```bash
python collect_company_pages.py --tickers PCTY --methods html rendered wayback \
  --max-articles 3
```

Outputs are written under `outputs-local/growth_signals/`:

```text
raw_html/<IQ_ID>/<timestamp>/<method>/P<n>.html.gz
page_records/<IQ_ID>.json
page_records_history/<IQ_ID>_<timestamp>.json
```

The homepage is `P1`; later pages are discovered News, Press, Careers, or
Jobs pages followed by specific articles discovered from News or Press landing
pages. When a page declares a same-company WordPress API, a bounded request for
latest posts supplies URLs and dates; article evidence is still fetched from
the official HTML page. Article-body dates take priority over listing dates,
and missing dates remain unknown rather than being guessed. Re-running a
company moves its previous page record to history.
Cloudflare and browser-verification shells are rejected and trigger the next
configured fetch method. Event pages that redirect to the same final URL are
saved only once.

## Extract events

Extract candidate events and retain an audit row for every article:

```bash
python extract_events.py \
  --page-record ../outputs-local/growth_signals/page_records/IQ254957567.json \
  --events ../outputs-local/growth_signals/events/IQ254957567.jsonl \
  --audit ../outputs-local/growth_signals/audit/IQ254957567.json
```

Only specific article pages are eligible. Generic Careers pages and broad
marketing phrases do not create events. The first rule set favors precision
and abstention; its output remains candidate evidence for human review, not a
claim that the event is automatically validated.

## Build features

```bash
python build_features.py \
  --events outputs-local/growth_signals/events/events.jsonl \
  --cutoff-date 2024-12-31 \
  --output outputs-local/growth_signals/features/features_2024-12-31.csv
```

The feature builder uses only events on or before the cutoff date and reports
the number of undated records separately. Each window retains the total
`product_launch` count plus separate temporary, durable, and unknown-duration
counts. No arbitrary fixed weight is imposed; downstream validation can learn
or select the appropriate weighting.

## Build revenue-growth outcomes

The current 560-company snapshot contains only one revenue observation per
company, so it cannot supply future growth labels. Provide a separate annual
revenue CSV with these columns:

```text
IQ_COMPANY_ID,company_name,fiscal_year,revenue
```

Then build outcomes for a historical fiscal-year cutoff:

```bash
python build_outcomes.py \
  --annual-revenue outputs-local/growth_signals/annual_revenue.csv \
  --cutoff-fiscal-year 2022 \
  --output outputs-local/growth_signals/outcomes/outcomes_2022.csv
```

The builder requires an exact cutoff-year observation and calculates each
horizon only from the exact future fiscal year. It rejects duplicate
company-year rows, conflicting company names, negative revenue, and a zero
cutoff revenue. Build features and outcomes independently, then join them by
`IQ_COMPANY_ID` for modeling.
