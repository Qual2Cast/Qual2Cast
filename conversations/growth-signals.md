# Handoff: growth-signals foundation

## What was agreed

- Keep `website_scrape/` focused on company descriptions and similarity.
- Build growth signals as a separate pipeline and branch so News/Press/Careers page
  rules cannot alter the current scraper or its saved outputs.
- Reuse stable fetching, robots.txt, fallback, source logging, and company-ID
  conventions where possible.
- Treat the growth model as a separate or complementary way to identify
  comparable companies.

## Completed

- Created branch `growth-signals` in an isolated worktree.
- Added `growth_signals/schema.py` with a strict, source-backed event record.
- Added deterministic discovery of same-site News, Press, Careers, and Jobs
  links from saved HTML.
- Added a fetch adapter that reuses HTTP, rendered-browser, stealth, Wayback,
  robots.txt, and bot-page handling without changing the current scraper or
  writing to its output directory.
- Growth-signal extraction reads unfiltered source text so hiring, dates, and
  credit-stress evidence are retained.
- Added a company-level collection command that loads the approved snapshot,
  discovers event pages from each homepage, saves raw HTML, and archives prior
  company records rather than overwriting them.
- Added cutoff-safe feature aggregation for 365-, 730-, and 1,095-day windows.
- Added tests for schema validation, link discovery, event windows, undated
  records, and exclusion of post-cutoff events.
- Documented the pipeline boundary, event taxonomy, output schema, and usage.

## Checks

- 51 direct test functions passed using the available Anaconda environment.
- Python compilation passed for all new modules and tests.
- `git diff --check` passed.
- The machine's normal pytest entry point is currently affected by a broken
  Anaconda `conda-libmamba-solver` shared-library installation; the code itself
  imports and the direct tests run successfully.

## Data version

- No source data was read or modified in this milestone.
- The repository still requires `company_list_v3` when company collection is
  connected.
- Live PCTY validation on 2026-10-18 confirmed the plain HTML response is a
  Cloudflare verification shell while rendered Chromium retrieves the real
  homepage, blog landing page, and Careers page. Challenge detection now
  requires both a challenge marker and sparse visible content, so embedded
  Cloudflare scripts on a real page do not cause a false rejection.
- Article discovery now follows same-site News/Press listing links, retains
  dates stated in their anchor text without guessing, and fetches a bounded
  number of recent articles. A live PCTY run saved three dated articles with
  rendered HTML, complete text, source URLs, and raw provenance.
- Added a high-precision rule extractor with exact evidence and one audit row
  per article. Positive, negative, duplicate, undated, non-article, and
  marketing-language controls are covered. A nine-article live PCTY review
  exposed and fixed a false layoff match caused by "reducing repetitive data
  entry ... for employees." The final output contains one supported product
  launch ("Introducing Paylocity Ignite AI," 2026-07-21) and eight explicit
  abstentions.
- Completed a five-company pilot (PCTY, BV, HRI, PRGS, WING): all five yielded
  specific articles, for 22 total and 21 with explicit dates. Manual evidence
  review retained four events. Dynamic-shell rejection enables rendered
  fallback for HRI; a constrained, same-company official-IR fallback recovers
  WING when its homepage has no News/Press entry. Media assets and investor
  calendars are excluded, article-body dates override link-text dates, and
  duplicated title evidence is collapsed. See `growth_signals/sample_evaluation.md`.
- WING's HTML News archive lists 2015 entries first and exposes no HTML
  pagination. Its page does explicitly declare a same-company WordPress API;
  a bounded, date-descending API request now supplies five latest 2026 article
  URLs and dates while each article's official HTML remains the evidence
  source. The API response is retained with raw provenance and robots.txt is
  honored. The revised pilot contains 24 articles, 23 dated, and three accepted
  events; reviewed WING product/promotional language remains conservatively
  abstained pending guarded recall rules.

## Unresolved

- The first collector discovers only same-site and company-subdomain links.
  Third-party job boards such as Workday or Greenhouse need an attribution and
  allow-list policy before collection.
- Product-launch recall for `arrives nationwide`, `new ... available`, and
  `first-ever` needs guarded rules and negative controls. Undated Careers pages
  still need policy.
- Historical revenue outcomes and cutoff dates have not been added.
- The repository's existing rule against 10-K and financial matching inputs
  may need revision after the mentor's latest clarification that private-target
  LTM revenue, LTM EBITDA, and debt may be used for scale matching and that
  public-comparable details may be used in similarity scoring. That decision
  should be recorded separately from the growth-signal feature rules.

## Next recommended action

Run the collector for one company, inspect its page record and raw files, then
finalize the page/date schema before any full-company run.
