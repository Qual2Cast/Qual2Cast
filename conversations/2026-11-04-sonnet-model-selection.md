# Stronger model for the fills and the comp selectors (plan item 3) — 2026-11-04

Matthew (with Richard: model selection). Everything here ran through the Claude Code CLI under a student
subscription, not the team's API key: a new `claude-cli` backend in `v1/scripts/cli_models.py` that
`fill_facets.py`, `fill_sector_facets.py`, `fill_industry_facets.py`, `cosine_then_llm.py` and `direct_llm.py`
can use (`--backend claude-cli`; default model Claude Sonnet 5.5). It runs `claude -p` with no MCP servers, no
settings files and no CLAUDE.md, so a call carries about 1k tokens of overhead instead of 300k, and the
instructions go in the system prompt so the CLI's prompt cache covers them across calls. Nothing saved by the
Haiku/API runs was touched: every new run writes to its own folder.

## What was run

| run | folder (`outputs-local/v1/`) | companies / targets | model |
|---|---|---|---|
| General facets (the twelve of `facets.py`, prompt `2026-10-25k`) | `facets_sonnet/` | 533 / 533 | Sonnet 5.5 |
| Sector facets (Fiona's FF49 sector groups, sub-sector, `2026-10-27b`), training and holdout | `sector_facets_sonnet/` | 533 / 533 | Sonnet 5.5 |
| Industry facets (Barbara's SIC2 dictionary, new, `2026-11-04a`) | `industry_facets_sonnet/` | 533 / 533 | Sonnet 5.5 |
| B3 lists screened by the LLM (`cosine_then_llm.py --b3`, prompt `2026-11-04a`) | `cosine_then_llm/20261104T074915Z_2026-11-04a_{sonnet,haiku}/` | 373 targets, 2,396 pairs each | both |
| Direct picks from the pool (`direct_llm.py`, prompt `2026-11-04a`) | `direct_llm/20261027T204930Z_2026-11-04a_{sonnet,haiku}/` | 373 targets each | both |
| The comparison | `model_selection/<time>/` | | `model_selection_eval.py` |

The Haiku selector runs are new too: the saved Haiku picks (`judge/`, `suggest/`) used the old prompt with company
size and the z ≥ 2 lists, so they cannot be compared with a Sonnet run directly. Haiku and Sonnet here saw the
same facets (the Haiku fills in `facets/`), the same B3 lists and the same prompt, so the only difference is the model.

## Barbara's industry facets (new)

`v1/scripts/industry_facets.py` reads `v1/scripts/reference/sic2_industry_facet_dictionary.md` (her markdown, 83
SIC2 groups, 4 to 19 facets each; every one of the universe's 43 SIC2 codes is covered) and gives each company the
facets of its own SIC2, as free text in the style of her examples. `fill_industry_facets.py` fills them from the
saved website pages, cited line by line, like the sector facets; memory fills gaps and is flagged. Result on 533
companies, 5,331 facet rows: 48% stated (89% of those cited to the pages, 11% from memory), 29% not applicable,
23% unknown. The not-applicable share is high because a SIC2 group's list covers several sub-industries (SIC 73
has staffing, advertising and software facets side by side). Many of her facets ask for figures (acreage, unit
counts, retention rates); the prompt asks for words instead, as the other fills do, so those come back as a
qualitative description or unknown. Table: `industry_facets_sonnet/tables/industry_facets_long.csv`.

## Results

**Facet fills, Sonnet vs Haiku, same prompt (533 companies).** Both fill almost everything (status differs on
0 to 9% of companies per facet). The free-text values share about a third of their words. Where a facet has a
leading category, the two models agree 73 to 92% of the time: customer segment 92%, regulatory exposure 87%,
distribution channels 83%, revenue model 83%, geography 82%, value-chain position 80%, specialization 79%,
company size 73%. The disagreements are not noise: for AMC Networks Haiku wrote B2C (viewers), Sonnet B2B
(distributors and advertisers); for Accel Entertainment Haiku B2C (players), Sonnet B2B (host venues). The
golden set is the only way to say which is right; that is item 5.

**B3 lists screened by the LLM (373 targets, 2,396 pairs).** The two models give the same verdict on 92% of pairs.
Sonnet keeps 21% of the pairs, Haiku 17%. Haiku leaves 161 of 373 targets with no comp at all, Sonnet 106.
Against the round 1 labels both are strict: for Paylocity both keep exactly the three direct comps (ADP, Paycom,
Asure) and drop the seven adjacent ones; for Wendy's Haiku keeps nothing and Sonnet keeps Texas Roadhouse only.
So the screen is not where a stronger model helps; the B3 list itself already has precision 1.0 on the labeled
comps, and screening only removes the adjacent ones.

**Direct picks from the pool (373 targets).** Sonnet lists 4.9 comps per target on average, Haiku 2.8; where both
pick, the lists overlap 58% (Jaccard). On the round 1 labels Sonnet finds all four good Wendy's comps (Haiku one)
and six of Paylocity's seven (Haiku four), with every listed comp labeled 1 or 2 and NDCG@10 of 0.90 and 0.94.
This is the one place the stronger model clearly changes the output: it recalls the adjacent comps that Haiku
leaves out, with no labeled non-comp added. Two targets is too few to settle it; round 2's 67 pairs are the next
check.

| method, on the round 1 labels | WEN good listed / 4 | PCTY good listed / 7 | non-comps listed |
|---|---|---|---|
| B3 list (no LLM) | 4 | 7 | 0 |
| screen, Haiku | 0 | 3 | 0 |
| screen, Sonnet | 1 | 3 | 0 |
| direct, Haiku | 1 | 4 | 0 |
| direct, Sonnet | 4 | 6 | 0 |

## Cost and checks

About 3,000 CLI calls: three fills (533 each, plus a few retries), four selector runs (373 each). Output tokens:
general facets ~1.0M, sector ~0.44M, industry ~0.52M, screens 0.15M (Sonnet) and 0.38M (Haiku), direct 0.11M
(Sonnet) and 0.46M (Haiku). Input was mostly cache reads (the direct pool is ~98k tokens, read from cache after
the first call). Failures: 3 general-facet calls and 1 industry-facet call hit the CLI's structured-output
retry limit and succeeded on a rerun (Crane needed `--effort high`; it kept writing quotation marks inside a
value). Tests: 209 pass.

## Not done

- The selectors ran on the **Haiku** facets. Nothing yet points B3 or the selectors at `facets_sonnet/`,
  `sector_facets_sonnet/` or the industry facets, so the effect of the better fills on comps and valuation is
  untested. That needs `facet_weighting`/`candidates` to read another facets folder and a new
  `method1_candidates.py` run.
- Barbara's facets are filled but not used by any similarity method (free text, no category lists).
- Company size (F9) is still filled, because it is in the fill prompt's schema; the similarity code drops it.

## Next

1. Richard and Matthew: re-run B3 and the valuation with the Sonnet fills (and with the industry facets as
   extra text facets) against the Haiku baseline; same split, same targets.
2. Score the Sonnet and Haiku direct picks on the round 2 labels when the sheet is filled.
3. If the direct picks hold up, decide whether `direct_llm` with Sonnet becomes a route in the holdout test.
