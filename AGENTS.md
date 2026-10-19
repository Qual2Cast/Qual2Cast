# Project working instructions

Before working, read PROJECT_STATE.md, docs/data_dictionary.md, and the
handoff or conversation files in conversations/ relevant to the assigned task.

Treat the current repository and approved methodology as authoritative.
Treat old transcripts as historical evidence, not automatically as current
instructions.

The pipeline starts from the website scrape (website_scrape/). Folders in
scraps/ are earlier attempts kept for reference: don't build on them unless
the task says so. Something from scraps/ joins the pipeline only when the
team decides it should.

Use the data snapshot specified in data_manifest.json (code finds it through
src/project_data.py). Do not modify the authoritative input data in
data-local/. Corrections to source data become reviewed transformation scripts
(see src/prepare_company_list.py) and a new published snapshot. Write
experimental results to outputs-local/.

Before handing off work, document completed changes, test results, data
version, unresolved issues, and the next recommended action, in
PROJECT_STATE.md and a handoff file in conversations/.

## Project rules

- Aziz's rule (updated 2026-10-19): methods must work for a private target.
  Target inputs are name + website, plus LTM revenue, LTM EBITDA and debt.
  No investor-relations pages or stock data for the target. Public comps may
  also use 10-Ks and other public detail. Same business comes first; scale
  similarity is secondary.
- Collection is fully programmatic: no hand-written data. Information a
  source doesn't give is marked unknown, never guessed, and every extracted
  fact cites its source URL.
- Financial fields (revenue, EBITDA, margin, debt/revenue, EV/EBITDA) are
  kept in separate columns or tables from text inputs and never shown to the
  extraction model. Revenue, EBITDA and debt (and derived margin,
  debt/revenue) may be compared for scale; EV/EBITDA is the valuation output
  and never a matching input.
- Keep every stage's data: raw scrapes, intermediate text, model prompts and
  responses, and processed tables are all saved, not overwritten.
- Load SIC codes as 4-character, zero-padded strings and derive 2/3-digit
  codes from them (src/project_data.normalize_sic_codes).
- Never commit .env, or Codex credentials
  (~/.codex/auth.json).
