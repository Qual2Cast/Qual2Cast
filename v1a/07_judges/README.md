# 07_judges: LLM judges

LLM-as-judge evaluators (GPT family). They grade pairs for evaluation only and never choose comps: the evidence-only judge, the 0-2 exact judge on the round-1 pairs, and the label-blind GPT-6.1 Sol judge on the 293 pairs.

**Status (2026-11-19): ported.** Scripts, tests and `judges.ipynb` are in place; the notebook reproduces the saved v1 numbers (5/5 checks pass).

## Current setting (`v1a/current.toml`)

- `model` = `gpt-5.6-terra`
- `backend` = `codex`

## Outputs (`outputs-local/v1a/07_judges/`)

- `gpt61sol_293/` (6 files)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/integration_judge_eval.py` (script): now judge_293_eval.py; verdicts rebuilt from the saved answers
- `v1/scripts/judge_gold_eval.py` (script)
- `v1/scripts/peer_evaluation.py` (script): evidence-only judge; explicit pairs (Kethan)
- `v1/scripts/requirements-judge.txt` (other)
- `v1/notebooks/peer_evaluation.ipynb` (notebook)
- `v1/PEER_EVALUATION.md` (doc)

Not from v1 on main:

- `v1/scripts/peer_evaluation.py` from `kethan/wip`

Commit authors of these files (git): mcschlatt, EFL-YL.

## Notes

- Judges stay in the GPT family (decision 2026-11-18): Claude selects, GPT judges. New judge runs use GPT-Terra
  (`gpt-5.6-terra`, `current.toml [judges]`, decision 2026-11-19); the saved 293-pair run is GPT-6.1 Sol.
- `judge_293_eval.py` (v1 `integration_judge_eval.py`) rebuilds the 11-10 verdicts from the 293 saved answers in the
  v1 record and reproduces the evaluation exactly (exact 0.785, peer/non-peer 0.843).
- The judge-filter valuation tables moved to `08_valuation/gpt61sol_293_selection/`.
- Sol's cited grades of the v0 holdout routes (`graded_peer_selection.py`) stay in v1; results in
  `10_final_holdout/v1_holdout_runs/graded_peer_selection/`.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `judges.ipynb` ported; v1 numbers reproduced.
