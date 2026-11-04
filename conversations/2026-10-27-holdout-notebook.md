# 2026-10-27: holdout notebook (built, holdout not scored)

Goal: a separate notebook that tests the baseline on the 160 holdout firms,
once, with the settings frozen first. `comps_and_valuation.ipynb` stays the
training-only development notebook.

## Changes

- `v0/notebooks/holdout_test.ipynb` (executed in training mode, kernel `qual2cast`):
  inputs and saved split; mode and freeze; candidates (facets only); LLM judge
  step; estimates; scores with bootstrap intervals; save.
  - `MODE = "training"`: reference run on the training firms; reproduces the
    development notebook (373 targets, 4,996 judged pairs, 592 good; no
    matching 31.9%, cosine top 10 weighted mean 28.8%, z >= 2 29.6%, LLM good
    comps 30.5%, same SIC 35.0-36.7%). Saved to `holdout/reference_training/<run>/`.
  - `MODE = "holdout"`: needs `holdout/freeze.json` and stops if the current
    settings differ from it, or if the holdout was already scored under that
    freeze. Writes the holdout candidates run (facets only), then stops
    and prints the `judge_comps.py` command until every holdout target is
    judged; scores only after. Comps' multiples come from `ev_pool` (training
    firms), so a holdout multiple cannot reach an estimate. Saved to `holdout/scores/<run>/`.
  - Freeze file: split run, universe run, facets version, embedding model, k, z
    levels, judge model and prompt version, rule list, `primary_rule`, git
    commit and whether `v0/` had uncommitted changes. An old freeze moves to `holdout/history/`.
- `v0/valuation.py`: `bootstrap` (95% interval on each rule's median absolute
  % error and on its paired gain over the baseline). Test added in `tests/test_valuation.py`.
- Docs: `v0/README.md` row, `PROJECT_STATE.md`.

## Tests and data

- 129 tests pass (128 + 1). Training-mode notebook ran end to end; a temporary
  copy in holdout mode stopped at the no-freeze check (deleted afterwards).
- Data: `company_list_v3`; split run `20261027T204930Z`; universe run
  `20261025T060358Z`; facets `2026-10-25k`; judge prompt `2026-10-25a`.
- No holdout multiple was read. No API calls were made.

## Finding on the training set

No rule's gain over no matching has a 95% interval that excludes 0 (373
targets): cosine top 10 weighted +3.1 points (-1.5 to +5.5), LLM good comps
+1.1 (-3.0 to +6.1), same SIC4/3 about -4.7 (worse). A one-point gap between
routes on 160 holdout targets will not be distinguishable.

## Open issues / next step

- `PRIMARY_RULE` is not chosen; it has to be chosen on training results, with the team.
- Which split is final (SIC2 vs size-stratified) and the "not applicable" facet
  treatment (notebook section 10) should be settled before freezing.
- The direct-LLM routes (`suggest_comps.py`, `llm_then_cosine.py`) are not scored
  on the holdout: `suggest_comps.py` takes the training firms as targets and needs
  a target-set option.
- Order: label the golden set, pick the route, set `PRIMARY_RULE`, set
  `WRITE_FREEZE = True` once, set `MODE = "holdout"`, run, run the printed judge
  command, run again.
