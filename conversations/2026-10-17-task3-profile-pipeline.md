# Handoff: Task 3 profile pipeline (2026-10-17)

> **Files renamed later the same day** (this note keeps the original names):
> `scrape_sites.py` → `step1_scrape_websites.py`, `extract_profiles.py` →
> `step2_extract_profiles.py`, `audit_profiles.py` → `step3_audit_profiles.py`,
> `profile_models.py` → `profile_schema.py`; outputs grouped into
> `outputs-local/task3/step1_scrape/`, `step2_extract/`, `step3_audit/`,
> `final_tables/`, `logs/`; snapshots `company_list_v2_sic_fixed.csv` and
> `company_list_v3_websites_fixed.csv`. Current names: PROJECT_STATE.md and
> docs/data_dictionary.md.

Work done in Claude Code. The full session transcript can be added next to
this file with Claude Code's `/export`. This file is the summary.

## What was asked

- Replace the 12 hand-written company descriptions with fully programmatic
  collection, reusing the scraper from
  https://github.com/mwc2150/everlane-sustainability-analysis.
- Collect description, products/services, customers, business model and
  similar attributes for all 560 companies, with sources; mark unknowns
  instead of guessing; keep financial fields apart from matching inputs.
- Fix the BrightView SIC error; cap scraping at 3 pages; keep raw and
  processed data separately (keep every stage); use Codex CLI (student
  ChatGPT sign-in) instead of paid API calls; follow the professor's shared
  project layout.

## Completed

- `src/prepare_company_list.py` builds snapshot `company_list_v2` from the raw
  list: SIC codes zero-padded, 2/3-digit re-derived. Only BrightView changed
  (700 → 0700, Agricultural Services). Checksums are in data_manifest.json.
- `p087_task3_descriptions/scrape_sites.py`: homepage + 2 pages per company;
  falls back html → Playwright → undetected-chromedriver → Wayback; honors
  robots.txt; keeps raw HTML, raw text, cleaned text, and a log of every
  removed sentence.
- Fixed a parsing bug in `collect_descriptions.py` that deleted whole pages
  (body / ASP.NET form / React root with "menu"/"search" in class names). It
  caused most of the old "thin" results.
- `p087_task3_descriptions/extract_profiles.py`: Codex (`codex exec
  --output-schema ... -o ...`) reads the cleaned pages and fills in
  structured fields with sources and verbatim quotes. The script checks the
  quotes against the pages, masks company and brand names, drops financial
  mentions, records page relevance, and writes `matching_inputs.csv` (no
  financials) and `financial_fields.csv` (financials only).
- Repo layout: AGENTS.md, PROJECT_STATE.md, docs/, conversations/, src/,
  data_manifest.json; data-local/ and outputs-local/ are git-ignored.

## Test results

- Scraper on SIC 35 (6-page version): 37/38 sites read automatically,
  including all 12 that were hand-written before. Resolute Holdings' site is
  only 111 words in total.
- 3-page version tested on BrightView, Kadant (needed stealth Chrome), and
  Timken: raw HTML, raw/clean text and removal logs saved as intended.
- Extraction tested end to end with a stand-in `codex` executable: flags,
  schema file, stdin prompt, output file, quote verification (an invented
  quote → `unverified`), dollar-figure removal, masking, history archiving,
  and both CSVs. **Not yet run with a real Codex sign-in.**
- On the first 116 companies, 3 pages captured nearly as much as 6 (keyword
  check: customers mentioned for 101 vs 105 companies, markets 90 vs 96).

## Data version

company_list_v2 (sha256 3066d54a…; see data_manifest.json).

## Unresolved

- No real Codex run yet: check output quality, masking, and how many calls
  one student's allowance covers.
- Data maintainer and snapshot storage location not yet decided.
- Old `descriptions.csv` / `text/` (Richard's version) are still in the repo;
  they are superseded but kept for history.

## Next recommended action

1. Check `outputs-local/task3/scrape_log.csv` once the full scrape finishes.
2. A student with Codex signed in runs `python extract_profiles.py --sic2 35`
   and reviews ~10 profiles before the full run.
