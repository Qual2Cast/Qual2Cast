# Rubric v3 labels in: Matthew and Barbara — 2026-11-27

Michael, with Claude Code (Opus 5.5). Branch `michael/site` (working tree; nothing committed).

## Request

Michael saved the filled rubric v3 sheet in the repo root (`rubric_v3_sheet.xlsx - matthew.csv`, a Google Sheets
download of the `matthew` tab, holding Matthew's and Barbara's answers). Move and rename it, make it usable, then
set out next steps.

## What was done

| file | what |
|---|---|
| `outputs-local/v2/06_labels/rubric_v3/filled/rubric_v3_filled_matthew_barbara_20261127.csv` | the export, moved and renamed, bytes unchanged (sha256 `d19dfe3f...`) |
| `.../filled/manifest.json` | provenance: received-as name, layout, counts, sha256 of it and of the blank sheet, the pairs-and-descriptions match |
| `.../rubric_v3/scores/20261128T001954Z/` | `rubric_v3.py scores` and `consensus` (no tie-break), plus a manifest with commands and hashes |
| `v2/current.toml` | `[rubric_v3] filled`, `scores` pinned; three cohorts added to `[labels] cohorts` (default cohort unchanged) |
| `v2/06_labels/scripts/cohorts.py` | `matthew_v3_311`, `barbara_v3_311`, `v3_agreed` (from the pinned run, anchors out) |
| `v2/06_labels/tests/test_cohorts.py` | counts for the three cohorts; agreed grade equals both reviewers' score |
| `v2/06_labels/labels.ipynb` | section 3.7 (agreement, overall call vs score, score crosstab, splits by question, anchors, change from earlier labels); three new checks; 10/10 pass |
| `v2/06_labels/README.md` | status, outputs, cohort table, changelog |

Checks on the file: 323/323 answered by both; `rubric_v3.py check` finds no problems; pair order and all 17
description columns equal the blank sheet; Barbara's appended columns line up with the right pairs (her notes name
the pair's companies). The file has no riya columns. The two reviewers' answers are not checked for independence.

Tests: `v2/06_labels` 39 pass; all of `v2` 305 pass. No model calls. Data: `company_list_v3`.

## Results (311 scored pairs, 67 targets; anchors left out)

| item | agreement | kappa | yes rate Matthew / Barbara |
|---|---:|---:|---:|
| overall call | 88.7% | 0.76 | 35% / 37% |
| same product | 79.7% | 0.61 | 36% / 55% |
| same customers | 79.1% | 0.57 | 55% / 60% |
| same revenue model | 95.5% | 0.86 | 80% / 79% |
| same chain step | 88.1% | 0.63 | 77% / 83% |
| peer (score >= 1) | 78.5% | 0.56 | 55% / 60% |
| direct (score 2) | 88.7% | 0.76 | 33% / 43% |
| score 0/1/2 (linear weights) | 73.3% | 0.66 | |

- Earlier (Barbara old form vs Matthew rubric v2) the same two agreed at kappa 0.19.
- Derived scores (rows Matthew, columns Barbara, 0/1/2): `[[98, 23, 19], [25, 29, 15], [0, 1, 101]]`.
- Consensus: all four questions agreed on 180 (101 direct, 8 adjacent, 71 not a peer); 131 pairs have a split
  question: customers 65, product 63, chain step 37, revenue model 14; overall call split on 35. Same derived
  score on 228.
- Product splits are one-directional: Barbara yes / Matthew no 62, the reverse 1 (32 targets; CRAI, DGII 4 each).
  Notes show Barbara counting an overlapping line or component category (Stride's small adult-learning line for
  APEI; Allient motion control for Crane), Matthew asking whether the target's buyer could place the same order.
  Chain step: 28 vs 9; customers: 40 vs 25, same direction.
- Overall call vs own derived score: Matthew yes on 3/140 of his 0s, 7/69 of his 1s, 100/102 of his 2s; Barbara
  0/123, 11/53, 104/135. Overall call vs direct: kappa 0.91 (Matthew), 0.72 (Barbara).
- Anchors: both gave the proposed answer on 11 of 12. Barbara answered no on P318 THR/FLS customers (proposed:
  clear yes). Reviewers had the guide, so this checks reading, not independent agreement.
- Change from earlier labels on the same pairs: Barbara old 1s (173) became v3 0 / 1 / 2 = 49 / 43 / 81; her 2s
  went from 21 to 106 of 281. Matthew v2 1s (117) became 65 / 44 / 8; of his 116 v2 "product no, customers yes"
  pairs, 51 keep customers yes (v3 score 0: 65, 1: 43, 2: 8).

