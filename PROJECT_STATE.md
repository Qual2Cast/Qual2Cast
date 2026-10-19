# Project state

Short, current summary. Detailed history is in conversations/; methodology
for the scrape is in website_scrape/README.md.

_Last updated: 2026-10-18 (growth-signals foundation: see
conversations/growth-signals.md)_

## Data

- Required snapshot: `company_list_v3` (see data_manifest.json). 560 US
  public companies, used as stand-ins for private targets.
- v3 = raw list + SIC zero-padding fix + website fixes (IR hosts → main
  domain; Smith Douglas website supplied). Built by src/prepare_company_list.py.
  BrightView Holdings was SIC 700 → 0700, Agricultural Services (it had been
  grouped with hotels under SIC 70). Only row affected. See docs/data_issues.md.
- Data maintainer distributes snapshots outside GitHub: _TBD (name)_.

## Agreed methodology

- Aziz's rule for similarity inputs: company inputs are name + website only
  (methods must work for private companies). No 10-Ks or stock data. The
  separate growth-signals collector may use official company IR News/Press
  pages as dated first-party event sources, but not as similarity features.
- All collection is programmatic; nothing written by hand. Unknown
  information is marked unknown, and every extracted fact cites a source URL.
- Financial fields are never matching inputs; they live in separate columns
  or tables keyed by IQ_COMPANY_ID.
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
| Growth signals | **Five-company pilot complete.** News/Press/Careers/Jobs and dated article collection, high-precision audited rule extraction, event schema, and cutoff-safe feature aggregation. Dynamic-page, constrained official-IR, and declared WordPress latest-post fallbacks now cover all five: 24 articles, 23 dated, 7 reviewed candidate events (4 temporary, 3 durable). | growth_signals/ |
| Matching method | **Not started** in the main pipeline. The first pass (embeddings of page text, PCTY NDCG@20 0.90) is in scraps as a baseline. | n/a |
| Results, sanity check, valuation, definitions / limitations | **Not started.** | n/a |
| Earlier attempts | Set aside 2026-10-18, kept runnable for reference: Codex profiles (219/560 done), first matching pass, first collection script. | scraps/, outputs-local/scraps/ |

## Open questions

- Websites needed for 4 companies whose main domain redirects to an
  investor-relations site (docs/data_issues.md #3): Avista, Black Hills,
  Simpson Manufacturing, IAC.
- Who is the data maintainer, and where are snapshots stored (university /
  sponsor storage)?
- Should company size (headcount) ever be a matching feature? Currently
  filtered out of all text.
- Date of the multiples in the company list (needed to judge how stale the
  website text is relative to them).
- Whether financial columns may stay in files like Riya's
  `company_list_for_interns.csv`: decide when training the forecasting model.
  For now financials are kept, but always in separate columns or tables from
  matching inputs.

## Next steps

1. Define historical cutoff dates and future 3-year revenue-growth outcomes;
   keep outcomes isolated from event extraction.
2. Evaluate whether temporary launches add predictive value and whether
   durable launches need finer platform/service/capability subtypes.
3. Design the matching method on `outputs-local/website_scrape/page_text/`.
4. Results obtained, and how they are checked (peer labels for more targets
   than PCTY, written before running them; `scraps/comps_first_pass/` results
   as the baseline to beat).
5. Human sanity check of the top comps against their source pages.
6. Valuation calculation from the comps' multiples (financial fields enter
   only here, never in matching).
7. Definitions and limitations.
8. Supply websites for the 4 IR-only companies (or accept "unknown").
