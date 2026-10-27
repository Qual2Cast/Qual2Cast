# LLM judge for cosine → LLM outputs — 27 October 2026

## Request and scope

Work from main (`8822ec6`), not the earlier kethan/wip execution refactor.
Build a notebook evaluating the cosine + LLM model's comparable-company outputs,
with Codex CLI as an inference proxy and a Claude CLI alternative. The user
selected a **0–3 business-fit rubric**. This is a downstream evaluator of final
accepted peers, separate from the existing LLM selection model.

## Implemented

- `v0/notebooks/peer_evaluation.ipynb`: six code cells for configuration,
  preparation, prompt/source inspection, execution/resume and reports.
  Defaults to PCTY and preview only; `RUN_JUDGE=True` makes real calls.
- `v0/peer_evaluation.py`: explicit candidate/judgment inputs, training-only
  pairs matching the existing z-qualified, current-prompt, complete-target
  selection rule. Only score=1 outputs are evaluated. Zero-peer targets remain
  in the target report; incomplete upstream decisions are separately identified.
- The judge uses company names/websites and saved cleaned website passages
  (default 1,500 words/company). Existing facet input filters remove figure
  lines. Generated facets, original reasons/verdicts/ranks/similarities, SIC and
  financials are excluded from the prompt. Rubric: 3 direct, 2 partial,
  1 weak/adjacent, 0 different business, null insufficient evidence.
- Answers include offering/customer/business-model assessments and source
  citations. Numeric grades require citations from both companies; code resolves
  supplied labels back to exact text and URLs. Invalid labels/score-verdict
  mismatches become failed answers, not numeric grades.
- `v0/cli_models.py`: small transport reused from the earlier branch without
  merging its pipeline changes. Codex uses `exec`, JSON schema and final-message
  output; Claude Code uses `-p`, JSON schema and `structured_output`. Both use
  normal CLI authentication, stdin prompts and saved raw logs. No HTTP server,
  Anthropic SDK requirement, framework or automatic retry loop was introduced.
- Each pair's successful result resumes by backend/model/effort/schema/prompt
  and exact evidence fingerprint. Call failures leave subsequent pairs not_run
  and return a partial report. Failed/invalid pairs can be retried on rerun.
- `comps_and_valuation.ipynb`: only two appended cells. Its final section
  exports a frozen selection-judgment CSV and input handoff JSON alongside
  the candidate run. No existing code cell, output or valuation was changed.
- Setup/output documentation in `v0/PEER_EVALUATION.md`, dependency list in
  `v0/requirements-judge.txt`, entry links in both READMEs, output definitions
  in `docs/data_dictionary.md`. Standard venv/notebook caches are ignored.

Outputs: `outputs-local/comps/peer_evaluation/<run>/`, including configuration,
input hashes and evidence, prompt previews, call attempts, checked answers,
pair/target/aggregate CSV reports, human-review template and archived replacements.
Provider comparison uses separate run directories with the same input settings.

## Validation and limitations

Python AST parsing succeeded for both new modules and every code cell of the
new and modified notebooks. `git diff --check` passed. No tests were added or
run; no live CLI call, inference evaluation, embedding download or clean Python
environment installation was performed. There are no synthetic grades or
claimed numerical evaluation results.

CLI contracts were read in the official documentation:
- https://learn.chatgpt.com/docs/non-interactive-mode
- https://code.claude.com/docs/en/headless

Judge pass rate is not accuracy. Accepted-peer review cannot measure recall.
The evidence is existing saved website text, potentially stale or thin, and
can overlap upstream gap-fill evidence. Citation existence is checked, not
semantic entailment. Independent human labels, judge calibration and holdout
evaluation remain open. The notebook exports a human-review template but does
not yet calculate accuracy against those annotations.

## Data version and next step

Snapshot: `company_list_v3`, SHA-256
`3ab9a43e7426c1f41a77055a6d3ca9553845cb3046a954e28dc5c2a82c934eae`.
Default saved candidate run: `20261025T080854Z`; current shared selection table
is an explicit input. The preferred workflow handoff freezes a judgment copy
for each new matching run. Snapshots and saved source captures were not edited.

Next: open the new notebook, inspect the rubric and PCTY prompt, select an
explicit model, and run a small live sample. Independently label a sample
before treating automated pass rates as reliable quality evidence.
All changes are local on main. Nothing was committed or pushed.

## Full-training configuration requested

The user requested evaluating the entire training output, following an earlier
request to execute inside VS Code. Installed `v0/requirements-judge.txt` in the
project `.venv` using VS Code's integrated terminal. The user selected a kernel.

