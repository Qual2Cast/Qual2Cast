# 06_labels (v2): rubric v3 and its sheet

Human labels for target-comp pairs under rubric v3: an overall call ("would you put it in the comp set?") first, then
four yes/no questions (same product, same customers, same revenue model, same chain step) with the score
derived. The reviewer guide, including the twelve worked anchor pairs, is [RUBRIC_V3.md](RUBRIC_V3.md).

The cohorts, rubric v2 and the earlier rounds' scripts are in this component too (copied from v1a; their saved
outputs stay in `outputs-local/v1a/06_labels/` and are read in place). `rubric_v3.py` reuses
`rubric_v2.parse_answer` and `derive_score`.

**Status (2026-11-28):** filled by Matthew and Barbara (323/323, no problems in `check`), tie-broken by GPT-Terra.
Headline labels: cohort `v3_final` (team ruling 2026-11-27: agreement per outcome; a split outcome takes the judge's
outcome, 2 of 3): 311 pairs, 67 targets; 106 direct, 78 adjacent, 127 not a peer; none open. Also cohorts
`matthew_v3_311`, `barbara_v3_311`, `v3_agreed`. `labels.ipynb` sections 3.7-3.8 (13/13 checks pass). 49 tests pass.

Reviewers (below), then the judge:

| item (311 scored pairs) | agreement | kappa | yes rate M / B |
|---|---:|---:|---:|
| overall call | 88.7% | 0.76 | 35% / 37% |
| same product | 79.7% | 0.61 | 36% / 55% |
| same customers | 79.1% | 0.57 | 55% / 60% |
| same revenue model | 95.5% | 0.86 | 80% / 79% |
| same chain step | 88.1% | 0.63 | 77% / 83% |
| peer (score >= 1) | 78.5% | 0.56 | 55% / 60% |
| direct (score 2) | 88.7% | 0.76 | 33% / 43% |
| score 0/1/2 (linear) | 73.3% | 0.66 | |

- All four questions agreed on 180 pairs (101 direct, 8 adjacent, 71 not a peer); 131 have at least one split
  question (customers 65, product 63, chain step 37, revenue model 14). Same derived score on 228.
- Product splits run one way: Barbara yes, Matthew no on 62 pairs; the reverse on 1.
- The overall call tracks the direct score: yes on 100/102 of Matthew's 2s and 104/135 of Barbara's; on 7/69 and
  11/53 of their 1s.
- Anchors: both reviewers gave the proposed answer on 11 of 12; Barbara answered no on THR/FLS customers (P318).
- Barbara old form vs v3 (281 shared pairs): 81 of her old 1s are v3 2s, 49 are 0s. Matthew v2 vs v3 (250): 65 of
  his v2 1s are v3 0s; of his 116 v2 "product no, customers yes" pairs, 51 keep customers yes.

**GPT-Terra judge** (`judge_v3.py`, `gpt-5.6-terra` through the Codex CLI, prompt `2026-11-27a`, all 323 pairs,
blind, under the guide with the 11-27 rulings; ~13 s and ~15k input tokens a call, no failures):

| | judge vs Matthew | Matthew vs Barbara | judge vs Barbara |
|---|---:|---:|---:|
| same product | 0.81 | 0.61 | 0.53 |
| same customers | 0.65 | 0.57 | 0.50 |
| same revenue model | 0.89 | 0.86 | 0.88 |
| same chain step | 0.79 | 0.63 | 0.50 |
| direct | 0.84 | 0.76 | 0.70 |
| peer | 0.65 | 0.56 | 0.50 |
| overall call | 0.76 | 0.76 | 0.66 |

- Where the reviewers agree, the judge gives the same outcome on 94.6% of direct (kappa 0.88), 87.7% of peer (0.74)
  and 90.6% of overall calls (0.80).
- Anchors: 12 of 12 on the guide's rulings (it saw them; a reading check only).
- Split outcomes: direct 35 (judge with Matthew 29, Barbara 6), peer 67 (44 / 23), overall call 35.
- Partial overlaps: of the 62 pairs where Barbara said same product and Matthew did not, the judge says yes on 6
  (the main-business ruling).

**Round 4, the final reviewer round (sheet ready 2026-11-28, Matthew and Barbara):**
`outputs-local/v2/06_labels/rubric_v3/round4/round4_sheet.xlsx` (upload as one Google Sheet; one tab per reviewer;
`.csv` beside it). 118 pairs, 48 targets, no anchors; the key above the header carries the 11-27 wording
(`rubric_v3.KEY_ROWS_1127`: product on the comp's main business; "the same buyers, in the same role"). Contents, by
`round4_key.csv` (never on the sheet): 32 selector keeps without a label, 56 EXPERIMENTAL tier-2 picks (`llm_tier2`,
up to k = 5) without a label, 30 GPT-Terra tie-breaks to re-check (seeded; 17 peer-only, 7 both, 6 direct-only
splits). Built by `scripts/round4_sheet.py` (+ test); scored like the first sheet (`rubric_v3.py check`, `scores`,
`final` with the judge for any split).

## Current setting

- Rubric: v3 (`RUBRIC_V3.md`); score 2 = all four yes, 1 = product or customers yes, 0 = neither.
- Sheet: `outputs-local/v2/06_labels/rubric_v3/rubric_v3_sheet.csv`. 323 pairs from 67 targets: 262
  round-3 + 31 round-2 dev pairs (`dev_293`) + 30 extra B3 pairs (`b3_kept_30`). 12 anchors
  (`is_anchor = 1`), so 311 are scored. Column sets for matthew, barbara and riya. Seed 2026.
- Tie-break (team ruling 2026-11-27): agreement per outcome; GPT-Terra's outcome decides a split (`rubric_v3.py final`).
  The per-question `consensus` (and `--earned-only`) stays as a diagnostic. Riya is not asked this round.
- Rulings 2026-11-27 (after the sheet was filled; `RUBRIC_V3.md`): question 1 on the comp's main business (the one its
  description leads with); question 2 reworded to "the same buyers, in the same role", any business of the comp.

