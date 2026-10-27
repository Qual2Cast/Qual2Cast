# 2026-10-27: golden-set notebook (pool to label, labels check, metrics)

Goal: label target-comp pairs by hand as a golden set for PCTY and WEN (the
section 9 pick of `comps_and_valuation.ipynb`) and get precision@10, direct
hits@10 and NDCG@10 per route at the end.

## Changes

- `v0/golden_set.py`: pool (union of routes), shuffled labeler sheet, label
  checks, metrics. `v0/tests/test_golden_set.py`: 6 tests.
- `v0/notebooks/golden_set.ipynb` (executed, kernel `qual2cast`, no API calls):
  1. routes from the saved outputs of the main notebook: cosine similarity
     (top 10 or z >= 2), cosine then LLM good comps, LLM picks directly, LLM
     picks then cosine;
  2. the pool to label: 36 pairs (WEN 20, PCTY 16), and the blank sheet;
  3. label check; 4. metrics, written to `golden_set/metrics/<run>/`.
- Sheet: `outputs-local/comps_pilot_targets/golden_set/labels/golden_set_labels.csv`
  (UTF-8 with BOM for Excel). Columns: pair, target and comp name / SIC /
  website / model-written offering and customer text, then `score`,
  `reason_if_0`, `notes`, then ids. Rows are shuffled with seed 2026; no rank,
  similarity, LLM verdict or EV/EBITDA on it. `pool_with_routes.csv` beside it
  has which route found each pair and where (not for the labeler).
- Rubric as given: 2 direct competitor, 1 adjacent, anything else 0 with one
  reason: Different business model, Different customers, Different scale,
  Generic wording only, Wrong industry code. A blank score with no reason is
  "not reviewed", so a half-filled sheet cannot produce metrics by accident.
- Docs: rows added to `v0/README.md` and `outputs-local/comps_pilot_targets/README.md`.

## Metric definitions (decisions to review)

- Precision@10 is divided by what the route listed (up to 10), not by 10: the
  direct-pick routes list 3-5 comps, and dividing by 10 would mostly measure
  list length. The "listed in top 10" column is shown beside it.
- NDCG@10 uses the score as the gain (no 2^g - 1), log2(position + 1) discount,
  and the ideal order of the target's whole labeled pool. It counts good peers
  a short list left out against it.
- Peers no route found are not in the pool, so recall is not measured.
- Mean over targets is a plain mean of the two targets.

## Tests and data

- 105 tests pass (99 + 6). The notebook ran with the real (blank) sheet, and
  separately with random throwaway labels in a scratch copy, which printed
  sensible tables; those numbers mean nothing.
- Data: `company_list_v3`; universe run `20261025T060358Z`; candidates and
  LLM-then-cosine run `20261027T204930Z`; judge and suggest tables as in the
  README there. The labels file is in the shared `outputs-local/comps*/` rule.

## Open issues / next step

- Michael scores the 36 pairs, saves the CSV, re-runs from section 3.
- Then compare the LLM judge's good/bad verdicts (`judgments.csv`) with the
  hand scores (precision and recall of the judge); not built.
- The sheet shows model-written facet text for convenience, which is the same
  text the LLM judge read; score from the websites if that worries you.
- Nothing is committed.
