# 09_analysis (v2): trait X-learner

Tests whether pairs that match on an economic trait (recurring revenue, cyclical demand, big-ticket, people-delivered,
large customers, asset-heavy) are judged peers more often, beyond what B3's facet similarities already say, and
whether that differs by kind of target (services or not, consumer-facing or not). The plan is fixed in
[`PREREG_TRAITS.md`](PREREG_TRAITS.md); read it before the results.

v1a's X-learner is in this component too (`scripts/facet_uplift.py`, copied unchanged apart from paths); its
pinned runs stay in `outputs-local/v1a/09_analysis/`. `trait_uplift.py` imports that estimator (`estimate_fold`, `group_splits`, `arm_support`, `load_pairs`,
`b3_signals`) unchanged and adds only what the pre-registration needs: trait matches as treatments, one fit then
averages by target tag, a shuffle test for p-values, a refit bootstrap for intervals, and Benjamini-Hochberg across
all 60 tests.

**Status (2026-11-24): first pre-registered run done** on Matthew's rubric v2 labels (262 pairs, 40 targets),
`outputs-local/v2/09_analysis/trait_uplift/20261124T101142641398Z/` (pinned in `current.toml`), after the plan was
committed (`41551066`). 8 minutes on 14 workers.

**See it in the notebook:** `analysis.ipynb` section 3.1 (round 1: headline table, lift intervals, lift by slice, the
shuffle test and Benjamini-Hochberg explained with charts, a reliability table), 3.2 (round 2, the same charts plus
the stability and peer-disagreement diagnostics) and 3.3 (the improvement ledger). Figure copies for the website:
`outputs-local/v2/09_analysis/trait_uplift/<run>/figures/<stamp>/` for each round's run.

**Improvement ledger** (`scripts/progress.py`, how-to in [`PROGRESS.md`](PROGRESS.md)): one append-only row per
pipeline version with its overlap against the human labels (precision and recall, any and direct peer, target means
with 95% intervals). Seeded 2026-11-24 with the baseline (B3 all, B3 top 7, selector, agent ≥ 1, agent 2 on
`matthew_v2_262`); `outputs-local/v2/09_analysis/progress/` holds `ledger.csv`, `latest.csv` and `progress.png`.
Run `uv run python v2/09_analysis/scripts/progress.py show` to refresh the chart.

## First results (single reviewer, rubric v2 wording)

All 60 tests were supported; 15 are findings at BH q = 0.10 (7 direct, 8 peer). Lift in percentage points, adjusted
for the 12 B3 signals and the other traits; "boot" = usable refit-bootstrap draws of 200.

| trait | direct peer (primary), all pairs | peer (secondary), all pairs | read |
|---|---|---|---|
| **large customers** | **+8.6** (-0.3 to +15.4), q 0.088, finding | **+19.0** (+7.6 to +35.9), q 0.022, finding | the one robust result: full support (232 pairs, 40 targets, all 200 draws), both outcomes, doubly robust check same sign; strongest for consumer-facing targets (direct +9.8, +1.2 to +15.6) and non-services targets (+11.6) |
| people-delivered | +11.2 (+5.8 to +17.1), q 0.055, finding | -2.0, null | direct only; a rare trait (85 overlap pairs, 55 usable draws), so the interval is shaky; the services-no cell (8 pairs, 5 targets, 19 draws) should not be read |
| big-ticket | +8.4 (-4.4 to +13.6), null | **+30.1** (+9.6 to +47.6), q 0.022, finding | peer only, the outcome inflated by the loose customers wording; rare trait (70 pairs, 73-76 draws) |
| cyclical demand | -6.8, null; services-yes cell -10.5 (q 0.048, finding) | -8.4, null; services-no cell -20.6 (q 0.022, finding) | negative and unexplained: both finding cells have bootstrap intervals that cross zero and doubly robust checks that disagree in size or sign; treat as a question, not a result |
| recurring revenue | +1.7, null | -5.6, null | no signal |
| asset-heavy | +7.8 (+2.2 to +14.4), q 0.134, null | -4.7, null | no finding after the correction |

