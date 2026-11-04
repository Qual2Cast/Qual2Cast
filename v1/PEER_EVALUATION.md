# Evaluate cosine → LLM peer outputs

Entry point: [notebooks/peer_evaluation.ipynb](notebooks/peer_evaluation.ipynb).

This is a downstream evaluator for the final peers produced by the existing
cosine-shortlist → LLM-filter method. `judge_comps.py` remains the selection
model; `peer_evaluation.py` evaluates its accepted outputs.

The defaults and completed 663-pair analysis refer to the original size-stratified
baseline under `outputs-local/comps/`. Main now uses a SIC2 split under
`outputs-local/comps_pilot_targets/`; export its section 11 handoff and set
`HANDOFF` in the evaluator to review that version in a new run. The evaluator
reads the split beside the selected candidates, keeping the two runs separate.

## Run

Notebook section 7 analyzes saved results without inference. Set `ANALYSIS_RUN`
to a completed run and execute only that section: coverage/pass metrics,
outcome and fit-dimension charts, target coverage, illustrative pair explanations
and evidence/validation review lists. Derived CSVs, PNGs and a short finding
are saved under that run's `analysis/`; replaced files move to `history/`.
The default points to the completed `20261027T190213461887Z` local run.
Use another path if that local output is not available. Charts require
`matplotlib`, now included in `requirements-judge.txt`.

Use Python 3.11 or 3.12. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r v0/requirements-judge.txt
jupyter lab v0/notebooks/peer_evaluation.ipynb
```

On Windows, use `python` and `.venv\Scripts\Activate.ps1`. Select the environment
as the notebook kernel. This notebook needs neither an embedding download nor
the Anthropic Python SDK.

Install and sign in to either CLI using its official setup:

- [Codex CLI](https://developers.openai.com/codex/cli/): `codex login`.
- [Claude Code](https://code.claude.com/docs/en/overview): run `claude` to sign in.

`BACKEND="codex"` is the default; use `"claude-cli"` for Claude Code. The shared
`cli_models.py` adapter sends a prompt through stdin and reads structured JSON
from `codex exec` or `claude -p`. It uses the CLI's usual authentication;
there is no local HTTP server or project API key requirement. Account usage
limits still apply. The notebook setup cell accepts optional `CODEX_BIN` and
`CLAUDE_BIN` executable paths; `None` keeps existing environment settings.
Codex discovery checks `CODEX_BIN`, then PATH, then the macOS ChatGPT desktop
app bundle under `/Applications` or `~/Applications`. Claude checks `CLAUDE_BIN`
then PATH. An explicit invalid override raises a setup error instead of silently
using another executable. The setup cell prints the resolved CLI for live runs
before preparing inputs; preview mode does not require a CLI. No SDK is used.

1. In `comps_and_valuation.ipynb`, run the final handoff cell after the matching
   results. It saves a copy of the selection judgments alongside the candidate
   run and prints `peer_evaluation_input.json`'s path.
2. Paste that path into the new notebook's `HANDOFF`. Alternatively, leave
   `HANDOFF=None` to use its explicit, already-shared development inputs.
3. Choose model and rubric. The notebook now defaults to all training targets:
   `TARGET_TICKERS=None`, `MAX_PAIRS=None`, Codex CLI and the agreed 0–3 rubric.
   The saved inputs contain 373 training targets and 663 accepted pairs for
   277 targets; the 96 zero-peer targets remain in the target report.
4. Run All to execute the full evaluation (`RUN_JUDGE=True`). For a source
   and prompt preview with no inference, first set `RUN_JUDGE=False`.
   One accepted pair consumes one CLI call.
5. `RUN_DIR=None` creates a new output folder. To reuse a prior run, paste
   its output path into `RUN_DIR`. Use a new directory for changed settings.
6. For a later resume, retain `RUN_DIR` and the same settings, then Run All.
   Successful, matching judgments are reused. Failed or
   invalid answers are retried on that rerun; there are no automatic retries.

An empty `MODEL` uses the CLI default, which can change outside this repository.
Use explicit model names and separate run directories for provider comparisons.
The notebook does not run or alter the upstream model calls or valuation rule.

## What is judged

The input matches the current valuation notebook: training-only candidates
at z ≥ 2, judgments from its selection prompt version, complete upstream
decisions for a target, and selection score 1. Targets with no accepted peer
are retained in the target report. Incomplete upstream targets are identified
separately in input metadata and `upstream_complete` in the target report.

The evaluator gives each pair's judge:

- Company names and websites.
- Existing cleaned website passages, with line labels and a configurable
  word budget per company (1,500 words by default).
- The rubric and requested answer schema.

It withholds generated facets, upstream decisions/reasons, ranks, cosine
scores, SIC codes, financials and target outcomes from the prompt. Saved-page
lines pass through the existing facet input filters. Both models are instructed
to use only the passages; Claude's built-in tools are disabled, and calls run
in a temporary directory. This instruction does not establish that a model has
forgotten its prior knowledge. The source pages can also overlap the upstream
gap-fill evidence; this is a separate evaluation prompt, not independent truth.

The judge returns offering, customer and business-model assessments and:

- **3 / direct_peer:** compatible principal offerings, customer need and
  economic role; a defensible same-business comparable.
- **2 / partial_peer:** meaningful overlap with a material limitation.
- **1 / weak_peer:** adjacent business with weak core comparability.
- **0 / not_peer:** evidence establishes materially different businesses.
- **null / insufficient_evidence:** the passages cannot settle the comparison.

Every numeric grade needs source citations for both companies. Code checks
that the labels exist and resolves them to actual text, URLs and capture dates.
An unsupported label or mismatched score/verdict becomes `invalid_answer`, not
a numerical grade. These checks establish citation existence, not whether
the cited text logically supports the model's conclusion.

## Outputs and interpretation

Each run saves under `outputs-local/comps/peer_evaluation/<timestamp>/`:

- `config.json`: provider/model, rubric, sampling settings, input paths and threshold.
- `inputs/`: input hashes, targets, upstream pairs, sampled pairs, exact evidence,
  rubric, schema and per-pair prompt previews.
- `runs/`: each attempt's prompt, schema, raw response, stdout/stderr and metadata;
  Codex also supplies JSONL events.
- `judgments/`: checked answers and errors, one file per pair.
- `tables/pair_judgments.csv`: scores, reasons, assessments, resolved citations
  and upstream information joined back only for reporting.
- `tables/target_summary.csv`: all requested training targets, including those
  without peers, with graded/passing/insufficient/failed/not-run counts.
- `tables/summary.csv`: pass rate **among graded pairs** and grading coverage
  **among all sampled pairs**, plus insufficient-evidence and execution counts.
- `tables/human_review_template.csv`: a copyable annotation sheet.
- `history/`: prior versions of replaced files.

Default passing threshold is 3, meaning direct peers. Scores and nulls remain
available so you can inspect every decision. The pass rate describes this
judge's judgments; it is not precision, accuracy, or a valuation-error estimate.
Accepted-output review also cannot measure recall or wrongly rejected peers.

Thin, stale or missing pages can produce abstentions. No fresh web collection
is performed. Independently label a sample, preserve the annotations in a
separate file, and inspect disagreements before trusting the rubric. A human
reviewer should ideally label pairs before seeing model grades. This notebook
does not yet calculate accuracy against human labels or score the holdout.

Transport references:
[Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode),
[Claude programmatic mode](https://code.claude.com/docs/en/headless).
