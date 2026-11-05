# Agent loop for checking high-scoring target-comp pairs — 2026-11-05

Fiona (similarity checks, with Riya). Branch `fiona/agent-loop`, from `main` at `a84a58f5` (PR #26). Not merged; no PR yet.

## Request

Michael's plan for the week: "agent loop: check target-comp pairs with high enough scores". B3 ranks comps by facet-text
similarity, so a pair can score high on shared words without being a real peer. The one-shot graders
(`graded_peer_selection.py`, `peer_evaluation.py`) read about 900 words of each saved website and must grade from that.
The agent loop lets the model look things up before it grades a pair.

## What was built

| file | what it does |
|---|---|
| `v1/scripts/agent_loop.py` | The loop. Takes pairs from a B3 candidates run (`--pairs selected`, default: B3's own list; `--top-k`, `--min-similarity` to narrow it) or the 36 round-1 golden-set pairs (`--pairs gold`). Each pair: facet summaries (context, not citable) and the first 450 words of each saved website; then up to 4 steps, each one action: `search_site` (BM25 over the rest of a company's saved pages, `retrieve.py`), `web_search` (Claude Code CLI WebSearch, or `--search api` for the Serper/Tavily/Brave key in `.env`), or `final`. The grade is the team's 0–2 rubric with reasons for a 0, citing at least one shown line from each company; a bad citation is sent back once, then `invalid`. Saves every prompt, answer and search result per pair; finished pairs are not called again (resume with `--out`). `--dry-run` writes the first prompts without calls. |
| `v1/scripts/agent_loop_eval.py` | Scores a run: agreement with the reviewers' majority grade (round 1; round 2 is picked up once `round2_filled.csv` exists) next to the one-shot Sol grades on the same pairs; agreement with Sol's holdout grades where pairs overlap; how many labelled peers and non-peers B3's list keeps as is, with the agent's 1s and 2s, and with its 2s only; valuation (median APE, bootstrap) when the run has 20+ targets. Writes `<run>/eval/summary.md`. |
| `v1/scripts/tests/test_agent_loop.py` | 10 offline tests (fake model, no network). |
| `v1/AGENT_LOOP.md` | Guide: what it does, rules, how to run, results, open questions. |

Rules kept: the target is treated as private (its web results drop investor-relations, SEC and market-data sources,
`evidence.blocked`); lines with figures are removed (`evidence.clean_line`); no multiple, revenue, similarity or rank
reaches the model; facet summaries are not citable.

## Runs (Claude Sonnet through the Claude Code CLI, prompt `2026-11-05a`, web search on)

| run | folder (`outputs-local/v1/agent_loop/`) | pairs |
|---|---|---|
| Round-1 golden set (PCTY, WEN) | `gold_sonnet/` | 36 |
| Round-2 targets (CSL, AFG, AZZ, BBCP, BUKS), B3's lists | `round2_targets_sonnet/` | 35 |

All 71 pairs finished (`ok`), about 8 seconds a pair.

## Results

- **Round 1, 32 pairs with a majority grade:** the agent agrees exactly on 31/32 and on peer vs not-peer on 32/32,
  with no labelled non-peer graded as a peer. The one-shot Sol grades on the same pairs agree on 26/32 (29/32 peer vs
  not-peer; 3 non-peers graded 1). The one miss: WEN-TXRH, reviewers 2, agent 1 (quick-service vs casual dining).
- **On B3's PCTY/WEN lists** the agent keeps all 11 labelled peers; keeping only its 2s leaves 3 of the 4 direct comps.
- **Round 2:** 1 two, 24 ones, 10 zeros; BUKS's casino-only comps get at most 1, as the multi-business rule says.
  Not scored yet: the reviewers' sheet is unfilled.
- **The model rarely looks things up:** 1 of 36 round-1 pairs and 2 of 35 round-2 pairs (RRR, SSD; the web
  searches returned results).

## Caveats

- Two labelled targets, both simple one-business cases: the round-1 agreement is likely optimistic.
- Sonnet and Sol differ in model and in input (Sol: 900 website words, no facet summary), so the gap is not only the loop.
- Well-known companies may be graded partly from the model's memory despite the instruction.
- Web snippets are copied out by the search model and can be paraphrased; the raw search answer is saved per lookup.

## Tests and data version

`python -m pytest v1/scripts/tests/test_agent_loop.py -q`: 10 pass. Data: `company_list_v3`, B3 run
`candidates_method1/20261104T074915Z`, split `20261027T204930Z`. Facet context: Haiku fills `2026-10-25k` in the first runs, Sonnet fills (`facets_sonnet/`) in the `*_facets` runs and by default (see the update below).

## Next

1. Rerun `agent_loop_eval.py` on `round2_targets_sonnet_facets/` once `round2_filled.csv` is committed.
2. Decide the threshold for "high enough" (B3's list, top k, or a similarity cut) and whether to keep 1s or only 2s.
3. Run on all 373 training targets (about 2,400 pairs) to get the valuation check.
4. Try nudging the model to look things up more often, and compare with web search off (`--search none`).

## Update (same day): Sonnet's facet fills as context

Yifan's check of the fills (batch 1, 15 gold-set companies): Sonnet 81% correct, Haiku 68%; Haiku still describes
businesses CSL, AFG and AZZ sold years ago. The agent loop showed Haiku's fills as context, and for AFG its reasons
repeated the sold annuity business (9 mentions). Both runs were repeated with `--facets
outputs-local/v1/facets_sonnet/tables/facets.csv`, now the default in `agent_loop.py`:

- Round 1 (`gold_sonnet_facets/`): still 31/32 with the reviewers' majority; 2 grades changed (PCTY-THRY and
  PCTY-DHX, 0 to 1), both on pairs with no majority.
- Round 2 targets (`round2_targets_sonnet_facets/`): 7 of 35 grades changed, 5 for AFG (ORI and ASIC 1 to 2, BOW 2
  to 1, BRO and SNFC.A 1 to 0) and 2 for BBCP (IESC and GVA 1 to 0); "annuity" mentions 9 to 1.
- The first runs stay as they were, for comparison. B3's comp lists are still built from Haiku's fills.
- The agent should still check for divestitures itself when a facet is wrong (Riya is working on the prompt).
