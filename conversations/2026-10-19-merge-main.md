# 2026-10-19: merge main into michael/wip

Merged `origin/main` (`8e72d9e`) into `michael/wip` so the branch can go to
main by pull request.

## What came in from main

- `de322e2` (Xiaozhe): input rules updated after Aziz's reply on 10-Ks and
  financials (PROJECT_STATE.md, "Agreed methodology").
- `86b29fd`, `8e72d9e` (Yikai): ten-company comparability and valuation
  pilot in `experiments/whole_company_pilot/`, `notebooks/`,
  `reports/whole_company_pilot/`, plus `.gitattributes` entries for it.

## Changes made in the merge

- PROJECT_STATE.md: the only conflict. Kept main's rules, Growth signals
  row and pilot section (including its mention of `michael/wip`, unchanged)
  and this branch's matching rows, methodology and next steps. Main's
  "Results…" row is now "Ten-company research pilot". Added a note that the
  matching methods are stricter than the new rules, and a next step to use
  scale (target revenue, EBITDA, debt) and comps' 10-K detail.
- matching/README.md: same strictness note under "Discipline".
- AGENTS.md (and so CLAUDE.md, which includes it): Aziz's rule and the
  financial-fields rule brought in line with the 2026-10-19 update.
- README.md: `matching/` row now lists all three methods and the
  evaluation notebook.

## Tests

- `website_scrape` + `growth_signals`: 96 passed.
- `experiments/whole_company_pilot/tests`: 108 passed, 6 failed. The pilot
  files are byte-identical to main's. The failures come from this machine:
  `POT` and `gensim` are not installed (in the pilot's
  requirements-test/replay files), and two notebook-builder tests hit a
  Windows temp-path error under `experiments/whole_company_pilot/outputs-local/`.
  Not caused by the merge.

## Data version

`company_list_v3`, unchanged.

## Next

Open a pull request from `michael/wip` to main for team review of the
matching approach. Then: scale as a secondary criterion (PROJECT_STATE.md,
next step 2).
