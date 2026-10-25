# pre-v0/

Work from before v0, the comps recipe in [`../v0/`](../v0/README.md)
(started 2026-10-21, recipe received 2026-10-24). Moved here on 2026-10-24 so
the top level shows only the current pipeline. Nothing was deleted or
rewritten; each folder keeps its own README, and the code still runs from
its new place.

| folder | what it is | last on main |
|---|---|---|
| [`matching/`](matching/README.md) | Comparable-company matching from website embeddings: methods 1-3 and the evaluation notebook | 2026-10-19 |
| [`growth_signals/`](growth_signals/README.md) | Dated growth events from News/Press/Careers pages, rule-based extraction, cutoff-safe features | 2026-10-18 |
| `notebooks/`, `experiments/`, `reports/` | The ten-company research pilot: [results](reports/whole_company_pilot/README.md), [notebook](notebooks/whole_company_pilot.ipynb), [code](experiments/whole_company_pilot/README.md) | 2026-10-19 |
| [`pipeline/`](pipeline/TEAM_WORKFLOW.md), [`valuation/`](valuation/), `notebooks/team_company_workflow.ipynb`, `notebooks/integrated_company_analysis.ipynb`, `experiments/integrated_company_analysis/`, `reports/team_company_workflow/`, `reports/integrated_company_analysis/` | The integrated team workflow (Yikai): staged company workflow, integrated 19-company experiment, four-page [team memo](reports/team_company_workflow/team_research_memo.pdf). Merged into main 2026-10-19/20 (PRs #5-#7) and moved here 2026-10-25 | 2026-10-20 |
| [`scraps/`](scraps/README.md) | Attempts set aside earlier still: Codex profiles, first matching pass, first collection script | 2026-10-18 |

Still at the top level, because v0 uses them: `website_scrape/`, `src/`,
`docs/`, `data-local/`, `outputs-local/` and `conversations/`.

## Notes on the move

- **Outputs didn't move.** Runs still write to `outputs-local/matching/`,
  `outputs-local/growth_signals/` and `outputs-local/scraps/`, as before.
- **Repo-root lookups were updated** (one more `parents[...]` level) in
  `growth_signals/collect_company_pages.py`, `growth_signals/fetch_adapter.py`,
  `scraps/codex_profiles/profile_schema.py`,
  `scraps/collect_descriptions_v0/collect_descriptions.py`,
  `scraps/comps_first_pass/comps_similarity.py` and
  `scraps/comps_first_pass/comps_embeddings.ipynb`. The matching notebooks
  find the root by searching upward for `data_manifest.json`, so they needed
  no change.
- **The pilot package is byte-for-byte unchanged.** Its file hashes are
  recorded relative to the folder holding `notebooks/`, `experiments/` and
  `reports/`, which is now `pre-v0/`; the `-text` rules in `.gitattributes`
  moved with it. It finds the team data through the absolute `team_root` in
  its frozen design file, which the move doesn't affect.
- Handoff notes in `conversations/` dated before 2026-10-24 use the old
  paths (`matching/`, `scraps/`, ...): read them as `pre-v0/matching/`, etc.

## The integrated team workflow (moved 2026-10-25)

Merged into main on 2026-10-19/20 while this reorganization was on a branch,
and moved here when the branch was merged with main (2026-10-25).

- **Its packages import from `pre-v0/`.** `pipeline`, `matching`,
  `growth_signals` and `valuation` are imported by those names, so run its
  commands from the repo root with `PYTHONPATH=pre-v0` (see
  [`pipeline/TEAM_WORKFLOW.md`](pipeline/TEAM_WORKFLOW.md)), and its tests from
  `pre-v0/` (`python -m pytest pipeline/tests -q`; 50 pass) or
  `pre-v0/growth_signals/` (`python -m pytest tests -q`; 218 pass).
- **Repo-root lookups updated** (one more `parents[...]` level) in
  `pipeline/collection.py` (website_scrape), `growth_signals/edgar_revenue.py`
  and `pipeline/run_workflow.py` (outputs-local); nothing else changed.
- **Its notebooks and reports are byte-for-byte as on main.** The notebooks
  unpack their own code into a working folder, so the move doesn't affect
  them; their `-text` rules in `.gitattributes` moved with them.
