# 06_labels (v2): rubric v3 and its sheet

Human labels for target-comp pairs under rubric v3: an overall call ("would you put it in the comp set?") first, then
four yes/no questions (same product, same customers, same revenue model, same chain step) with the score
derived. The reviewer guide, including the twelve worked anchor pairs, is [RUBRIC_V3.md](RUBRIC_V3.md).

The cohorts, rubric v2 and the earlier rounds' scripts are in this component too (copied from v1a; their saved
outputs stay in `outputs-local/v1a/06_labels/` and are read in place). `rubric_v3.py` reuses
`rubric_v2.parse_answer` and `derive_score`.

**Status (2026-11-24):** sheet written, not yet filled. 10 tests pass. No model calls.

## Current setting

- Rubric: v3 (`RUBRIC_V3.md`); score 2 = all four yes, 1 = product or customers yes, 0 = neither.
- Sheet: `outputs-local/v2/06_labels/rubric_v3/rubric_v3_sheet.csv`. 323 pairs from 67 targets: 262
  round-3 + 31 round-2 dev pairs (`dev_293`) + 30 extra B3 pairs (`b3_kept_30`). 12 anchors
  (`is_anchor = 1`), so 311 are scored. Column sets for matthew, barbara and riya. Seed 2026.
- Tie-break: GPT-Terra judge on questions where it has earned it, otherwise Riya (`consensus --earned-only`).

## Outputs (`outputs-local/v2/06_labels/`)

- `rubric_v3/rubric_v3_sheet.xlsx` (upload this as a Google Sheet; yes/no dropdowns) and `rubric_v3_sheet.csv`: the
  blind sheet (no method, rank, similarity or multiple) with the question key above the header row, written once
  (`build-sheet` refuses to overwrite). The first build, with a `blind_` column, is in `rubric_v3/history/`.
- `rubric_v3/manifest.json`: counts by batch, the anchors with their proposed answers, the seed, and the
  sha256 of the sheet and every source.

## Scripts and tests

- `scripts/rubric_v3.py`
  - `build-sheet`: the blind sheet;
  - `check`: blank, misspelled or half-answered answers, one row per problem;
  - `scores`: derived scores, per-question kappa with yes rates and unsure counts, overall call vs derived score;
  - `consensus`: agreed answers, disputed questions, optional tie-break column set, `--earned-only`.
- `tests/test_rubric_v3.py`: synthetic sheets only. Run `uv run pytest v2/06_labels/tests -q`.

## Sources

- `outputs-local/v1a/06_labels/barbara_293/sonnet_label_b3_kept_30_20261119T030414Z.xlsx` (323 rows): pair
  list for the 30 extra pairs and the description columns for all 323.
- `v1a/06_labels/scripts/cohorts.py` `dev_293`: the 293 dev pairs and their round.
- Gaps in descriptions would be filled from the Sonnet general facets (`current.toml [profiles] general`);
  none were needed.
- Anchors chosen from `outputs-local/v1a/06_labels/round3/round3_sheet_v2.csv` (Matthew's answers and notes),
  checked against Barbara's `dev_293` grades.

---

## From v1a: 06_labels: Labels and cohorts

Human review: who graded which pairs, under which rubric, and when. Defines the named cohorts every other component loads (`dev_293`, `round1_36`, `matthew_v2_262`; `final_holdout_24` is locked) and the pair ledger that counts every pair judged by people and models.

**Status (2026-11-19): ported.** Scripts, tests and `labels.ipynb` are in place; the notebook reproduces the saved v1 numbers (7/7 checks pass).

## Current setting (`v2/current.toml`)

- `default_cohort` = `dev_293`
- `cohorts` = `['dev_293', 'round1_36', 'matthew_v2_262']`
- `locked_cohorts` = `['final_holdout_24']`

## Outputs (existing runs in `outputs-local/v1a/06_labels/`, read in place; new runs in `outputs-local/v2/06_labels/`)

- `barbara_293/` (5 files)
- `barbara_published/` (3 files)
- `round1/` (4 files)
- `round2/` (6 files)
- `round3/` (5 files)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/golden_set.py` (script): round 1; copied early (03's similarity_eval imports it); verified with 06
- `v1/scripts/integration_barbara.py` (script): Barbara published profiles cache
- `v1/scripts/integration_barbara_matches.py` (script): Barbara published lists vs 293
- `v1/scripts/integration_review.py` (script): builds the 293 label table; rename review_labels
- `v1/scripts/integration_sources.py` (script): freezes sonnet_label.xlsx and shared inputs; rename freeze_sources
- `v1/scripts/reviewer_gold_eval.py` (script)
- `v1/scripts/round3_sheet.py` (script): round 3 sheet (262)
- `v1/scripts/sonnet_pairs_sheet.py` (script): round 2 Sonnet sheet (31)
- `v1/scripts/tests/test_golden_set.py` (test)
- `v1/scripts/tests/test_reviewer_gold_eval.py` (test)
- `v1/notebooks/golden_set.ipynb` (notebook)
- `v1/notebooks/golden_set_showcase.ipynb` (notebook)
- `v1/GOLDEN_SET_ROUND2.md` (doc)

Not from v1 on main:

- `pair_ledger.py` from `new 2026-11-18 (saved patch)`
- `test_pair_ledger.py` from `new 2026-11-18 (saved patch)`
- `conversations/2026-11-13-rubric-v2.md` from `matt/rubric-yes-no`
- `outputs-local/v1/golden_set_round3/labels/round3_scores_v2.csv` from `matt/rubric-yes-no`
- `outputs-local/v1/golden_set_round3/labels/round3_sheet_v2.csv` from `matt/rubric-yes-no`
- `v1/GOLDEN_SET_ROUND2.md` from `matt/rubric-yes-no`
- `v1/scripts/rubric_v2.py` from `matt/rubric-yes-no`
- `v1/scripts/tests/test_rubric_v2.py` from `matt/rubric-yes-no`

Commit authors of these files (git): Fiona Shao, EFL-YL, mcschlatt.

## Cohorts (to be defined in `scripts/cohorts.py`)

| cohort | pairs | who / rubric |
|---|---:|---|
| `dev_293` | 293 (45 targets) | Barbara, rounds 2-3 old form; 31 round-2 + 262 round-3 pairs from B3 "Sonnet + Fiona sub-sector" |
| `round1_36` | 36 (PCTY, WEN) | Riya, Barbara, Matthew; round-1 rubric |
| `matthew_v2_262` | 262 (40 targets) | Matthew, rubric v2 (four yes/no questions), same pairs as round 3 |
| `final_holdout_24` | 24 (20 targets) | Barbara direct-peer Yes/No; locked to 10_final_holdout |

`pair_ledger/20261118T205008Z/` is the ledger built on 2026-11-18 from the v1 files (before the move).

`scripts/golden_set.py` was copied early because 03's `similarity_eval.py` imports it; it is checked when 06 is ported.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `labels.ipynb` ported; v1 numbers reproduced.
- 2026-11-24: component created in v2. Rubric v3 guide with twelve anchor pairs; `rubric_v3.py` (build-sheet,
  check, scores, consensus, earned tie-break); blind sheet of 323 pairs written; 10 tests pass.
- 2026-11-24: copied into full v2 (v2 became a working copy of v1a); existing outputs stay in `outputs-local/v1a/` and are read in place, new runs go to `outputs-local/v2/`.
