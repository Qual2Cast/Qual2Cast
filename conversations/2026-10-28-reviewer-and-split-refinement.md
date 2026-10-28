# Reviewer labels and business-split refinement — 2026-10-28

## Data and implementation

- Source snapshot: `company_list_v3`; updated SIC2 candidates run
  `20261027T204930Z`. Three blind reviews were copied read-only from the
  shared `golden_set_labels` Google Sheet (`labels!A1:Z37`) at 11:25 UTC.
  The local snapshot records scores, zero reasons, notes, pair IDs, and source.
- `v0/reviewer_gold_eval.py` reconstructs the four route rankings from the
  team's frozen 36-pair pool and calls `v0/golden_set.py` for precision@10,
  direct hits@10, and NDCG@10. It validates each reviewer independently and
  exports pairwise disagreement. It does not alter the team's blank label CSV.
- `v0/business_split_refinement.py` uses the saved 40-company source-bound
  decisions. Complete source-cited groupings take priority over contradictory
  pairwise model labels. Otherwise, related or unresolved current activities
  stay together unless a direct distinct-business judgment separates them. Every
  current activity belongs to exactly one group. Completed exits are recorded
  outside current scope. Each firm keeps one Capital IQ ID. The original
  decisions and evidence remain in the frozen snapshot for audit. Dated official
  sources correct UFPT, Brown & Brown, and Silgan activity statuses in a separate
  `source_corrections.json`; the original snapshot is unchanged.
- `v0/source_split_benchmark.py` checks ten selected source-challenge cases
  against 34 current/exited activity labels and nine exact group partitions
  documented in `primary_source_reference.json`. This is a targeted source
  regression check, not a blinded population accuracy estimate.
- `v0/split_peer_eval.py` tests selective current-scope notes against a control
  on the same ten development targets, SIC2 candidate pool, `gpt-6.1-sol`
  model, similarity-weighted valuation function, and no-matching fallback.
  `v0/holdout_split_candidates.py` applies the fixed SIC2 split to the six
  source-pilot holdout companies using the saved training embedding cache.
  All prompts, responses, pair decisions, and valuations are saved. The
  executed `v0/notebooks/business_split_refinement_eval.ipynb` displays the
  reviewer, source, development, and holdout results with three charts. The
  main v0 notebook and its outputs were not edited.

## Results

- Human labels: 36 pairs, 11 unanimous and 25 disputed. Pairwise exact
  agreement is 12/36 (Riya–Barbara), 12/36 (Riya–Matthew), and 30/36
  (Barbara–Matthew). Route metrics vary substantially by reviewer. The
  PCTY/WEN labels assess peer ranking but cannot validate multi-business
  splits, because both targets are one-business firms.
- Forty split records: 8 are multi-business after refinement, versus 7 in the
  saved decisions. NWSA retains four source-cited groups, SNFC.A three, and
  BBCP two: its directly distinct current services cannot be rejoined via a
  chain of merely related pair labels. Brown & Brown moves from one group to
  two, following its current Retail and Specialty Distribution structure.
  UFPT's divested Molded Fiber line is excluded from current scope. Four
  companies have conflicting pair labels: NWSA, BUKS, BBCP, and BRO.
- In the ten targeted cases, source-consistent current/exited statuses improve
  from 27/34 to 34/34 and exact current group partitions from 7/9 to 9/9.
  The checks use the sources that informed corrections and must not be read as
  an independent generalization score.
- Paired downstream test: 137 candidate pairs, 4 changed peer decisions,
  matched-peer coverage 7/10 in both modes. Median APE: control 19.26%,
  selective scope 39.41%. The increase is chiefly CSL and BOC. These are ten
  selected development cases.
- Fixed-holdout check: six source-pilot companies, 72 evaluated candidate
  pairs, one changed decision (LUCK–PRKS). Matched-peer coverage rises from
  4/6 to 5/6 but median APE rises from 31.02% to 40.21%; LUCK's own APE rises
  from 9.58% to 40.74%. The holdout was not used to choose the tested rule.

## Decision and next step

Keep the source-checked split as auditable business-scope metadata. Do not
replace the v0 peer selection or valuation with the tested selective-scope
prompt: median APE worsened on both development and holdout subsets. The
shared reviewers' raw scores are preserved; an exact 2-of-3 majority label is
exported for 32 pairs, while four three-way ties remain unresolved.
`changed_pair_source_audit.json` records post-run analyst diagnostics,
not blinded human peer labels.

Local output: `outputs-local/comps_pilot_targets/business_structure_refinement/`
and `outputs-local/comps_pilot_targets/golden_set/reviewer_evaluation/`.
New tests: eight focused tests pass; notebook executes 14 cells, no errors.
No remote upload or shared Google Sheet edit was made.
