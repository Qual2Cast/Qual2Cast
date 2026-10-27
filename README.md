# Qual2Cast

Find comparable public companies and estimate an EV/EBITDA multiple for a target business.
Columbia University capstone with Rational AI.

**Start with [pipeline.ipynb](pipeline.ipynb).** It runs the current v0 recipe in order,
shows each stage's results, and saves the inputs, prompts, model responses and tables.
You select **Codex CLI or Claude Code CLI once**; that selection applies to every model stage.

## Quick start

Use Python **3.11 or 3.12** (recommended for the embedding dependencies).
From a fresh clone:

```bash
git clone https://github.com/Qual2Cast/Qual2Cast.git
cd Qual2Cast
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m ipykernel install --user --name qual2cast --display-name "Qual2Cast"
jupyter lab pipeline.ipynb
```

On Windows, use `python` instead of `python3` and activate with
`.venv\Scripts\Activate.ps1` in PowerShell. In Jupyter or VS Code, choose the
**Qual2Cast** kernel. If a CLI is installed after Jupyter starts, restart Jupyter
so its executable is on PATH.

Install **one** CLI using its official instructions and sign in normally:

- [Codex CLI](https://developers.openai.com/codex/cli/): sign in with `codex login`.
- [Claude Code](https://code.claude.com/docs/en/overview): sign in by running `claude`.

The pipeline calls `codex exec` or `claude -p` as a subprocess and reads structured
JSON. No local API server or project API key is needed for these CLI backends.
CLI calls use the chosen account's normal authentication and usage allowance.
The original paid Anthropic API backend is still available as `backend="claude"`;
install `anthropic` and provide `ANTHROPIC_API_KEY` only if you choose that option.

## Run the notebook

Change the settings cell near the top of [pipeline.ipynb](pipeline.ipynb):

```python
BACKEND = "codex"          # or "claude-cli"
MODEL = ""                 # CLI default, or an explicit model available in your account
COMPANY_LIMIT = None        # full 533-company universe; use 12 for a small wiring trial
TARGET_TICKERS = None       # all training targets; or e.g. ("PCTY", "BRO")
DIRECT_SUGGESTIONS = False  # optional full-pool comparison with large prompts
RUN_DIR = None             # new run; paste an existing run path here to resume
```

Then **Restart Kernel → Run All**. Both CLI backends use the same prompts and
schemas. `MODEL` and `EFFORT` apply to all calls. For a controlled comparison,
name the model explicitly; an empty string means the CLI's external default,
which can change outside this repository. Change `BACKEND` and start a new run
to compare providers. If discovery fails, set `CODEX_BIN` or `CLAUDE_BIN` to the
full executable path before starting Jupyter.

The input snapshots and current saved website pages are included in the repo.
The notebook checks the snapshot checksum. Its first embedding run downloads
MPNet (~420 MB); later runs reuse embeddings keyed by model and input text.
The main workflow consumes saved pages; it does not need to scrape all sites again.

A full run makes hundreds of model calls. A small `COMPANY_LIMIT` trial checks
execution only and changes the candidate universe and split. When using a small
trial, leave `TARGET_TICKERS=None`, since a named company may not be in that subset.

## Pipeline steps

1. **Universe:** load the supplied 560 companies, separate financial fields,
   and apply the mentor's EV/EBITDA range of 3–30 (533 companies).
2. **Facets:** fill twelve business characteristics from model knowledge;
   use saved website pages only to fill unknown facets.
3. **Split:** fixed 70/30 split stratified by company size, seed 2026;
   existing showcase companies stay in training.
4. **Candidates:** embed each facet except company size, combine per-facet
   similarities, and retrieve top-10 or z ≥ 2 candidates from training only.
5. **Judgments:** the selected CLI judges whether z ≥ 2 candidates are in
   the same business, with good/bad answers and reasons.
6. **Optional suggestions:** the same CLI chooses peers directly from the
   full training pool, without embeddings.
7. **Valuation:** weighted-mean/median estimates versus no-matching and
   SIC baselines; show conditional errors, all-target coverage, and common-case results.

`TARGET_SAMPLE="training"` is the default. Do not select `"holdout"` until
method choices are frozen. The existing v0 estimator permits a single usable
peer; it abstains if there are none. Financial dates and EBITDA definitions
remain unresolved. Automated judgments are not independent human validation.
This refactor changes execution and model transport, not those method decisions.

## Saved outputs and resuming

Every fresh notebook run prints its directory:

```text
outputs-local/pipeline/<timestamp>/
  config.json
  universe/       company list, exclusions, financials, snapshot provenance
  facets/         prompts, schemas, raw logs/responses, profiles, facet tables
  split/          assignments and balance checks
  candidates/     full ranking, candidate pairs, facet scores, falloff plot
  judge/          prompts/responses, judgments, joined pair table
  suggest/        optional direct-selection prompts/responses and tables
  valuation/      summary, common-case summary, every target's estimate/error/status
  history/        replaced stage tables
```

To resume, put that directory in `RUN_DIR` and Run All with the same settings.
Completed model calls are reused; failed or unfinished ones run again.
Failed website gap fills leave unknown facets in the first-pass profile and
allow the pipeline to continue with available facets; a later rerun retries them.
In the same kernel, you can rerun the failed stage and continue with later cells.
Changed settings require a new run directory. Prompts, responses and outputs
stay local and are ignored by Git. The notebook itself can be saved with outputs
for sharing only when the underlying data permissions allow it.

## Code organization

- `pipeline.ipynb`: the main execution notebook; code cells call one stage each.
- `v0/pipeline.py`: stage orchestration and saved outputs.
- `v0/cli_models.py`: shared Codex/Claude CLI transport.
- `v0/fill_facets.py`, `facets.py`: facet extraction, gap filling, checks and tables.
- `v0/split.py`, `candidates.py`, `judge_comps.py`, `suggest_comps.py`, `valuation.py`:
  the recipe's independent computational steps.
- `v0/README.md`: detailed method decisions and historical results.
- `v0/notebooks/`: earlier analysis notebooks, retained for reference.
- `v0/verification/`: optional source-verification studies, separate from the comps recipe;
  their model runners also accept `--backend codex` or `--backend claude-cli`.
- `website_scrape/`: optional website collection/refresh, with its own requirements.
- `src/`, `data_manifest.json`, `data-local/snapshots/`: shared snapshot loading and provenance.
- `pre-v0/`: previous experiments, not imported by the main notebook.
- `PROJECT_STATE.md`, `conversations/`: current status and handoffs.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest v0/tests v0/verification/tests -q
```

The integration checks run every main-notebook code cell with synthetic model
responses and embeddings. They test both CLI contracts, stage wiring, saved
outputs and resuming. They do not make live inference calls or establish valuation accuracy.
