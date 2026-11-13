# Qual2Cast

Find comparable public companies from business descriptions, then estimate
an EV/EBITDA multiple for a target treated as private.

## Start here

**Open [`pipeline/pipeline.ipynb`](pipeline/pipeline.ipynb)** in VS Code.
It runs the workflow in order and displays and saves outputs at each step.
See [`pipeline/README.md`](pipeline/README.md) for setup, methods, models and
output definitions.

```bash
uv sync
npm install -g @openai/codex
codex login
uv run python pipeline/run.py            # preview, no model calls
uv run python pipeline/run.py --execute  # full run, live model calls
```

Select the repository's `.venv` kernel in VS Code. The notebook previews by
default; set `EXECUTE = True` to run its model stages.

## Two pipelines

1. **B3**: facet similarity blends MPNet cosine and TF-IDF cosine, applies
   information weights, and selects mutual top-10 peers topped up to three.
2. **B3 + LLM filter**: the same candidates, screened good/bad by an LLM.

Both share **GPT-6.1 Sol facet fills** and are evaluated by a separate,
weaker **GPT-6 Luna judge** using saved website evidence and a 0–3 rubric.
The judge also evaluates rejected peers to help diagnose filtering losses.
It does not select peers. Valuation uses the median selected-peer multiple.

The default covers all training targets, not a sample. Model quality must
still be checked against human labels; judge scores are not measured accuracy.

## Run Claude instead

Install Claude Code and sign in by running `claude`, then:

```bash
uv run python pipeline/run.py --config pipeline/configs/claude.toml --execute
```

This uses Sonnet fills/filtering and a Haiku judge through Claude CLI.
Choose the same config in the notebook. No Anthropic API key is needed for
this CLI route; the older API backend remains in the research scripts.

## Repository map

```text
pipeline/           Current entry point: notebook, runner, workflow, two configs
v1/scripts/         Shared method implementations and earlier experiments
v1/notebooks/       Earlier research, evaluation and integration notebooks
src/                Snapshot loader and shared data helpers
website_scrape/     Website collection and cleaning
outputs-local/      Results; new runs under pipeline/<provider>/<models>/<run>/
data-local/         Versioned input snapshots
v0/, pre-v0/        Historical deliverables and experiments
conversations/      Work-session handoffs
docs/               Data definitions
```

Within each new run, `shared/` holds facets, candidates and judge results;
`pipelines/b3/` and `pipelines/b3_llm_filter/` hold each method's outputs;
`comparison/` holds metrics, rejected-peer analysis and a chart. Codex and
Claude have separate provider folders, and model/effort variants have
separate run folders. Historical outputs are not reused implicitly.

The focused workflow reuses the existing method modules rather than copying
them. [`v1/README.md`](v1/README.md) documents the broader research history;
it is not necessary to run its integration matrix for this workflow.

## Data and interpretation

The supplied snapshot has 560 public companies used as private-company
stand-ins; 533 meet the existing universe rules. The fixed split has 373
training and 160 holdout companies. Peers come from training only, excluding
the target itself. The holdout has already been used during development.

Matching and model prompts do not receive financial fields. Multiples are
used for the existing universe eligibility rule and, after peer selection,
for valuation and error calculation. Website gaps remain visible; unknown
facts are not assumed correct. Input snapshots are never edited by hand.

See [`docs/data_dictionary.md`](docs/data_dictionary.md),
[`PROJECT_STATE.md`](PROJECT_STATE.md) and [`AGENTS.md`](AGENTS.md).
