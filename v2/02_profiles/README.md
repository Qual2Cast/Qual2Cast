# 02_profiles (v2): tags and economic traits

v2 adds one thing to v1a's profiles: yes/no/unknown questions per company (ten in round 1, four more in round 2),
filled by Sonnet 5.5 through the
Claude Code CLI (subscription, no API key). The 12 general facets, Fiona's sector facets and Barbara's industry
facets are in this component too (copied from v1a, unchanged) and are still what B3 uses; see the v1a sections
below.

**Status (2026-11-24):** both rounds done. Round 1 (T1-T4, E1-E6) and round 2 (E7-E10, section below)
each passed the 30-company double fill and are filled for all 533 companies; tables pinned in `v2/current.toml`
(`[traits]`, `[traits_r2]`).

## Round 1: the ten questions (`scripts/traits.py`, prompt `2026-11-24a`)

| id | column | kind | question |
|---|---|---|---|
| T1 | `offers_products` | tag | Are products one of its main offerings? (software counts) |
| T2 | `offers_services` | tag | Are services, meaning work done for customers, one of its main offerings? |
| T3 | `sells_to_consumers` | tag | Are individual people or households among its main buyers? (chooser and receiver, not payer) |
| T4 | `sells_to_organizations` | tag | Are businesses, institutions or government among its main buyers? |
| E1 | `recurring_revenue` | trait | Does most revenue come from customers who keep buying on an ongoing basis? |
| E2 | `cyclical_demand` | trait | Can its customers easily postpone or cut these purchases in a downturn? |
| E3 | `big_ticket` | trait | Is a typical sale large and infrequent for the buyer? |
| E4 | `people_delivered` | trait | Is what customers pay for mainly the time and skill of its own staff? |
| E5 | `large_customers` | trait | Are its main customers large enterprises or government agencies? |
| E6 | `asset_heavy` | trait | Does it need heavy, ongoing investment in plants, fleets, networks or properties? |

The full wording, with examples of yes and no and the rule for hard cases, is in `traits.py` and is exactly what
the model reads. Tags say what kind of company it is and are used only to cut the analysis; traits are tested as
explanations of what makes a peer (see `v2/EVAL_METHOD.md`, "Traits and tags").

## Rules

- Every company answers every question; "unknown" only when it can't be told, never a mismatch.
- A company with several businesses answers for the larger part.
- Input: name, website and up to 1,500 words of the saved website text (figures removed by the scrape). The model
  may use what it knows; a company it doesn't know is answered from the page text only, and with no page text it is
  all unknown.
- Keep rule (before the full fill): the 30-company test is filled twice; a question whose answer flips for more
  than 20% of companies, or is unknown for more than 20%, is reworded or dropped (`scripts/trait_stability.py`).

## Run

```bash
uv run python v2/02_profiles/scripts/fill_traits.py --sample 30 --out outputs-local/v2/02_profiles/traits_test/run1
uv run python v2/02_profiles/scripts/fill_traits.py --sample 30 --out outputs-local/v2/02_profiles/traits_test/run2
uv run python v2/02_profiles/scripts/trait_stability.py outputs-local/v2/02_profiles/traits_test/run1 outputs-local/v2/02_profiles/traits_test/run2
uv run python v2/02_profiles/scripts/fill_traits.py --workers 4      # all 533 -> outputs-local/v2/02_profiles/traits_new/
uv run pytest v2/02_profiles/tests -q
```

Test sample: the v0 showcase targets that are in the training split (7 of the 10: BGS, BRO, DXPE, PCTY, ROAD,
SLGN, WEN) plus 23 random training companies (seed 2026), saved as `sample.csv` in each run folder.

## Test result (2026-11-24)

Both fills 30/30 ok. Every question passes the keep rule: at most 2 flips in 30 (asset-heavy), at most 1 unknown
(large customers). Watch points: `sells_to_organizations` is yes for all 30, so only `sells_to_consumers` is a
useful slice; `big_ticket` (2-3 of 30 yes) and `people_delivered` (4 of 30) are rare; two-sided marketplaces
(Cars.com) flip on the consumer question.

## Full fill (2026-11-24, current: `v2/current.toml [traits] table`)