## Open issues

- **"Same product" reading.** The two read question 1 differently on partial overlaps. Tied to two open rules:
  what counts as a *material* business of the comp, and the minor-business cap (carried from v2).
- **P318 THR/FLS** customers "clear yes": Barbara says no. The team's ruling decides whether customers can be yes
  when product is no for shared plant-engineering buyers.
- **Which agreement defines the headline set:** all four answers alike (the coded rule: 180 pairs) or the same
  outcome (direct agreed on 276, peer on 244, score on 228).
- **Adjacent is thin:** 8 agreed score-1 pairs, and the overall call is yes on few 1s. "Any peer" as a north-star
  outcome may not be what either reviewer would use as a comp.
- 131 split pairs need a tie-break: GPT-Terra judge prompt not written (approval needed), or Riya.
- Not yet scored against v3: the improvement ledger baseline, GRADING_REVIEW agent/selector figures, the trait
  X-learner (pre-registered rerun). The pair ledger has no v3 source yet.
- Site (`site/facts/ch5_judging.py`) still reports the old-form/v2 kappa only; freeze Nov 30.

## Next steps

1. Team rules on question 1 (partial overlap / material line), P318, and whether the headline set is "all four
   alike" or "same outcome"; then update `RUBRIC_V3.md` with a dated note.
2. Break the 131 ties: write the GPT-Terra five-question prompt (Michael's approval before any run) or send the
   split pairs to Riya.
3. Score the saved baseline on v3 (`progress.py score --cohort-file .../consensus.csv`): no model calls.
4. Rerun the pre-registered trait X-learner unchanged on the v3 cohort once the headline set is decided; overall
   call as the separate cross-check family.
5. Add v3 facts to the site's judging chapter before the Nov 30 freeze (people write the sentences).

## Added later (2026-11-27): the two open rulings, and both headline sets scored

**P318 THR/FLS (customers).** The guide's "clear yes" for question 2: heat tracing vs pumps and valves, different
products, same plant engineers and EPC contractors. Matthew: product no, customers yes (score 1), overall call
yes. Barbara: product no, customers no (score 0), overall call no; her note is about the product only. Across the
sheet Barbara says customers yes with product no on 16 of 139 product-no pairs, Matthew on 60 of 200; on the 138
pairs both call product no they split on customers 31 times (24 Matthew yes). Readings: customers = who buys (the
guide; makes "same buyers, different product" an adjacent), or customers = would they buy the target's kind of
thing from the comp (folds into question 1).

**Partial product overlap (question 1).** The 62 Barbara-yes / Matthew-no pairs (32 targets) are of two kinds in
Barbara's notes: a narrow line of the comp (Stride's adult career line for APEI, Ingles's fuel for Par Pacific,
Hormel's Planters for Simply Good Foods), and the same broad category without the same order (new vs thrift
clothing for Savers, motion control for Crane, different kidney-disease drugs for Akebia). The guide says the broad
category is not enough, and that any *material* business of the comp counts (undefined). On these 62 Barbara
scores 29 direct and 33 adjacent; with product no her scores would be 60 adjacent, 2 not a peer. Revenue model and
chain step ("judge the comp by its larger part") rarely demote them, because both sides usually "sell a service"
or "make it". These 29 explain most of the direct-count gap (Barbara 135, Matthew 102).

**Headline set, both ways** (`v2/09_analysis/scripts/headline_sets.py`, run
`outputs-local/v2/09_analysis/headline_sets/20261128T004855Z/`; table in `v2/09_analysis/README.md`). Every profile
on the same pairs (45 dev targets; the agent run lacks the 30 extra B3 pairs). Same 72 direct peers either way, so
direct recall is identical; `same_outcome` adds 96 pairs both reviewers call not direct while differing on a
question, and these lower direct precision for loose filters (agent ≥ 1 69% → 42%, B3 all 43% → 26%) more than
for the selector (91% → 87%). Under `all_four` only 8 agreed adjacents remain, so any peer is close to direct
(80 vs 72 positives); under `same_outcome` 116 peers. Tie-breaks needed: 131 pairs (`all_four`) vs 83 (35 split
on direct, 67 on peer). On v3 labels the selector's any-peer recall is 54-75% against 34% on Matthew's v2 labels
(the labels changed, not the pipeline). 2 tests added (09: `test_headline_sets.py`).
