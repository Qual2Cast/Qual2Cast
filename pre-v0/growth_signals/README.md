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
- `acquisition`, `divestiture`, `funding_round`,
  `guidance_raised`, `guidance_lowered` (schema version 2)

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
- `edgar_revenue.py`: multi-year annual revenue from SEC EDGAR 10-K filings
  (XBRL company facts), used only as the growth-outcome answer, never as a
  feature or a target input.
- `extract_events.py`: high-precision rule extraction from article pages, plus
  hiring and layoff phrases on Careers/Jobs pages, with exact source evidence
  and a per-page audit trail. It abstains when no explicit event phrase is
  present.
- `sample_evaluation.md`: evidence and remaining coverage gaps from the first
  five-company live pilot.
- `eval/`: blind hand-labelled event sets (pilot and held-out A, B, C) and
  `score_rules.py`, which scores the rule extractor against them.
- `tests/`: schema, link-discovery, extraction, scoring, EDGAR, and look-ahead
  tests.

## Event JSONL format

One event per line:

```json
{
  "schema_version": 2,
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
  "event_status": "unknown",
  "via_ir_fallback": false,
  "supporting_text": [],
  "unknown_reason": null
}
```

`event_date_precision` is explicit because some sources provide only a month,
quarter, or year. Coarse dates (`October 2026`, `Q3 2026`) are accepted only
from date markup or listing link text, never from body text, and are stored as
the last day of the period so a cutoff never counts an event early. Day-first
(`18 October 2026`) and ISO dates give day precision; numeric slash dates are
ambiguous and stay unknown. Records with no usable event date should be retained with
`event_date` set to null and an `unknown_reason`, but they are excluded from
cutoff-based features.

