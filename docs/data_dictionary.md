# Data dictionary

## Peer-evaluation outputs

`v0/notebooks/peer_evaluation.ipynb` grades the accepted outputs of cosine → LLM,
using saved website passages and the agreed 0–3 rubric. Results stay local under
`outputs-local/comps/peer_evaluation/<run>/`.

- `inputs/`: file hashes, target list, upstream candidate decisions, sampled
  accepted pairs, exact passage text/URLs/capture dates, rubric, schema and prompts.
- `runs/`, `judgments/`: raw CLI attempts and checked pair answers/errors.
- `tables/pair_judgments.csv`: `judge_score` (0–3 or null), `verdict`,
  offering/customer/business-model fit, reason, missing evidence, checked citations,
  provider/model and execution status. Upstream score/reason/rank/similarity are
  joined only for the report; they are not given to the judge.
- `tables/target_summary.csv`: upstream completeness, accepted/sampled/graded/
  passing pairs and explicit insufficient-evidence, failed and not-run counts.
- `tables/summary.csv`: pass rate among numeric grades, grading coverage among
  sampled pairs, execution counts and the passing threshold (default 3).
- `tables/human_review_template.csv`: blank reviewer/human-score/reason fields
  alongside model outputs. Annotate a separate copy; reruns archive replacements.
- `history/`: earlier versions of replaced outputs.
- `analysis/`: notebook section 7's derived coverage metrics, outcome counts,
  fit-dimension counts, target attention list, illustrative pair examples,
  answer errors, two PNG charts and a generated findings note. Source judgment
  tables remain unchanged; percentages distinguish all selected pairs from
  valid numeric grades. These are automated judge diagnostics, not accuracy.

`insufficient_evidence` is a null grade with successful execution; it is distinct
from `not_run`, CLI failure and `invalid_answer`. All requested training targets
remain in target reports, including those with no accepted peer. This is
automated business-fit evaluation, not independent labels or valuation accuracy.
The matching notebook exports `peer_evaluation_input.json` and a frozen
`selection_judgments_for_evaluation.csv` beside its candidate run for handoff.

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
