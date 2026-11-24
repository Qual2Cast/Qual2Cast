# v2/

The current method, started 2026-11-24. **Read [`EVAL_METHOD.md`](EVAL_METHOD.md) first**: it is how the rubric,
the labels, the facets and the X-learner fit together, and what each group optimizes for.

## A full working copy of v1a

v2 is a full working copy of v1a (all ten components, the pipeline runner, notebooks, tests and docs), the way v1
was a copy of v0. `v1a/` stays frozen as the record of the 2026-11-19 state; don't edit it.

Earlier on 2026-11-24 v2 was *layered* (only the components this round changes lived here, the rest was read from
v1a). Michael switched to a full copy the same day so the team works in one tree: the model-improvement group edits
the selector and agent prompts (04, 05), the eval group works with the label sheets (06), and the website group
reads the notebooks, all under `v2/` with one settings file, and nobody has to know which parts still live in v1a.

Start with [`00_overview.ipynb`](00_overview.ipynb), then the component notebooks in order.

| # | component | what it does | new in v2 |
|---|---|---|---|
| 01 | [universe](01_universe/) | 533 companies; 373 training (comp pool), 160 holdout | |
| 02 | [profiles](02_profiles/) | business-model facets per company | **tags T1-T4 and economic traits E1-E6 (round 1) and E7-E10 (round 2)** (Sonnet, prompts `2026-11-24a`, `2026-11-24b`) |
| 03 | [retrieval](03_retrieval/) | B3 comp lists | unchanged this round (diagnostic only) |
| 04 | [selection](04_selection/) | LLM keeps the good comps from B3 | unchanged this round; the model-improvement group tunes it next |
| 05 | [agent grading](05_agent_grading/) | agent grades each pair 0/1/2 with citations | unchanged this round; next: ask the rubric v3 questions |
| 06 | [labels](06_labels/) | human grades, rubrics, cohorts, pair ledger | **rubric v3**, its scorer and the sheet for the first round of evals |
| 07 | [judges](07_judges/) | LLM-as-judge (evaluation only) | later: GPT-Terra as tie-breaker, if it earns it |
| 08 | [valuation](08_valuation/) | median comp EV/EBITDA vs actual | |
| 09 | [analysis](09_analysis/) | X-learner facet lift, error analysis | **trait X-learner**, pre-registered (`PREREG_TRAITS.md`) |
| 10 | [final holdout](10_final_holdout/) | locked final check, run once | still locked (`FINAL_CHECK = False`) |

[`pipeline/`](pipeline/) is Kethan's end-to-end runner: a fresh run of 01 -> 02 -> 03 -> 04 -> 07 -> 08 with the
model choices in its config files. Default config `configs/v2.toml` (Sonnet fills and selects, a GPT model judges);
training targets only; preview unless `--execute`.

## Outputs: existing runs are read in place, new runs go to v2

v2 does not copy v1a's saved runs (about 200 MB, already shared through git). In `common/paths.py`:

- `out(component)` is `outputs-local/v2/<component>/`: where every **new** run, figure or table is written.
- `src(component, *parts)` is where an **existing** output is read: the v2 copy if v2 has made one, otherwise
  `outputs-local/v1a/<component>/...` (v1a's runs and the tables seeded from v1).
- `latest(component, *parts)` is the newest time-stamped run in either place.
- `current.toml` names the current runs explicitly; most still point into `outputs-local/v1a/`, and that is
  intended. A new run becomes current by changing its line there (with a dated note in the component's changelog).

The local embedding caches (`outputs-local/*/03_retrieval/cache/`, not in git) were copied once into
`outputs-local/v2/03_retrieval/cache/` so v2 doesn't recompute them.

## Rules

- **One source of settings.** [`current.toml`](current.toml) names the current runs (v1a's settings, copied, plus
  the v2 sections at the end). Notebooks and scripts read it; nothing hard-codes a run.
- **One notebook per component**, named after it and updated in place; every notebook has the same sections: what
  it does, the current setting, inputs with hashes, results, and a check against the saved numbers.
- **Cohorts by name** from `06_labels` (`dev_293`, `round1_36`, `matthew_v2_262`); `final_holdout_24` loads only
  inside `10_final_holdout`.
- **EV/EBITDA stays in valuation.** `financials.csv` is read only by 08 and 10, never by 01-07.
- **Outputs** are never overwritten; replaced files move to a `history/` folder. `outputs-local/v2/` is shared
  through git **in full** (history, logs, raw model output and caches included; only test scratch and Office lock
  files stay out), and so is every later `outputs-local/vN/`. The repository is public.
- **No model calls without Michael's approval.** Claude fills and selects (on the subscription CLI); GPT models only
  judge.
- **Teammates' code stays close to how they wrote it** (graphs and tables ported nearly verbatim).

## Code layout

```
v2/
  EVAL_METHOD.md       how everything fits together (start here)
  00_overview.ipynb    the pipeline at a glance
  current.toml         the current runs and settings
  <component>/         README.md, <component>.ipynb, scripts/, tests/
  pipeline/            Kethan's end-to-end runner (configs/v2.toml)
  common/paths.py      setup(), current(), path(), out(), src(), latest()
  common/v2paths.py    the same module under the name the 11-24 v2 scripts import
  common/nbtools.py    notebook helpers (inputs table, checks)
  common/cli_models.py one structured call through the Claude Code or Codex CLI
```

Scripts and notebooks start with `sys.path.insert(0, "<repo>/v2/common"); import paths as v2; v2.setup()` (the
notebooks keep the name `paths`). Only v2 code is on the import path; nothing is imported from v1a.

## Tests

```bash
uv run pytest v2 -q        # 293 tests (v1a's 267 + v2's 26)
```

## Where things came from

- v1a's history (`MIGRATION_MAP.csv`, the "Comes from v1" sections in each README, `outputs-local/v1a/seed_manifest.json`)
  is copied unchanged; it describes how v1a was made from v1.
- `common/seed_from_v1.py` is kept as the record and refuses to run in v2.
