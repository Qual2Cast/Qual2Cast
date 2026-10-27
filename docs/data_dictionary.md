# Data dictionary

## Main notebook run outputs

`pipeline.ipynb` runs the current v0 recipe. Each invocation creates a directory
under `outputs-local/pipeline/` (not committed); setting `RUN_DIR` resumes an
existing directory with the same configuration. Computational stages use these
explicit paths instead of a global latest-run lookup.

- `config.json`: backend/model/effort, worker count, sample/target choices,
  split seed/share, embedding model, retrieval settings and optional comparisons.
- `universe/`: all source-company flags, selected universe, separate financials,
  snapshot name/hash and prompt version.
- `facets/`: call prompts, schemas, raw responses/logs, checked profiles and tables,
  using the existing facet format described below. Backend and effort are part
  of the resume identity, alongside model, prompt version and input hash.
- `split/`: assignments, size/sector balance and financial balance diagnostics.
- `candidates/`: complete ranking, candidate pairs with per-facet scores,
  falloff plot and metadata linking the exact universe, split and facet outputs.
- `judge/`: per-target prompts/responses, judgments and the current candidate-pair
  table. Historical judgments outside the current candidate set are not included.
- `suggest/`: optional full-training-pool prompts/responses and direct peer choices.
- `valuation/summary.csv`: conditional errors, scored/attempted counts, coverage
  percentage and percentage of all attempted targets within 25% error.
- `valuation/summary_common.csv`: the same core errors on common LLM-covered cases.
- `valuation/per_target.csv`: every attempted target for every rule, including
  null estimates with `no_comps` status, target outcome, estimate and signed error.
- `history/`: prior versions of stage files replaced on a resumed run.

Codex CLI logs include `events.jsonl`; both CLI backends save `stdout.txt`,
`stderr.txt`, `schema.json`, `prompt.txt` and `response.json` for successful calls.
Failure logs are retained. Failed website gap fills leave unknown facets in
the successful first-pass profile; the pipeline continues with available facets
and retries unfinished gap fills on a later rerun.
CLI outputs are transport records, not independent verification of model facts.

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
`outputs-local/scraps/`; see [pre-v0/scraps/README.md](../pre-v0/scraps/README.md).

## Comp universe and facets (`outputs-local/comps/`)

Written by `v0/` (recipe steps 1-3); full layout in
[v0/README.md](../v0/README.md).

| path | stage | contents |
|---|---|---|
| `universe/<run time>/companies.csv` | processed | every company, non-financial columns, with `us_hq`, `sic2_in_target_list`, `candidate`, `kept_multiple`, `drop_reason` (`below_3`, `above_30`, `missing`) and `in_universe` |
| `universe/<run time>/financials.csv` | processed | the five financial columns, keyed by IQ_COMPANY_ID: **not a matching input**, except revenue, EBITDA and debt for comparing scale in later steps |
| `facets/codex_runs/` | raw | prompt, raw answer, `run.json` (backend, model, tokens) and logs of every model call, Claude (`api_response.json`) or Codex (`events.jsonl`, `stderr.txt`) |
| `facets/profiles/<IQ_ID>.json` | intermediate | checked facets, each with status (`filled`, `not_applicable`, `unknown`), value, category, source ("model knowledge" and/or page URLs), flags and cited page lines (`block` label such as P1.3, page, URL, quote = the line's text, `quote_found`); version g on: no source asked without pages, citations by line label |
| `facets/tables/facets.csv` | processed | one row per business profile (most companies have one; B1 is the largest): `business_id`, `business`, `business_count`, `<facet>_status`, `<facet>` (category facets: `category: detail`, several joined with "; "), `<facet>_category` (category facets: the categories alone), `<facet>_source` ("model knowledge" and/or URLs of the cited pages), `<facet>_flags` for the 12 facets, `with_pages`, `issues` (`no_business`, `too_many_businesses`), `llm_status` (`ok`, `not_run`, or an error) Manual review: `needs_review` (true/false) and `review_reasons` (`described_from_pages_only`, `facet_unknown`, `facet_flagged`, and other issues such as `pages_mention_divestiture`), set by code from what the fill recorded (`fill_facets.review_reasons`); 32 of 533 on 2026-10-25. |
| `facets/tables/facet_quotes.csv` | processed | one row per cited page line, with `business_id` and `block` |
| `fill_test/<folder>/` | experiment | fill test: `knowledge_only` (31 companies, Codex), `with_pages` (12 of them, version e, pages from the start), one folder per later run; same layout as `facets/` |
| `api_checks/<time>/` | experiment | `check_claude_api.py`: `checks.json` (each check's result, tokens, seconds, US dollars) and each call's raw answer; made-up companies only |
