# Handoff: growth signals (Xiaozhe)

One record of the growth-signals work, 2026-10-18 to 2026-10-19.

The code described from "recall widening" onward lives on branch
`growth-signals-recall` until it is merged into main.

## Current status

- Branch `growth-signals-recall`; `cd growth_signals && python -m pytest
  tests -q` passes 218 tests (excluding the uncommitted LLM tests).
- Pipeline: collect News/Press/Careers pages per company, extract dated
  events with source quotes, build cutoff-safe features. Revenue-growth
  outcomes use multi-year 10-K revenue from SEC EDGAR
  (`edgar_revenue.py`), as labels only.
- Extraction is rule-based: one event per article and event type, an
  other-company actor check, 13 event types (schema version 2).
- On unseen companies the rules reach about 58-61% precision and 43% recall
  (held-out C below). Each round of rule fixes moved the unseen-data score
  only a few points.
- History covers only months, not the 3 years the outcome model needs.
- Next: decide the extraction approach (an LLM pass is in progress, not
  committed), then add years of history from sitemaps.

## 2026-10-18: foundation

Agreed:

- Keep `website_scrape/` focused on company descriptions and similarity;
  growth signals is a separate pipeline so News/Press/Careers rules cannot
  change the scraper or its outputs.
- Reuse the fetching, robots.txt, fallback, source logging and company-ID
  conventions.
- Treat the growth model as a separate or complementary way to find
  comparable companies.

Built:

- `schema.py`: strict, source-backed event record.
- Same-site News/Press/Careers/Jobs link discovery from saved HTML.
- Fetch adapter reusing HTTP, rendered browser, stealth, Wayback, robots.txt
  and bot-page handling, writing only under `outputs-local/growth_signals/`.
- Extraction reads unfiltered source text, so hiring, dates and
  credit-stress evidence are kept.
- Company collection command: loads the approved snapshot, discovers event
  pages, saves raw HTML, archives earlier records instead of overwriting.
- Cutoff-safe features for 365/730/1,095-day windows.
- Plain HTML for PCTY was a Cloudflare shell; rendered Chromium gets the real
  pages. Challenge detection needs both a challenge marker and sparse text, so
  real pages that embed Cloudflare scripts are not rejected.
