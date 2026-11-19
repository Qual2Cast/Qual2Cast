# 04_selection: LLM selection

An LLM reads each target's B3 list (names, websites, facets; no ranks, scores, labels or multiples) and keeps the good comps. The alternative route lets the LLM pick comps directly from the pool.

**Status (2026-11-19): ported.** Scripts, tests and `selection.ipynb` are in place; the notebook reproduces the saved v1 numbers (6/6 checks pass).

## Current setting (`v1a/current.toml`)

- `route` = `cosine_then_llm`
- `model` = `claude-sonnet-5-5`
- `prompt_version` = `2026-11-04a`
- `backend` = `claude-cli`
- `candidates` = `outputs-local/v1a/03_retrieval/selector_candidates`
- `judgments` = `outputs-local/v1a/04_selection/b3_selector_candidates_2026-11-04a_claude-cli_claude-sonnet-5-5/tables/judgments.csv`

## Outputs (`outputs-local/v1a/04_selection/`)

- `cosine_then_llm_haiku/` (1 file)
- `cosine_then_llm_sonnet/` (1 file)
- `direct_llm_haiku/` (1 file)
- `direct_llm_sonnet/` (1 file)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/check_prompt_versions.py` (script)
- `v1/scripts/cosine_then_llm.py` (script): B3 -> LLM filter
- `v1/scripts/direct_llm.py` (script): LLM direct picks
- `v1/scripts/llm_then_cosine.py` (script): LLM -> cosine route
- `v1/scripts/model_selection_eval.py` (script): Matthew/Richard Sonnet vs Haiku
- `v1/scripts/tests/test_cosine_then_llm.py` (test)
- `v1/scripts/tests/test_direct_llm.py` (test)
- `v1/PROMPT_VERSIONS.md` (doc): copied to v1a/04_selection/PROMPT_VERSIONS.md

Not from v1 on main:

- `v1/scripts/cosine_then_llm.py` from `kethan/wip`

Commit authors of these files (git): EFL-YL, mcschlatt, zynskibud.

## Notes

- **Current run (2026-11-18):** Sonnet 5.5 through the Claude Code CLI on the Claude subscription (no API key),
  prompt `2026-11-04a`, on the current list "Sonnet + Fiona sub-sector": all 373 targets, 2,538 pairs, 0 answer
  issues. 507 pairs kept (20%); 108 targets keep no comp. Folder
  `b3_selector_candidates_2026-11-04a_claude-cli_claude-sonnet-5-5/` (prompts and raw answers under `runs/`).
- Against Barbara's 293 grades: kept 24/24 of her 2s, 42/178 of her 1s, 3/91 of her 0s. The selector is strict:
  it keeps direct peers and drops most adjacent ones.
- The run hit the Claude plan's usage limit after 188 targets and finished after the reset. `common/cli_models.py`
  now stops a run on that message (HTTP 429, "hit your limit") and tolerates Windows temp-folder cleanup errors;
  a rerun of the same command continues from the saved answers.
- `cosine_then_llm_{sonnet,haiku}/` and `direct_llm_{sonnet,haiku}/` are the 11-04 v1 runs on the B3 list built
  from Haiku facets: history, reproduced in the notebook (`check_prompt_versions.py`, `model_selection_eval.py`).
- `direct_llm.py` and the selector replay v1 runs with their own split and Haiku facets; current runs read
  `current.toml`.
- Run: `uv run python v1a/04_selection/scripts/cosine_then_llm.py --b3 --backend claude-cli --workers 2`;
  tests `uv run pytest v1a/04_selection/tests -q`; open `selection.ipynb`.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `selection.ipynb` ported; v1 numbers reproduced.
