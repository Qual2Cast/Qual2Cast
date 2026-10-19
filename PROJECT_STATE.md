# Project state

Short, current summary. Detailed history is in conversations/; methodology
for the scrape is in website_scrape/README.md.

_Last updated: 2026-10-19 (methodology rules updated after Aziz's reply on
10-Ks and financial inputs; growth-signal rule and collection fixes: see
conversations/2026-10-19-growth-signals-rule-fixes.md)_

## Data

- Required snapshot: `company_list_v3` (see data_manifest.json). 560 US
  public companies, used as stand-ins for private targets.
- v3 = raw list + SIC zero-padding fix + website fixes (IR hosts → main
  domain; Smith Douglas website supplied). Built by src/prepare_company_list.py.
  BrightView Holdings was SIC 700 → 0700, Agricultural Services (it had been
  grouped with hotels under SIC 70). Only row affected. See docs/data_issues.md.
- Data maintainer distributes snapshots outside GitHub: _TBD (name)_.

## Agreed methodology

- Aziz's rule (updated 2026-10-19 after his reply to Haoyan): the **private
  target** side is name + website, plus three figures we may assume are
  known: LTM revenue, LTM EBITDA, and debt. The **public comp** side may use
  10-Ks and other public detail (business description, segments, detailed
  financials, founding year, operating locations, etc.) as similarity
  inputs. Aziz's priority: comps must be in the same business as the target
  (public vet hospitals for a private vet hospital, not human clinics);
  scale similarity is secondary. Investor pages and stock data are still
  not used for the target.
- All collection is programmatic; nothing written by hand. Unknown
  information is marked unknown, and every extracted fact cites a source URL.
- Financial fields: the target's LTM revenue, LTM EBITDA and debt (and
  derived margin, debt/revenue) may be compared with the comps' figures to
  favor similar-scale comps. EV/EBITDA is the valuation output and is never a
  matching input. Financials still live in separate columns or tables keyed
  by IQ_COMPANY_ID, not mixed into text inputs.
- Non-financial information only: the scrape's filters remove financial and
  size figures, tickers and public-company language from the text, and log
  every removal with its reason.
- Raw scrapes, intermediate text, model prompts/responses, and processed
  tables are all kept.
- robots.txt: honored. One that answers 401/403 counts as no restrictions
  (RFC 9309), decided 2026-10-18.

## Status

| part | status | where |
|---|---|---|
| Website scrape | **Done for all 560** (3 pages per site, re-parsed 2026-10-18): 532 ok, 15 thin, 4 investor_site, 4 robots_disallowed, 4 http_403, 1 blocked. 26 tests. | website_scrape/, outputs-local/website_scrape/ |
| Growth signals | **Extraction revised 2026-10-19 (branch growth-signals-recall).** One event per article and type, actor check, schema v2 types, decimal/abbreviation window fix. Fresh blind held-out (10 new companies): 58-61% precision, 43% recall; earlier fresh holdouts ~60% / 32-39%. Rule fixes generalize only slightly; see conversations/2026-10-19-growth-signals-rule-fixes.md. History still covers only months. 211 tests. | growth_signals/ |
| Matching method | **Not started** in the main pipeline. The first pass (embeddings of page text, PCTY NDCG@20 0.90) is in scraps as a baseline. | n/a |
| Results, sanity check, valuation, definitions / limitations | **Not started.** | n/a |
| Earlier attempts | Set aside 2026-10-18, kept runnable for reference: Codex profiles (219/560 done), first matching pass, first collection script. | scraps/, outputs-local/scraps/ |

## Open questions

- Websites needed for 4 companies whose main domain redirects to an
  investor-relations site (docs/data_issues.md #3): Avista, Black Hills,
  Simpson Manufacturing, IAC.
- Who is the data maintainer, and where are snapshots stored (university /
  sponsor storage)?
- Size as a matching feature: answered 2026-10-19 for revenue, EBITDA and
  debt (allowed, secondary to same-business match). Headcount is still
  filtered out of the website text; undecided.
- Date of the multiples in the company list (needed to judge how stale the
  website text is relative to them).
- Whether financial columns may stay in files like Riya's
  `company_list_for_interns.csv`: decide when training the forecasting model.
  For now financials are kept, but always in separate columns or tables from
  matching inputs.

## Next steps

1. Design the matching method on `outputs-local/website_scrape/page_text/`.
2. Results obtained, and how they are checked (peer labels for more targets
   than PCTY, written before running them; `scraps/comps_first_pass/` results
   as the baseline to beat).
3. Human sanity check of the top comps against their source pages.
4. Valuation calculation from the comps' multiples (financial fields enter
   only here, never in matching).
5. Definitions and limitations.
6. Supply websites for the 4 IR-only companies (or accept "unknown").
