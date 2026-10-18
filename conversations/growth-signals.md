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

- 15 direct test functions passed using the available Anaconda environment.
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

- After merging `main` commit `be2bb3a`, the newly committed snapshot files do
  not match the SHA256 values in `data_manifest.json`. The required v3 file is
  `d4d6cc109cda...`, while the manifest expects `3ab9a43e7426...`.
  `snapshot_path()` correctly refuses to load it. Do not bypass the check;
  the team should confirm whether the committed files changed through line
  endings/export and then publish matching authoritative files or checksums.
- The first collector discovers only same-site and company-subdomain links.
  Third-party job boards such as Workday or Greenhouse need an attribution and
  allow-list policy before collection.
- Event-date extraction needs a clear policy for page dates, article metadata,
  archive dates, and undated Careers pages.
- Historical revenue outcomes and cutoff dates have not been added.
- The repository's existing rule against 10-K and financial matching inputs
  may need revision after the mentor's latest clarification that private-target
  LTM revenue, LTM EBITDA, and debt may be used for scale matching and that
  public-comparable details may be used in similarity scoring. That decision
  should be recorded separately from the growth-signal feature rules.

## Next recommended action

Run the collector for one company, inspect its page record and raw files, then
finalize the page/date schema before any full-company run.
