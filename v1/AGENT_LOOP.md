# Agent loop: checking high-scoring target-comp pairs

Code: [`scripts/agent_loop.py`](scripts/agent_loop.py) (the loop) and
[`scripts/agent_loop_eval.py`](scripts/agent_loop_eval.py) (the scoring). Tests:
`scripts/tests/test_agent_loop.py`.

## What it does

B3 gives each target a list of comps by similarity. The agent loop takes the pairs that scored high enough
and has an LLM check each one before it counts as a comp. Unlike the one-shot graders, the model can look
things up first:

1. **Start.** The model sees both companies' facet summaries (context only, not citable) and the first 450
   words of each saved website, every line labelled (`T:P1.3` target, `C:P2.1` comp).
2. **Look up, or answer.** Each step it picks one action:
   - `search_site`: search the rest of one company's saved website (BM25); adds the 5 best new lines.
   - `web_search`: search the web about one company; adds up to 5 result snippets (`T:S1.1`, `C:S2.1`).
   - `final`: the grade.
3. **At most 4 steps**; the last one must be `final`.
4. **The grade** is the team's rubric: 2 direct competitor, 1 adjacent, 0 not a peer (with one of the six
   reasons), or null when the evidence can't settle it. A grade must cite at least one shown line from each
   company. A wrong citation is sent back once; a second wrong answer is recorded as `invalid`.

## Rules it keeps

- **The target is treated as private.** For the target's web searches, investor-relations, SEC and
  market-data sources are dropped (the same rule as `verification/evidence.py`). The comp is public, so its
  results are kept.
- **No financial figures.** Lines with figures are removed (`evidence.clean_line`), and the model never sees
  a multiple, revenue, similarity score or rank.
- **No memory.** The model may only use the lines shown; facet summaries are not citable.
- **Everything is saved:** every prompt, answer and search result, per pair, under
  `outputs-local/v1/agent_loop/<run>/pairs/<target>__<comp>/`.

## How to run

The model runs through the Claude Code CLI under your own subscription (`cli_models.py`), so no API key is
needed. Web search also goes through the CLI (its WebSearch tool), so it works without a search key.

```text
# free: write the first prompt of every pair, no calls
uv run python v1/scripts/agent_loop.py --pairs gold --dry-run

# the 36 round-1 golden-set pairs (PCTY, WEN), to compare with the reviewers
uv run python v1/scripts/agent_loop.py --pairs gold --model sonnet --workers 4

# B3's own list for some targets, or for all 373 training targets
uv run python v1/scripts/agent_loop.py --tickers CSL,AFG,AZZ,BBCP,BUKS --workers 4
uv run python v1/scripts/agent_loop.py --workers 4

# score a run
uv run python v1/scripts/agent_loop_eval.py --run outputs-local/v1/agent_loop/<run>
```

Options: `--min-similarity 0.45` or `--top-k 5` keep only the higher-scoring pairs; `--search api` uses the
Serper/Tavily/Brave key in `.env` instead; `--search none` turns web search off (saved websites only);
`--backend codex` uses Codex CLI. A run folder can be passed again with `--out` to resume: finished pairs are
not called again.

## What the evaluation reports

`agent_loop_eval.py` writes `<run>/eval/summary.md` and its tables:

1. **Agreement with the reviewers' majority grade** (round 1; round 2 is added automatically once
   `round2_filled.csv` exists), next to the one-shot Sol grader on the same pairs.
2. **Agreement with Sol's holdout grades** where pairs overlap (alternative check only).
3. **The filter on B3's lists:** how many reviewer-labelled peers and non-peers B3 keeps as is, with the
   agent's 1s and 2s, and with its 2s only.
4. **Valuation** (20+ targets only): median absolute % error of the similarity-weighted multiple for the same
   three lists, with bootstrap intervals.

## Results (2026-11-05, prompt `2026-11-05a`)

Sonnet throughout: Sonnet grades, Sonnet's facet fills as context, Sonnet for web search.

| run | folder (`outputs-local/v1/agent_loop/`) | pairs | result |
|---|---|---|---|
| Round-1 golden set (PCTY, WEN) | `gold/` | 36 (32 with a majority grade) | **31/32** exact with the reviewers' majority, 32/32 peer vs not-peer, 0 non-peers graded as peers (one-shot Sol on the same pairs: 26/32, 29/32, 3) |
| Round-2 targets (CSL, AFG, AZZ, BBCP, BUKS), B3's lists | `round2_targets/` | 35 | 3 twos, 21 ones, 11 zeros; to be scored once `round2_filled.csv` exists |

- The one round-1 miss is WEN-TXRH: the reviewers gave 2, the agent 1 (quick-service vs casual dining).
- On B3's PCTY/WEN lists the agent keeps all 11 labelled peers and drops none; keeping only its 2s leaves 3 of the 4
  direct comps.
- For BUKS it gave the casino-only comps (CNTY, MCRI, RRR, ACEL) 1, as the multi-business rule says.
- **It rarely looks things up:** 1 of 36 round-1 pairs and 2 of 35 round-2 pairs (BUKS-RRR, CSL-SSD, a web search
  each). With the facet summaries and 450 words of each website, Sonnet was sure enough to answer at once.
- About 6 to 7 seconds per pair.

Caveats: two labelled targets is a small test; Sonnet and Sol differ in model and in what they see (Sol had 900
website words and no facet summary), so the gap is not only the loop; and a well-known company may be graded partly
from the model's memory despite the instruction.

