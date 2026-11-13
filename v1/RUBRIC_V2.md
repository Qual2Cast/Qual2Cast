# Rubric v2: four yes/no questions per pair

**For:** everyone who labels target-comp pairs (round 3 onward), whoever prepares and collects the
sheets, and whoever changes the agent grader's prompt. The code is `v1/scripts/rubric_v2.py`.

## Why the rubric changed

Rounds 1 and 2 used one judgment per pair: 2 = same product **and** same customers, 1 = one of the
two, 0 = neither, with one of six reasons on every 0. Three problems showed up on the 324 labeled
pairs (31 in round 2, 293 in Barbara's round 3):

- **A 1 hides which half matched.** The sheet records "product or customers" but not which. Of the
  293 pairs Barbara labeled, 178 are 1s. None of them can be checked question by question.
- **"Same product" and "same customers" were never defined.** Matthew and Barbara split on 6 of 31
  round-2 pairs, and 5 of the 6 were a 1 against a 0 (for example Carlisle vs Comfort Systems:
  installs HVAC vs makes roofing). The disagreement was about the definition, not the facts.
- **The six zero reasons were not used.** Across 101 zeros from two reviewers, only three reasons
  appear: different business model, different customers, different industry. Scale, generic wording
  and wrong industry code were never chosen.

The mentor asked (Nov 8) for "a more detailed rubric so that you have an objective way to grade comps
and facet fills" to reduce person-to-person variability. The team and Professor Robbins agreed (Nov 9)
to grade **yes/no questions** and derive the score from the answers. Published finance evals do the
same thing: a checklist of components scored one at a time, not a whole-answer grade.

## The four questions

Answer each one **yes** or **no** for the pair. Nobody types a score.

| # | column | question | how to decide |
|---|---|---|---|
| 1 | `same_product` | Can a customer of the target buy the same kind of product or service from the comp instead? | Think of one actual buyer of the target. If that buyer can place the same order with the comp, yes. A roofing manufacturer and an HVAC installer: no. |
| 2 | `same_customers` | Does the comp sell to the same type of buyer? | Type means consumer or business, and for business buyers the buyer's industry. Two companies both selling to oil and gas operators: yes. A consumer app and a B2B software vendor: no. |
| 3 | `same_revenue_model` | Does the comp earn money the same way? | The ways are: sells goods, sells a service, subscription, commission or fees, insurance premiums, interest. A food manufacturer (sells goods) and a restaurant (sells a service): no. |
| 4 | `same_chain_step` | Does the comp sit at the same step of the chain? | The steps are: makes it, distributes it, sells it to the end user, services it. A distributor and the manufacturer it buys from: no. |

Use the descriptions in the sheet, the companies' websites, and what you know. Five to ten minutes per
pair is plenty. Put anything else, for example which product line matches or what you were unsure
about, in your `notes_` column.

## The score comes from the answers

| score | meaning | rule |
|---|---|---|
| **2** | direct competitor | yes to all four |
| **1** | adjacent | yes to question 1 or question 2, but not yes to all four |
| **0** | not a peer | no to question 1 and no to question 2 |

The notebook computes it (`rubric_v2.scores`). The 2/1/0 scale stays, so the metrics
(precision@k, direct hits, NDCG), the agent-grader comparison and the valuation checks keep working.
The old "reason for a 0" column is gone: the reason is whichever questions got a no. If the team later
decides a 2 needs only questions 1 to 3, the notebook recomputes and nobody relabels.

## Targets with several businesses

Answer the four questions against the **one** target business the comp matches, and name that
business in the `business_graded_` column (for example "concrete pumping" for BBCP, or "whole company"
for a one-business target). The sheet's `target_business_scope` column lists the businesses. Whether a
comp that matches only a minor business is capped at 1 is then a rule in the notebook, not a judgment
in the sheet. This follows the mentor's Nov 9 advice to filter with facets rather than split companies
by hand.

## Filling in a sheet

- **Columns per reviewer:** `same_product_<you>`, `same_customers_<you>`, `same_revenue_model_<you>`,
  `same_chain_step_<you>`, `business_graded_<you>`, `notes_<you>`. Type `yes` or `no` (capitals do not
  matter; `y` and `n` are accepted). Fill only your own columns, and do not look at the others' until
  everyone is done.
- **Leave alone:** the `pair`, `target_…` and `comp_…` columns and the two id columns at the right end.
- **Blind:** you do not see which method suggested a pair, its rank, its similarity or any multiple.
  Please do not look these up.

## Old labels

A round-1 or round-2 label converts only partly: a 2 means yes to questions 1 and 2 (questions 3 and 4
unknown), and a 0 with "Different customers" means no to question 2. A 1 cannot be converted, because
the sheet never said which half matched. `rubric_v2.py convert` therefore leaves every answer blank
and keeps any old score and reason in `old_score_<reviewer>` and `old_reason_<reviewer>` columns for
reference. Round 1 and round 2 keep their 0/1/2 labels as they are.

## The agent grader

The agent grader (`v1/scripts/agent_loop.py`, Fiona's) still grades with the old rubric text. The
intended change, for Fiona: ask the same four questions, one citation per question from the shown
evidence lines, and derive the score with `rubric_v2.derive_score`. Agreement with the human
reviewers is then measured per question (`rubric_v2.agreement`), which says *which* judgment the
model gets wrong, not only that the score differs.

## Files and commands

- **Round-3 sheet in the new layout:** `outputs-local/v1/golden_set_round3/labels/round3_sheet_v2.csv`
  (262 pairs, 40 targets, reviewers `matthew` and `barbara`), made with

      uv run python v1/scripts/rubric_v2.py convert outputs-local/v1/golden_set_round3/labels/round3_sheet.csv \
          outputs-local/v1/golden_set_round3/labels/round3_sheet_v2.csv

  It is written once and never overwritten. Upload it as a Google Sheet to fill together, as in round 2.
- **Check a filled sheet** (blank, half-answered or misspelled answers, one row per problem):

      uv run python v1/scripts/rubric_v2.py check <filled sheet>.csv

- **Derive the scores and the per-question agreement between reviewers:**

      uv run python v1/scripts/rubric_v2.py scores <filled sheet>.csv <scores out>.csv

  The output has, per reviewer, the four answers as `True`/`False` and the derived `score_<reviewer>`;
  the command prints the agreement table.
- **Tests:** `uv run pytest v1/scripts/tests/test_rubric_v2.py`.

## Still open

- [ ] **Question 2 wording.** On Matthew's 262 round-3 answers, 120 pairs are "product no, customers
      yes" and so score 1. Barbara's old labels split them 72 ones / 48 zeros. Either tighten the
      question (the target's customers would buy this kind of thing from the comp: customer-list
      overlap, not the same industry or payer) or accept a customers-only match as a 1.

- [ ] Riya: second reviewer on the round-3 sheet, or a third column set for a tie-break.
- [ ] Batch size: the plan is 6 or 7 comps per target instead of 10. On Barbara's 293 labels the
      non-comp rate rises from 9% at rank 1 to 67% at rank 10; a cut at 7 drops 28 of 91 zeros and 20
      of 178 ones. Keeping comps with B3 similarity ≥ 0.43 (4% zeros) and dropping below 0.35 (52%
      zeros) loses fewer good pairs than a fixed count.
- [ ] Fiona: the agent grader's four-question prompt.
- [ ] Whether the minor-business cap stays at 1 or becomes 0 (Eric's split work).
