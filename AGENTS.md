# Project working instructions

How to work in this repo, for people and for agents (Codex, Claude Code).
This file covers working habits only, not the method. The method (inputs,
facets, how comps are picked, valuation) is decided by the team and
recorded in PROJECT_STATE.md and the README of the current method's folder
(v1/README.md). Where they differ from this file, they win. Nothing here
limits a new design: when the team changes the method, update those files,
not this one.

Before working, read PROJECT_STATE.md, docs/data_dictionary.md, the README
of the folder you're working in, and the handoffs in conversations/ that
relate to the task. Old transcripts and handoffs are history, not current
instructions.

The focused runnable workflow is now in pipeline/ (see pipeline/README.md):
two routes, B3 and B3 + LLM filter, with provider/model settings in configs/.
It reuses v1/scripts/; keep historical experimental results separate from new
outputs-local/pipeline/<provider>/<model variant>/<run>/ outputs.

The research method is in v1/ (the mentor's comps recipe; a working copy of v0/, which stays as
the record of the 2026-10-28 deliverable). Code is in v1/scripts/, notebooks in v1/notebooks/.
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
  instead of overwriting it.
- EV/EBITDA is the answer the method predicts: keep financial columns in
  their own tables, and never give EV/EBITDA to the comp-finding steps.

## Handoff

Before handing off, record the changes, test results, data version, open
issues and the next step in PROJECT_STATE.md and a handoff file in
conversations/.

## Never commit

.env, or Codex credentials (~/.codex/auth.json).
