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

**Status (2026-11-28): pre-registered rerun on the rubric v3 labels done** (`v3_final`: 311 pairs, 67 targets;
Matthew and Barbara, split outcomes tie-broken by GPT-Terra). The leads from the first run (large customers,
mission-critical) do not hold; see "Rubric v3 rerun" below. First run (2026-11-24, Matthew's rubric v2 labels, 262
pairs, 40 targets): `outputs-local/v2/09_analysis/trait_uplift/20261124T101142641398Z/`.

**See it in the notebook:** `analysis.ipynb` section 3.1 (round 1: headline table, lift intervals, lift by slice, the
shuffle test and Benjamini-Hochberg explained with charts, a reliability table), 3.2 (round 2, the same charts plus
the stability and peer-disagreement diagnostics) and 3.3 (the improvement ledger). Figure copies for the website:
`outputs-local/v2/09_analysis/trait_uplift/<run>/figures/<stamp>/` for each round's run. (The notebook still shows the
v2-label runs; the v3 runs are in the tables below.)

**Improvement ledger** (`scripts/progress.py`, how-to in [`PROGRESS.md`](PROGRESS.md)): one append-only row per
pipeline version with its overlap against the human labels (precision and recall, any and direct peer, target means
with 95% intervals). Seeded 2026-11-24 with the baseline on `matthew_v2_262`; the same pipeline was recorded again on
`v3_final` on 2026-11-28 (the cohort from now on, `current.toml [analysis.progress]`). Later versions are compared
with that row. `outputs-local/v2/09_analysis/progress/` holds `ledger.csv`, `latest.csv` and `progress.png`.
Run `uv run python v2/09_analysis/scripts/progress.py show` to refresh the chart.

**Headline sets** (`scripts/headline_sets.py`, no model calls): the five baseline profiles on the rubric v3 labels.
`v3_final` is the headline (team ruling 2026-11-27): agreement per outcome, split outcomes tie-broken 2 of 3 by
GPT-Terra. `same_outcome` (agreed outcomes only) and `all_four` (all four answers alike) are sensitivity rows. The
agent profiles stack the 30 extra B3 pairs graded separately with the same prompt and model
(`[agent_grading] extra_verdicts`), so every profile covers all 311 pairs. Run
`outputs-local/v2/09_analysis/headline_sets/20261128T044100Z/`; earlier runs are in `headline_sets/history/`.
Target means; "direct" = score 2, "peer" = score 1 or 2 (direct + adjacent):

| set | outcome | pairs / targets / positives | selector precision, recall | agent ≥ 1 precision, recall | agent 2 precision, recall | B3 all precision |
|---|---|---|---|---|---|---|
| **v3_final** | direct | 311 / 67 / 106 | 87%, 87% | 58%, 100% | 97%, 59% | 48% |
| **v3_final** | peer | 311 / 67 / 184 | 96%, 61% | 83%, 92% | 100%, 42% | 68% |
| same_outcome | direct | 276 / 66 / 101 | 92%, 88% | 62%, 100% | 100%, 59% | 50% |
| same_outcome | peer | 244 / 66 / 146 | 96%, 72% | 87%, 98% | 100%, 49% | 67% |
| all_four | direct | 180 / 62 / 101 | 95%, 88% | 81%, 100% | 100%, 59% | 63% |
| all_four | peer | 180 / 62 / 109 | 96%, 86% | 85%, 100% | 100%, 57% | 66% |

The selector is asked for "the same business" (a direct-peer filter): on `v3_final` it keeps 86 of 106 direct pairs,
6 of 78 adjacent and 4 of 127 not-a-peer pairs (on Matthew's v2 labels: 50 of 60, 8 of 124, 3 of 78).

**Peer mix** (`scripts/peer_mix.py`, 2026-11-28, descriptive, no model calls): direct vs adjacent vs not a peer
among the labelled B3 candidates, by target sector group (SIC → Fama-French 49 → sector, small sectors merged to 8
groups of 5+ targets); what makes an adjacent pair not direct; B3 rank; the overall call and pipeline keep rates by
grade. Run `outputs-local/v2/09_analysis/peer_mix/20261128T051409Z/`. Adjacent per direct peer: 0.17-0.35 in
healthcare, business services, construction/real estate; 1.27-1.77 in consumer and manufacturing (5 of 11
manufacturing targets have no direct peer but an adjacent one). 66 of 78 adjacent pairs are "product no, customers
yes" in the judge's answers. Adjacent pairs sit where non-peers do in B3's ranking (mean rank 4.85 vs 5.35; direct
2.53) and reviewers would put 13% of them in the comp set (direct 99%).

**Profile size.** The selector has no minimum: over all 443 B3 pairs of the 67 `v3_final` targets it keeps 0 comps
for 13 targets, 1 for 22, 2 for 9, 3 for 10 and 4+ for 13 (`analysis.ipynb` 3.7). Of the 13 with none, 2 have a
labelled direct peer it dropped (DECK, SVV), 7 have only adjacents, 4 have neither. Team direction (2026-11-28,
**experimental**): a profile is every direct peer, filled up to k = 3 with the best adjacents (flagged) when short.

