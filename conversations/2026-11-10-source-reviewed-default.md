# 2026-11-10: Source-reviewed default for v1 integration

The requested integration task was to use corrected business scope as the
local default and rerun affected downstream stages.

- Official 2026 company releases corrected ten fields across HLTC, ENSG and
  SKIL. TKR was already current. The source, prior value and replacement are
  in `outputs-local/v1/integration/source_reviewed_default/changes.csv`.
- The 533-company corrected table is the default for the integrated retrieval
  and company-report path. Historical team files and comparison inputs were
  preserved. This review targeted four firms, not the entire universe.
- Rebuilt 20 retrieval methods, 160 B3 shortlists, all four GPT-6.1 Sol
  selection routes, factor and reviewer comparisons, and error diagnosis.
  The four-route run completed all 160 targets without answer issues.
- The same-rule before/after B3 comparison changed one selected peer list.
  Median absolute multiple error was 34.5187% before and 34.5172% after;
  the paired bootstrap interval includes zero. The four new default routes
  have different coverage and their medians alone do not rank them.
- `v1/notebooks/comps_and_valuation.ipynb` retains its original first 65
  cells and continues section numbering from 13 to 23; all 23 integration
  code cells executed. `validation.json` passed. The experiment matrix has
  3,167 rows. The result is prepared for PR #32 as Update 2.

The independent private-company outcome test and fresh final holdout belong
to later project validation, not to this local integration task.
