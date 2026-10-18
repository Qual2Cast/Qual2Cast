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
- Added cutoff-safe feature aggregation for 365-, 730-, and 1,095-day windows.
- Added tests for schema validation, link discovery, event windows, undated
  records, and exclusion of post-cutoff events.
- Documented the pipeline boundary, event taxonomy, output schema, and usage.

## Checks

- 11 direct test functions passed using the available Anaconda environment.
- Python compilation passed for all new modules and tests.
- `git diff --check` passed.
- The machine's normal pytest entry point is currently affected by a broken
  Anaconda `conda-libmamba-solver` shared-library installation; the code itself
  imports and the direct tests run successfully.

## Data version

- No source data was read or modified in this milestone.
- The repository still requires `company_list_v3` when company collection is
  connected.

## Unresolved

- The fetch adapter is connected, but the company-level collection command
  still needs to combine homepage discovery, event-page fetching, and a saved
  page manifest.
- Event-date extraction needs a clear policy for page dates, article metadata,
  archive dates, and undated Careers pages.
- Historical revenue outcomes and cutoff dates have not been added.
- The repository's existing rule against 10-K and financial matching inputs
  may need revision after the mentor's latest clarification that private-target
  LTM revenue, LTM EBITDA, and debt may be used for scale matching and that
  public-comparable details may be used in similarity scoring. That decision
  should be recorded separately from the growth-signal feature rules.

## Next recommended action

Add a company-level collection command that discovers and saves News, Press,
and Careers pages under `outputs-local/growth_signals/`, then finalize the
page/date schema before any full-company run.