What this says, carefully:
- **Customer size matters beyond what B3 sees.** Pairs whose companies both sell mainly to large enterprises or
  government, or both don't, are judged peers more often on both outcomes. B3 has no direct customer-size signal (company
  size is out, and the customer-segment facet names customer groups, not their size, though its text can hint at it). Caveat: it sits close to the
  definition list's "same customers" question, and Matthew answered that question with the loose v2 wording, so part
  of the lift may be that question restated. The rubric v3 rerun (tighter wording, two reviewers) is the test.
- **Aziz's sub-segment question:** the large-customers lift is larger for consumer-facing and non-services targets,
  but the pre-registration tests each cell against zero, not the cells against each other, so "matters more for X"
  is not established.
- **Next:** rerun this plan unchanged on rubric v3 consensus labels. If large customers holds, it is the first
  candidate for the selector prompt (a dated prompt version, scored in the improvement ledger).

## Round 2 (pre-registered separately: [`PREREG_TRAITS_R2.md`](PREREG_TRAITS_R2.md), commit `b3b5e309`)

Four more traits, designed after round 1 (cyclical demand split into the two facts that decided it, plus two PE value
drivers): maintenance-led, publicly funded, serial acquirer, mission-critical. Same design; covariates add all six
round-1 traits; its own BH family of 40 tests. Run `outputs-local/v2/09_analysis/trait_uplift/20261124T111715563218Z_r2/`
(pinned in `current.toml [analysis.trait_uplift_r2]`), 4 minutes on 14 workers.

| trait | direct peer (primary), all pairs | peer (secondary), all pairs | read |
|---|---|---|---|
| **mission-critical** | **+10.6** (+4.3 to +18.3), q 0.040, finding | **+25.1** (+9.4 to +42.4), q 0.013, finding | the strongest trait of either round: a finding in all 10 tests, full support (223 pairs, 40 targets, all 200 draws), doubly robust +10.2; tracks the business (direct peers disagree 8%, non-peers 37%). A lead: confirm on rubric v3 labels |
| maintenance-led | unsupported | unsupported | only 4.1% of companies yes, 21 mismatched pairs; one fold lacked support every time. Tracks the business in the diagnostic (5% vs 14%) |
| publicly funded | unsupported | unsupported | 5.4% yes, 23 mismatched pairs; does not track the business (7% vs 5%) |
| serial acquirer | unsupported | unsupported | 6.0% yes, 31 mismatched pairs |

Unsupported means no estimate (p = 1 in the family), not zero: more labelled pairs involving these kinds of
companies would make them measurable.

## Run

```bash
uv run python v2/09_analysis/scripts/trait_uplift.py \
    --traits outputs-local/v2/02_profiles/traits_new/tables/traits.csv          # round 1: 8 minutes on 14 workers
uv run python v2/09_analysis/scripts/trait_uplift.py --round 2 --traits outputs-local/v2/02_profiles/traits_new/tables/traits.csv \
    --traits-r2 outputs-local/v2/02_profiles/traits_r2/tables/traits.csv        # round 2: 4 minutes
uv run pytest v2/09_analysis/tests -q                                         # 7 tests, about 40 s
```

Flags: `--outcome both|direct|peer` (default both: the 60-test family), `--permutations 1000`, `--bootstrap 200`,
`--workers` (default CPU count - 1), `--cohort matthew_v2_262` (the rubric v3 cohort once it exists), `--smoke` for
plumbing checks on a test table (the run folder gets a `_smoke` suffix and the prompt-version check is skipped).
A real run refuses a trait table that is not at prompt `2026-11-24a`.

## Outputs (`outputs-local/v2/09_analysis/trait_uplift/<stamp>/`)

| file | what |
|---|---|
| `summary.csv` | one row per outcome × trait × cell: status, pairs, targets, lift, doubly robust difference, refit-bootstrap 95% interval, shuffle p, BH-adjusted p (`bh_q`), `finding` (bh_q ≤ 0.10) |
| `report.md` | the same, as tables for the team |
| `oof_effects.csv` | out-of-fold per-pair effects with propensity, overlap flag and the target's tags |
| `tag_effects.csv` | the observed lift per cell before resampling |
| `permutations.csv`, `bootstrap.csv` | every shuffled and bootstrapped lift |
| `fold_diagnostics.csv` | per fold: arm sizes, unknown pairs, status |
| `pair_features.csv` | the 262 pairs with grades, B3 signals, trait matches and target tags |
| `manifest.json` | input and script hashes, settings, runtime |

Lift is in probability units in the CSVs (0.05 = 5 percentage points) and in percentage points in `report.md`.

