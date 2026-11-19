# v1a: the pipeline reorganized by component — 2026-11-18

Michael, for Kethan. Branch `michael/wip`, from `main` at `4b35db6b`. Not committed.

## Request

Kethan asked to rerun Fiona's direct-peer work (Barbara's 90 pairs, 2026-11-17) on the same steps as the earlier
pairs, leaving out comps outside the universe; count the target-comp pairs judged across the pipeline with the
spans of each rubric; and make the X-learner quick to rerun. Michael then asked to plan first and to consolidate
the team's work: one folder per pipeline component, one notebook per component updated in place, outputs in the
same structure, v1 kept as the record. Name: v1a. Unmerged branches are taken in if current and not in conflict
with main. Holdout pairs are kept for the end.

## Decisions

- `v1a/` beside a frozen `v1/`; outputs in `outputs-local/v1a/<component>/`.
- Ten components: 01 universe, 02 profiles, 03 retrieval, 04 selection, 05 agent grading, 06 labels, 07 judges,
  08 valuation, 09 analysis, 10 final holdout; plus `common/` and Kethan's runner as `pipeline/`.
- `v1a/current.toml` names the current runs (all lines confirmed by Michael): Sonnet fills prompt `2026-10-25k`
  + Fiona sub-sector; B3 "Sonnet + Fiona sub-sector", mutual top 10, top-up 3; Sonnet selection prompt
  `2026-11-04a`; agent run `ranking_45targets_sonnet` (prompt `2026-11-05b` + facet scores); cohort `dev_293`.
- Seed tables, link raw per-call folders (not copied). `financials.csv` lives in `08_valuation` only.
- Of the 52 `integration_*` scripts (PR #32), 7 move (the 293 label table, Barbara's published lists, the GPT
  Sol judge); 45 stay in v1, to be indexed in `09_analysis`.
- Branches: `matt/rubric-yes-no` and `kethan/wip` taken in (conflicts only in PROJECT_STATE.md, the data
  dictionary and v1/README text); `riya/wip` (10-17, pre-v0) left out.
- Barbara's 24 in-universe direct-peer pairs (comps all holdout companies) are the locked `final_holdout_24`.
  The 66 pairs with comps outside the universe are not seeded.

## Done (steps 1-2 of 4)

| item | where |
|---|---|
| mapping of every v1 file and changed branch file | `v1a/MIGRATION_MAP.csv` |
| skeleton: READMEs (generated from the mapping, seed manifest, current.toml and git authors) | `v1a/README.md`, `v1a/<component>/README.md` |
| settings and paths | `v1a/current.toml`, `v1a/common/paths.py` |
| seed (153 files, 30 MB copied; 43 raw folders, 156 MB, linked) | `v1a/common/seed_from_v1.py`, `outputs-local/v1a/seed_manifest.json` |
| git sharing for v1a outputs, same exclusions as v1 | `.gitignore` |

Earlier the same day, before the plan was agreed, I added a `standardize` step to `direct_peer_pairs.py`,
`--labels/--agent` to `facet_uplift.py`, and `pair_ledger.py`, all in `v1/`. They were taken back out of v1
(saved as a patch, ported in step 3). Their outputs moved: the 24-pair B3/C/S/E scoring to
`outputs-local/v1a/10_final_holdout/direct_peers_24/standardized_20261118T204217Z/` (the X-learner inputs that
added 19 of those pairs were deleted), the ledger to `outputs-local/v1a/06_labels/pair_ledger/20261118T205008Z/`.

Findings from that work, still valid:
- The 293 pairs are B3 "Sonnet + Fiona sub-sector" exactly (similarity and rank); Fiona's `prepare` looked B3
  up in the Haiku list instead (no effect on her pairs: none had a score in either).
- Recomputed B3 reproduces the 293 saved scores (max difference 9e-8, 0 rank mismatches).
- Pair ledger (v1 files): human review 353 unique pairs (7 sources), agent loop 365 (18 runs), LLM judges
  2,275, LLM screens 5,291. Rubric spans: round 1 (10-28), old 0/1/2 form (Barbara 293, 11-10), rubric v2
  (Matthew 262, 11-13), direct-peer Yes/No (11-18). Agent prompts `2026-11-05a`, `2026-11-05b`, and
  `2026-11-05b` + facet scores (11-12 to 11-18).
