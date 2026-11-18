# Barbara's direct-peer pairs: facets and agent loop on 90 pairs — 2026-11-17

Fiona, at Kethan's request (his run instructions `barbara_new_peer_pairs_teammate_prompt.md`). Branch
`fiona/direct-peer-pairs`, from `main` at `50ef8e53`.

## Request

Barbara picked two candidate direct peers for each of the 45 labelled targets (90 pairs) and marked each Yes or
No. Fill facets for the comps outside the universe, run the agent loop on all 90 pairs, write the 66
development pairs into a copy of `sonnet_label.xlsx` and the 24 holdout pairs into `holdout_completion/`, and add
Barbara's labels only after the model has run (Yes = 2, No = blank, never 0).

## What was built

| file | what it does |
|---|---|
| `v1/scripts/direct_peer_pairs.py` | `prepare`: checks the counts, copies the source CSV with its sha256, writes the manifest (90 pairs, every source column, ids, split, B3 status), the external companies (`EXT_<ticker>`), the label-free pair list and `freeze.json`. `assemble`: the 359-row workbook copy and the 24-row holdout output, labels applied there. |
| `v1/scripts/fill_facets.py` | `--companies CSV`: fill companies outside the universe (same prompt and passes) into a separate `--out`. |
| `v1/scripts/agent_loop.py` | `--pairs file --pair-file`, `--extra-companies`, `--extra-facets`: run exactly the listed pairs, including comps outside the universe. |
| `v1/scripts/tests/test_direct_peer_pairs.py` | counts and the pair-file input. |

## Run (`outputs-local/v1/direct_peers_barbara/20261117_run/`)

- Source sha256 `97daaa2c5760546e40881c8866d05e90907ff6d332bfe7bd6f0f60a57bcf7473`. Counts as in the instructions:
  90 pairs, 45 targets, 88 comps, 62 Yes / 28 No; 66 external pairs (64 comps, 43 Yes), 24 holdout (19 Yes).
  All targets are training companies; all 24 "universe (holdout)" comps are in the holdout sample.
- Facets for the 64 external comps: Sonnet (`claude-sonnet-5-5`, CLI), facet prompt `2026-10-25k`. 64/64 ok, all
  one business, identities checked by hand (SPX = Spirax Group, London; not SPX Technologies).
- Agent loop: Sonnet, prompt `2026-11-05b`, web search Sonnet, `--facet-scores`. 90/90 ok (27 pairs were
  rerun after the 5-hour usage limit; `agent/verdicts_partial_63ok.csv` is the first pass).
- Outputs: `outputs-local/v1/integration/sources/sonnet_label_direct_peers_20261118T014938Z.xlsx` (293 original
  rows unchanged + 66) and `outputs-local/v1/holdout_completion/direct_peers_20261118T014938Z/` (24 rows,
  manifest, summary). Barbara scores: 62 x 2, 28 blank, 0 zeros. Source columns kept as `src_*`.

## Deviations

- No saved website pages for the external comps: company websites are blocked from the environment this ran
  in, so they were not scraped. Their facets come from the first pass only (name and website); the page
  gap-fill and the split check had nothing to run on. In the agent loop their only citable evidence is web search.
- No B3 score for any of the 90 pairs: external comps are outside the universe and the holdout comps are
  outside B3's comp pool (training companies only). `b3_status` says which.

## Results (Yes rows only; No rows are not labelled negatives)

Barbara Yes = 62: agent 2 on 47, 1 on 12, insufficient evidence on 3 (APG-EME, DORM-MPAA, and holdout APG-LMB).
Development 34/43 graded 2; holdout 13/19 graded 2. Holdout is for the final check only; nothing was tuned on it.