## Reading the results

- Round 2 is its own family (40 tests) designed after round 1: its findings are leads until the rubric v3 rerun.

- Adjusted associations within B3's lists, from one reviewer: not causes and not a pipeline improvement.
- Direct peer is the primary outcome; the peer outcome is inflated by rubric v2's loose customers wording.
- A cell marked unsupported or partial has no estimate; a missing effect is not zero.
- Only `finding = True` rows count as findings; everything else is reported as a null.

---

## From v1a: 09_analysis: Analysis

Diagnostics across components: the X-learner facet lift (which facet matches go with people's peer grades, and which the LLM selector keeps on), the error analysis, and an index of the 11-10 v1 integration study (its scripts stay in v1).

**Status (2026-11-19): ported.** Scripts, tests and `analysis.ipynb` are in place; the v1 X-learner runs reproduce to within 4e-7, and the new runs on the current lists and the selector are pinned in `current.toml` (12/12 checks pass).

## Outputs (existing runs in `outputs-local/v1a/09_analysis/`, read in place; new runs in `outputs-local/v2/09_analysis/`)

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
| `human_peer` | dev_293 | Barbara grade >= 1 | current (12 B3 signals incl. sub_sector) + agent facet scores; stage treatments: selector keep (04), agent grade (05) |
| `human_rating` | dev_293 | Barbara grade 0/1/2 | current |
| `selector_all` | b3_current (2,538 pairs, 373 targets) | Sonnet selector kept | current |
| `selector_293` | dev_293 | Sonnet selector kept | current |
| `record_peer`, `record_rating` | dev_293 | as v1 | v1's 11 signals; reproduce v1 runs `20261113T190330202875Z` and `20261113T201612982633Z` |

Headline (B3 signals, strong vs weak match, percentage points; adjusted associations, not causal):
- People's peer grade goes with primary services (+24), end markets (+21), customer segment (+21), primary products
  (+15); sub-sector (+2.5) and offering description (+4) add little once the other facets are known.
- The selector keeps most on sub-sector (+13) and offering description (+11); it under-uses services, end markets
  and customer segment relative to people on the same 293 pairs.
- Stage ablation (beyond the 12 B3 signals): the agent's grade (05) adds +49.9 pp (45.2 to 54.3; doubly robust
  +48.3); the selector's keep (04) adds +4.0 pp (0.1 to 7.6), but its doubly robust check is -9.7, so it is fragile.

Figures and tables live in `analysis.ipynb` section 3, which is Kethan's stakeholder notebook ported cell by cell
(Methods A and B, sensitivity, diagnostics, agent support, comparison) plus his technical notebook's missingness
chart, and two v1a additions drawn with his functions: Method C (selector keep) and the stage ablation. Each Run All
also saves the 11 PNGs under the rating run's `presentation/<stamp>/`, as in v1.

Run: `uv run python v2/09_analysis/scripts/facet_uplift.py --cohort b3_current --outcome selector` (seconds, offline).
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
- 2026-11-19: stage ablation of 05 (`agent_grade` treatment) added; `human_peer` -> `20261119T031027158914Z`,
  `human_rating` -> `20261119T031040215833Z` (earlier pins plus that row only, checked in the notebook).
  Results section rebuilt from Kethan's stakeholder notebook (his plotting and table cells, adapted only for the 12th
  B3 signal and the current runs); a separate figure script written earlier the same day was retired (its folder is
  in `facet_uplift/history/figures_retired_2026-11-19/`).
- 2026-11-24: component created in v2. `PREREG_TRAITS.md` written before any real run; `trait_uplift.py` and
  7 tests (synthetic known effect recovered, null data, unknown handling, tag averaging, shuffle p, BH). Smoke run
  on the 30-company test table (`20261124T091611619336Z_smoke`): every cell unsupported, as expected with 30 of 533
  companies filled; plumbing checked. Nothing pinned.
- 2026-11-24: copied into full v2 (v2 became a working copy of v1a); existing outputs stay in `outputs-local/v1a/` and are read in place, new runs go to `outputs-local/v2/`.
- 2026-11-24: round 2 (`--round 2`, PREREG_TRAITS_R2.md, commit `b3b5e309`): run `20261124T111715563218Z_r2` pinned; notebook section 3.2 added (ledger 3.3, v1a 3.4).
