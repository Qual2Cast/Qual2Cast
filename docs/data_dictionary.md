# Data dictionary

## Focused pipeline (2026-11-12)

Entry point `pipeline/pipeline.ipynb`; details in `pipeline/README.md`.
Outputs are local under `outputs-local/pipeline/<provider>/<model and effort
variant>/<run>/`. `run.json` records role settings, snapshot/split/website
hashes and code hashes. `inputs/financials.csv` is never a matching input.

- `shared/facets-<model>/`: new general profiles, per-call raw outputs and
  `tables/facets.csv`, using the existing v1 schema. Historical raw-call
  directory name `codex_runs` is retained even for Claude.
- `shared/profile_coverage.csv`: every eligible company, `has_profile`;
  unavailable profiles are explicit, not silently replaced by old fills.
- `shared/b3_candidates/`: full ranking and one-way top-10 candidates;
  `selected`, `mutual`, `topped_up` record B3's shortlist.
- `pipelines/<route>/peers.csv`: final selected pairs for `b3` or
  `b3_llm_filter`. `b3_llm_filter/decisions.csv` retains all B3 pairs with
  binary `score`, `reason`, `filter_complete`, nullable `accepted`.
  Incomplete answers are not counted as rejections.
- `shared/judge-<model>/`: existing 0–3 rubric, frozen saved-page evidence,
  prompts, per-call JSON/logs, checked citations, grades and human-review
  template. Every B3 pair is graded, including filtered-out pairs; no
  sampling. `max_pairs` and historical z-gated preparation are not used.
- `pipelines/<route>/pair_results.csv`: selected peers joined to the same
  shared judge grades. The judge does not control peer selection.
- `pipelines/<route>/valuation.csv`: every requested target, estimated
  median peer multiple (`estimate`), `comps`, observed `actual_multiple`
  joined afterward, `absolute_pct_error` and `selection_status` (complete,
  missing_profile, filter_incomplete). No estimate stays null, not zero.
- `comparison/summary.csv`: requested/covered targets, valuation error,
  selected/graded pairs, mean score and pass rate on numeric grades only,
  insufficient evidence, not-run and failed counts.
- `comparison/filter_audit.csv`: all accepted/rejected/incomplete filter
  decisions alongside judge reasons and grades. `common_target_errors.csv`
  and `common_target_summary.json` compare errors only where both methods
  have estimates. `overview.png` shows coverage and numeric judge grades.

No automatic human-accuracy claim or new holdout claim follows from these
metrics. Historical rubric outputs are not pooled into this run.

## v1 saved-result error analysis

`v1/notebooks/error_analysis.ipynb` / `v1/scripts/error_analysis.py` write a new
`outputs-local/v1/error_analysis/<timestamp>/` per execution; no inference.
`manifest.json` pins source paths/hashes, configuration, missing inputs and code
commit. See `v1/ERROR_ANALYSIS.md` for the input scope and all output files.

- `facet_audit.csv`: historical `labeled_text`, `human_label`, note/evidence URL,
  current Haiku/Sonnet text, and `exact_*_text` (case/whitespace normalized only).
  A label must not be transferred to different current text.
- `facet_priorities.csv`: historical problem counts/rates over checkable labels,
  exact-current denominators and problems; size marked excluded from B3.
- `profile_differences.csv`: current model text/status/category differences;
  full category sets ignore ordering. Disagreement does not mean inaccuracy.
- `pair_comparison.csv`, `method_metrics.csv`: saved list membership/reasons,
  human-majority grades, labeled precision/coverage and known-peer retention.
  Unlabeled pairs remain unknown. Metrics refer to returned top 10.
- `judge_comparison.csv`, `judge_metrics.csv`: evaluator grades and human
  agreement on valid numeric overlap, plus lookup counts; no pooled rubrics.
- `case_queue.csv`: observed flags and prioritization, not causal error labels.
  `cases/*.json` links each case to both models' facet values, original human
  labels, selectors/judges and saved website evidence. JSON references are
  available to an optional manual evaluator, whose diagnoses stay hypotheses.
- `report.md` / `facet_review.md`: computed summary and all historical problem
  claims with notes and current comparisons; manual agent instructions separate.

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
