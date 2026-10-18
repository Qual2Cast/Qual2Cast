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
- `collect_events.py`: deterministic discovery of News, Press, Careers, and
  Jobs links from saved HTML. Network fetching will reuse the existing fetch
  layer in the next milestone.
- `build_features.py`: converts dated event records into company features for
  a specified cutoff date without using future events.
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
  "unknown_reason": null
}
```

`event_date_precision` is explicit because some sources provide only a month
or year. Records with no usable event date should be retained with
`event_date` set to null and an `unknown_reason`, but they are excluded from
cutoff-based features.

## Run tests

```bash
cd growth_signals
python -m pytest tests -q
```

## Build features

```bash
python build_features.py \
  --events outputs-local/growth_signals/events/events.jsonl \
  --cutoff-date 2024-12-31 \
  --output outputs-local/growth_signals/features/features_2024-12-31.csv
```

The feature builder uses only events on or before the cutoff date and reports
the number of undated records separately.
