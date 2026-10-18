# Data dictionary

## Where data lives

| location | in Git? | contents |
|---|---|---|
| `data_manifest.json` | yes | which snapshot the code needs, with checksums |
| `data-local/snapshots/` | yes | read-only input snapshots |
| `outputs-local/website_scrape/page_text/`, `scrape_log.csv` | yes | current website text, one JSON per company |
| rest of `outputs-local/` | no | other outputs (raw HTML, page_text history, logs, profiles, tables) |

The snapshots come with the repo at the paths listed in data_manifest.json.
Code checks the checksum and stops if it doesn't match. If you only have the raw list, `python src/prepare_company_list.py`
rebuilds the required snapshot (v3) from it.

## Company list (`company_list_v3_websites_fixed.csv`, the required snapshot)

One row per company (560). All values are text.

| column | meaning | matching input? |
|---|---|---|
| `IQ_COMPANY_ID` | Capital IQ company ID; the key for joining every table | key |
| `target_company_name` | legal name | identifier only |
| `target_ciq_ticker`, `target_ciq_exchange` | stock ticker and exchange | identifier only (reveals the company is public) |
| `target_ciq_website` | website, the only input to collection | input to scraping |
| `target_country_name`, `target_country_iso3` | country (all USA) | no |
| `target_sic4_code` | 4-digit SIC, zero-padded (e.g. `0700`) | optional |
| `target_sic3_code`, `target_sic2_code` | first 3 / 2 characters of the 4-digit code | optional |
| `target_primary_sic_industry` | SIC industry name | optional |
| `target_revenue`, `target_ebitda` | revenue and EBITDA, $ millions | **no: financial** |
| `target_margin` | EBITDA / revenue | **no: financial** |
| `target_debt_to_revenue` | debt / revenue | **no: financial** |
| `target_ev_to_ebitda` | EV / EBITDA multiple | **no: financial** |

SIC codes can mislead (e.g. CPI Card Group is "Computer Storage Devices" but
is a payments company); website text should drive matching.

## Website scrape outputs (`outputs-local/website_scrape/`)

Written by `website_scrape/scrape_websites.py`; folder names are defined in
its `output_paths()`. Field-by-field contents of the JSON files are in
[website_scrape/README.md](../website_scrape/README.md).

| path | stage | contents |
|---|---|---|
| `raw_html/<IQ_ID>/<time>/<method>/P<n>.html.gz` | raw | pages exactly as downloaded, every method tried |
| `page_text/<IQ_ID>.json` | intermediate | per page: URL, category, method, fetch time, raw text, cleaned text, every removed sentence or phrase with its reason, `block_page` (bot check: raw text kept, no cleaned text) |
| `page_text_history/` | intermediate | earlier versions of `page_text` files (moved here, never overwritten) |
| `scrape_log.csv` | intermediate | one row per company: scrape status (`ok`, `thin_content`, `blocked`, `robots_disallowed`, `investor_site`, `http_<code>`, `error: ...`), method, pages, words, page URLs |
| `logs/` | | run logs |

Reasons in `removed`: `ticker_tag`, `bare_ticker`, `public_phrase`,
`founding_year`, `history_date`, `size_count` (cut inline; `size_count` becomes
"multiple ..."), and `public_company`, `filler`, `financial_figure`,
`finance_talk`, `scale_figure`, `deal_event`, `site_chrome`, `cta_question`,
`too_short_after_cleaning` (whole sentence or block dropped).

Outputs of earlier attempts (Codex profiles, the first matching pass) are in
`outputs-local/scraps/`; see [scraps/README.md](../scraps/README.md).
