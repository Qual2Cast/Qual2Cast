# Focused pipeline on kethan/wip — 12 November 2026

## Request and branch

Make the pipeline Codex-only by default, with stronger facet fills and a
weaker LLM judge; retain Claude instructions, two methods including B3 +
LLM filter, and navigable provider/model/pipeline-specific outputs.
Confirmed `kethan/wip` and a clean starting working tree. No branch switch,
commit, push, fetch or destructive reset in this implementation session.

## Implementation

- Added `pipeline/`: `workflow.py`, `run.py`, one main `pipeline.ipynb`,
  two role-model TOML configs, and README. Rewrote the root README around
  this entry point; updated AGENTS/v1 README/data dictionary/state.
- Selected B3 and B3 + binary LLM filter to isolate the filter's effect.
  The earlier initial suggestion of an agent-loop second route was
  replaced during inspection with the B3 baseline. No agent-loop web
  adapter is required or invoked in these two routes.
- Codex: Sol high fills, Sol medium filters, Luna medium grades. Claude:
  Sonnet high fills, Sonnet medium filters, Haiku medium grades. All calls
  use CLI authentication; no API key or SDK migration required.
- The focused runner reuses the v1 schemas, B3 math, selector prompt,
  evidence-only 0–3 judge and valuation functions. No copied method or
  research-matrix rerun. Existing research files remain accessible under
  v1; v0/pre-v0 remain historical. Only two routes are exposed here.
- Added Codex to the binary selector and included backend/effort in call
  identity. Codex facet compatibility function now calls the common CLI
  wrapper. Shared Codex calls disable web search, retain structured JSON,
  raw logs and authentication through the CLI. Individual failures/timeouts
  do not abort every subsequent call; systemic auth/quota failures do.
- Added explicit-pair preparation to `PeerEvaluation`, preserving its
  historical preparation method. New workflow grades all B3 pairs once
  without z filtering or sampling; no facets, selector reasons, scores or
  financial fields enter judge prompts. Both routes reuse those grades.
  Numeric grades require valid supplied citations from both companies;
  insufficient evidence stays null. Grades remain diagnostic.
- Outputs are local under `outputs-local/pipeline/<provider>/<model-effort
  variant>/<run>/`; stage data, per-route peers/results/valuation and
  comparison reports are distinct. Each run freezes config, code hashes,
  snapshot/split/page hashes. Resume with the same config and run directory;
  completed model calls are cached and derived outputs archived/rebuilt.
- Financial table read only for existing universe eligibility and later
  median selected-peer valuation; every target, no-peer case and incomplete
  selection stays in output. Overall coverage and common-target valuation
  errors are separate. Rejected-peer judge reasons are in filter_audit.

## Data and limitations

Uses manifest `company_list_v3`, original SIC2 split `20261027T204930Z`,
and the saved website captures. Default: all 373 training targets with all
533 profiles and a training-only peer pool, excluding self. Optional target
tickers do not shrink the fill/pool. Fresh fills follow the old knowledge-first,
saved-page gap-fill and split-check protocol. Failed gap fills retain earlier
values. They do not automatically inherit source-reviewed Sonnet corrections.
Current claims and scope still need verification. This is not an expanded
pool, a fresh final holdout, or proof that Sol/Luna improves accuracy.

## Checks and next step

Parsed modified/new Python ASTs, notebook JSON and code cells, both TOML
configs; checked diff whitespace. No tests added/run, no notebook execution,
no model calls or new experiment outputs, no package installation. Live
Codex/Claude compatibility and end-to-end results remain unverified.

Next: open `pipeline/pipeline.ipynb` with `.venv`, select the config, set
`EXECUTE = True`, run cells in order; save printed run directory for resume.
Inspect profile coverage, failures, common-target error and high-grade
rejections, then hand-review pairs before claiming a model improvement.

## Live Codex execution started — 12 November 2026

User authorized running the Codex pipeline. Started the complete 533-profile,
373-training-target workflow, two fill/filter workers, Sol high fills, Sol
medium filter and Luna medium judge. Run directory:
`outputs-local/pipeline/codex/fill-gpt-6.1-sol-high__filter-gpt-6.1-sol-medium__judge-gpt-6-luna-medium/20261112T191148461107Z`.

