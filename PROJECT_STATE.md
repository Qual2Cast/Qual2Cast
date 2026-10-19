# Project state

Short, current summary. Detailed history is in conversations/; methodology
for the scrape is in website_scrape/README.md.

_Last updated: 2026-10-18 (matching notebook: method 1 now ends in a
valuation, comps = cosine z ≥ 2 and z ≥ 2.5; embedding baseline added:
see conversations/2026-10-18-matching-baseline.md; repository reorganized: see
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

## Status

| part | status | where |
|---|---|---|
| Website scrape | **Done for all 560** (3 pages per site, re-parsed 2026-10-18): 532 ok, 15 thin, 4 investor_site, 4 robots_disallowed, 4 http_403, 1 blocked. 26 tests. | website_scrape/, outputs-local/website_scrape/ |
| Matching method | **Method 1 (section 3) complete end to end:** `matching/matching_methods.ipynb` loads the snapshot (non-financial columns) and the scraped page text, then runs the embedding method from Riya's branch (all-mpnet-base-v2, 200-word chunks averaged, cosine similarity; no name masking or template removal). 535 matchable, 25 excluded. Comps: no fixed number; companies whose cosine is ≥ 2 or ≥ 2.5 SDs above the target's mean cosine (z levels, both run through the whole section). Comps per company: z ≥ 2 median 17, range 2-41; z ≥ 2.5 median 7, range 0-23 (13 companies get none). PCTY: 14 / 6. Check: top-5 neighbours share SIC4 24% vs 1.7% by chance (14× lift). Valuation (EV/EBITDA loaded only there): PCTY actual 22.13; comps median 13.54 (−39%) at z ≥ 2, 14.87 (−33%) at z ≥ 2.5, vs 10.84 (−51%) with no matching. Section 4 (method 2) is an empty placeholder. `matching/README.md` explains the method and what changed from Riya's notebook. Pushed to branch `michael/wip`, not merged to main. | matching/, outputs-local/matching/ |
| Results across targets, sanity check, definitions / limitations | **Not started.** Valuation so far is PCTY only. | n/a |
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

1. Method 2 (notebook section 4), compared with method 1 on the same
   targets and the same valuation step.
2. Run the valuation for every matchable company, not only PCTY, so the
   methods are compared on valuation error across the whole list.
3. Results obtained, and how they are checked (peer labels for more targets
   than PCTY, written before running them).
4. Human sanity check of the top comps against their source pages.
5. Definitions and limitations.
6. Supply websites for the 4 IR-only companies (or accept "unknown").
