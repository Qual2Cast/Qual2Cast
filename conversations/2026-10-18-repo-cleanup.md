# Handoff: repository cleanup (2026-10-18)

Work done in Claude Code. This file is the summary.

## What was asked

- Confirm that every company in the list was scraped, and describe what the
  scraped JSON files contain.
- The Codex extraction was started too early. Keep it, but separately.
- Drop the `p087_` and task-number names. "Task 3" (non-financial
  information) is covered by the scrape's filters, so it isn't a separate
  piece of work.
- Move everything except the website scrape into a "things we tried" folder,
  so work can start on the actual pipeline: matching method, results, sanity
  check, valuation, definitions/limitations.

## Answer on the scrape

All 560 companies were attempted; each has a `page_text/<IQ_ID>.json` and a
`scrape_log.csv` row. Statuses: 532 ok, 15 thin_content, 4 investor_site,
4 robots_disallowed, 4 http_403, 1 blocked. The JSON fields are documented in
website_scrape/README.md.

## New layout

| was | now |
|---|---|
| `p087_task3_descriptions/step1_scrape_websites.py` | `website_scrape/scrape_websites.py` |
| fetch/parse/filter part of `collect_descriptions.py` | `website_scrape/fetch_and_clean.py` (split out; old main() and description-building left behind) |
| filter tests in `tests/test_profile_schema.py` | `website_scrape/tests/test_fetch_and_clean.py` |
| `collect_descriptions.py`, `descriptions.csv`, `text/`, old README | `scraps/collect_descriptions_v0/` (git mv; script kept whole, only its `src/` import path changed) |
| `step2_extract_profiles.py`, `step3_audit_profiles.py`, `profile_schema.py`, their tests | `scraps/codex_profiles/` |
| `p087_task6_matching/` (all), `docs/comps_writeup.md` | `scraps/comps_first_pass/` (write-up as `comps_writeup_draft.md`) |
| `outputs-local/task3/step1_scrape/*` | `outputs-local/website_scrape/` (scrape logs in `logs/`) |
| `outputs-local/task3/{step2_extract,final_tables,step3_audit}`, `extract_*.log` | `outputs-local/scraps/codex_profiles/` (inner layout unchanged, so stored `llm_run_dir` paths still resolve) |
| `outputs-local/task6/` | `outputs-local/scraps/comps_first_pass/` |
| `outputs-local/archive/task3_2026-10-17_6page_partial/` | `outputs-local/scraps/scrape_6page_partial_2026-10-17/` |

Code changes beyond the moves:
- `scrape_websites.output_paths()` now lists only the scrape's folders.
- The Codex step has its own `output_paths()` and `DEFAULT_OUT`
  (`outputs-local/scraps/codex_profiles/`), and reads page text from the
  scrape.
- `comps_similarity.py` has `--scrape-out` and `--codex-out` in place of
  `--task3-out`.
- The notebook's path cells were updated (8 source lines; outputs left as
  they were).
- New READMEs: `website_scrape/README.md`, `scraps/README.md`,
  `scraps/codex_profiles/README.md` (taken from the old Task 3 README).
- Updated: root README layout, AGENTS.md (scraps rule), the data dictionary
  (scrape outputs only), PROJECT_STATE.md.
- Requirements split per folder. Pydantic is now listed; it was missing.

## Output path rewrite

Page-text JSONs store each page's raw HTML path, relative to the repo root.
After the move, the prefix `outputs-local/task3/step1_scrape/` was replaced
with `outputs-local/website_scrape/` (plain string replacement, nothing else
in the files changed):
- `page_text/`: 551 files, 2,152 paths
- `page_text_history/`: 1,217 files, 4,748 paths
- Codex `profiles/`: 392 files, 1,089 paths
- `profiles_history/`: 292 files, 850 paths
- the notebook run's `source_pages.csv`: 1,515 paths

Codex `codex_runs/` logs still name the old folders; nothing reads them as
paths.

## Checks

- **Tests:** `website_scrape` 26 passed; `scraps/codex_profiles` 28 passed
  (54 total, same as before the split); `scraps/comps_first_pass` 4 passed.
- **Stored paths:** all 2,152 raw-HTML paths in `page_text/` resolve.
- **Re-cleaning:** all 1,531 saved pages re-clean with `fetch_and_clean.py`
  to exactly the stored text (title, meta, blocks, raw blocks, removed, word
  count, block_page). The split changed no behaviour.
- **Codex profiles:** all 402 still count as current (219 ok, 166
  codex_error, 17 skipped). `comps_similarity` loads 560 page texts and 402
  profile rows from the new locations.

## Data version

company_list_v3 (sha256 3ab9a43e…). Page text as re-parsed 2026-10-18; no
scrape or re-parse was run in this session.

## Unresolved

- Nothing was committed. Most of the new code had never been committed, so
  git has no history for it yet.
- The filters still let some event/news lines through (e.g. Toro's homepage
  keeps "More events are coming soon." and a conference fireside chat).

## After the cleanup

- **Pushed:** commit 8ec080f to `main` on GitHub. Checked first: no data or
  output files, no credentials, and no financial columns in the notebook's
  saved outputs.
- **New notebook:** `matching/matching_methods.ipynb` (kernel "Python 3.14
  (Qual2Cast)").
  - Loads the snapshot's non-financial columns, and asserts no financial
    column is present.
  - Loads every scraped page with its cleaned text and source, and builds
    one row per company with status, pages, words and text.
  - Shows the scrape overview and the target's pages (`TARGET = "PCTY"`).
  - Sections 3-7 (matching method, results, sanity checks, valuation,
    definitions/limitations) are placeholders for the user's plan.
  - Runs top to bottom. 13 companies have no usable pages here: the 12
    with none, plus MSC Industrial, whose only page is a bot check.
  - Not committed yet.

## Next recommended action

Commit this layout, then start the matching method on
`outputs-local/website_scrape/page_text/` (PROJECT_STATE.md next steps 1-5).
