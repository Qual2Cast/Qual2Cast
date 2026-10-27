# Main notebook and CLI model backends

## Request

Refactor the current repo into one runnable pipeline notebook, print and save
outputs at each stage, support both Codex CLI and Claude CLI as inference
proxies, and make a fresh clone straightforward to run. Keep the implementation
simple; no proxy server, orchestration framework, or layered retry mechanisms.

## Changes

- Root `pipeline.ipynb` is the main entry point (18 cells, 9 code cells).
  One settings cell controls backend/model/effort, workers, optional universe
  limit, target selection, training/holdout selection and direct suggestions.
- `v0/pipeline.py` connects existing universe, facets, split, candidates, judge,
  direct suggestions and valuation code. It displays and persists stage results
  under one timestamped run folder. The same folder/settings resumes expensive
  calls, and replacements are archived. Optional full-pool suggestions are
  explicitly skipped by default because their prompts are large.
- `v0/cli_models.py`: synchronous subprocess calls using normal CLI login.
  Codex uses `exec`, stdin, an output schema and final-message file;
  Claude Code uses `-p`, stdin, JSON/schema output and `structured_output`.
  Both save raw logs, schema, prompt and parsed response. No API keys are
  read for CLI backends and no live auth files were inspected.
- `fill_facets.call_model` dispatches the same prompts/schemas to `codex`,
  `claude-cli`, or the retained original `claude` API. Facet cache identity
  includes backend/effort. Judge, suggestion and optional verification runners
  now accept the same backend options. CLI stage failures stop further queued
  work and leave finished outputs for resume.
- Judge tables include only current candidate pairs; superseded judgments
  stay on disk but cannot silently enter a changed candidate set.
- Root README now starts with clone/venv/kernel/CLI setup and the main notebook.
  Added runtime/development requirements; ignored venv and notebook/test caches.
  Existing method notebooks and pre-v0 experiments were retained, not imported
  or modified by the new workflow.

## Method decisions retained

Snapshot v3; EV/EBITDA range 3–30; twelve knowledge-first facets with saved-page
gap fill; 70/30 size split, seed 2026, showcases in training; equal facet weights;
training-only peer pool; z ≥ 2 LLM judgment; similarity-weighted mean/median and
no-matching/SIC baselines. Existing v0 permits one usable peer and abstains if
there are none. Independent labels, weight fitting, dated financial definitions
and a frozen final holdout experiment remain open.

## Validation

Temporary Python 3.12 environment (not committed):

```bash
MPLCONFIGDIR=/private/tmp/qual2cast-mpl MPLBACKEND=Agg \
  /private/tmp/qual2cast-pipeline-venv/bin/python -m pytest \
  v0/tests v0/verification/tests website_scrape/tests -q
```

**166 passed.** Includes both CLI subprocess contracts and errors, per-stage
resume, target exclusion and training-only peers, output tables, target-outcome
isolation, and all nine main-notebook code cells executed sequentially. Tests
replace model inference and embeddings with synthetic fixtures; they do not
spend account allowance, download the embedding model or claim financial accuracy.

The installed Codex executable's `exec --help` was inspected for supported flags.
Claude CLI is not installed here; its adapter was checked against official
documentation and simulated CLI JSON envelopes, not a live Claude session.
No full live model or embedding run was performed. Fresh-clone dependencies
are documented; the temporary test environment used the bundled base runtime.

Official transport references:
- https://learn.chatgpt.com/docs/non-interactive-mode
- https://code.claude.com/docs/en/headless
- https://code.claude.com/docs/en/cli-reference

## Data version

`company_list_v3`, SHA-256
`3ab9a43e7426c1f41a77055a6d3ca9553845cb3046a954e28dc5c2a82c934eae`.
Source snapshots and tracked website captures were not edited.
Test outputs are temporary; no synthetic profiles or valuations were published.

## Follow-up audit after disconnect

Compared the implementation with the original request: one Run All notebook,
step displays and saved outputs, one backend selection across model stages,
fresh-clone setup, and resumable runs are present. The main pipeline consumes
the tracked website captures; recollection and evidence studies stay separate.

Two resume gaps were fixed:
- The facet runner now returns failure if any model pass fails, and the main
  pipeline stops. Previously a failed website gap fill could be hidden by a
  successful first-pass profile. The standalone command also exits unsuccessfully.
- Cached peer judgments with unanswered candidates are retried; they no longer
  remain stuck as apparently successful responses on every resume.

Added checks for both cases and reran the same three test directories:
**168 passed in 12.47 seconds.** No live inference or embedding download was
performed. Source data and the method remain unchanged; edits remain local.

## User-directed gap-fill behavior restoration

The user requested retaining the original behavior for failed website gap fills.
Removed the audit's new failure return/exception and restored the facet runner's
previous scheduling behavior. A failed gap fill is logged, first-pass facets
remain available, unknown facets stay unknown, and the notebook may continue.
A later rerun retries the gap fill. Removed the check requiring this optional
pass to stop the pipeline and restored the existing runner check's assertions.
Notebook/output documentation now describes continuation. The peer-judgment
resume fix remains: a review missing a candidate score is retried on rerun.

No tests were run for this restoration. The 168-test result above predates it.
The same v3 data snapshot is unchanged; edits remain local and uncommitted.

## Next action

Install the root requirements in a project environment, sign in to either CLI,
open the main notebook and run a small integration trial. Then set
`COMPANY_LIMIT=None` for the full universe. Use explicit model names for
provider comparisons, preserve run directories, and review real inference
outputs before drawing conclusions. Nothing was committed or pushed.

## Publication requested

The user requested committing and pushing the current edits to `kethan/wip`.
Fetching origin shows the remote branch at `9c9d77b` (older SIC experiment),
which was intentionally excluded by the earlier local reset to main. The user
explicitly declined creating a backup branch. Publish the current refactor
directly with an explicit lease on the old remote tip. No unrelated
new main commits are being pulled into this change. No additional tests were
run for publication; data version and validation limits remain as above.