All 533 companies ok (two calls hit the CLI's 3-turn limit and were refilled; Sonnet says it knows 525 of 533).
About 27 minutes on 4 workers; 5.8M of 7.5M input tokens came from the prompt cache; 785k output tokens.

| question | yes | no | unknown |
|---|---:|---:|---:|
| offers products | 67.6% | 32.4% | 0 |
| offers services | 62.0% | 38.0% | 0 |
| sells to consumers | 45.4% | 54.6% | 0 |
| sells to organizations | 91.1% | 8.9% | 0 |
| recurring revenue | 74.6% | 25.4% | 0 |
| cyclical demand | 44.6% | 55.4% | 0 |
| big-ticket | 11.9% | 88.1% | 0 |
| people-delivered | 12.8% | 87.2% | 0 |
| large customers | 42.4% | 55.6% | 2.1% |
| asset-heavy | 39.2% | 60.8% | 0 |

On the 30 test companies the full fill agrees with test run 1 on 90-100% of answers per question. 14 reasons are
flagged `figure_in_reason` (scale figures such as square feet, listing counts or "66% of the Fortune 100", no
revenue or profit); only the yes/no answers are used downstream, so they are kept as flagged.

## Round 2: four more traits (prompt `2026-11-24b`, current: `v2/current.toml [traits_r2] table`)

Round 1's cyclical demand split true direct peers as often as non-peers, and the model's reasons showed the two facts
that decided it: new builds vs maintenance of an installed base, and who ultimately pays. Round 2 asks those directly
and adds two PE value drivers, in a separate call (`fill_traits.py --round 2`, questions in `traits.ROUND_2`; round
1's questions, prompt and table are unchanged):

| id | column | question |
|---|---|---|
| E7 | `maintenance_led` | Does most revenue come from repairing, servicing, maintaining or replacing an installed base, not new builds or first purchases? |
| E8 | `publicly_funded` | Is most revenue ultimately paid by government, even when a contractor, insurer or provider sits in between? |
| E9 | `serial_acquirer` | Does the company grow mainly by buying other companies (a roll-up or platform)? |
| E10 | `mission_critical` | Would customers face real cost, risk or disruption switching away from it? |

30-company double fill (same sample as round 1): all four kept. Flips: maintenance-led 1/29, publicly funded 0/29,
serial acquirer 0/30, mission-critical 2/30; unknown at most 1/30. Yes rates in the test: 3-7%, 10-13%, 10% and 47%.

Full fill (533/533 ok, 16 minutes on 5 workers): maintenance-led 4.1% yes, publicly funded 5.4%, serial acquirer
6.0%, mission-critical 42.2%; unknown at most 0.4%. Five reasons flagged `figure_in_reason` (scale figures, no
revenue or profit), kept as flagged.

```bash
uv run python v2/02_profiles/scripts/fill_traits.py --round 2 --sample 30 --out outputs-local/v2/02_profiles/traits_r2_test/run1
uv run python v2/02_profiles/scripts/fill_traits.py --round 2 --workers 5        # all 533 -> traits_r2/
```

## Outputs (`outputs-local/v2/02_profiles/`)

- `traits_test/run1/`, `traits_test/run2/`: the two test fills (per-call prompts and raw answers in `runs/`, one
  JSON per company in `profiles/`, `tables/traits.csv`); `traits_test/stability/`: the comparison.
- `traits_new/`: the full fill (533 companies), `tables/traits.csv` is current.
- `traits_r2_test/run1|run2/`, `traits_r2_test/stability/`: the round-2 test fills and comparison.
- `traits_r2/`: the round-2 full fill (533 companies), `tables/traits.csv` is current for round 2.

---

## From v1a: 02_profiles: Company profiles (facets)

Each company's business-model profile. The 12 general facets are filled by Sonnet 5.5 from the company name and model knowledge, then gap-filled from the saved website pages (prompt `2026-10-25k`). Also Fiona's sector facets (her sub-sector feeds B3), Barbara's SIC2 industry facets (not in B3), the multi-business split, and facet evidence checks.

**Status (2026-11-19): ported.** Scripts, tests and `profiles.ipynb` are in place; the notebook reproduces the saved v1 numbers (7/7 checks pass).

## Current setting (`v2/current.toml`)

- `general` = `outputs-local/v1a/02_profiles/facets_sonnet/tables/facets.csv`
- `general_prompt_version` = `2026-10-25k`
- `sector` = `outputs-local/v1a/02_profiles/sector_facets_sonnet/tables/sector_facets.csv`
- `industry` = `outputs-local/v1a/02_profiles/industry_facets_sonnet/tables/industry_facets_long.csv`
- `corrected_general` = `outputs-local/v1a/02_profiles/facets_sonnet_corrected.csv`
- `website_pages` = `outputs-local/website_scrape/page_text`

## Outputs (existing runs in `outputs-local/v1a/02_profiles/`, read in place; new runs in `outputs-local/v2/02_profiles/`)

- `facets_sonnet/` (4 files)
- `facets_sonnet_corrected.csv` (1 file)
- `industry_facets_sonnet/` (1 file)
- `sector_facets_sonnet/` (1 file)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/business_split.py` (script): multi-business split
- `v1/scripts/business_split_refinement.py` (script): split refinement
- `v1/scripts/facets.py` (script): 12-facet schema, prompt 2026-10-25k
- `v1/scripts/fill_facets.py` (script): Sonnet fills (Matthew/Richard); --companies (Fiona); Codex wrapper (Kethan)
- `v1/scripts/fill_industry_facets.py` (script): Barbara SIC2 industry facets
- `v1/scripts/fill_sector_facets.py` (script): Fiona sector facets
- `v1/scripts/industry_facets.py` (script): Barbara SIC2 industry facets
- `v1/scripts/sector_facets.py` (script): Fiona sector facets
- `v1/scripts/source_split_benchmark.py` (script): split source check
- `v1/scripts/tests/test_business_split_refinement.py` (test)
- `v1/scripts/tests/test_sector_submodels.py` (test)
- `v1/scripts/verification/evidence.py` (verification)
- `v1/scripts/verification/gold_from_labels.py` (verification)
- `v1/scripts/verification/pages_only_fill.py` (verification)
- `v1/scripts/verification/README.md` (verification)
- `v1/scripts/verification/retrieve.py` (verification)
- `v1/scripts/verification/tests/test_gold_from_labels.py` (verification)
- `v1/scripts/verification/tests/test_retrieve.py` (verification)
- `v1/scripts/verification/tests/test_verification.py` (verification)
- `v1/scripts/verification/verify_with_evidence.py` (verification)
- `v1/scripts/reference/sic2_industry_facet_dictionary.md` (reference)
- `v1/notebooks/business_split_refinement_eval.ipynb` (notebook)
- `v1/notebooks/business_structure_eval.ipynb` (notebook)
- `v1/notebooks/facet_fill_runs.ipynb` (notebook)

Not from v1 on main:

- `v1/scripts/fill_facets.py` from `kethan/wip`

Commit authors of these files (git): mcschlatt, Fiona Shao, zynskibud.

## Notes

- 98.5% of the general facet values come from model knowledge; 10 companies have website-sourced values, because
  the website pass only runs for facets the first pass left unknown. The scraped pages are cited mainly by the
  agent loop (05) and Fiona's sector facets.
- `facets_sonnet_corrected.csv` is the Sonnet table with Yiming's divestiture corrections (42 companies, 116 values,
  flagged `divestiture_corrected`; built by v1's `integration_sources.py`). Kept, not the default.
- New fill runs write to `facets_new/`, `sector_facets_new/` and `industry_facets_new/`, never over the current
  tables. The business-split inputs (pilot snapshot, source corrections) and the Haiku fills stay in the v1 record.
- `split_peer_eval.py` and `source_scope_sensitivity.py` read EV/EBITDA, so they move to `08_valuation`.
- Run: `uv run pytest v2/02_profiles/tests v2/02_profiles/scripts/verification/tests -q`; open `profiles.ipynb`.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `profiles.ipynb` ported; v1 numbers reproduced.
- 2026-11-19: v1 `comp_universe_and_facets.ipynb` tables ported on the Sonnet fills (facet definitions; 3.6 coverage,
  flags, categories, review list, example profiles). Stay in v1: `facet_fill_runs.ipynb` (Haiku/Codex fill history),
  `business_structure_eval.ipynb` and `business_split_refinement_eval.ipynb` (v0-route and holdout tests of split
  context, not adopted 10-28).
- 2026-11-24: component added to v2 (Michael's grill session): tags and traits schema, fill, stability check, 8
  tests. First test attempt failed on a shared temporary file written by parallel workers; fixed by writing the
  system prompt once before the workers start.
- 2026-11-24: copied into full v2 (v2 became a working copy of v1a); existing outputs stay in `outputs-local/v1a/` and are read in place, new runs go to `outputs-local/v2/`.
- 2026-11-24: round 2 (E7-E10, prompt `2026-11-24b`): `traits.ROUND_2`, `fill_traits.py --round 2`, stability check reads either
  round; round 1's prompt checked byte-identical (system prompt hash `b87aed18`). 30-company double fill: all four kept.
