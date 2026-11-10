# Divestiture check on the Sonnet facet fill — results (2026-11-05)

Yiming. Code: `v1/scripts/verification/divestiture_check.py` (check version 2026-11-05b). Run folder: `outputs-local/v1/divestiture_check/20261106T015858Z/`.

## What it does
For each of the 533 companies, the check collects evidence of businesses the company has sold, spun off or closed:
- lines from its saved website pages that mention an exit;
- three targeted web searches (Serper): two by name, one on the company's own site. Investor-relations, SEC and market-data sources are dropped, and so are results that don't name the company.

Claude Sonnet is asked only when an exit line turns up. It names the exits that the facets still describe and gives corrected values for those facets.

Code then decides what is applied. An exit counts only if it is completed, cited, dated, and not supported by company databases alone. A correction is applied only to the facets that a confirmed exit names (core offering, products, services, end markets, specialization).

## Results (533 companies, all with search; 452 model calls)
| outcome | companies |
|---|---|
| no_exit (evidence found, nothing exited) | 240 |
| exit_not_in_facets (exits found; Sonnet's facets already leave them out) | 115 |
| no_signal (no exit line, no model call) | 81 |
| exit_not_confirmed (only announced, undated or database-only) | 52 |
| **corrected** | **42** |
| stale_not_corrected (stale, but no acceptable correction) | 3 |

- **45 companies (about 8%)**: Sonnet's facets still describe a business the company has sold. 42 were corrected automatically, changing 116 facet values: core offering 28, specialization 27, products 24, end markets 22, services 15.
- **Examples:**
  - Carlisle: Interconnect Technologies, completed May 2024
  - Edwards: Critical Care, 2024
  - Etsy: Depop, 2026
  - TDS: UScellular wireless, 2025
  - Fortive: Ralliant spin-off, 2025
  - Timken: Belts, 2026
  - PTC: Kepware and ThingWorx, 2026
  - Coty: Wella
- **Round-2 targets:** CSL corrected. AFG and AZZ: their exits are found, but Sonnet's facets already leave them out.

## Needs review (`review_list.csv`, 44 rows)
- **6 applied corrections to check:** KNTK, FG, EVCM, RAIL, HLTC, BGS.
- **3 stale but not corrected:** GGG, SSD, AMCX. GGG and SSD probably need no change.
- **35 exits held back that the model says the facets still describe:**
  - 29 judged announced only. Some are in fact completed, e.g. XPO's spin-offs, IAC's spin-off of Angi, SunOpta's ingredients sale; the snippets used "announces" wording.
  - 6 undated.

## Files
| file | contents |
|---|---|
| `checks.csv` | one row per company: outcome, evidence lines, exits, facets corrected |
| `exits.csv` | every exit the model named: date, whether the facets still describe it, cited URLs, confirmed or why not |
| `corrections.csv` | each facet: old value, new value, applied or why refused |
| `facets_corrected.csv` | the Sonnet fill with the corrections applied (flag `divestiture_corrected`); B3 reads it with `method1_candidates.py --facets <run>/facets_corrected` |
| `review_list.csv` | the 44 items above, with reasons and URLs |
| `run.json` | settings: check version, model, search queries |

## Next
1. Review the list.
2. Re-search for completion of the 29 announced-only exits, and add an exclusion list for corrections rejected in review.
3. With Eric, rebuild B3 on the Sonnet fill and on the corrected fill, then compare both with `b3_compare.py` against the golden set (round 2 once it is labelled).