- High-precision rule extractor with exact evidence and an audit row per
  article. A false layoff match ("reducing repetitive data entry ... for
  employees") was fixed.
- Five-company pilot (PCTY, BV, HRI, PRGS, WING): 24 articles, 23 dated,
  seven reviewed events (`growth_signals/sample_evaluation.md`). Rendered
  fallback recovers HRI; a same-company `ir.<domain>` fallback recovers WING
  (useful for public companies only).
- WING's archive lists 2015 first; when a page declares a same-company
  WordPress API, a bounded latest-posts request supplies 2026 article URLs,
  while the article HTML stays the evidence.
- `signal_duration`: explicit limited-time wording marks a launch
  temporary; explicit platform/service objects mark it durable. Feature
  windows keep the counts separate; no fixed weight.

Settled since: the 10-K / financial-input question is decided in
PROJECT_STATE.md (Aziz's reply, 2026-10-19).

## 2026-10-18: recall widening

The first rules missed common press-release wording.

- Wider action + object rules for contracts, hiring, layoffs, expansion and
  credit, still abstaining on marketing language and job-board boilerplate.
- Careers/Jobs pages may yield only `hiring` or `layoff`.
- Article paths include `/stories/` and `/media-center/`; one listing
  continuation (`rel=next`, Next/Older) is followed; `--max-articles` 10.

## 2026-10-19: rule fixes (round 1)

A hand-labeled check of the pilot (36 articles, 6 careers/jobs pages) found
7 of 16 true events, with 2 false positives (an award article read as
hiring; an AUV definition read as expansion).

- Extractor: numbered or job-object hiring; more layoff forms; base-form
  "expand" and "N net new openings"; launch noun forms; credit rating
  verbs, outlooks, forbearance, Chapter 11; financing/legal agreements are
  not contracts; text that is not the article's own is dropped (blocks on
  3+ pages, partner "About" blocks, metric definitions, forward-looking
  statements); undated `/insights/` and `/resources/` pages skipped.
- `event_status` (planned/completed/unknown) and `via_ir_fallback`, with
  backward-compatible defaults; `quarter` date precision.
- Collector: day-first and ISO dates; month/quarter dates only from markup or
  link text, stored as the period's last day (no counting an event early);
  wider article paths; short link labels only; industry/product/job-site
  pages excluded; `--max-articles` 25, `--max-listing-pages` 3.
- A held-out live run (CSGS, GEF, WMK) exposed mega-menu misclassification;
  fixed.

## 2026-10-19: extraction (round 2)

The user asked to get extraction right before collection or history work.

- One event per (article, event type); other sentences go to
  `supporting_text`, so feature counts are article counts.
- Actor check: a named actor before the matched action that is not the
  company rejects the sentence (logged under `rejected`); credit events are
  exempt because rating agencies act on the company.
- Schema version 2 adds `acquisition`, `divestiture`, `funding_round`,
  `guidance_raised`, `guidance_lowered`; version 1 records still load.

## 2026-10-19: rule generalization (round 3)

- Rule windows no longer stop at decimals or abbreviations ("$2.2 million",
  "Inc.", "U.S."): matching runs on a same-length copy with those periods
  masked, so evidence text is unchanged.
- Broader patterns: present-tense awards and partnerships, noun forms of
  launches/acquisitions/divestitures, openings and footprint expansion with a
  destination, repricing and credit-agreement amendments, passive "Acquired
  by <the company>". Exclusions: plan of merger, share repurchase, securities
  offerings, taglines, credit facilities, "expand access", capabilities,
  third-party statistics ("according to ..."), company About/Founded blocks.

## 2026-10-19: revenue outcomes from SEC EDGAR

10-K filings may be used. The snapshot has one revenue figure per company,
so `edgar_revenue.py` builds the multi-year revenue that `build_outcomes.py`
turns into growth labels. It is the answer the model is scored against,
never a feature or a target input.

- Ticker -> CIK from SEC `company_tickers.json` (class shares such as
  `ARTN.A` also tried as `ARTNA`/`ARTN-A`); one XBRL company-facts JSON per
  company, saved raw.
- Annual 10-K facts covering 330-400 days; fiscal year = calendar year the
  period ends; a changed fiscal year end keeps the later-ending period.
- Revenue is the largest of seven total-revenue concepts per year, because
  `RevenueFromContractWithCustomer...` can exclude rental or interest income
  (Herc 2023: $600M contract revenue vs $3.3B total).
- First-filed value used; the latest restatement is kept alongside. Every
  row has concept, form, filing date, accession and filing link.
- Year-over-year changes beyond +/-50% are flagged for review, not corrected.
- The SEC contact is passed at run time and not stored in the repository.
- Run `20261019T220622Z`: 518 of 560 companies with 10-K revenue (36
  tickers not in SEC's list, 6 with no 10-K revenue). With a 2022 cutoff,
  500 have the cutoff year and 488 a three-year growth label; 438 rows
  across 211 companies are flagged.
- `tests/test_edgar_revenue.py`: six offline tests.

## Evaluation

Labels were written before running the extractor, and the rules were frozen
for each held-out run; misses were fixed only in the next round. Scores
count (article, event type) pairs.

| set | when scored | precision | recall |
|---|---|---:|---:|
| Pilot, 5 companies | round 1, in-sample | 16/16 | 16/16 |
| Held-out B: older BV/WING sitemap articles | round 2, unseen | 60% | 32% |
| Held-out A: 10 new companies | round 2, unseen | 60% | 39% |
| Held-out C: 10 more new companies | round 3, unseen | 58% (61% adjudicated) | 43% |

After round 3, the pilot and held-outs A and B were used for tuning (100%,
88% and 95% precision in-sample), so held-out C is the honest number.
Only 13 of 32 and 15 of 32 sampled companies had 7+ dated own-site articles.
Labels, page records, miss lists and scorers are in
`growth_signals/eval/2026-10-19/` (re-score with `python eval/score_rules.py`).

## Data version

`company_list_v3`; no source data modified.

## Unresolved

- History depth: dates reach back only months. Sitemaps hold years (BV 180
  press releases from 2020, Wingstop IR 390 from 2016) but are not used yet.
- Third-party job boards, rating agencies and Wayback history need an
  attribution/allow-list policy.
- Temporary-launch predictive value and finer durable launch subtypes.
- EDGAR revenue: review the 438 flagged rows (211 companies), and the 42
  companies with no 10-K revenue; choose the cutoff fiscal year(s).
- Capex increase as an event type.
- Collection defects: monthly archive listing pages and an RSS feed were
  saved as articles (held-out C).

## Next recommended action

Choose the extraction approach (rules alone, or the LLM pass in progress)
using held-out C and a fresh held-out sample, then add sitemap history so
event features reach back to the EDGAR outcome cutoff. Review the flagged
EDGAR years before using them as labels.
