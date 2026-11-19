# 01_universe: Universe and split

Which companies are in scope and how they are split. 533 eligible public companies (snapshot `company_list_v3`); 373 training companies form the comp pool and the development targets; 160 holdout companies are the valuation test and never enter the comp pool.

**Status (2026-11-19): ported.** Scripts, tests and `universe.ipynb` are in place; the notebook reproduces the saved v1 numbers (7/7 checks pass).

## Current setting (`v1a/current.toml`)

- `snapshot` = `company_list_v3`
- `universe_run` = `20261025T060358Z`
- `split_run` = `20261027T204930Z`
- `universe` = `outputs-local/v1a/01_universe/universe/universe.csv`
- `split` = `outputs-local/v1a/01_universe/split/split.csv`

## Outputs (`outputs-local/v1a/01_universe/`)

- `split/` (5 files)
- `universe/` (3 files)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/split.py` (script): 373 training / 160 holdout, SIC2-stratified
- `v1/scripts/universe.py` (script)
- `v1/scripts/tests/test_split_and_candidates.py` (test)
- `v1/notebooks/comp_universe_and_facets.ipynb` (notebook)

Commit authors of these files (git): mcschlatt.

## Notes

- `split.sic2_split()` holds the split logic that was in `v1/notebooks/comps_and_valuation.ipynb` cell 7.
- `split/balance_numeric.csv` has aggregate financial balance (means, SMD) from the split check. No per-company
  financials are in 01; they are in `08_valuation/financials.csv`.
- Run: `uv run pytest v1a/01_universe/tests -q`; open `universe.ipynb` and run all.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `universe.ipynb` ported; v1 numbers reproduced.
