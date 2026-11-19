# 08_valuation: Valuation

The estimate is the median EV/EBITDA of a target's selected comps, compared with its actual multiple, with bootstrap intervals over targets. With 10_final_holdout, the only component that reads `financials.csv`.

**Status (2026-11-19): ported.** Scripts, tests and `valuation.ipynb` are in place; the notebook values the current lists (5/5 checks pass); v1's numbers were for the Haiku B3 list and are not reproduced (decision 2026-11-19).

## Current setting (`v1a/current.toml`)

- `financials` = `outputs-local/v1a/08_valuation/financials.csv`
- `estimate` = `median EV/EBITDA of the selected peers`

## Outputs (`outputs-local/v1a/08_valuation/`)

- `financials.csv` (1 file)
- `gpt61sol_293_selection/` (5 files)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/valuation.py` (script): median peer EV/EBITDA, bootstrap; plus agent_valuation.py (moved from 05)
- `v1/scripts/tests/test_valuation.py` (test)
- `v1/notebooks/comps_and_valuation.ipynb` (notebook): current lists; v1 Haiku-list numbers not reproduced (decision 2026-11-19)

Commit authors of these files (git): EFL-YL, mcschlatt.

## Notes (training targets; the holdout valuation is in 10)

- On the current lists, no rule is shown to beat "no matching" (31.9% median absolute error on 373 targets):
  B3 median 33.8%, B3 similarity-weighted 30.2%, selector with B3 fallback 31.3%; on the 265 targets where the
  selector kept a comp, selector 30.6% vs B3 32.6%. Every interval of the gain includes 0.
- `agent_valuation.py`: the valuation code that was in `agent_ranking.py` and `agent_loop_eval.py`.
- `split_peer_eval.py` and `source_scope_sensitivity.py` (valuation checks of 11-10 profile variants) stay in v1.
- Valuation numbers check chosen lists; they are never used to choose a list, facet or prompt.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `valuation.ipynb` ported; v1 numbers reproduced.
