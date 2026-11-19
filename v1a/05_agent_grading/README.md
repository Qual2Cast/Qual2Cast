# 05_agent_grading: Agent grading

The agent loop grades each target-comp pair 0/1/2 with citations from both companies, in up to four steps (search either saved website, search the web, or answer). With facet scores it also rates 11 facets 0-100; `agent_ranking.py` turns those into coverage C, observed similarity S and evidence points E (Barbara's scoring standard) and the final order.

**Status (2026-11-19): ported.** Scripts, tests and `agent_grading.ipynb` are in place; the notebook reproduces the saved v1 numbers (5/5 checks pass).

## Current setting (`v1a/current.toml`)

- `run` = `outputs-local/v1a/05_agent_grading/ranking_45targets_sonnet`
- `model` = `sonnet`
- `prompt_version` = `2026-11-05b`
- `facet_scores` = `True`

## Outputs (`outputs-local/v1a/05_agent_grading/`)

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
- **Pending Michael's review:** Barbara's scoring standard and the C/S/E ranking built on it.
- Valuation of these lists moved to `08_valuation/scripts/agent_valuation.py` (this component never reads EV/EBITDA).
- `direct_peer_pairs.py` prepares and assembles Barbara's direct-peer pairs; its 11-18 `standardize` step is now
  `10_final_holdout/scripts/final_check.py direct-peers`.
- Default candidates are the current B3 list (v1 defaulted to the Haiku B3 run), so WEN has 7 comps, not 6.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `agent_grading.ipynb` ported; v1 numbers reproduced.
