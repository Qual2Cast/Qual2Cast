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

## Open questions

- Web snippets are copied out by the search model, so a snippet can be paraphrased. The search answer is saved
  for each lookup (`search_stdout.json`) to check.
- A web result can name competitors outright ("competes with ADP"). That is public information a buyer would
  also find for a private target, but it makes the grade easier than the website alone.
- Which threshold to use for "high enough scores" (B3's list, `--top-k`, or `--min-similarity`) is open.
