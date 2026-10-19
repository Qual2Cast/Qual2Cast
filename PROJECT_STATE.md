# Project state

Short, current summary. Detailed history is in conversations/; methodology
for the scrape is in website_scrape/README.md.

_Last updated: 2026-10-19 (matching: three methods and an evaluation notebook, committed to
`michael/wip`; methodology in matching/README.md; history in
conversations/2026-10-19-method2-mutual-knn.md. Earlier: conversations/2026-10-18-matching-baseline.md,
conversations/2026-10-18-repo-cleanup.md)_

## Data

- Required snapshot: `company_list_v3` (see data_manifest.json). 560 US
  public companies, used as stand-ins for private targets.
- v3 = raw list + SIC zero-padding fix + website fixes (IR hosts → main
  domain; Smith Douglas website supplied). Built by src/prepare_company_list.py.
  BrightView Holdings was SIC 700 → 0700, Agricultural Services (it had been
  grouped with hotels under SIC 70). Only row affected. See docs/data_issues.md.
- Snapshot CSVs are CRLF and stored byte-for-byte (.gitattributes `-text`),
  so the manifest checksums match on every OS. Before 2026-10-18 (commit
  3a50a32) git stored them as LF and non-Windows checkouts failed the
  checksum check; anyone who cloned earlier should pull, then run
  `git checkout -- data-local/snapshots`.
- Data maintainer distributes snapshots outside GitHub: _TBD (name)_.

## Agreed methodology

- Aziz's rule: company inputs are name + website only (methods must work for
  private companies). No 10-Ks, investor pages, or stock data.
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

## Matching methodology (working approach)

On branch `michael/wip`, not yet reviewed by the team. Full write-up:
matching/README.md, "Methodology".

- Every public company takes a turn as the private target: comps are found
  among the other 534 from website text only, the estimate is the comps'
  median EV/EBITDA, and the actual multiple is the answer key.
- Benchmark: no matching (the median of all other companies). Measures:
  median absolute % error and Spearman(estimate, actual); differences from
  method 1 by paired bootstrap; methods also compared at equal comp counts
  (3-10) and on ten chosen targets.
- Settings are fixed before scoring, on the shape of the comp sets, never
  tuned on valuation error. SIC codes are a check only.

## Status

| part | status | where |
|---|---|---|
| Website scrape | **Done for all 560** (3 pages per site, re-parsed 2026-10-18): 532 ok, 15 thin, 4 investor_site, 4 robots_disallowed, 4 http_403, 1 blocked. 26 tests. | website_scrape/, outputs-local/website_scrape/ |
| Matching method | **Three methods and an evaluation, on branch `michael/wip`.** `matching/matching_methods.ipynb`: website text → `all-mpnet-base-v2` embeddings (535 matchable, 25 excluded) → comps by method 1 (embedding similarity, cosine z ≥ 2 / 2.5), method 2 (mutual kNN, k = 10 / 20; then UMAP + HDBSCAN clusters), or method 3 (agglomerative tree, complete / ward linkage) → estimate = comps' median EV/EBITDA (financials read only there). Each method is shown on PCTY and then values every company from its own comps. `matching/matching_evaluation.ipynb` (runs the methods notebook first): every method at 3-10 comps, and ten targets (PCTY, BV, ROAD, FIX, BRO, ADUS, LOPE, ODFL, WING, DXPE). **Results:** median absolute error ≈ 35% for every method, the same as no matching (34.6%); method 1 ranks companies best (Spearman 0.31 vs 0.21-0.24 for the others and 0.22-0.24 for SIC peer groups); at equal comp counts no method beats method 1; targets with clear peers get them (ROAD, BRO, LOPE, ADUS), finer distinctions fail (truckload types, contractors vs HVAC makers, distributors), BV gets comps though it has no real peer, and right peers still miss by 29-43%. Latest runs `20261019T080322Z` (methods) and `20261019T080416Z` (evaluation). `umap-learn` and `hdbscan` 0.8.44 are installed in the kernel's Python 3.14. | matching/, outputs-local/matching/ |
| Results across targets, sanity check, definitions / limitations | **Started:** valuation error for all 535 matchable companies, every method at 3-10 comps, and ten targets (`matching/matching_evaluation.ipynb`). Human check of comps against source pages, and definitions / limitations, not started. | matching/ |
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

1. Picking peers doesn't look like the bottleneck: no comp rule beats method 1,
   even at equal comp counts, and right peers still give large errors. Next:
   change the estimate (shrink the comps' median toward the all-company
   median; weight comps by similarity) and try a "no good match" rule from
   absolute similarity (BV). Judge with `versus()` (bootstrap vs method 1)
   and the ten targets, settings fixed before scoring.
2. Results obtained, and how they are checked (peer labels for more targets
   than PCTY, written before running them).
3. Human sanity check of the top comps against their source pages.
4. Definitions and limitations.
5. Supply websites for the 4 IR-only companies (or accept "unknown").