Changed notebook `TARGET_TICKERS=None`, `MAX_PAIRS=None`, `RUN_JUDGE=True`, and
`RUN_DIR="outputs-local/comps/peer_evaluation/training_20261027"`. The Config
class now also defaults to all training targets. Updated the notebook's opening
instructions and guide to match. Programmatic preparation in the installed
environment succeeded: all 373 training targets, 663 accepted pairs across
277 targets, no missing upstream verdicts; 96 targets have no accepted peer.
Prompts/evidence and source manifests are saved in that run's inputs directory.

The full live batch has **not** started. Repeated VS Code UI actions did not
reliably focus the terminal or run commands; visible state stayed unchanged.
The configured notebook is ready for the user to click Run All in VS Code.
An optional temporary notebook runner was prepared at
`/private/tmp/run_qual2cast_peer_in_vscode.py`, but its terminal launch was not
observed and no execution log or full-run results are claimed. Do not treat
preparation as a completed live evaluation. No tests were added or run for
this configuration change, and no source data changed. Nothing was committed
or pushed.

## Execution correction and user-directed stop

The earlier UI observations were stale: the terminal command did run after all.
The full-training runner executed a live partial batch. Some valid citation
references were returned as `[T:P1.2]` or that label followed by prose; the
parser previously required only `T:P1.2`. Updated parsing to extract that exact
ID and still look it up in the supplied passages, taking the quoted text and
URL only from saved source evidence. Four existing responses were recovered
from raw output without additional inference calls.

The user clarified that they want only the notebook code configured for all
training results and will execute manually. Sent SIGINT to the specific
temporary runner and terminated its kernel; verified neither that runner nor
an inference process for this run remained. Other VS Code kernels were left
alone. Partial output records are preserved under `training_20261027`, not
represented as a completed evaluation. No further model calls were started.

Current notebook settings: `TARGET_TICKERS=None`, `MAX_PAIRS=None`,
`RUN_JUDGE=True`, `RUN_DIR=None`. A manual Run All will create a new run;
to reuse the partial results, explicitly set RUN_DIR to the preserved folder.
All 373 training targets remain in the report; 663 accepted pairs across
277 targets are eligible for judging. No source data changed or commit/push
was made.

## CLI discovery for manual notebook execution

The user chose to keep subprocess CLI inference rather than migrate to an SDK.
Updated `cli_models.executable` to prefer an explicit environment override,
then PATH; Codex additionally discovers the macOS ChatGPT app's bundled CLI
under `/Applications` or `~/Applications`. Invalid explicit overrides fail
with a path-specific message. Claude retains the same subprocess transport.

The peer-evaluation notebook now exposes optional `CODEX_BIN` / `CLAUDE_BIN`
settings, reloads its local modules on setup, and prints the selected executable
before preparing a live run. Preview mode needs no CLI. This addresses the
VS Code kernel PATH error without a machine-specific path in the notebook.
No tests, notebook execution or model calls were run for this update. Input
snapshot remains `company_list_v3`; no source captures or prior results changed.
Next: the user can rerun the notebook from its first cell in VS Code.

## Saved-run findings section

User requested simple analysis at the bottom of the existing notebook.
Appended section 7, independently runnable from saved CSVs with no CLI calls.
Default `ANALYSIS_RUN` is the user's completed `20261027T190213461887Z` run.
Includes explicit-denominator metrics; counts for grades, abstentions, errors
and pending pairs; two saved charts (outcomes and fit dimensions); target
coverage; evidence/validation attention list; deterministic illustrative
examples comparing upstream and judge explanations; full-citation example
export and an error list. Derived outputs are archived on replacement.
Added matplotlib to the notebook dependency list and documented outputs.

Read-only inspection found 663 pairs, 615 numeric grades, 139 passing at 3,
395 partial, 78 weak, 3 non-peers, 44 abstentions and 4 invalid citation-range
answers. No pending pairs. No score or selection/valuation logic changed.
Source remains company_list_v3. Earlier notebook cells and outputs were kept.
No tests, new analysis-cell execution or model calls were performed. Next:
user runs only section 7 in VS Code; independent human labels remain pending.

## Integrate latest main and publish

User authorized pulling main updates and pushing peer-evaluation work. Fetched
origin/main at e2bf5a2e (19 new commits), committed the local work and rebased.
Resolved PROJECT_STATE by preserving both updates and the matching notebook
by taking all updated-baseline cells unchanged plus the handoff as section 11.
The updated baseline writes to comps_pilot_targets; changed evaluator split
lookup to follow the candidate output root (universe remains shared in comps).
The original 663-pair defaults/results remain distinct from the new SIC2 run.
Preserved local-only peer-evaluation raw output/analysis ignore rule despite
upstream's broader comps output sharing. No new inference or tests performed.