## Outputs (`outputs-local/v2/06_labels/`)

- `rubric_v3/rubric_v3_sheet.xlsx` (upload this as a Google Sheet; yes/no dropdowns) and `rubric_v3_sheet.csv`: the
  blind sheet (no method, rank, similarity or multiple) with the question key above the header row, written once
  (`build-sheet` refuses to overwrite). The first build, with a `blind_` column, is in `rubric_v3/history/`.
- `rubric_v3/manifest.json`: counts by batch, the anchors with their proposed answers, the seed, and the
  sha256 of the sheet and every source.
- `rubric_v3/filled/rubric_v3_filled_matthew_barbara_20261127.csv`: the filled sheet as received (Google Sheets
  download of the `matthew` tab, with Barbara's columns appended after `comp_id`; no riya columns), byte for byte;
  `filled/manifest.json` records its sha256 and the check that pairs and descriptions match the blank sheet.
- `rubric_v3/scores/20261128T001954Z/`: `scores.csv`, `agreement.csv`, `overall_vs_derived.csv`, `consensus.csv`
  (no tie-break) and `manifest.json` (commands, input and file hashes). Pinned in `current.toml [rubric_v3]`.
- `rubric_v3/judge/terra_20261128T030942Z/`: the judge run (pilot of 32, then the 63 other split pairs, then the
  rest): `manifest.json` (settings, hashes, each session), `inputs/`, `runs/<pair>/` (prompt, raw response, usage),
  `answers/`, `judge_answers.csv` (answers and reasons), `filled_with_terra.csv` (the filled sheet plus the judge's
  columns) and `scores/` (agreement with each reviewer). Pinned as `[rubric_v3] judge`.
- `rubric_v3/final/terra_20261128T030942Z/`: `final.csv` (per pair: direct, peer, overall call, each with its source
  and a tie-broken flag; the score), `judge_vs_agreed.csv`, `manifest.json`. Pinned as `[rubric_v3] final`.

## Scripts and tests

- `scripts/rubric_v3.py`
  - `build-sheet`: the blind sheet;
  - `check`: blank, misspelled or half-answered answers, one row per problem;
  - `scores`: derived scores, per-question kappa with yes rates and unsure counts, overall call vs derived score;
  - `consensus`: agreed answers, disputed questions, optional tie-break column set, `--earned-only`;
  - `final`: the headline labels, agreement per outcome, the judge breaks a split (`--judge terra`).
- `scripts/judge_v3.py` (`prompt`, `run`, `collect`) and `scripts/judge_v3_prompt.py` (the prompt, version
  `2026-11-27a`, quoting `RUBRIC_V3.md`): the LLM judge through `call_cli` (codex or claude-cli); resumable, stops
  after repeated failures. Pair selections: `pilot`, `split`, `all`, `anchors`, or a file.
- `tests/test_rubric_v3.py`: synthetic sheets only; `tests/test_judge_v3.py`: the judge with the model call mocked. Run `uv run pytest v2/06_labels/tests -q`.

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
| `matthew_v3_311` | 311 (67 targets) | Matthew, rubric v3 (overall call + four questions), the v3 sheet less its 12 anchors |
| `barbara_v3_311` | 311 (67 targets) | Barbara, rubric v3, same pairs |
| `v3_agreed` | 311 (180 graded) | rubric v3 consensus of the two: grade only where all four answers match; NaN = disputed |
| `v3_final` | 311 (67 targets) | **headline**: same outcome, split outcomes tie-broken 2 of 3 by GPT-Terra |
| `final_holdout_24` | 24 (20 targets) | Barbara direct-peer Yes/No; locked to 10_final_holdout |

`pair_ledger/20261118T205008Z/` is the ledger built on 2026-11-18 from the v1 files (before the move).

`scripts/golden_set.py` was copied early because 03's `similarity_eval.py` imports it; it is checked when 06 is ported.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `labels.ipynb` ported; v1 numbers reproduced.
- 2026-11-24: component created in v2. Rubric v3 guide with twelve anchor pairs; `rubric_v3.py` (build-sheet,
  check, scores, consensus, earned tie-break); blind sheet of 323 pairs written; 10 tests pass.
- 2026-11-24: copied into full v2 (v2 became a working copy of v1a); existing outputs stay in `outputs-local/v1a/` and are read in place, new runs go to `outputs-local/v2/`.
- 2026-11-27: rubric v3 filled by Matthew and Barbara; scored and consensus run pinned; three v3 cohorts in
  `cohorts.py` (+1 test); `labels.ipynb` section 3.7 and three checks.
- 2026-11-28: rulings of 11-27 in `RUBRIC_V3.md` (main business; question 2 wording and scope; Boston Omaha anchor;
  per-outcome tie-break). `judge_v3.py` + prompt; GPT-Terra on all 323 pairs; `rubric_v3.py final`; cohort
  `v3_final`; `labels.ipynb` section 3.8 and three checks (13/13).
- 2026-11-28: round 4 sheet (`round4_sheet.py`); `rubric_v3.KEY_ROWS_1127`, `save_sheet(key_rows=)`, `build_sheet(anchors=)` (the first sheet rebuilds unchanged). Tests: 52 pass.