**EXPERIMENTAL recall audit** (`scripts/recall_audit.py`, 2026-11-28; `analysis.ipynb` 3.10): are thin profiles a
small pool or a retrieval miss? 10 `v3_final` targets (seed 2026: 7 with no labelled direct peer, 3 controls with two
or more); for each, the 15 comps next in B3's ranking that were never labelled (unselected top 10, then ranks beyond
10 in B3's 373-company pool), judged by the rubric v3 judge (GPT-Terra, prompt `2026-11-27a`; 150 Codex calls, 31
minutes). Run `outputs-local/v2/09_analysis/recall_audit/20261128T055935Z_EXPERIMENTAL/`.
- New direct peers: **0 of 150** (thin 0 of 105, controls 0 of 45). New adjacents: 21 of 105 for the thin targets
  (DGII 8, SND 5, ACH 4), 2 of 45 for the controls; all "product no, customers yes".
- Peer rate by B3 rank band: unselected top 10 30%, ranks 11-15 14%, 16-20 7%, 21+ 0%.
- Judge-only labels from one run; the judge is stricter than `v3_final` (on the controls it confirms 5 of the 8
  labelled direct peers), so it may undercount.

**EXPERIMENTAL tier-2 fill** (`scripts/tier2_fill.py`, `scripts/tier2_llm.py`, 2026-11-28; `analysis.ipynb` 3.11):
thin profiles filled up to k comps with flagged adjacents. Tier 1 = the pinned selector's keeps; pool = B3's list
plus ranks 11-15. Rules: `b3_rank`, `agent`, `agent_then_rank`, and `llm_tier2` (59 Sonnet calls: up to 5 adjacent
peers per target, best first, or none). GPT-Terra labelled the 92 picks without a reviewer label (judge-only). Run
`outputs-local/v2/09_analysis/tier2_fill/20261128T082654Z_EXPERIMENTAL/` (the k = 3 no-model run before it:
`20261128T075724Z_EXPERIMENTAL/`). At k = 3 (targets with 3+ comps: 23 of 67 without a fill):

| rule | targets reaching 3 | added comps at least adjacent (v3_final labels, 95% CI) | whole profile at least adjacent / direct |
|---|---|---|---|
| b3_rank | 67 | 48% [33-62] | 78% / 61% |
| agent | 41 | 60% [42-75] | 85% / 66% |
| agent_then_rank | 67 | 60% [42-75] | 85% / 66% |
| llm_tier2 | 62 | 59% [44-73] | 83% / 64% |

Tier 1 alone: 96% / 87%. Across k = 2-5 the rules overlap (b3_rank 46-50%, the others 58-67%); 11-20% of added comps
are direct peers. With judge-only labels pooled, `llm_tier2` holds at 60% while `agent_then_rank` falls to 50% (17 of
its 19 unlabelled picks judged not a peer). Healthcare and business services stay near 0% under every rule. Filling to
k makes every profile bigger at the cost of about 2 in 5 added comps not being peers.

**Trait lines in the selector** (2026-11-28; `v2/04_selection/README.md`, `analysis.ipynb` 3.8-3.9): all ten traits
as one data line each, against three runs of the unchanged prompt. None moves direct precision or recall beyond the
range of the unchanged runs (direct recall 82.7-89.2% from rerunning alone).

## Rubric v3 rerun (2026-11-28, `v3_final`, pre-registered, unchanged plan)

Cohort fixed by the dated amendment in `PREREG_TRAITS.md` before the run. Runs:
`trait_uplift/20261128T042306693074Z/` (round 1, 60 tests), `20261128T043127850920Z_r2/` (round 2, 40 tests),
`20261128T043638119157Z_overall/` (overall-call cross-check, its own 30-test family). Lift in percentage points, all
pairs; BH q = 0.10.

| trait | direct (primary) | peer (secondary) | overall call (cross-check) | v2-label run (direct / peer) |
|---|---|---|---|---|
| large customers | -2.1, null | -1.6, null | +8.1, null; non-services cell +12.6 (q 0.030, finding) | +8.6 finding / +19.0 finding |
| mission-critical (round 2) | +3.4, null | -1.9, null | not run (round 1 traits only) | +10.6 finding / +25.1 finding |
| big-ticket | +1.5, null | **+17.2** (+0.5 to +32.1), q 0.094, finding; consumer-facing +23.1 (q 0.030), services +17.9 | +9.5, null | +8.4 null / +30.1 finding |
| recurring revenue | +8.5 (-1.8 to +16.4), null; non-services +11.0 and non-consumer +11.2 (q 0.094, findings) | -8.2, null | -4.8, null | +1.7 null / -5.6 null |
| people-delivered | +7.5, null | +2.5, null | +5.5, null | +11.2 finding / -2.0 null |
| asset-heavy | +2.0, null | -7.5, null; non-services -18.0 (q 0.030), consumer-facing -10.3 (q 0.094), findings | +2.3, null | +7.8 null / -4.7 null |
| cyclical demand | +2.5, null | +0.8, null | -4.1, null | cells negative / cells negative |

Round 1: 7 findings of 60. Round 2: 0 of 40 (maintenance-led and publicly funded only partly supported). Overall
call: 1 of 30.

- The two v2 leads drop out on the tighter labels, as the first run's caveat allowed: large customers sat close to
  the loose v2 "same customers" question.
- Big-ticket is the one all-pairs finding, on the secondary outcome, from 110 pairs, with a lower bound near zero.
- Recurring revenue shows on the primary outcome only inside two cells.
- Next (team, 2026-11-28): test traits in the selector one at a time as data lines (recurring revenue, then
  big-ticket, then both), each a dated prompt version scored in the ledger.

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
