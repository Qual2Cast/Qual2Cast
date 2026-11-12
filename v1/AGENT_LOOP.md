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

## Ranking: facet scores and evidence-supported points

With `--facet-scores` the final answer also scores 11 general facets 0/25/50/75/100 (100 same offering or role,
75 close substitute, 50 adjacent, 25 weak overlap, 0 evidenced mismatch). Each score needs a cited line from both
companies, otherwise the facet is null (unknown). Unknown is never 0. The 0/1/2 grade is unchanged.

`agent_ranking.py` turns the facet scores into Barbara's three numbers (her Similarity Scoring Standard) and ranks
comps within each target by E:

- coverage C = sum of the weights of the facets scored on both sides
- observed similarity S = 100 x sum(w x s) / C
- evidence-supported points E = 100 x sum(w x s), bounds [E, E + 100(1 - C)]

Weights are Barbara's proposed v3.1 general-facet points mapped to our facets and renormalized: products 10,
services 5, customer segment 9 (her customer type 5 + segment 4), end markets 7, business model 9, revenue model 9,
value chain 5, geography 3, specialization 3, distribution 3, regulatory 3 (66 points = 100%).

With `--industry-facets` the agent also scores the target's SIC2 industry facets from Barbara's policy (a read-only
copy in `v1/scripts/policy/`): base fields only, diagnostic fields dropped, and conditional subtype fields (for
example `[pharma]` in SIC 28) only when listed for that target in an `--activate` CSV. Industry points are
renormalized within the block, then general 60% and industry 40% (her default). Each pair saves the weights it used
in `facet_weights`, and the ranking reports general and industry coverage separately.

```bash
uv run python v1/scripts/agent_loop.py --candidates <B3 candidates> --tickers AKBA,SVV,MD --facet-scores \
    --out outputs-local/v1/agent_loop/ranking_test_sonnet
uv run python v1/scripts/agent_ranking.py --run outputs-local/v1/agent_loop/ranking_test_sonnet \
    --labels outputs-local/v1/integration/barbara_matches/reviewed_pairs.csv
```

The evaluation compares three orderings within each target against Barbara's labels (peer = 1 or 2): by E, by B3
similarity, and by the agent's 0/1/2 grade. It reports peers in the top k (3, 6, 7), pairwise accuracy (share of
peer/non-peer pairs where the peer is ranked higher) and rank correlation with the label.

## Open questions

- Web snippets are copied out by the search model, so a snippet can be paraphrased. The search answer is saved
  for each lookup (`search_stdout.json`) to check.
- A web result can name competitors outright ("competes with ADP"). That is public information a buyer would
  also find for a private target, but it makes the grade easier than the website alone.
- Which threshold to use for "high enough scores" (B3's list, `--top-k`, or `--min-similarity`) is open.