`event_status` is `planned`, `completed`, or `unknown`, from explicit wording
in the evidence sentence ("plans to expand" is planned; "opened 3 previously
planned locations" is completed). `via_ir_fallback` is true when the page was
reached only through the conventional `ir.<domain>` host; private targets have
no IR site, so coverage should be reported with and without these events.
Older records without either field remain valid and get the defaults.

Each record is one event per article and event type: `source_text` is the
first supporting sentence in reading order (title, summary, body) and
`supporting_text` keeps up to five more from the same article, so feature
counts are article counts, not sentence counts. Schema version 2 added the
five new event types and `supporting_text`; version 1 records still load.

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
  --max-articles 25 --max-listing-pages 3
```

Outputs are written under `outputs-local/growth_signals/`:

```text
raw_html/<IQ_ID>/<timestamp>/<method>/P<n>.html.gz
page_records/<IQ_ID>.json
page_records_history/<IQ_ID>_<timestamp>.json
```

The homepage is `P1`; later pages are discovered News, Press, Careers, or
Jobs pages followed by specific articles discovered from News or Press landing
pages. Same-site `/stories/`, `/media-center/`, `/insights/`, `/resources/`,
`/announcements/` and `/company-news/` article paths are included, and
explicit listing `rel=next` or Next/Older continuations are followed up to
`--max-listing-pages` (default 3, counting the first) while more articles are
needed. Only short link labels (four words or fewer) classify a page, so
mega-menu descriptions do not; `/industries/`, `/products/`, `/solutions/`,
"job-site" equipment pages and "media and technology" industry pages are not
event pages. Pages reached through the IR-host fallback carry
`via_ir_fallback: true`, and the record reports `ir_fallback_article_count`. When a page declares a same-company WordPress
API, a bounded request for latest posts supplies URLs and dates; article
evidence is still fetched from the official HTML page. Article-body dates take
priority over listing dates, and missing dates remain unknown rather than
being guessed. Re-running a company moves its previous page record to history.
Cloudflare and browser-verification shells are rejected and trigger the next
configured fetch method. Event pages that redirect to the same final URL are
saved only once.

## Extract events

Extract candidate events and retain an audit row for every article:

```bash
python extract_events.py \
  --page-record ../../outputs-local/growth_signals/page_records/IQ254957567.json \
  --events ../../outputs-local/growth_signals/events/IQ254957567.jsonl \
  --audit ../../outputs-local/growth_signals/audit/IQ254957567.json
```

Specific article pages are eligible for the full taxonomy. Careers and Jobs
pages may yield only `hiring` or `layoff` events when an explicit workforce
action is present. Before matching, the extractor drops text that is not the
article's own: blocks repeated on three or more pages of the same company
(sidebars, teasers), "About <other company>" partner blocks, and sentences
that define a metric or carry forward-looking-statement boilerplate. Undated
pages under `/insights/` or `/resources/` are evergreen marketing content and
are skipped with audit status `skipped_undated_marketing_page`. Financing and
legal agreements (credit, forbearance, merger) are not customer contracts.

An event counts only when the company does the action. The extractor reads
the capitalized words directly before the matched action in the same clause
("In mid-2025, Telstra launched ..."); a different named actor rejects the
sentence and the audit lists it under `rejected` with
`other_actor: <name>`. The company's own name words, its website label
(`hercrentals`), "we", "our" and "the Company" keep the sentence. Credit
events are exempt because a rating agency is the expected actor. Acquisition
rules exclude "was acquired by", rumored or analyst-reported deals, and
"newly acquired" references to past deals; divestitures exclude "sold out"
and share sales; funding rounds exclude debt offerings and charity. Generic marketing phrases and undated job-board boilerplate
do not create events.

Sentence windows such as `[^.!?]{0,100}` do not stop at decimals
("$2.2 million"), abbreviations ("Inc.", "Sept.") or initialisms ("U.S."):
the extractor matches against a same-length copy where those periods are
masked, so evidence offsets still point at the original text. The company's
own "About ..." and "Founded in ..." boilerplate blocks are dropped, since they
repeat history rather than report the article's news. Further exclusions:
mergers, share buybacks, securities offerings and credit facilities are not
contracts or funding rounds, and third-party statistics ("according to ...",
other than the company itself) do not create events. The rule set still
favors precision and abstention; its output remains candidate evidence for
human review, not a claim that the event is automatically validated.

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

The 560-company snapshot has only one revenue figure per company, so future
growth labels come from SEC EDGAR. 10-K filings may be used; here they supply
only the answer the growth model is scored against, never a feature or an
input describing a target.

```bash
python edgar_revenue.py --contact "Qual2Cast research name@example.edu"
```

SEC requires a contact in the User-Agent: pass `--contact` or set
`SEC_CONTACT`. The contact is not stored in the repository. `--tickers` and
`--limit` run a subset. Each run writes a new folder
`outputs-local/growth_signals/edgar/<UTC timestamp>/` with:

- `annual_revenue.csv`: one row per company and fiscal year (the calendar
  year the period ends), from 10-K facts covering about 12 months. Revenue is
  the largest of several total-revenue concepts, because
  `RevenueFromContractWithCustomer...` can exclude rental or interest income.
  Each row keeps the concept, form, filing date, accession number and a link
  to the filing. The first-filed value is used; a later restatement is kept
  in `revenue_latest`. Year-over-year changes beyond +/-50% get a
  `review_flag` for a person to check (a spin-off or a reused CIK, for
  example); they are not corrected.
- `coverage.csv`: per-company status (`ok`, `ticker_not_in_sec_list`,
  `no_companyfacts`, `no_10k_revenue`). Unmatched companies stay unknown.
- `raw/`: every SEC response, gzipped, as fetched.

The 2026-10-19 run found 10-K revenue for 518 of 560 companies. With a 2022
cutoff, 500 have the cutoff year and 488 a three-year growth label. 438 rows
across 211 companies carry a review flag. `annual_revenue.csv` already has the
`IQ_COMPANY_ID,company_name,fiscal_year,revenue` columns that
`build_outcomes.py` reads; it ignores the extra columns.

Then build outcomes for a historical fiscal-year cutoff:

```bash
python build_outcomes.py \
  --annual-revenue outputs-local/growth_signals/edgar/<run>/annual_revenue.csv \
  --cutoff-fiscal-year 2022 \
  --output outputs-local/growth_signals/outcomes/outcomes_2022.csv
```

The builder requires an exact cutoff-year observation and calculates each
horizon only from the exact future fiscal year. It rejects duplicate
company-year rows, conflicting company names, negative revenue, and a zero
cutoff revenue. Build features and outcomes independently, then join them by
`IQ_COMPANY_ID` for modeling.
