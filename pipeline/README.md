# Focused company-comps pipeline

Start with **`pipeline.ipynb`** in this folder. It runs the same stages as
`run.py`, displays intermediate tables and saves the results. No Claude
installation or API key is needed for the default Codex configuration.

## Setup

From the repository root:

```bash
uv sync
npm install -g @openai/codex
codex login
```

In VS Code, select the repository's `.venv` kernel. If a notebook cannot
find your CLI, set `CODEX_BIN` to its executable path and restart the kernel.
The shared wrapper also finds the bundled macOS desktop executable.

## Two methods

1. **B3**: compare each general facet with 50% MPNet embedding cosine and
   50% TF-IDF cosine, combine with information weights, keep mutual top-10
   peers and top up to three where possible. Unknown/not-applicable facets
   are missing. Company size is excluded. The representation uses B1, the
   existing first-business profile; it is not a new multi-business method.
2. **B3 + LLM filter**: start with exactly those B3 peers. The selector sees
   company names, websites and facets; it answers good/bad with a reason.
   It may use model knowledge, as in the existing selector prompt. It does
   not receive ranks, similarity scores, human labels or financial figures.
   It can reject every peer; it does not top up after filtering.

Both use the same new facet fills and frozen training peer pool. By default
all 373 training targets are processed, with no target or pair sampling.
The existing split also supports `holdout` and `all` in the config. Holdout
companies never enter the training peer pool. This reused holdout has
already informed development and is not an independent final test.

## Model roles

Edit one of the two TOML files in `configs/`:

- **Codex (default)**: GPT-6.1 Sol, high effort, fills facets; Sol, medium
  effort, filters peers; GPT-6 Luna, medium effort, judges pairs.
- **Claude**: Sonnet 5.5 fills and filters; Haiku 5.5 judges. This uses
  Claude Code CLI authentication, not an Anthropic API key. Install Claude
  Code and run `claude` to sign in, then select `configs/claude.toml`.

The general facets retain the existing protocol: name/URL + model knowledge
first, saved website passages for unknown facets, then saved-page checks
on multi-business splits. Failed/missing website gap fills retain the
first-pass profile and its unknown fields. New fills are not silently
replaced with historical Sonnet, Haiku or source-reviewed integration fills.
Consequently, the earlier manual scope corrections need rechecking against
the new text; changing the model does not guarantee more accurate facets.

The separate **0–3 judge** sees only cleaned saved website passages, up to
1,500 words per company. It receives no facets, selector decision/reason,
rank, similarity or multiples. Every numeric score needs citations from
both companies; insufficient evidence is null, not zero. It evaluates
every B3 pair once, including rejected peers. Both pipelines reuse those
same grades. Judge scores are diagnostic and never change selected peers
or valuation. This is the existing 0–3 rubric, not the research agent's 0–2
rubric. Web search is disabled for shared Codex inference calls.

## Run

Preview the configuration and output location without model calls:

```bash
uv run python pipeline/run.py
```

Run all stages (live model calls):

```bash
uv run python pipeline/run.py --execute
uv run python pipeline/run.py --config pipeline/configs/claude.toml --execute
```

The notebook previews by default too. Set `EXECUTE = True` and run all cells
to execute. It prints the exact run directory, which can be reused after
an interruption. To resume from the shell:

```bash
uv run python pipeline/run.py --config pipeline/configs/codex.toml --run-dir outputs-local/pipeline/codex/<variant>/<run> --execute
```

Use the same config when resuming. Completed profiles, selection calls and
judge calls are cached; derived tables are rebuilt. Model, effort, target
scope or input changes require a new run. Optional `target_tickers` narrows
the targets, **not the profile/peer pool**: the fill stage still fills the
entire eligible universe so B3 ranks against the complete pool.

To resume from a specific judge iteration, append `--judge-start 379`.
This preserves every earlier result in reports, including invalid answers;
those earlier invalid answers are left for a separate retry using the normal
resume command (default `--judge-start 1`).

## Output layout

```text
outputs-local/pipeline/
  codex/                         # claude/ is a separate sibling
    fill-<model>-<effort>__filter-<model>-<effort>__judge-<model>-<effort>/
      <run timestamp>/
        run.json                 # exact config, source hashes, code commit
        inputs/                  # companies, split, targets; financials separate
        shared/
          facets-<fill model>/   # profiles, tables, raw calls
          embeddings/           # deterministic MPNet text cache
          b3_candidates/        # full ranks and shortlist
          judge-<judge model>/   # frozen evidence, prompts, raw calls, grades
        pipelines/
          b3/                    # peers.csv, pair_results.csv, valuation.csv
          b3_llm_filter/
            filter-<model>/      # prompts, raw responses and checked decisions
            decisions.csv        # all shortlisted pairs, including rejected/incomplete
            peers.csv
            pair_results.csv
            valuation.csv
        comparison/              # summary, common-target errors, filter audit, chart
        history/                 # prior versions of regenerated files
```

Facet raw calls retain the historical leaf name `codex_runs/` for compatibility;
the enclosing provider and model identify whether they are Claude or Codex.
New pipeline outputs stay local by default. Historical `outputs-local/v1/`
results remain separate. There is no automatic provider fallback.

Each requested target remains in `valuation.csv`, even with no estimate.
The estimate is the **median of the selected peers' EV/EBITDA multiples**.
The target's observed multiple is joined afterward for evaluation; no
financial table enters a model call. Missing profiles and incomplete filter
answers are reported separately from completed rejections. No peers means
no estimate. `comparison/common_target_errors.csv` compares valuation error
only where both routes have estimates; report overall coverage alongside it.
`filter_audit.csv` joins judge reasons to both accepted and rejected peers.
Judge agreement is not human accuracy. The judge's human-review template
is a starting point for manual labels; annotate a separate copy.

## Where the code lives

- `configs/`: provider and model choices; no duplicated pipeline code.
- `pipeline.ipynb`: one sequential notebook.
- `workflow.py`: six stages and output organization.
- `run.py`: command-line entry point.
- `../v1/scripts/`: reused facet schema, B3 implementation, binary selector,
  evidence-only judge and valuation functions. Earlier experiments and their
  notebooks remain documented in `../v1/README.md`; they are not run here.
- `../v0/` and `../pre-v0/`: historical versions, not required entry points.

The relevant shared modules are `facets.py` / `fill_facets.py` (profiles),
`facet_weighting.py` / `method1_candidates.py` (B3), `cosine_then_llm.py`
(filter), `peer_evaluation.py` (judge), `valuation.py` (multiple), and
`cli_models.py` (the common Codex/Claude transport).

Codex calls use the existing `codex exec` wrapper, not the SDK. Each call
saves its prompt, JSON schema, raw output, response and execution metadata.
Authentication/quota failures stop new calls within that stage; individual
timeouts or unusable answers remain explicit failed/missing results.
