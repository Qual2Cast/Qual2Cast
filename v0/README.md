# v0/

Comparable-company selection, following the mentor's recipe for getting comps
(received 2026-10-24). This folder covers the first three steps:

1. **Candidate comps:** a universe covering the list's 2-digit SIC codes, HQ in the US.
2. **Multiple range:** drop firms, as targets and as comps, whose EV/EBITDA is outside 3-30.
3. **Facets:** descriptive attributes, available for every company, that together
   give a reasonable sense of its business model.

Built on these (2026-10-25): the 70/30 training/holdout split and step 4,
candidate comps by embedding similarity. Still to come: profiles for the
scoring model, scoring each comp 0-1, the weighted average of the comps'
EV/EBITDA, and evals.

The folder separates the two kinds of work. The `.py` modules at the top hold
the logic, so it is defined once, tested, and runnable on its own (e.g. the
facet fill). `notebooks/` holds the pipeline work itself: each notebook
imports the modules, runs a step, and shows and saves its results.

| file | what it does |
|---|---|
| `notebooks/comp_universe_and_facets.ipynb` | Steps 1-3: the universe, the dropped firms, the facet definitions, what the model reads, and the filled facets (coverage, source checks, the numbered profile list with fill %, example profiles) |
| `notebooks/comps_and_valuation.ipynb` | Steps 4-7 and the training/holdout split (kernel `qual2cast`): the split with its balance check; steps 4-5, candidates (each target's profile) with fall-off plots; step 6, the LLM's good/bad answers (run by `judge_comps.py`); step 7, LLM good comps against cosine comps and no matching |
| `suggest_comps.py` | Step 4 without embeddings: the LLM picks up to ten comps per target from the whole training pool; writes `suggest/tables/suggestions.csv` |
| `judge_comps.py` | Step 6: Claude Haiku 5.5 marks each z ≥ 2 candidate good (1) or bad (0) with a reason; writes `judge/tables/judgments.csv` |
| `split.py` | The training/holdout split: stratified on company size, fixed seed, showcase targets in training; balance tables |
| `candidates.py` | Step 4: per-facet embeddings (model loaded from the local cache, no Hub request), combined similarity, ranking with z, candidates (top k or z level) |
| `valuation.py` | Step 7 and the evaluation: weighted mean or median of the comps' multiples, the no-matching baseline, error summary |
| `notebooks/facet_fill_runs.ipynb` | Development record for step 3, not a v0 output: every prompt version and what changed, the model choice, the pages-fill-gaps rule, the API checks, every fill run (tokens, time, cost, fill %) and the fill test |
| `check_claude_api.py` | Checks on the Claude API with made-up companies only (~$0.003 a run): the no-digits rule, the schema, caching, guessing from the name; results in `outputs-local/comps/api_checks/<time>/` |
| `universe.py` | Steps 1-2 |
| `facets.py` | The twelve facets, defined once: prompt, answer schema and checks are built from them |
| `fill_facets.py` | Runs the model (Claude Haiku 5.5 by default, or Codex CLI) over the universe and writes the facet tables |
| `tests/` | `python -m pytest tests -q` from this folder |

## Decisions (2026-10-24)

- **The universe is the 560-company list.** Every company is a target in turn;
  its candidate comps are the others. All 560 are US-HQ and the SIC codes are
  the list's own, so step 1 keeps everyone; the functions take any list with
  the same columns, so a wider universe can be passed in later.
- **Built on the cleaned snapshot** `company_list_v3` (SIC zero-padded, IR
  websites replaced; see `src/prepare_company_list.py`). SIC codes stay
  4-character strings.
- **EV/EBITDA 3-30, inclusive**, applied to the list's multiples. The recipe asks
  for year-end-2025 financials; the list's as-of date isn't documented, so this
  is an open question. 27 firms drop (20 above 30, 7 below 3), leaving 533; all
  43 SIC 2-digit codes are still covered.
- **Financials stay separate.** The list is split into company information and
  a financials table as soon as it is read. EV/EBITDA is used only for the
  range; it is never a matching input.
- **Every facet is filled by the LLM from what it knows; nothing is computed.**
  The model gets the company's name and website and fills all twelve facets.
  It is **Claude Haiku 5.5** (`claude-haiku-5-5`) through the Anthropic API,
  chosen 2026-10-24: paid per token from a Console account (about $0.50 for
  all 533 with caching, below), with no usage window, which stopped the
  Codex runs at ~200 calls. Codex CLI (`codex exec` under the student's
  ChatGPT sign-in) is still a backend (`--backend codex`). Every company in
  a run uses the same model. "Unknown" is a last resort: when unsure, the model
  gives its best description and says what is uncertain in the notes; products or services a company doesn't sell
  are "not applicable", which counts as filled. The model never gets
  financial fields and is told not to write financial figures. Every prompt
  is checked in code with the website scrape's financial, size and ticker
  filters: page lines that match are left out, and anything left over is
  recorded (`input_figures`, issue `figures_in_input`; none in the 533
  prompts on 2026-10-24).
- **No guessing** (version i, 2026-10-24). The model describes only
  companies it knows. It first says whether it knows this specific company
  (`knows_company`); a name or web address alone isn't knowing it, and it
  must not guess from the name or from what is typical for similar names.
  In the first pass, "doesn't know" makes every facet unknown in code,
  whatever the model wrote (issue `company_not_known`), and the company goes
  to the pages pass, where the pages are all it may use. Checked with
  `check_claude_api.py`: at version h, made-up companies came back with most
  facets invented from the name; at version i they come back all unknown,
  and Paylocity is still fully filled.
- **The scraped pages only fill gaps** (decided 2026-10-24). Every company
  is first filled from what the model knows, from its name and website
  alone. Only a company left with an unknown facet gets a second call with
  the pages the website scrape already saved (no new scraping), and only
  the unknown facets are taken from that answer. Nothing the model filled
  from its own knowledge is replaced by page text, so a poor scraped
  description can't bias it. The profile records what the second call
  filled (`gap_fill`), and `facets.csv` lists it per business
  (`filled_from_pages`). A rescrape that changes a company's pages makes
  the second pass run again.
- **Business splits are checked against the current website** (third
  pass, 2026-10-24; only with splitting on, see "One profile per company"
  below, so it doesn't run now). The model's knowledge of a company's structure can be
  years out of date (it listed Carlisle's foodservice unit, sold in 2018).
  For a company split into several businesses, the model says per business
  whether the saved pages show it, citing lines, using only the pages. Code
  decides: a business not shown is removed only if another one is shown and
  none of its own name words appears in the pages; if its name words are
  there it is kept and flagged `split_disputed` (Boston Omaha's billboards);
  if the pages show no business nothing changes (`split_not_checked`). The
  check can only remove a business, never add one or change a facet; the
  removed ones stay in the profile (`split_check`). `facets.csv`:
  `split_check`, `businesses_removed`, `businesses_disputed`.
- **Divestiture lines flag a company for review** (no model). A company
  whose saved pages mention a sale, divestiture or spin-off ("Sale of
  Annuity Business to MassMutual") is flagged `pages_mention_divestiture`,
  with the lines in `divestiture_lines`: its facets may describe something
  it no longer owns, which the split check can't see inside one business.
  13 of the 533 on 2026-10-25. Out-of-date facts on other companies are
  left to the manual review (a RAG step may come later).
- **Company size is a category with no text** (version h, 2026-10-24):
  small, mid-sized, large or among the largest, within the company's own
  industry. As free text it could hold figures: with digits banned, a test
  answer still read "employs five thousand people". It is scale only;
  where the company operates is F8 and how it sells is F11.
- **One profile per company** (version k, decided 2026-10-25). Each company
  is described as one business: a company that runs several lines or
  businesses covers all of them in each facet, the largest first. The
  answer schema has room for one business only, so the model can't split.
  Splitting into unrelated businesses (versions f-j: one profile per
  business, B1 the largest, at most four, checked by the third pass) is
  left for the group to pick up: set `facets.SPLIT_BUSINESSES = True` to
  turn it back on (prompt, schema and third pass follow it; the tests for
  it run with the `split_on` fixture). Known issues when it is turned on:
  first-pass splits vary between runs (American Financial, AZZ and
  Carlisle split in one run and not the next), and the third pass removed
  News Corp's book publishing and property listings because its scrape
  saved only the homepage; a guard for thin pages is still to be decided.
- **Every facet records its source:** "model knowledge", "website" or both.
  In the first call the source is always model knowledge, so the model isn't
  asked for it. In the second (pages), every page line is labeled (`[P1.3]`)
  and the model cites the labels of 1-2 lines instead of copying quotes; the
  cited lines and their page URLs are looked up in code.
- **Caching:** with Claude, the instructions and the answer schema (about
  5,800 tokens, the same for every company) are cached, so each call after
  the first pays full price for only ~40 input tokens and a tenth for the
  rest; most of the remaining cost is output, mostly the model's hidden
  reasoning.
- **Answer length** (prompt version h): one-line JSON; core offering in two
  or three sentences; products, services and end markets up to about five
  items each; details of about twenty words; notes only for real gaps.
  (Version g had kept details to twelve words to save Codex usage.)
- **Correctness isn't checked yet** (that's the recipe's manual review).
  Problems with a value's source are flagged (`no_value`, `no_source`,
  `website_without_quote`, `quote_not_found` (a cited label that isn't in
  the prompt), `financial_in_value`), but nothing is dropped.
- **Replaces the earlier website-only design** (prompt versions a-d): the
  model then got only the masked page text and was told not to use what it
  knew, as in `pre-v0/scraps/codex_profiles/`. That left gaps wherever a site
  didn't state something, and no answer at all for the 20 universe companies
  whose sites gave under 40 words.

## Decisions (2026-10-25): split and step 4

- **Model:** prompts plus weights fit on training pairs; no fine-tuning.
  What the weights are fit to (human labels, closeness of multiples) is
  still open.
- **Split:** 70/30, stratified on company size (F9; unknown size is its
  own stratum), counts per stratum rounded by largest remainder (373 / 160),
  seed 2026, not re-drawn for balance. The ten showcase targets (PCTY, BV,
  ROAD, LMB, BRO, ADUS, DXPE, SLGN, BGS, WEN) are in training. Balance is
  checked on SIC division shares and on SMDs of log revenue, margin,
  debt/revenue and EV/EBITDA (read only for that check).
- **Who can be a comp:** during development, training firms only. At the
  end, holdout targets get comps from the training firms.
- **Step 4, candidates:** each facet except company size is embedded on
  its own (`all-mpnet-base-v2`); a pair's similarity is the mean of its
  per-facet cosines over the facets both have (equal weights until they
  are fit; "not applicable" embedded as "none"). z is relative to the
  target's mean and SD over the pool, as in pre-v0. Candidates are the top
  10, or any firm with z ≥ 2 (2.5 also flagged); the LLM step chooses
  among them. Fall-off plots per showcase target, as in pre-v0.
- **Terms:** a target's **profile** is its collection of comps. A company's
  facets are its **business-model characteristics**. (Step 3's code and
  `facets.csv` still say "business profile" for a row of facets.)
- **Recipe step 5 is covered by step 4:** a target's profile is its step 4
  candidate list.
- **Step 6, the model** (`judge_comps.py`): Claude Haiku 5.5 marks every
  z ≥ 2 candidate of a training target good (1) or bad (0), with a short
  reason; one call per target. It reads names, websites and all twelve
  facets, candidates labeled C1, C2, ... in alphabetical order, with no
  similarity, rank, ticker or multiple. A rubric with more levels and the
  manual review wait for the evals (a separate notebook, starting from
  `judge/tables/judgments.csv`). Prompt and any fitted weights are changed
  only on training targets, then frozen and run once on the holdout.
  Run 2026-10-25 (prompt 2026-10-25a): 373 targets, 5,293 pairs, 663 good
  (13%); median 1 good comp per target, 96 targets with none (BV, SLGN);
  57% of rank-1 candidates good, 1% past rank 10. About $0.57.
- **Step 7, evaluation** (`valuation.py`): the estimate (similarity-
  weighted mean of the comps' EV/EBITDA; median also shown) against the
  actual multiple from the financials table, on the training targets
  (2026-10-25): no matching 32.7% median absolute error; cosine
  30.6-32.4% (top 10, z ≥ 2, z ≥ 2.5; mean or median), Spearman
  0.32-0.39. LLM good comps cover 277 of 373 targets; on those 277 they
  give 31.1% (cosine z ≥ 2, the same candidates: 31.1%; cosine z ≥ 2.5:
  30.2%), Spearman 0.39-0.40. So far the LLM's choice doesn't lower the
  error: it helps BRO (-39% to -14%) and LMB, hurts WEN and ADUS, and
  leaves 96 targets without an estimate.
- **Comps without embeddings** (`suggest_comps.py`, notebook section 4,
  2026-10-25): the LLM picks up to ten same-business comps for each
  target from the whole training pool (all 373 firms in a cached system
  prompt, ~99k tokens, with core offering, products, services, customers
  and revenue model; candidates alphabetical, labeled P001..). 1,194
  picks, median 3 per target, 32 targets with none; about $0.55. 89% of
  its picks are cosine z ≥ 2 candidates anyway (median cosine rank 3,
  8% past rank 20), so the embedding shortlist rarely hides a comp the
  LLM would choose. Same-SIC peers (no model): SIC4 / SIC3 / SIC2.
  Errors, on the 277 targets where both LLM rules give an estimate: LLM
  direct 30.8% (equal-weighted mean), LLM good comps 31.1%, cosine z ≥ 2.5
  30.2%, cosine z ≥ 2 31.1%, no matching 31.9%, same SIC 33.1-34.4%
  (Spearman 0.28-0.30, the lowest). Every comp rule lands within about
  30-33%, as in pre-v0: choosing comps doesn't look like the bottleneck.

## The facets

| ID | facet | what it captures | example values | categories |
|---|---|---|---|---|
| F1 | `offering_description` (core offering) | what it sells and to whom, as its own site says | Designs and manufactures rooftop HVAC units for commercial buildings | |
| F2 | `primary_products` | main products sold | HR software; medical devices; hot-mix asphalt | |
| F3 | `primary_services` | main services delivered | consulting; freight logistics; payroll processing | |
| F4 | `customer_segment` | who buys | B2B: mechanical contractors, commercial building owners; B2G: school districts | any of: B2B, B2C, B2G |
| F5 | `end_markets` | industries served | healthcare; retail; manufacturing | |
| F6 | `revenue_model` | how it earns revenue | product sales: equipment sold through dealers; service fees: installation and repair | any of: product sales, subscription, transaction or usage fees, licensing or royalties, service fees, project or contract, rental or leasing, advertising, healthcare reimbursement, interest or premiums, commissions or management fees, other |
| F7 | `value_chain_position` | role in the industry | OEM / manufacturer: builds HVAC units from purchased components, sold to contractors | any of: raw materials, component supplier, OEM / manufacturer, brand owner, distributor, retailer, service provider, software / platform, asset operator, financial intermediary, other |
| F8 | `geography_served` | markets of operation | US regional: Alabama, Florida, Georgia and the Carolinas | one of: US regional, US national, North America, global |
| F9 | `company_size` | scale within its own industry | mid-sized | one of: small, mid-sized, large, among the largest (no detail) |
| F10 | `specialization` | breadth of offerings | related lines: HVAC units, controls and replacement parts | one of: niche specialist, related lines, diversified |
| F11 | `distribution_channels` | how products reach customers | distributors / dealers: independent HVAC dealers; direct sales: national accounts | any of: direct sales, distributors / dealers, own locations, third-party retail, online, partners / resellers, agents / brokers, other |
| F12 | `regulatory_exposure` | importance of regulation | high: medical devices that need FDA clearance | one of: high, medium, low |

Text facets get a short value in the style of the examples. Category facets
get a category from the list (the answer schema rejects anything else) plus
a short detail in the company's own terms, so companies can be compared on
the category without losing what the site says. Every facet has a status
(`stated`, `not_applicable` for products or services a company doesn't sell,
or `unknown`) and a **source**: "model knowledge" and/or the URLs of the
pages whose lines it cites. Definitions of
the categories (e.g. what counts as high regulatory exposure) are in `facets.FACETS`; the notebook prints exactly what the model
is told.

## Running

```
python v0/fill_facets.py --tickers PCTY ROAD     # a few companies
python v0/fill_facets.py --workers 4             # the whole universe: both passes
python v0/fill_facets.py --no-gap-fill           # first pass only (no pages)
python v0/fill_facets.py --dry-run               # write the prompts only
python v0/fill_facets.py --tables-only           # rebuild the CSVs
python v0/fill_facets.py --backend codex --model gpt-6-luna --out ...   # Codex instead
```

**API key (once).** Make a key at console.anthropic.com (API keys; the
account needs billing or credit), then either set it for the PowerShell
window, `$env:ANTHROPIC_API_KEY = "sk-ant-..."`, or put the line
`ANTHROPIC_API_KEY=sk-ant-...` in a `.env` file at the repo root. `.env` is
git-ignored and must never be committed.

The model is recorded in each call's `run.json` and in the profile; a
profile made with another model is redone. With `--backend codex` and no
`--model`, Codex uses its own default (the `model` line in
`~/.codex/config.toml`) and records the model as blank, so pass `--model`.

A rerun skips companies whose profile is current (same prompt, input and
model); the second pass runs only for current profiles with an unknown
facet that it hasn't tried yet. Use a separate `--out` folder for each
model or test. The
run stops if the Codex usage limit or the API credit runs out, or the key
is refused; finished companies are kept, so run it again after fixing that.
Then run the notebook.

## Outputs (`outputs-local/comps/`)

The output folder keeps the name `comps/` (it holds the comp universe and
facets); the code folder was renamed to `v0/` on 2026-10-24.

| path | contents |
|---|---|
| `universe/<run time>/` | `companies.csv` (every company with its step 1-2 flags and `in_universe`), `universe.csv` (the 533 universe companies only, company information, no financials), `financials.csv` (financials, keyed by IQ_COMPANY_ID), `run.json` |
| `facets/codex_runs/<IQ_ID>/<time>/` | per call (folder name kept from the Codex backend): `prompt.txt`, `response.json` (raw answer), `run.json` (backend, model, effort, seconds, tokens); Claude also `api_response.json` (the whole API response), Codex `events.jsonl` and `stderr.txt` |
| `facets/profiles/<IQ_ID>.json` | checked facets with their sources and quotes; replaced ones move to `profiles_history/` |
| `facets/tables/facets.csv` | one row per business profile (current facet version only): `business_id` (B1 the largest), `business`, `business_count`, then for each facet `<facet>_status`, `<facet>` (category facets: `category: detail`), `<facet>_category`, `<facet>_source` ("model knowledge" and/or page URLs), `<facet>_flags` Manual review: `needs_review` (true/false) and `review_reasons` (`described_from_pages_only`, `facet_unknown`, `facet_flagged`, and other issues such as `pages_mention_divestiture`), set by code from what the fill recorded (`fill_facets.review_reasons`); 32 of 533 on 2026-10-25. |
| `facets/tables/facet_quotes.csv` | one row per cited page line: facet, `block` (the line's label, P1.3), page, URL, quote (the line's text), `quote_found` (the label was in the prompt) |
| `facets/tables_history/<time>/` | earlier tables |
| `facets/answer_schema.json`, `facets/answer_schema_with_pages.json`, `facets/logs/` | answer schemas (prompts without and with pages; the Claude API gets them without the company-size pattern, which makes it refuse the schema as too complex); run logs |
| `fill_test/<folder>/` | fill-test runs, same layout as `facets/`: `knowledge_only/` (Codex, versions e and f), `with_pages/` (Codex, version e, pages from the start, an experiment the two-pass design replaced), `knowledge_only_g_luna/` (stopped by the usage limit, empty); read in `notebooks/facet_fill_runs.ipynb` |
| `api_checks/<time>/` | `checks.json` and each call's raw answer from `check_claude_api.py` |
| `split/<run time>/` | `split.csv` (every universe company: size stratum, `sample` training/holdout, `showcase`), `balance_size.csv`, `balance_sector.csv`, `balance_numeric.csv`, `run.json` (seed, share, counts) |
| `embeddings/` | cached per-facet embeddings (`facets_<model>_<hash>.npz`), keyed by the model and the facet texts |
| `candidates/<run time>/` | `candidates.csv` (training target-comp pairs in the top 10 or at z ≥ 2: rank, similarity, z, flags, per-facet cosines `sim_<facet>`), `ranking.csv.gz` (every training pair), `similarity_falloff_<ticker>.png` (showcase targets), `run.json` |
| `judge/` | `runs/<IQ_ID>/<time>/` (per call: `prompt.txt`, `api_response.json`, `response.json`, `run.json`), `judgments/<IQ_ID>.json` (checked answer per target; replaced ones in `judgments_history/`), `tables/judgments.csv` (one row per target-comp pair: score 1/0, reason, step 4 rank, similarity, z), `logs/` |
| `suggest/` | same layout as `judge/`: `runs/` (the shared pool prompt once as `system_<version>_<split>.txt`, then per call `prompt_target.txt`, `api_response.json`, `response.json`, `run.json`), `suggestions/<IQ_ID>.json`, `tables/suggestions.csv` (one row per suggested pair, rank 1 = best; a row with no comp for a target given none), `logs/` |
| `valuation/<run time>/` | `summary.csv` (one row per comp rule: errors, Spearman, % closer than no matching), `summary_llm_covered.csv` (the same on the targets with at least one good comp), `per_target.csv` (each rule's estimate, actual and error per training target), `run.json` |
