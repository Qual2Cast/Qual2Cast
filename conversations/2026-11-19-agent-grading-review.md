# Agent grading review: the grade as a filter, Barbara's C/S/E ranking — 2026-11-19

Michael, with Claude Code. Branch `michael/wip`, PR to `main`.

## Request

Review the agent grading and the mechanisms behind Barbara's ranking work: keep them in v2 only if they hold
up. A groupmate pointed out that the order is lexicographic (agent grade, then S, then B3), with no combined
score. Michael wanted the grading criterion made clear, the agent compared with the selector as an any-peer
filter for the report, Barbara's model choice and assumptions listed, and thoughts on rubric v2 (yes/no
questions, Cohen's kappa) and on how reviews can improve the models (for example, a shorter comp list).

## Decisions (Michael)

- Ranking is worth having, but not an agent's ranking taken on trust. C/S/E has to be reworked to make sense;
  that work is left for next steps.
- No 0/25/50/75/100 facet scale: too fine, and reviewers would disagree on it.
- The agent's 0/1/2 grade stays as the any-peer filter.

## What was built

| file | what |
|---|---|
| `v1a/05_agent_grading/GRADING_REVIEW.md` | the review: the two filters, results against both reviewers, kappa, Barbara's model and assumptions, list length, rubric v2, how to improve the models, next steps |
| `v1a/05_agent_grading/scripts/filter_comparison.py` | saved runs only, no model calls; writes `outputs-local/v1a/05_agent_grading/filter_comparison/<stamp>/` |
| `v1a/05_agent_grading/tests/test_filter_comparison.py` | 4 offline tests |
| `v1a/05_agent_grading/README.md`, `PROJECT_STATE.md` | status and pointers |

## Results (run `20261119T033731Z`)

- Any peer vs Barbara (293 pairs, 202 peers): agent ≥ 1 precision 91.8%, recall 83.2%, kappa 0.63; selector
  95.7% / 32.7% / 0.21. Vs Matthew v2 (262 pairs): agent 83.4% / 73.9% / 0.37; selector 95.1% / 31.5% / 0.19.
- Direct peers: the selector keeps all 24 of Barbara's 2s; vs Matthew's 60 twos, precision 82.0%, recall
  83.3%, kappa 0.77.
- Reviewer agreement: Barbara vs Matthew peer kappa 0.19 (different rubrics too); the disagreement is Barbara's
  broad 1s (she gives 42 ones where Matthew says neither product nor customers match).
- C/S/E: S comes from the same answer as the grade (median 29/50/79 by grade); +0.6 over grade-then-B3
  (−5.3 to +5.9); 11 of her 32 facets (66/100 points); her 80% coverage rule met by 27/293.
- Batch size: zero rate rises from 9% at rank 1 to 67% at rank 10; with the agent filter, a cap at 7 removes
  15 peers and 3 zeros among the 18 kept at ranks 8-10.

## Tests and data version

`uv run pytest v1a/05_agent_grading/tests -q`: 26 pass. Data as in `v1a/current.toml`: selector
`b3_selector_candidates_2026-11-04a_claude-cli_claude-sonnet-5-5`, agent run `ranking_45targets_sonnet`
(ranking `20261113T060740Z`), labels `dev_293` and `round3_scores_v2.csv`.

## Open issues

- No second reviewer on rubric v2 yet (Barbara's v2 columns are empty), so there is no same-rubric person-vs-
  person kappa.
- `agent_ranking.py` still computes `final_rank` / `e_rank`, and `10_final_holdout/final_check.py` reports
  them; they are kept for the record, not for decisions.
- The untracked `outputs-local/v1a/05_agent_grading/b3_kept_30/` and `v1a/06_labels/scripts/extend_label_book.py`
  are from other work and were left untouched.

## Next

1. A second reviewer fills the round-3 rubric v2 sheet; per-question kappa.
2. The agent grader asks the four rubric v2 questions (one citation each).
3. Rework the ranking: yes/no facet judgments in a separate call, decide what unknown means, choose on half
   the labelled targets and check on the other half.