- The 24 holdout-comp pairs have been graded and scored; nothing was chosen or tuned on them.

## Checks

- Every `current.toml` path exists; `paths.setup()/current()` load.
- No financial columns in 01-07 seeds (only the universe eligibility range in `run.json`).
- v1 is unchanged: `git status` clean under `v1/` and `outputs-local/v1/`; v1 suite 204 pass.
- No model calls. Data: `company_list_v3`, universe `20261025T060358Z`, split `20261027T204930Z`.

## Step 3, first part: 01-03 ported (same day)

- Scripts and tests copied from v1 with mechanical rewrites (repo-root depth, a two-line `paths.setup()` bootstrap
  binding `v1a`, usage lines), then targeted edits: new runs write to `outputs-local/v1a/<component>/`; current
  inputs come from `current.toml`; the v1 record (Haiku fills, Haiku B3 run, Haiku screen, caches, business-split
  pilot inputs) is read in place. Fill scripts write to `*_new/` folders, never over the current tables.
- `split.sic2_split()` now holds the split logic from `v1/notebooks/comps_and_valuation.ipynb` cell 7.
- `method1_candidates.py` builds the current B3 variant ("Sonnet + Fiona sub-sector") from `current.toml`.
- `b3_facet_add_drop.py` reads v1's Sol grades of holdout pairs only with `--v1-holdout-diagnostic`.
- Moved by the rules: `split_peer_eval.py` and `source_scope_sensitivity.py` read EV/EBITDA → `08_valuation`;
  `sector_facet_candidates.py` (10-28 holdout candidates) → v1 only; `golden_set.py` copied early to `06_labels`
  (03 imports it); FF49 codes → `03_retrieval`.
- Notebooks `universe.ipynb`, `profiles.ipynb`, `retrieval.ipynb`, each: what it does, current setting, inputs with
  hashes vs the seed, results, checks, v1 history, changelog. Shared helpers in `v1a/common/nbtools.py`.

Reproduction (all checks pass: 7/7, 7/7, 4/4):
- 01: the universe rebuilt from the snapshot is the same 533 companies with identical saved columns; the split has
  0 differences (373/160); `financials.csv` in 08 matches.
- 02: the general, sector and industry tables rebuild exactly from the saved raw answers.
- 03: the rebuilt B3 list has the same 2,538 selected pairs; max similarity difference 1.1e-7; 5 exact-tie swaps
  beyond rank 10. The add/drop experiment reproduces v1's 210-row table exactly with the flag; the v1a run without
  holdout rows (`facet_add_drop/20261118T225043Z`, 180 rows) equals it minus the 30 holdout rows.
- Tests: v1a 01-03 180 pass; v1 204 pass, no tracked changes in v1. This morning's `standardize` run left a local,
  gitignored embedding cache in `outputs-local/v1/facet_add_drop/cache/` (untracked; v1a reads it).

Findings:
- 98.5% of the Sonnet general facet values come from model knowledge; only 10 companies have website-sourced
  values (the website pass fills only facets left unknown). The scraped pages are used mainly by the agent loop and
  Fiona's sector facets.
- `facets_sonnet_corrected.csv` is Yiming's divestiture corrections (42 companies, 116 values), not the 10
  HLTC/ENSG/SKIL source-review fixes (those are a separate later layer in `integration/source_reviewed_default/`).
  An earlier summary to Michael said otherwise; corrected in `current.toml`, the notebook and this record.

## Step 3, second part: 04 selection ported, selector run on the current list (same day)

Michael chose to run the selector on the current list (option a). Setup: Claude Sonnet 5.5 through the Claude Code
CLI on his Claude subscription, no API key; the judge (LaaJ) stays in the GPT family, and a GPT model of similar
strength to Sonnet may replace Sol as judge later (Michael).

