# 04_selection: LLM selection

An LLM reads each target's B3 list (names, websites, facets; no ranks, scores, labels or multiples) and keeps the good comps. The alternative route lets the LLM pick comps directly from the pool.

**Status (2026-11-19): ported.** Scripts, tests and `selection.ipynb` are in place; the notebook reproduces the saved v1 numbers (6/6 checks pass).

**Trait-line experiments (2026-11-28, rubric v3 labels `v3_final`; no change to the pinned selector).** Ten prompt
versions add one data line per company ("<trait>: yes/no/unknown", from the trait tables of
`v2/02_profiles`; instructions unchanged): `2026-11-28a` recurring revenue, `28b` big-ticket, `28d` cyclical demand,
`28e` people-delivered, `28f` large customers, `28g` asset-heavy, `28h` maintenance-led, `28i` publicly funded, `28j`
serial acquirer, `28k` mission-critical (`28c`, both of the first two, is defined and not run). Each ran on the 67
`v3_final` targets' B3 lists, Sonnet 5.5 through the Claude CLI, next to two reruns of the unchanged `2026-11-04a`
prompt (the noise band). Summary `outputs-local/v2/04_selection/trait_line_experiments_20261128/` (`summary.csv`,
`flips.csv`; `scripts/trait_line_experiments.py`); each run is a ledger row; `v2/09_analysis/analysis.ipynb` 3.8-3.9.
Target means on 311 labelled pairs (106 direct, 78 adjacent, 127 not):

| run | trait line | kept direct / adjacent / not | flips vs baseline | direct precision | direct recall | peer recall |
|---|---|---|---|---|---|---|
| baseline | — | 86 / 6 / 4 | 0 | 86.8% | 86.8% | 61.1% |
| repeat1 | — | 87 / 6 / 5 | 10 | 87.0% | 89.1% | 61.9% |
| repeat2 | — | 79 / 6 / 5 | 10 | 86.5% | 82.7% | 58.9% |
| 2026-11-28a | recurring_revenue | 88 / 6 / 5 | 15 | 85.8% | 89.5% | 61.7% |
| 2026-11-28b | big_ticket | 86 / 6 / 4 | 10 | 87.0% | 87.8% | 60.9% |
| 2026-11-28d | cyclical_demand | 88 / 5 / 4 | 11 | 86.1% | 86.3% | 60.7% |
| 2026-11-28e | people_delivered | 84 / 6 / 5 | 13 | 85.5% | 86.5% | 60.8% |
| 2026-11-28f | large_customers | 83 / 5 / 4 | 14 | 86.8% | 85.0% | 59.7% |
| 2026-11-28g | asset_heavy | 83 / 5 / 5 | 11 | 85.5% | 85.3% | 59.5% |
| 2026-11-28h | maintenance_led | 89 / 6 / 5 | 8 | 86.4% | 87.3% | 61.8% |
| 2026-11-28i | publicly_funded | 84 / 7 / 6 | 11 | 84.8% | 85.5% | 60.3% |
| 2026-11-28j | serial_acquirer | 90 / 7 / 5 | 8 | 83.6% | 88.8% | 62.2% |
| 2026-11-28k | mission_critical | 85 / 5 / 4 | 10 | 86.5% | 85.4% | 59.9% |

No trait line moves the selector beyond what rerunning the unchanged prompt does: the three unchanged runs alone span
direct recall 82.7-89.2% and flip 10 pairs against each other; the trait versions flip 8-16 pairs, about as often
against the trait's direction as with it. Kept adjacents stay at 5-7 of 78 in every run (the prompt asks for the same
business).

**Running the selector on B3's lists:** pass `--b3` (without it the script screens v0's z >= 2 shortlist; a run made
that way by mistake is in `outputs-local/v2/04_selection/history/`), `--targets-file` for a subset, and
`--workers 1` with the Claude CLI on Windows (two workers can collide writing the shared system-prompt file in
`v2/common/cli_models.py`; rerunning resumes).

## Current setting (`v2/current.toml`)

- `route` = `cosine_then_llm`
- `model` = `claude-sonnet-5-5`
- `prompt_version` = `2026-11-04a`
- `backend` = `claude-cli`
- `candidates` = `outputs-local/v1a/03_retrieval/selector_candidates`
- `judgments` = `outputs-local/v1a/04_selection/b3_selector_candidates_2026-11-04a_claude-cli_claude-sonnet-5-5/tables/judgments.csv`

## Outputs (existing runs in `outputs-local/v1a/04_selection/`, read in place; new runs in `outputs-local/v2/04_selection/`)

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
- `v1/PROMPT_VERSIONS.md` (doc): copied to v2/04_selection/PROMPT_VERSIONS.md

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
- Run: `uv run python v2/04_selection/scripts/cosine_then_llm.py --b3 --backend claude-cli --workers 2`;
  tests `uv run pytest v2/04_selection/tests -q`; open `selection.ipynb`.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `selection.ipynb` ported; v1 numbers reproduced.
- 2026-11-19: section 3.5 from `comps_and_valuation.ipynb` section 8 (facet AUC against the selector's verdicts,
  top-10 lift, PCTY/WEN heatmaps) on the current B3 facet scores; F9 and the shared-"none" view stay in v1.
- 2026-11-24: copied into full v2 (v2 became a working copy of v1a); existing outputs stay in `outputs-local/v1a/` and are read in place, new runs go to `outputs-local/v2/`.
- 2026-11-28: trait-line prompt versions `2026-11-28a`-`28k` (+ `--traits`, `--traits-r2`, `--targets-file`, a run manifest); ten trait runs and two noise reruns on the 67 `v3_final` targets; `scripts/trait_line_experiments.py`. Tests: 30 pass.
