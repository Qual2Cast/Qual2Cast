# Agent loop ranking: per-facet scores and C / S / E — 2026-11-13

Fiona (task d of the V1 plan, with Barbara). Branch `fiona/agent-ranking`, from `main` at `55e810c0`. Not merged.

## Request

V1 plan, task d: "Expand on the agent loop with ranking mechanisms, i.e. weighted evidence coverage, observed facet
similarity". Use Barbara's scoring standard (her repo `Barbara069/Private-Company-Public-Comparables-Search`,
`code/Similarity_Scoring_Standard.md` and `code/scoring_policy_v3.json`) to rank each target's comps, and check
the ranking against her 293 labelled pairs. Her repo was only read; nothing was changed there.

## What was built

| file | what it does |
|---|---|
| `v1/scripts/agent_loop.py` | `--facet-scores`: the final answer also scores 11 general facets 0/25/50/75/100 (100 same, 75 close substitute, 50 adjacent, 25 weak overlap, 0 evidenced mismatch). Each score cites a shown line from both companies, else null (unknown, never 0). `--industry-facets` adds the target's SIC2 fields from Barbara's policy; `--activate` lists conditional subtype fields per target. Without the flags the prompt and answer are unchanged. |
| `v1/scripts/agent_ranking.py` | Barbara's formula: coverage C, observed similarity S = 100 x sum(w x s) / C, evidence points E = 100 x sum(w x s) = S x C, bounds. Weights: her v3.1 general points mapped to our facets (66 points = 100%). `final_rank` = agent grade, then S, then B3; `e_rank` = by E. `--labels` compares orderings with reviewer labels; `--valuation` gives the EV/EBITDA error of each ordering's top k. |
| `v1/scripts/policy/barbara_scoring_policy_v3.json` | Unchanged read-only copy of her policy (commit `da9ba66`). |
| `v1/scripts/tests/test_agent_ranking.py` | 10 offline tests (formula, weights, schema, citations, industry fields, final order). |
| `v1/AGENT_LOOP.md` | New "Ranking" section with results and what was tried. |

## Runs (Sonnet through the Claude Code CLI, prompt `2026-11-05b`, candidates = Eric's "Sonnet + Fiona sub-sector" B3 list)

| run (`outputs-local/v1/agent_loop/`) | targets | pairs |
|---|---|---|
| `ranking_test_sonnet/` | AKBA, SVV, MD | 26 |
| `ranking_test_industry_sonnet/` | same, with industry facets | 26 |
| `ranking_20targets_sonnet/` | 20 | 140 |
| `ranking_45targets_sonnet/` | all 45 labelled targets | 293 |

All 293 pairs finished (`ok`). The 5-hour usage limit was hit twice; finished pairs were reused when resuming.

## Results (Barbara's labels, 45 targets, 293 pairs, 202 peers)

| Ordering | Peer/non-peer pairs in the right order | Peers in top 3 | Peers in top 6 |
|---|---:|---:|---:|
| Final: agent grade, then S | 88.6% | 82.2% | 75.2% |
| Agent grade, then B3 | 87.9% | 83.0% | 75.2% |
| S only | 86.7% | 82.2% | 75.2% |
| B3 similarity only | 81.6% | 80.0% | 73.1% |
| E only (Barbara's ordering) | 78.7% | 80.0% | 73.5% |

- Bootstrap over targets: final vs E +9.7 points (95% interval +3.5 to +16.8); final vs B3 +7.0 (-0.7 to +15.0);
  final vs agent-then-B3 +0.6 (-5.3 to +5.9).
- E ranks worse than B3: mean coverage is 59.5%, and E counts a facet the website does not mention as no
  similarity. Most of the gain over B3 comes from the agent's 0/1/2 grade; S helps a little within a grade.
- Industry facets (3 targets): industry coverage 34%, no gain. Unknown-as-50 and blends with B3: no gain. Weights
  fitted to the labels: not kept (too few pairs).

## Decisions

- The ordering is chosen on labels only. EV/EBITDA is not used to choose (that would tune the method on the answer
  key); `--valuation` is kept for one final check on holdout targets. On 20 training targets the valuation
  intervals overlapped for every ordering (about 20% to 50% median error), so it could not separate them anyway.
- Barbara's labels are one person's judgment, not ground truth (her point), so small differences are not conclusive.
- No 10-K-derived benchmark (for example text-based industry classifications or proxy peer groups) is used.

## Tests and data version

`python -m pytest v1/scripts/tests/test_agent_loop.py v1/scripts/tests/test_agent_ranking.py -q`: 20 pass. Data:
universe `20261025T060358Z`, split `20261027T204930Z`, Sonnet facets `facets_sonnet/`, labels
`outputs-local/v1/integration/barbara_matches/reviewed_pairs.csv` (same as Barbara's filled sheet).

## Next

1. Get a second reviewer's labels on the same pairs (Matthew's column is empty) and compare on pairs both agree on.
2. Try ways to raise coverage: targeted lookups for unknown high-weight facets, or listwise ranking per target.
3. Run the final order on the holdout targets once, with the valuation check.
