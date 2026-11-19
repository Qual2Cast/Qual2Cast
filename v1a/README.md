# v1a/

The current method, organized by pipeline component (2026-11-18). v1a keeps v1's method and settings; it
reorganizes the files so each part of the pipeline has one folder, one notebook and one README. `v1/` stays
unchanged as the record, as `v0/` did for v1.

**Status: all components ported (2026-11-19).** Start with [`00_overview.ipynb`](00_overview.ipynb), then the
component notebooks in order. Every notebook runs end to end and its checks pass; 01-07 reproduce the saved v1
numbers, 08 values the current lists, 09 reproduces v1's X-learner runs and adds runs on the current lists and the
selector, 10 is locked. 226 tests pass (`uv run pytest v1a/<component>/tests -q`). Not yet done: pointing
AGENTS.md and the root README here (waits for Michael's review).

## The pipeline

| # | component | what it does | current setting |
|---|---|---|---|
| 01 | [universe](01_universe/) | 533 companies; 373 training (comp pool), 160 holdout | split `20261027T204930Z` |
| 02 | [profiles](02_profiles/) | business-model facets per company | Sonnet 5.5 fills, prompt `2026-10-25k` |
| 03 | [retrieval](03_retrieval/) | B3 comp lists | "Sonnet + Fiona sub-sector", mutual top 10, top-up 3 |
| 04 | [selection](04_selection/) | LLM keeps the good comps from B3 | Sonnet, prompt `2026-11-04a` |
| 05 | [agent grading](05_agent_grading/) | agent grades each pair 0/1/2 with citations; C/S/E | Sonnet, prompt `2026-11-05b` + facet scores |
| 06 | [labels](06_labels/) | human grades, rubrics, cohorts, pair ledger | default cohort `dev_293` |
| 07 | [judges](07_judges/) | LLM-as-judge evaluators (evaluation only) | GPT family; GPT-6.1 Sol on the 293 |
| 08 | [valuation](08_valuation/) | median comp EV/EBITDA vs actual | training targets only |
| 09 | [analysis](09_analysis/) | X-learner facet lift, error analysis | runs pinned in `[analysis.facet_uplift]` |
| 10 | [final holdout](10_final_holdout/) | locked final check, run once | `FINAL_CHECK = False` |

[`pipeline/`](pipeline/) is Kethan's end-to-end runner from `kethan/wip`: a fresh run of 01 -> 02 -> 03 -> 04 ->
07 -> 08 with the model choices in its config files. Default config `configs/v1a.toml` (Sonnet fills and selects,
a GPT model judges); training targets only; preview unless `--execute`.

## Rules

- **One source of settings.** [`current.toml`](current.toml) names the current runs. Notebooks and scripts read
  it; nothing hard-codes a run. Changing the current setting means editing that file and adding a dated line to
  the component's changelog.
- **One notebook per component**, named after it and updated in place; its changelog cell records what changed.
  No new notebooks for a new run or variant.
- **Every notebook has the same sections:** what it does, the current setting, inputs with hashes, results, and a
  check against the saved numbers.
- **Cohorts by name.** Labelled pair sets come from `06_labels` (`dev_293`, `round1_36`, `matthew_v2_262`).
  `final_holdout_24` loads only inside `10_final_holdout`.
- **EV/EBITDA stays in valuation.** `financials.csv` lives in `outputs-local/v1a/08_valuation/` and is read only by
  08 and 10, never by 01-07.
- **Outputs** go to `outputs-local/v1a/<component>/`, never overwritten; replaced files move to a `history/`
  folder. Shared through git like v1 (logs, raw Codex output, caches and history stay local).

## Code layout

```
v1a/<component>/
  README.md        what, who, current setting, outputs, v1 sources, changelog
  <component>.ipynb
  scripts/         modules import each other by name, as in v1/scripts
  tests/
v1a/common/        paths.py (setup(), current(), out()), cli_models.py, seed_from_v1.py
```

Scripts and notebooks start with `sys.path.insert(0, "<repo>/v1a/common"); import paths; paths.setup()`.

## Where things came from

- [`MIGRATION_MAP.csv`](MIGRATION_MAP.csv): every v1 script, test, notebook and doc, and the changed files on
  `matt/rubric-yes-no` and `kethan/wip`, with its v1a component. 57 v1 scripts stay in v1 only: 47 from the 11-10
  integration study (indexed in [09_analysis](09_analysis/)), the six v0-route holdout scripts (results seeded in
  10), two 11-10 valuation checks of profile variants, `sector_facet_candidates.py` and `seed_from_v0.py`.
- `outputs-local/v1a/seed_manifest.json`: every seeded file with its v1 source and sha256, and every raw folder
  left in `outputs-local/v1/` (path, file count, size). Made by `common/seed_from_v1.py`: 153 files (30 MB)
  copied, 43 raw folders (156 MB) linked.
- Unmerged branches taken in: Matthew's rubric v2 (`matt/rubric-yes-no`, commit `65fb6358`) and Kethan's
  focused pipeline (`kethan/wip`). Riya's `riya/wip` (10-17, pre-v0) is left out.
