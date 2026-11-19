# Error analysis of profiles and peer selection

Start with `v1/notebooks/error_analysis.ipynb` using the uv `.venv` kernel.
For a report without notebook execution:

```bash
uv run python v1/scripts/error_analysis.py
```

This is an offline workflow. It makes no model calls, searches, crawls or
embedding changes and reads no financial tables. Inputs are not modified.
Each execution creates a new `outputs-local/v1/error_analysis/<timestamp>/`.
Use `--out` only for a fresh directory. Source hashes and pinned paths are in
`manifest.json`; Python users can override paths through `error_analysis.Config`.
No packages beyond the existing project dependencies are needed.

## What it reads

- The pinned B3 training-candidate run and saved similarity-method alternatives.
- The matched Haiku/Sonnet screens and direct selections (same Haiku profiles).
- Current general Haiku and Sonnet facet tables for all 533 companies.
- The 480 historical human facet claims from 40 companies, including original
  text, notes, evidence URLs and labelers.
- Round-1 human pair labels, with the established exact-majority rule; completed
  rows in round 2 when `round2_filled.csv` is present. Ties stay unresolved.
- One-shot Sol grades and both saved Sonnet agent-loop runs. Different judges'
  scores are not averaged or substituted for human labels.
- Cleaned saved website passages for companies in review cases (600 words per
  company, existing figure filters, URLs/capture dates; no new source retrieval).
- Saved information-weight, facet-label and ranking diagnostics, copied as
  context with their original run provenance. These do not establish causality.

## How to use the outputs

1. **`report.md`**: computed findings, denominators, method comparisons, review
   cases, next experiments and missing inputs. No LLM-written conclusions.
2. **`facet_review.md` / `facet_audit.csv`**: every historical problem claim,
   original reviewer note, evidence URL and the corresponding current texts.
   Exact-text applicability is explicit. A changed text is neither a proven
   correction nor a proven error. The historical benchmark is not the current
   fill's accuracy score.
3. **`facet_priorities.csv`**: historical problem rates by facet and exact-current
   checkable counts. Company size is marked excluded from B3.
4. **`profile_differences.csv` / `profile_disagreement_by_facet.csv`**: all current
   Haiku/Sonnet text, status and category differences. Categories compare full
   semicolon-separated sets, ignoring order; this is different from the earlier
   leading-category agreement measure. A disagreement is not an error label.
5. **`pair_comparison.csv` / `method_metrics.csv`**: saved list membership,
   reasons and human grades; labeled precision, label coverage, and retention of
   known good/direct peers within the reviewed pool. Never count an unreviewed
   pair as a non-peer. Retention is not universe-wide recall.
6. **`screen_disagreements.csv`**: every disagreement across the same 2,396 B3
   pairs, not only those with human labels.
7. **`judge_comparison.csv` / `judge_metrics.csv`**: exact grades and human-label
   coverage per evaluator. Model/context/retrieval differences remain visible.
8. **`case_queue.csv` / `cases/*.json`**: all human-reviewed pairs, agent-run
   pairs and Haiku/Sonnet screen disagreements, including agreement controls.
   Observed flags identify where to investigate, not a proven causal stage.
   Each packet contains original reviewer scores/notes, profile fields from both
   models, historical facet claims, selector/judge explanations and passages.

Notebook charts show historical facet problems and known-peer retention. They
are saved into the same analysis run.

## Optional manual eval agent

The user's first version is saved-results analysis only. Run All has no live
model option. `manual_agent_instructions.md` provides a structured diagnosis
format; give it to your evaluator with `report.md` and individual case packets.
Ask for source reference IDs, implicated facets, explanation, proposed change
and the verification needed. All model diagnoses must remain hypotheses until
checked; the agent must not edit source profiles or treat model memory as proof.

## Limits and next steps

Only two targets currently have majority peer labels; round 2 may be missing.
A human saying two companies are not peers does not identify a false facet.
Historic label text usually differs from current fills, so accuracy of current
profiles remains largely unmeasured. The old 663-pair 0–3 run, sector/industry
feature experiments and valuation outcomes are not pooled into this 0–2
comparison. Extend via explicit adapters and preserve each experiment's scope.

Review examples, verify exact current claims, and then run one controlled change
at a time. Do not optimize toward a model judge's approval rate. Broader human
labels (200–500 pairs) and current-facet checks (50–100 companies) remain needed.
