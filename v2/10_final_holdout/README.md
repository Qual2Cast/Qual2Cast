# 10_final_holdout: Final holdout (locked)

The final check, run once at the end with the frozen settings. Holds Barbara's 24 direct-peer pairs whose comps are in the universe (all holdout companies) and the earlier v1 holdout runs. Nothing here is used to choose or tune a method. The 160 holdout targets were already scored several times in v1, so they are not a clean test; the 24 pairs have been graded and scored but not used for any decision.

**Status (2026-11-19): ported.** Scripts, tests and `final_holdout.ipynb` are in place; the notebook is locked (`FINAL_CHECK = False`): it takes inventory and checks that nothing in 01-09 used the holdout (15/15 checks pass).

## Outputs (existing runs in `outputs-local/v1a/10_final_holdout/`, read in place; new runs in `outputs-local/v2/10_final_holdout/`)

- `direct_peers_24/` (9 files)
- `v1_holdout_runs/` (27 files)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1


## Contents

- `direct_peers_24/`: Barbara's 24 in-universe direct-peer pairs (19 Yes, 5 No; No is not a 0): manifest, agent verdicts (same settings as the 293 run), Fiona's assembled output, and `standardized_20261118T204217Z/` (B3 scores and C/S/E computed on 2026-11-18). The X-learner inputs that included 19 of these pairs were deleted the same day; its `run.json` still names them. The 66 pairs with comps outside the universe are not here.
- `v1_holdout_runs/`: the 10-28 holdout routes and Sol cited grades on the 160 holdout targets (already used in development).

## Final check (`scripts/final_check.py`, locked)

- `direct-peers`: the 24 pairs through the 293 pairs' steps (current B3 similarity, rank if in the pool, agent
  settings check, C/S/E alone and pooled). Reproduces the 11-18 standardized output exactly.
- `holdout`: the current B3 lists of the 160 holdout targets and their valuation. The selector on the holdout needs
  an LLM run first (approval).
- Both refuse to run without `--final-check`; the notebook runs them only with `FINAL_CHECK = True`.
- v1's holdout scripts (v0 routes; some made paid LLM calls on the holdout) stay in v1 as the record.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `final_holdout.ipynb` ported; v1 numbers reproduced.
- 2026-11-24: copied into full v2 (v2 became a working copy of v1a); existing outputs stay in `outputs-local/v1a/` and are read in place, new runs go to `outputs-local/v2/`.
