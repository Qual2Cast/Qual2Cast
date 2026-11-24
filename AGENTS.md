# Project working instructions

How to work in this repo, for people and for agents (Codex, Claude Code).
This file covers working habits only, not the method. The method (inputs,
facets, how comps are picked, valuation) is decided by the team and
recorded in PROJECT_STATE.md and the README of the current method's folder
(v2/README.md). Where they differ from this file, they win. Nothing here
limits a new design: when the team changes the method, update those files,
not this one.

Before working, read PROJECT_STATE.md, docs/data_dictionary.md, the README
of the folder you're working in, and the handoffs in conversations/ that
relate to the task. Old transcripts and handoffs are history, not current
instructions.

The current method is in v2/ (the mentor's comps recipe, organized by pipeline component; a working
copy of v1a/, which stays as the record of 2026-11-19, as v1/ and v0/ do for earlier rounds). Start
with v2/EVAL_METHOD.md and v2/00_overview.ipynb; code is in v2/<component>/scripts/, one notebook per
component. New outputs go to outputs-local/v2/; existing runs are read in place from outputs-local/v1a/.
Use the uv environment (`uv sync`, `uv run`); add packages with `uv add`. pre-v0/ holds
earlier work kept for reference; build on it only when the task says so.

## Data

- Use the snapshot named in data_manifest.json (code finds it through
  src/project_data.py). Don't edit data-local/: corrections become a reviewed
  transformation script (see src/prepare_company_list.py) and a new snapshot.
- Load SIC codes as 4-character, zero-padded strings
  (src/project_data.normalize_sic_codes).
- Data is collected by code, never typed in by hand.
- Write results to outputs-local/. Keep every stage's data (raw inputs, model
  prompts and responses, tables): move a replaced file to a history folder
  instead of overwriting it. From v2 on, everything under outputs-local/v2/
  (and later versions) is committed, history, logs and caches included, so
  teammates never miss a file. The repository is public: never write secrets
  or personal details into outputs.
- EV/EBITDA is the answer the method predicts: keep financial columns in
  their own tables, and never give EV/EBITDA to the comp-finding steps.

## Handoff

Before handing off, record the changes, test results, data version, open
issues and the next step in PROJECT_STATE.md and a handoff file in
conversations/.

## Never commit

.env, or Codex credentials (~/.codex/auth.json).
