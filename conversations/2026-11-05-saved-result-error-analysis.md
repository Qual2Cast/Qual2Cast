# Saved-result error analysis — 5 November 2026

## Request and boundary

Kethan wants error analysis as his main contribution, tracing possible facet
failures across matching methods, human labels and model results. He explicitly
chose saved-results analysis first and will run any LLM diagnosis manually.
No new model calls, searches, source scraping or embedding runs are authorized
by this implementation. Existing uncommitted v0 peer notebook edits preserved.

## Added

- `v1/scripts/error_analysis.py`: pinned configuration, human-label majority
  joins, exact-text historical facet applicability, all 533 current-profile
  comparisons, existing similarity-list comparisons, matched model selection,
  evaluator agreement, case queue and source-linked review packets.
- `v1/notebooks/error_analysis.ipynb`: offline builder, report display,
  historical facet-problem chart, known-peer retention chart, case explorer and
  manual evaluator instructions. No live-call flag or CLI model invocation.
- `v1/ERROR_ANALYSIS.md`: sources, commands, output schema and limits.
  README, data dictionary and project state updated.

Each run writes a fresh directory. Earlier development report runs were moved
under `outputs-local/v1/error_analysis/history/`; inputs stay unchanged.

## Executed findings

Latest offline report:
`outputs-local/v1/error_analysis/20261105T191342914598Z/report.md`.

- 36 peer-review pairs; 32 majority labels across PCTY and WEN. Round 2 filled
  labels are absent and explicitly reported as a gap, not filled in by a model.
- 480 historical facet labels across 40 companies; 41 exactly match current
  Haiku text (case/whitespace normalized), 33 match Sonnet text. Only 10 Haiku
  matches are outside size. Different current text is not assigned an old label.
- Exact-current non-size partial errors: DORM end markets (missing powersports /
  off-road vehicles); LUCK primary services (missing waterpark/amusement park
  admissions and PBA events). Original reviewer notes/URLs are preserved; the
  source URLs were not newly fetched or independently reverified.
- B3 retains 11/11 known direct/adjacent peers in the reviewed pool; selector
  comparisons expose lost adjacent peers. Precision excludes unlabeled outputs;
  retention is not a claim of universe-wide recall.
- 193 Haiku/Sonnet screening disagreements among 2,396 identical B3 pairs.
  These and human/agent-reviewed pairs produce 258 case packets, including
  controls, unresolved labels, evidence gaps and observed stage flags.
- 6,396 profile/facet comparisons. Full category sets are compared ignoring
  ordering; this differs from model_selection_eval's leading-category measure.
- Model evaluator comparisons preserve model/context differences; lookup
  effects are not inferred from the Sonnet-versus-Sol agreement gap.

## Artifacts and interpretation

`report.md` is computed from saved values, not written by an LLM. `facet_review.md`
lists every historical problem claim, note/labeler/URL and both current texts.
`manifest.json` hashes each consumed input and records configuration and commit.
`cases/*.json` supplies reference IDs for current facets, human reviews, model
explanations and 600 words of filtered saved evidence per company. Optional
manual diagnoses must cite references and remain hypotheses. No original facet
value, scoring weight or selection rule is edited automatically.

This version explicitly excludes pooling the historical 663-pair 0–3 study,
sector/industry facet experiments or valuation outcomes into general-facet
accuracy. Saved prior information/rank diagnostics are contextual artifacts,
not causal evidence. It does not claim to semantically audit all company facts.

## Checks, data and next step

Offline builder completed; module and all notebook code cells parsed;
`git diff --check` passed. Generated case JSON was reopened with strict parsing
during artifact inspection. No tests or notebook execution. Source snapshot
`company_list_v3`, B3 `20261104T074915Z`, similarity `20261104T075557Z`, general
facet prompt `2026-10-25k`, selectors `2026-11-04a`. Existing inputs unchanged.

Next: review cases in the notebook, reverify exact current facet claims, and
expand human labels before tuning. Run any external diagnosis manually using
`manual_agent_instructions.md`. Changes remain local; no commit or push.

## Publication requested — 6 November 2026

The user requested pushing the evaluation notebooks to GitHub main. The
publication includes the notebook, supporting module, guides, state/dictionary
updates and the user's small v0 notebook edit. Generated analysis folders stay
local; teammates can regenerate them with the offline builder. No new model
calls, tests or notebook runs were performed for publication. The report's
pinned initial agent runs are unchanged; later Sonnet-context/search agent
variants must be added explicitly for a new comparison.
