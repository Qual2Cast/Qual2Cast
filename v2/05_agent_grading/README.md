# 05_agent_grading: Agent grading

The agent loop grades each target-comp pair 0/1/2 with citations from both companies, in up to four steps (search either saved website, search the web, or answer). With facet scores it also rates 11 facets 0-100; `agent_ranking.py` turns those into coverage C, observed similarity S and evidence points E (Barbara's scoring standard) and the final order.

**Status (2026-11-19): ported.** Scripts, tests and `agent_grading.ipynb` are in place; the notebook reproduces the saved v1 numbers (5/5 checks pass).

## Current setting (`v2/current.toml`)

- `run` = `outputs-local/v1a/05_agent_grading/ranking_45targets_sonnet`
- `model` = `sonnet`
- `prompt_version` = `2026-11-05b`
- `facet_scores` = `True`

## Outputs (existing runs in `outputs-local/v1a/05_agent_grading/`, read in place; new runs in `outputs-local/v2/05_agent_grading/`)

- `ranking_45targets_sonnet/` (6 files)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/agent_loop.py` (script): Fiona/Riya agent loop
- `v1/scripts/agent_loop_eval.py` (script)
- `v1/scripts/agent_ranking.py` (script): Fiona/Barbara C/S/E ranking
- `v1/scripts/direct_peer_pairs.py` (script): prepare/assemble; standardize (11-18) -> 10_final_holdout/scripts/final_check.py direct-peers, without the X-learner inputs
- `v1/scripts/tests/test_agent_loop.py` (test)
- `v1/scripts/tests/test_agent_ranking.py` (test)
- `v1/scripts/tests/test_direct_peer_pairs.py` (test)
- `v1/scripts/policy/barbara_scoring_policy_v3.json` (policy)
- `v1/scripts/policy/README.md` (policy)
- `v1/AGENT_LOOP.md` (doc)

Commit authors of these files (git): Fiona Shao, Riya Mhatre, EFL-YL.

## Notes

- Current run `ranking_45targets_sonnet` (Sonnet agent, prompt `2026-11-05b`, facet scores): the 293 dev pairs.
  The saved ranking and its evaluation rebuild exactly.
- **Reviewed (Michael, 2026-11-19), see [GRADING_REVIEW.md](GRADING_REVIEW.md):** the 0/1/2 grade stays as
  the any-peer filter (grade ≥ 1: precision 91.8%, recall 83.2%, kappa 0.63 vs Barbara; the selector keeps
  32.7% of her peers and acts as a direct-peer filter). C/S/E and `final_rank` / `e_rank` are not used
  downstream until the ranking is reworked; no 0/25/50/75/100 facet scale in new work.
- `scripts/filter_comparison.py`: agent grade vs selector vs B3 against Barbara and Matthew (rubric v2), Cohen's
  kappa between raters, peer rate by B3 rank. Saved runs only, no model calls.
- Valuation of these lists moved to `08_valuation/scripts/agent_valuation.py` (this component never reads EV/EBITDA).
- `direct_peer_pairs.py` prepares and assembles Barbara's direct-peer pairs; its 11-18 `standardize` step is now
  `10_final_holdout/scripts/final_check.py direct-peers`.
- Default candidates are the current B3 list (v1 defaulted to the Haiku B3 run), so WEN has 7 comps, not 6.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `agent_grading.ipynb` ported; v1 numbers reproduced.
- 2026-11-19: review of the grade and Barbara's C/S/E ranking (`GRADING_REVIEW.md`); new
  `filter_comparison.py` + test; run `filter_comparison/20261119T033731Z`.
- 2026-11-19: section 3.4 from `peer_evaluation.ipynb` 7.2 (outcome counts, fit dimensions) on the agent's verdicts,
  0-2 rubric, plus the dimensions by Barbara's grade.
- 2026-11-24: copied into full v2 (v2 became a working copy of v1a); existing outputs stay in `outputs-local/v1a/` and are read in place, new runs go to `outputs-local/v2/`.
