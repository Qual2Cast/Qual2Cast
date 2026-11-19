# 09_analysis: Analysis

Diagnostics across components: the X-learner facet lift (which facet matches go with people's peer grades, and which the LLM selector keeps on), the error analysis, and an index of the 11-10 v1 integration study (its scripts stay in v1).

**Status (2026-11-19): ported.** Scripts, tests and `analysis.ipynb` are in place; the v1 X-learner runs reproduce to within 4e-7, and the new runs on the current lists and the selector are pinned in `current.toml` (12/12 checks pass).

## Outputs (`outputs-local/v1a/09_analysis/`)

- `facet_uplift/` (48 files)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/error_analysis.py` (script): Kethan; ported as is (reads the v1 record), output to v1a
- `v1/scripts/facet_uplift.py` (script): X-learner (Kethan); estimator unchanged; --cohort, --outcome selector, --features current|record, selector treatment (2026-11-19)
- `v1/scripts/tests/test_facet_uplift.py` (test)
- `v1/notebooks/error_analysis.ipynb` (notebook)
- `v1/notebooks/facet_uplift.ipynb` (notebook): v1 notebook kept as the record
- `v1/notebooks/facet_uplift_stakeholder.ipynb` (notebook): v1 notebook and its figures kept as the record
- `v1/ERROR_ANALYSIS.md` (doc)
- `v1/FACET_UPLIFT.md` (doc)

Commit authors of these files (git): Kethan Bethamcharla, EFL-YL.

## X-learner runs (`current.toml` [analysis.facet_uplift])

| key | cohort | outcome | features |
|---|---|---|---|
| `human_peer` | dev_293 | Barbara grade >= 1 | current (12 B3 signals incl. sub_sector) + agent facet scores |
| `human_rating` | dev_293 | Barbara grade 0/1/2 | current |
| `selector_all` | b3_current (2,538 pairs, 373 targets) | Sonnet selector kept | current |
| `selector_293` | dev_293 | Sonnet selector kept | current |
| `record_peer`, `record_rating` | dev_293 | as v1 | v1's 11 signals; reproduce v1 runs `20261113T190330202875Z` and `20261113T201612982633Z` |

Headline (B3 signals, strong vs weak match, percentage points; adjusted associations, not causal):
- People's peer grade goes with primary services (+24), end markets (+21), customer segment (+21), primary products
  (+15); sub-sector (+2.5) and offering description (+4) add little once the other facets are known.
- The selector keeps most on sub-sector (+13) and offering description (+11); it under-uses services, end markets
  and customer segment relative to people on the same 293 pairs.
- The selector's keep still adds +4.0 pp (0.1 to 7.6) to the chance of a human peer beyond the 12 B3 signals.

Run: `uv run python v1a/09_analysis/scripts/facet_uplift.py --cohort b3_current --outcome selector` (seconds, offline).
`company_profiles_and_comp_examples.html` (v1 stakeholder page) stays in `v1/`.

## v1 integration study (stays in v1)

45 `integration_*` scripts from PR #32 (11-10) re-ran most experiments on other inputs: GPT-6.1 Sol, cited-only and Orbis-aligned facets, 20 retrieval rules, factor sets, growth events, the expanded pool, and a 3,167-row experiment matrix. Results are in `v1/notebooks/comps_and_valuation.ipynb` sections 13-23 and `outputs-local/v1/integration/`. The seven scripts the current pipeline uses moved to 06_labels and 07_judges. Index (first docstring line of each script):

- `integration_barbara.py`: Cache and validate Barbara's published economic-group profile shards.
- `integration_barbara_matches.py`: Evaluate Barbara's published match lists on the shared reviewed pairs.
- `integration_candidate_methods.py`: Run comparable retrieval rules on one frozen company and facet view.
- `integration_claim_check.py`: Check new general facet claims against retrieved company-site passages.
- `integration_company_report.py`: Return a ranked public-peer report for a company name or website.
- `integration_default_candidates.py`: Recompute the B3 shortlist from the source-reviewed default facets.
- `integration_default_golden_eval.py`: Score the source-reviewed retrieval routes on the existing reviewer cohorts.
- `integration_default_report_index.py`: Build the company-input index from the source-reviewed retrieval run.
- `integration_default_scope.py`: Promote the source-reviewed Sonnet scope to the integration default.
- `integration_default_scope_compare.py`: Compare dated and source-reviewed Sonnet B3 on identical targets.
- `integration_embedding_audit.py`: Verify every reused MPNet vector against the installed local model.
- `integration_error_diagnosis.py`: Locate disagreement and coverage issues without inferring causal failures.
- `integration_execute_notebook.py`: Execute only the new local-results cells; preserve the team's saved cells.
- `integration_expanded.py`: Test the published larger peer pool with private-safe target website text.
- `integration_experiment_matrix.py`: Index every executed comparable and valuation configuration in one table.
- `integration_facet_293.py`: Score all saved B3 facet variants on the 45-target reviewer cohort.
- `integration_facet_quality.py`: Audit facet coverage and evidence provenance across team schemas.
- `integration_facet_valuation.py`: Value the fixed 160 targets under every saved B3 facet configuration.
- `integration_factor_cross.py`: Compare the existing factor policies on each saved GPT B3 shortlist.
- `integration_factors.py`: Compare private-supplied factor subsets after a fixed business shortlist.
- `integration_fields.py`: Align shared Orbis facet definitions and WRDS ratios to the frozen v1 pool.
- `integration_golden_routes.py`: Evaluate the four existing peer-selection routes on the reviewed training pairs.
- `integration_gpt_candidates.py`: Build and evaluate GPT facet variants on the fixed v1 company split.
- `integration_gpt_scope_alignment.py`: Check whether fresh GPT fields repeat activities removed by Yiming's dated review.
- `integration_gpt_scope_eval.py`: Check GPT whole-company scope on the fixed ten source-audited cases.
- `integration_growth.py`: Re-score the saved growth-event rule benchmark by cohort and event type.
- `integration_growth_llm.py`: Evaluate the existing growth LLM and hybrid stages on saved event labels.
- `integration_growth_outcomes.py`: Build Xiaozhe's dated revenue-growth labels from the saved EDGAR table.
- `integration_holdout_compare.py`: Compare facet conditions on the same targets for each selection route.
- `integration_holdout_eval.py`: Evaluate frozen B3 and three LLM routes on identical v1 holdout targets.
- `integration_judge_eval.py`: Compare source-citing 0–2 decisions with separately held reviewer scores.
- `integration_judge_input.py`: Freeze reviewed peer pairs for a label-blind source-citing judge run.
- `integration_judge_selection.py`: Evaluate the team's two judge filters on the same frozen reviewed pairs.
- `integration_manifest.py`: Record exact local inputs, outputs and model versions for the v1 study.
- `integration_notebook.py`: Append the executed integration study to the existing v1 results notebook.
- `integration_pipeline.py`: Run the local v1 integration in the order used by the results notebook.
- `integration_regression.py`: Compare train-fitted industry regressions with public-peer multiples.
- `integration_retrieval_compatibility.py`: Check which saved retrieval rules accept the sector-specific facet inputs.
- `integration_retrieval_paired.py`: Compare the same retrieval rules across two facet sources on common targets.
- `integration_review.py`: Evaluate the shared 0–2 reviewer sheet without inventing consensus labels.
- `integration_reviewed_ranks.py`: Compare saved peer lists on one fixed reviewer cohort at a time.
- `integration_scope_eval.py`: Compare the dated Sonnet scope corrections on the same peers and targets.
- `integration_scope_exception_sensitivity.py`: Test source-specific scope exceptions without altering teammate facet files.
- `integration_scope_source_review.py`: Record dated primary-source exceptions to automatic business-scope edits.
- `integration_source_facet_eval.py`: Compare memory-first and cited-only whole-company B3 facets on fixed labels.
- `integration_source_facets.py`: Fill one whole-company profile per firm using cited saved website evidence.
- `integration_sources.py`: Freeze and align the shared v1 inputs without changing their originals.
- `integration_thresholds.py`: Calibrate a B3 z cutoff on reviewer targets, then test valuation separately.
- `integration_validate.py`: Check the completed local study before recording its file manifest.
- `integration_web_evidence.py`: Find official-site snippets for firms with no usable saved website lines.
- `integration_yifan_eval.py`: Test the Orbis-aligned qualitative fields against fixed peer and value labels.
- `integration_yifan_facets.py`: Fill Yifan's Orbis-aligned qualitative schema from saved company websites.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `analysis.ipynb` ported; v1 numbers reproduced.
