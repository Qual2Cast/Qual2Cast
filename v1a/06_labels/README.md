# 06_labels: Labels and cohorts

Human review: who graded which pairs, under which rubric, and when. Defines the named cohorts every other component loads (`dev_293`, `round1_36`, `matthew_v2_262`; `final_holdout_24` is locked) and the pair ledger that counts every pair judged by people and models.

**Status (2026-11-19): ported.** Scripts, tests and `labels.ipynb` are in place; the notebook reproduces the saved v1 numbers (7/7 checks pass).

## Current setting (`v1a/current.toml`)

- `default_cohort` = `dev_293`
- `cohorts` = `['dev_293', 'round1_36', 'matthew_v2_262']`
- `locked_cohorts` = `['final_holdout_24']`

## Outputs (`outputs-local/v1a/06_labels/`)

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