The initial `uv run` failed on sandboxed cache access, and its expanded-access
retry found an incompatible Python 3.6 executable. The running command uses
`uv run --no-sync --python .venv/bin/python python -u pipeline/run.py --execute`
with expanded permissions. It uses the existing Python 3.14 venv; packages,
Python pin and environment were not modified. First two saved company profiles
have `llm_status=ok`. The process was still running at handoff, in facet fill;
this is a launch/progress record, not a completion or accuracy result. No
filter, judge or valuation completion has yet been established for this run.

## User-requested pause — 12 November 2026

Stopped the live Codex run with SIGINT at the user’s request. The process
exited 130; a process-table check found no remaining pipeline/fill/model
children for this run. Saved 384/533 first-pass profiles, all with
`llm_status=ok` (execution/schema status, not factual accuracy). Gap fills,
B3, filtering, judging and valuation have not completed. Resume the same
run directory and configuration only when the user asks to continue.
Run checkpoint: `outputs-local/pipeline/codex/fill-gpt-6.1-sol-high__filter-gpt-6.1-sol-medium__judge-gpt-6-luna-medium/20261112T191148461107Z/pause.json`.

## User-requested resume

Resumed the same run/config on `kethan/wip` with shell session 16853.
Startup confirmed 384 cached profiles reused and 149 remaining first-pass
companies, two workers. Command adds `PYTHONUNBUFFERED=1` for live stage logs.
The earlier pause.json is a historical stop record; resume.json records this
restart. The pipeline is running again; downstream completion is not claimed.

## Dependency repair and restart

The prior process completed all 533 profiles and all 15 saved-page gap-fill
calls, then failed at B3 with ModuleNotFoundError: sentence_transformers.
Installed sentence-transformers and every core dependency from pyproject.toml
into the existing .venv using uv pip. uv pip check reports all 145 installed
packages compatible. Package versions are captured in environment.json in
the run folder. Resumed the same run in shell session 89916; facet startup
confirmed all 533 profiles reused with no new fill calls. B3 and downstream
stages are in progress, not yet confirmed complete. No tests run.

## Resume after allowance reset

User requested continuation after the usage limit reset. Confirmed no old
pipeline process remained, then resumed the same config/run on kethan/wip
(session 88006). All 533 profiles reused, B3 reproduced 2,438 pairs. At
restart there were 181 successful filter results, three failed saved
filter attempts and one failed judge attempt; 192 target filters needed
completed results. Cached filter calls were skipped. New PBI and KORE
filter calls succeeded. Execution is ongoing; no final completion claimed.

## 13 November — restart from judge pair 379

User requested stopping the stalled call and restarting from 379. Sent
SIGINT to verified process group 86847 and confirmed no old children
remained. Added optional one-based start_pair/--judge-start support;
reporting retains all earlier results, including five invalid answers
left for a later normal resume. Syntax parsed, no tests run. Restarted
same run/config in session 56072 with --judge-start 379. All fills and
373 filters cached; 570 of 2,438 B3 pairs accepted by the filter. At
judge startup, 379 and 380 already had successful cached answers and
were reused; execution proceeds from the next unfinished pair. No
final completion or accuracy result claimed.

## User-requested pause — 13 November

Stopped session 56072 with SIGINT (exit 130). Saved judge statuses: {'ok': 1593, 'invalid_answer': 15}. Results retained in the same run directory; resume only when the user requests it.

## User-requested continuation after 1,593 valid judgments

Confirmed kethan/wip and no active old pipeline. Restarted the same run in
session 45025 with default judge-start 1: 1,593 valid results are reused;
15 invalid answers are retried along with 830 unprocessed pairs (845 total
without valid results at restart). Fills and all Sol filters remain cached.
The pipeline is running; no final completion claimed.

## Full pipeline execution finished

Session 45025 exited 0 and saved both routes’ valuations, pair results,
comparison CSVs/common-target summary and overview PNG. All 533 profiles
and 373 Sol target filters are complete. All 2,438 Luna pairs were
attempted: 2,272 numeric grades, 156 insufficient-evidence responses, and
10 invalid answers remain explicit failures (no not-run pairs). These
10 invalid answers were not silently counted as grades or retried again.
B3 provides estimates for 373 targets; filtered route for 245. On those
245 common targets, B3 median APE is 29.4474%, filtered 30.4269%; the
filtered route’s lower full-coverage headline median does not prove an
improvement. These are training/development results, not fresh holdout
validation. Run completion.json records execution completion with the
remaining judge failures. No new model calls in this status check.