## Haiku vs Sonnet facets

Before the current runs, the agent loop was run twice with Sonnet grading: once reading Haiku's facet fills and once
reading Sonnet's. On round 1 (PCTY, WEN) there was no difference: both matched the reviewers' majority on 31/32. On
the 35 B3 pairs for the round 2 targets, 7 grades changed, mostly for AFG. With Haiku's facets the agent gave some comps
credit for AFG's annuity business, which was sold years ago. With Sonnet's facets, BRO and SNFC.A dropped to 0, and
BBCP's IESC and GVA also went from 1 to 0. Those runs are kept in `gold_sonnet/`, `round2_targets_sonnet/` (Haiku
facets) and `gold_sonnet_facets/`, `round2_targets_sonnet_facets/` (Sonnet facets).

## Ranking: facet scores, C / S / E and the final order

With `--facet-scores` the final answer also scores 11 general facets 0/25/50/75/100 (100 same offering or role,
75 close substitute, 50 adjacent, 25 weak overlap, 0 evidenced mismatch). Each score needs a cited line from both
companies, otherwise the facet is null (unknown). Unknown is never 0. The 0/1/2 grade is unchanged.

`agent_ranking.py` turns the facet scores into Barbara's three numbers (her Similarity Scoring Standard):

- coverage C = sum of the weights of the facets scored on both sides
- observed similarity S = 100 x sum(w x s) / C
- evidence-supported points E = 100 x sum(w x s) = S x C, bounds [E, E + 100(1 - C)]

Weights are Barbara's proposed v3.1 general-facet points mapped to our facets and renormalized: products 10,
services 5, customer segment 9 (her customer type 5 + segment 4), end markets 7, business model 9, revenue model 9,
value chain 5, geography 3, specialization 3, distribution 3, regulatory 3 (66 points = 100%).

**Final order (`final_rank`):** the agent's 0/1/2 grade first, then S, then B3 similarity. `e_rank` (by E, Barbara's
ordering) is kept for comparison.

```bash
uv run python v1/scripts/agent_loop.py --candidates <B3 candidates> --tickers <45 tickers> --facet-scores \
    --workers 4 --out outputs-local/v1/agent_loop/ranking_45targets_sonnet
uv run python v1/scripts/agent_ranking.py --run outputs-local/v1/agent_loop/ranking_45targets_sonnet \
    --labels outputs-local/v1/integration/barbara_matches/reviewed_pairs.csv
```

### Results (2026-11-13, 45 targets, 293 pairs, Barbara's labels)

Candidates are Eric's "Sonnet + Fiona sub-sector" B3 list; Sonnet grades and scores, general facets only. 202 of
the 293 pairs are peers (label 1 or 2). Pairwise accuracy = share of (peer, non-peer) pairs of the same target in the
right order.

| Ordering | Pairwise accuracy | Peers in top 3 | Peers in top 6 |
|---|---:|---:|---:|
| Final: agent grade, then S | 88.6% | 82.2% | 75.2% |
| Agent grade, then B3 | 87.9% | 83.0% | 75.2% |
| S only | 86.7% | 82.2% | 75.2% |
| B3 similarity only | 81.6% | 80.0% | 73.1% |
| E only (Barbara's ordering) | 78.7% | 80.0% | 73.5% |

Bootstrap over targets (2,000 draws), pairwise accuracy: final minus E +9.7 points (95% interval +3.5 to +16.8);
final minus B3 +7.0 (-0.7 to +15.0); final minus agent-then-B3 +0.6 (-5.3 to +5.9). So the agent's grade gives most
of the gain over B3, S adds little on top, and E ranks worse than B3: mean coverage is only 59.5%, and E counts a
facet the website does not mention as no similarity.

The ordering was chosen on these labels only. One reviewer's labels are not ground truth (Barbara's own point), so
read small differences with care. The EV/EBITDA check (`--valuation`) is not used to choose an ordering; it is
kept for one final check on holdout targets.

### Tried and not kept

- Industry facets (`--industry-facets`, Barbara's SIC2 modules, general 60% / industry 40%), 3 targets / 26 pairs:
  pairwise accuracy by E 77% vs 74% general-only, peers in top 6 down from 61% to 56%. Industry coverage was 34%:
  fields like payer mix, R&D intensity or manufacturing model are rarely on the first pages of a website, and the
  agent did not look them up. Code kept: base fields only, conditional subtype fields only when listed for that
  target in an `--activate` CSV (`outputs-local/v1/agent_loop/ranking_test_activate.csv`).
- Unknown facets counted as 50, and z-score blends of E or S with B3: no better than the final order.
- Facet weights fitted to the labels (leave-one-target-out ridge): 88.8% on 20 targets, not kept (140 pairs, likely
  overfit).

Runs: `ranking_test_sonnet` (3 targets), `ranking_test_industry_sonnet` (3 targets, industry facets),
`ranking_20targets_sonnet`, `ranking_45targets_sonnet` (all 45; includes the 20).

## Open questions

- Web snippets are copied out by the search model, so a snippet can be paraphrased. The search answer is saved
  for each lookup (`search_stdout.json`) to check.
- A web result can name competitors outright ("competes with ADP"). That is public information a buyer would
  also find for a private target, but it makes the grade easier than the website alone.
- Which threshold to use for "high enough scores" (B3's list, `--top-k`, or `--min-similarity`) is open.