- Ported `cosine_then_llm.py` (from `kethan/wip`), `direct_llm.py`, `llm_then_cosine.py`, `check_prompt_versions.py`,
  `model_selection_eval.py`, tests and `PROMPT_VERSIONS.md`. `common/cli_models.py` from `kethan/wip`, plus: the
  claude-cli call never receives an API key (`.env` has one; the CLI path never loaded it), a run stops on the
  subscription limit message (HTTP 429, "hit your limit"; v1's check missed it), and Windows temp-folder cleanup
  errors no longer crash a run.
- Pilot (3 targets), then the full run: all 373 targets, 2,538 pairs, 0 issues. The plan's usage limit stopped the
  first pass after 188 targets (the next 183 calls failed at once, 0 tokens); the rerun after the 8pm reset
  finished the rest. About 15k input / 0.8k output tokens per call (half cached); ~$0.033 per call at API rates,
  drawn from the subscription instead. Folder:
  `outputs-local/v1a/04_selection/b3_selector_candidates_2026-11-04a_claude-cli_claude-sonnet-5-5/` (31 MB with the
  raw answers and the failed first-pass attempts). `current.toml [selection]` points here.
- Results: 507 of 2,538 pairs kept (20%); 108 targets keep no comp; keep rate 64% at B3 rank 1, 35% at rank 2,
  about 1% from rank 7. Against Barbara's 293: kept 24/24 of her 2s, 42/178 of her 1s, 3/91 of her 0s.
- Checks (`selection.ipynb`, 6/6): every target and every selected pair answered once; prompt and model as set;
  the v1 record's 373 saved selector prompts and 373 direct-pick prompts rebuild exactly; the 11-04 Sonnet vs
  Haiku tables reproduce exactly. v1a tests 01-04: 192 pass.

## Step 3, third part: 05-10, the runner and the overview (2026-11-18/19)

Michael: fill out the other folders; don't chase v1's B3 valuation number; the X-learner is the priority ("which
facets contribute to the LLM selecting the best target-comp pairs out of our B3 filter, and what gives the most
uplift").

| component | what was ported or added | check |
|---|---|---|
| 05 agent grading | `agent_loop.py`, `agent_loop_eval.py`, `agent_ranking.py` (valuation removed), `direct_peer_pairs.py` prepare/assemble, policy/, `AGENT_LOOP.md` | ranking and its eval rebuild exactly (5/5); ranking pending Michael's review |
| 06 labels | `cohorts.py` (new; `final_holdout_24` refused unless `final_check=True`), `pair_ledger.py`, `review_labels.py`, round sheets, rubric v2 (Matthew's branch) | all label tables and the ledger reproduce (7/7) |
| 07 judges | `peer_evaluation.py` (Kethan's), `judge_gold_eval.py`, `judge_293_eval.py` (verdicts rebuilt from the 293 saved answers) | GPT Sol on the 293: exact 0.785, binary 0.843, as v1 (5/5) |
| 08 valuation | `valuation.py`, `agent_valuation.py` (moved from 05), judge-filter tables (moved from 07) | current lists valued (5/5); v1's Haiku-list numbers not reproduced (Michael) |
| 09 analysis | `facet_uplift.py` with `--cohort`, `--outcome selector`, `--features current/record`, selector treatment; `error_analysis.py` (reads the v1 record) | both v1 X-learner runs reproduce to within 4e-7 (12/12) |
| 10 final holdout | `final_check.py` (direct-peers = the 11-18 standardize step without X-learner inputs; holdout = current B3 lists + valuation), both refuse without `--final-check` | locked notebook: inventory + 15 leak checks; direct-peers reproduces the 11-18 output exactly |
| pipeline | Kethan's runner: v1a imports and outputs, per-role provider, training targets only, new default `configs/v1a.toml` | preview only, no folder created; 3 tests |
| 00 overview | entry notebook: components and their saved checks, current.toml, pair ledger spans, numbers, X-learner headline | 13/13 |

Also: `method1_candidates.per_facet()` (03) exposes the per-facet B3 signals the X-learner reads (the combined
similarity is unchanged); Kethan's `fill_facets.py` refactor (one shared CLI wrapper) applied in 02. v1a tests: 226
pass across 10 suites. All 12 notebooks run end to end. No model calls.

Left in v1 (MIGRATION_MAP updated): the six v0-route holdout scripts (results seeded in
`10_final_holdout/v1_holdout_runs/`; two made paid LLM calls on the holdout, so not made runnable in v1a),
`graded_peer_selection.py`, `split_peer_eval.py`, `source_scope_sensitivity.py`, `integration_judge_input.py`,
`integration_judge_selection.py`, the stakeholder HTML page. The 09 README indexes the integration scripts.

### X-learner results (pinned in `current.toml [analysis.facet_uplift]`)

Strong vs weak B3 match per facet (above vs at/below the training-fold median), lift in percentage points, B3
signals of the current variant (12, with Fiona's sub-sector). Adjusted associations, not causal; facets overlap, so
lifts don't add; intervals are a fixed-prediction target bootstrap (too narrow).

| facet | people's peer grade (293) | selector keep (same 293) | selector keep (all 2,538) |
|---|---:|---:|---:|
| primary_services | +23.8 | +8.2 | +6.0 |
| end_markets | +21.4 | +10.6 | +8.9 |
| customer_segment | +20.7 | +6.7 | +2.5 |
| primary_products | +15.1 | +11.8 | +9.4 |
| revenue_model | +8.9 | +7.8 | +7.9 |
| regulatory_exposure | +8.7 | +7.3 | +6.2 |
| specialization | +5.3 | +8.3 | +4.9 |
| offering_description | +4.1 | +14.6 | +11.3 |
| sub_sector | +2.5 | +10.8 | +13.2 |
| distribution_channels | +1.6 | +4.4 | +5.0 |
| geography_served | +0.4 | +0.2 | +2.0 |
| value_chain_position | -4.3 | +2.0 | +8.2 |

- What goes with a good comp (Barbara): services, end markets, customers, products. Sub-sector and offering
  description add little once those are known.
- What the selector keeps on: sub-sector and offering description first. Relative to people it under-uses services
  (-15.6), customers (-14.0) and end markets (-10.8).
- The selector's keep, adjusted for all 12 B3 signals, adds +4.0 pp (0.1 to 7.6) to the chance of a human peer
  (+0.15 grade points on the 0-2 scale): it adds something beyond the facets, but not much.
- Read with the cohort in mind: the 293 pairs are already B3-selected, and the selector run is one model/prompt.

### Valuation on the current lists (training targets)

No matching 31.9% median absolute error (373 targets); B3 median 33.8%, similarity-weighted 30.2%, selector with B3
fallback 31.3%. On the 265 targets where the selector kept a comp: selector 30.6%, B3 32.6%, no matching 31.5%.
No interval of the gain over no matching excludes 0.

## Next

1. Michael reviews 05-10, the runner and the overview; then decide whether to commit and open a draft PR.
2. Michael reviews Barbara's scoring standard and the agent ranking (05).
3. Ideas from the X-learner, to discuss before any change: give the selector prompt more weight on products,
   services, customers and end markets (or show those facets first); check whether sub-sector belongs in B3.
   Any change is a new prompt version, checked on the dev cohorts, never on the holdout.
4. Done 2026-11-19: judges use GPT-Terra (`gpt-5.6-terra`), in `current.toml [judges]` and `pipeline/configs/v1a.toml`.
5. After review: point AGENTS.md, the root README and the data dictionary at v1a; merge Kethan's and Matthew's
   doc edits by hand.
6. The final check (10) runs once, when the team calls the method final.

## 2026-11-19: 30 more pairs for Barbara

Michael asked to run 30 target-comp pairs (B3 similarity above 0.45; candidates, not confirmed peers) through the
agent loop with facet scores, and add them to the Sonnet label workbook for Barbara.
- All 30: both companies training, on the current B3 lists, kept by the Sonnet selector, not in the 293 (either
  direction). Pair file with B3 rank and similarity: `outputs-local/v1a/05_agent_grading/b3_kept_30/pairs.csv`.
- Agent loop with the 293 run's exact settings (claude-cli Sonnet, Sonnet web search, 4 steps, facet scores, prompt
  `2026-11-05b`, current Sonnet facets). Two pairs (CARG-CARS, MCFT-MPX) failed with the CLI's "maximum number of
  turns" in a search step; resumed runs finished them. Result: 28 graded 2, 2 graded 1 (ONL-PDM, GVA-ROAD).
- `v1a/06_labels/scripts/extend_label_book.py` writes a new copy of `sonnet_label.xlsx` with the batch appended
  in Fiona's direct-peer layout (reviewer columns blank; agent grade, reason and facet scores; provenance) plus a
  JSON of inputs and hashes. Refuses holdout companies and pairs already in the book.
  Workbook: `outputs-local/v1a/06_labels/barbara_293/sonnet_label_b3_kept_30_20261119T030414Z.xlsx` (323 rows).
  A first copy whose JSON failed (path bug, fixed) is in `barbara_293/history/`.
- Judges (LaaJ) use GPT-Terra (`gpt-5.6-terra`) from today.
