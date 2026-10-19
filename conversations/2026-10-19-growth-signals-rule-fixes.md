# Handoff: growth-signal rule and collection fixes

Branch `growth-signals-recall`, uncommitted (waiting for review).

## Why

A hand-labeled check of the five pilot companies (36 articles, 6 careers/jobs
pages) found 7 of 16 true events, with 2 false positives: a Paylocity award
article read as hiring ("creating an environment where employees ..."), and a
Wingstop AUV definition read as expansion ("influenced by opening new
restaurants"). Most misses were noun forms ("the introduction of ...",
"national launch of ..."), "N net new openings", base-form "expand", and
"expanding our salesforce". Reviewer screenshots asked for the same areas.

## What changed

- `extract_events.py`
  - Hiring: numbers or jobs/positions/roles required after add/create (fixes
    the award false positive); occupational objects; sales force/sales team
    growth. Layoffs: "will lay off", "cutting about 5% of its workforce",
    workforce reduction, RIF.
  - Expansion: base-form "expand", "N (net) new openings", more site objects
    (branches, distribution centers, clinics, units).
  - Product launch: noun forms, "new additions:", "is introducing <Name>",
    "newest ... flavor", sentence-initial "The new X agent"/"New X agents".
  - Credit: raised/lowered rating, outlook to positive/negative, forbearance
    agreement, Chapter 11.
  - Contracts: financing/legal agreements (credit, forbearance, merger) are
    excluded. Customer loss: "a lost customer" and generic churn prose no
    longer match.
  - Text that is not the article's own is dropped: blocks on 3+ pages of the
    same company, "About <other company>" blocks, metric definitions and
    forward-looking-statement sentences. Undated `/insights/` and
    `/resources/` pages are skipped as marketing content.
  - New `event_status` (planned/completed/unknown) and `via_ir_fallback`.
- `schema.py`: `quarter` precision; `event_status`, `via_ir_fallback` with
  backward-compatible defaults.
- `collect_events.py`: day-first and ISO dates; month/quarter only from date
  markup or link text, stored as the period's last day; wider article paths;
  short link labels only; industry/product/solution and job-site pages are
  not event pages.
- `collect_company_pages.py`: `--max-articles` 25, `--max-listing-pages` 3,
  IR-fallback pages and articles tagged, `ir_fallback_article_count`.

## Checks

- `cd growth_signals && python -m pytest tests -q`: 132 passed (was 84).
- Saved 2026-10-19 page records for PCTY, WING, HRI, PRGS, BV against hand
  labels (article x event type): before 9 extracted, 7 correct, 16 true
  (precision 78%, recall 44%); after 16/16/16. This is in-sample: the rules
  were written against these misses, so it is not a generalization estimate.
- Held-out live run (scratch output, not outputs-local): CSGS, GEF, WMK.
  The first two passes exposed mega-menu misclassification and false events
  (2, then 4, all undated, all on CSG marketing pages); after the fixes, 0
  events. But CSG yielded only undated insights posts, Greif no
  articles, and Weis's homepage failed, so the held-out set says little about
  recall.

## Data version

- `company_list_v3`. No source data modified. Pilot page records in
  `outputs-local/growth_signals/` were read, not rewritten.

## Unresolved

- History depth: dates reach back only months. Sitemaps hold years (BV 180
  press releases from 2020, Wingstop IR 390 from 2016) but are not used yet.
- (Resolved in round 2: sentence-level counting, other-company actions,
  acquisition/funding/guidance types.) Still open: capex increase as a type.
- Job boards, rating agencies, Wayback history: not added (need policy).

## Round 2 (same day): extraction only

User asked to get extraction right before any collection or history work.

Changed:

- One event per (article, event type); extra sentences go to
  `supporting_text`, so feature counts are article counts.
- Actor check: a named actor directly before the matched action that is not
  the company (name words, website label, we/our/the Company) rejects the
  sentence; the audit lists it under `rejected`. Credit events exempt
  (rating agencies act on the company).
- New types, schema version 2 (version 1 still loads): `acquisition`,
  `divestiture`, `funding_round`, `guidance_raised`, `guidance_lowered`,
  each with positive and negative tests.
- 169 tests pass.

Evaluation (labels written before running the extractor; rules frozen for
the held-out runs, misses listed for the next round, not tuned):

| set | articles | precision | recall |
|---|---:|---:|---:|
| Pilot (training, regression) | 36 | 18/18 | 18/18 |
| Held-out B: older BV/WING sitemap articles | 28 | 6/10 = 60% | 6/19 = 32% |
| Held-out A: 10 new companies (6 small), own-site dated articles | 103 | 12/20 = 60% | 12/31 = 39% |

Main findings: a structural bug (every `[^.!?]` window stops at the decimal
point in "$2.2 million"), missing noun and present-tense forms ("closing of
its acquisition", "Partners with", "secures"), title-only articles, and
false positives from generic prose ("to hire ... people", industry
statistics, "the company" naming another firm). Only 13 of 32 sampled
companies had 7+ dated own-site articles.

Labels, held-out page records, miss lists and scorers are in
`outputs-local/growth_signals/eval_2026-10-19/` (not committed).

## Next recommended action

Fix the decimal-window bug and the listed misses, then score on a NEW
held-out sample (not the two used here) to check the fixes generalize.

## Round 3 (same day): generalization fixes and a fresh held-out

- Rule windows no longer stop at decimals or abbreviations ("$2.2 million",
  "Inc.", "U.S."): matching runs on a same-length copy with those periods
  masked, so evidence text is unchanged.
- Broader patterns: present-tense awards and partnerships, noun forms of
  launches/acquisitions/divestitures, openings and footprint expansion with a
  destination, repricing and credit-agreement amendments, passive "Acquired
  by <the company>". Exclusions: plan of merger, share repurchase, securities
  offerings, taglines, credit facilities, "expand access", capabilities,
  third-party statistics ("according to ..."), company About/Founded blocks.
- 211 tests pass.

| set | role | precision | recall |
|---|---|---:|---:|
| Pilot, held-out A, held-out B | now training (in-sample) | 100%, 88%, 95% | 100%, 97%, 100% |
| Held-out C: 10 fresh companies | blind, rules frozen | 58% (61% adjudicated) | 43% |

The in-sample gains generalized only slightly. Misses and the options for
the next round are in
`outputs-local/growth_signals/eval_2026-10-19/holdout_c_misses.md`.

## Round 4: LLM extraction

In progress, not in this commit.
