# v1/

**Facet lift experiment (2026-11-13):** start with
`notebooks/facet_uplift_stakeholder.ipynb` for the approach, eight presentation
figures, findings and recommended investigations. It separates the original
0/1/2 rating analysis (rating-point lift, `--outcome rating`) from the earlier
combined peer/non-peer analysis (probability lift, `--outcome peer`). The original
`notebooks/facet_uplift.ipynb` remains the original binary technical/raw version.
The stakeholder notebook reads both pinned outcomes for B3 similarities and agent facet
ratings against Barbara's 293 reviewed pairs. Run
`uv run python v1/scripts/facet_uplift.py` to create another preserved run.
This is exploratory conditional association, not causal CATE or a new ranking
rule. See [FACET_UPLIFT.md](FACET_UPLIFT.md) for treatments, target folds,
missing-evidence handling and interpretation limits.

**v1 is a copy of v0 as the team left it on 2026-10-28, to continue from (cloned 2026-11-03).** The notebooks keep
v0's saved outputs. Two things differ from v0, both mechanical:

- **Layout:** the `.py` modules, their tests, `verification/` and `reference/` are in [`scripts/`](scripts/); the
  notebooks are in [`notebooks/`](notebooks/) and add `v1/scripts` to the import path.
- **Outputs:** the code reads and writes `outputs-local/v1/`, a copy of v0's `outputs-local/comps_pilot_targets/`
  plus the universe, facet fills, fill tests, API checks and embeddings from `outputs-local/comps/`
  (`python v1/scripts/seed_from_v0.py`; manifest in `outputs-local/v1/seed_manifest.json`). v0's folders are untouched.
  Reads of the earlier size-stratified baseline (`comps/candidates/20261025T080854Z`, `comps/judge`) still point at
  `outputs-local/comps/`. Since 2026-11-04, `outputs-local/v1/` is **shared through Git**: a pull gives the data, comp
  lists, saved LLM answers and the golden-set sheets. Raw Codex output, logs, dry-run prompts and history folders stay
  local; see `.gitignore`.

Environment: `uv sync` at the repo root, then pick `.venv` as the notebook kernel (see the root README).
Tests: `uv run pytest v1/scripts/tests v1/scripts/verification/tests -q` (209 pass).

**Integrated experiment default (2026-11-10).** `integration_pipeline.py` uses
`outputs-local/v1/integration/source_reviewed_default/facets.csv` for its current
Sonnet B3 route. It retains one company ID and records ten source-backed field
corrections across HLTC, ENSG and SKIL; TKR was already current. The integrated
runner recomputes B3, the 20 common-field retrieval methods, reviewer comparisons,
factor settings and four peer-selection/valuation routes. `integration_company_report.py`
uses this source-reviewed input by default. Earlier saved v1 results remain separate
historical conditions.

## Start here (2026-11-04)

**Saved-result error analysis (2026-11-05):**
[`notebooks/error_analysis.ipynb`](notebooks/error_analysis.ipynb) joins human
labels, historical/current facet text, similarity methods, Haiku/Sonnet
selection and agent/one-shot grades. It produces a source-linked report and
case packets without new model calls. See [ERROR_ANALYSIS.md](ERROR_ANALYSIS.md).

| what | where |
|---|---|
| **The v1 baseline is B3 (method 1):** TF-IDF-blended facet scores, information weights, "none" as missing, company size out, mutual top 10 topped up to 3 | [`notebooks/similarity_methods.ipynb`](notebooks/similarity_methods.ipynb) (what B0–B3 mean, results, charts); code in [`scripts/facet_weighting.py`](scripts/facet_weighting.py) (`method1_similarity`) |
| B3's comp lists for every training target, as a candidates run | `uv run python v1/scripts/method1_candidates.py` writes `outputs-local/v1/candidates_method1/<time>/` |
| Have the LLM screen B3's lists (paid; Haiku by default) | `uv run python v1/scripts/cosine_then_llm.py --b3 --workers 4` (free first: add `--dry-run`) |
| The selectors' prompt no longer lists company size; the saved answers keep the old prompt | [`PROMPT_VERSIONS.md`](PROMPT_VERSIONS.md); check with `uv run python v1/scripts/check_prompt_versions.py` |
| **Golden set round 2** (CSL, AFG, AZZ, BBCP, BUKS + 2 WEN pairs; 67 pairs) | reviewer guide [`GOLDEN_SET_ROUND2.md`](GOLDEN_SET_ROUND2.md); sheet `outputs-local/v1/golden_set_showcase/labels/round2_sheet.csv`; notebook [`notebooks/golden_set_showcase.ipynb`](notebooks/golden_set_showcase.ipynb) |
| The multi-business rule for BBCP and BUKS | Source-checked scope and company-level 0–2 scoring in the guide and notebook section 5; reviewer grades remain blank |

**Local facet experiment (2026-11-05).** Section 10 of `similarity_methods.ipynb` evaluates 30 B3 facet variants against the existing peer labels. `b3_facet_add_drop.py --export-variant "Sonnet + Fiona sub-sector"` writes a compatible candidates run; pass its `selector_candidates/` directory to `cosine_then_llm.py --b3 --candidates`. A dry run generated all 373 training-target prompts; PCTY and WEN were checked for Sonnet facets and Fiona sub-sector. These experimental lists do not replace the default B3 run.

## Changes in v1 since the clone

**2026-11-04 (evening), a stronger model, and Barbara's industry facets** (Matthew; plan item 3 with Richard).
- **`--backend claude-cli`** on `fill_facets.py`, `fill_sector_facets.py`, `fill_industry_facets.py`, `cosine_then_llm.py` and `direct_llm.py`: the call goes through the Claude Code CLI under your own subscription (`cli_models.call_cli`), default model Claude Sonnet 5.5, no API key. New runs never write into the saved Haiku folders.
- **Sonnet fills, all 533 companies:** `outputs-local/v1/facets_sonnet/` (the twelve facets), `sector_facets_sonnet/` (Fiona's, training and holdout), `industry_facets_sonnet/` (Barbara's, new).
- **`industry_facets.py` + `fill_industry_facets.py`** (new): Barbara's SIC2 facet dictionary (`scripts/reference/sic2_industry_facet_dictionary.md`, 83 groups) as free-text facets per company, filled evidence-first from the saved pages and cited. Table: `industry_facets_long.csv`, one row per company and facet.
- **Sonnet vs Haiku on the selectors**, same B3 lists, same facets, same prompt: `cosine_then_llm/…_{sonnet,haiku}/`, `direct_llm/…_{sonnet,haiku}/`. **`model_selection_eval.py`** (new) scores both against the reviewers' labels, measures how often the two models agree, and compares the two facet fills facet by facet. Short version: the screen barely changes with the model (92% same verdict; both strict); the direct picks do (Sonnet 4/4 WEN and 6/7 PCTY good comps vs Haiku 1/4 and 4/7). Handoff: `conversations/2026-11-04-sonnet-model-selection.md`.

**2026-11-04, v1 baseline, prompt versions, round 2.**
- **B3 (method 1) is the v1 baseline** (team decision). It is chosen on comp quality: it keeps every reviewed direct comp, recovers the adjacent comps v0 missed, and lists none of the reviewed non-comps. It is not chosen on valuation, where it is within noise of v0 (30.0% vs 28.8% median APE). `facet_weighting.method1_similarity` computes it.
- **`method1_candidates.py`** (new) writes B3's lists in the selectors' candidates format. **`cosine_then_llm.py --b3`** screens them.
- **The F9 prompt fix.** New selector runs use prompt `2026-11-04a`, without company size. Everything that replays or reads saved answers pins `2026-10-25a`, so nothing saved was lost or needs re-paying. All 373 + 373 saved prompts were rebuilt byte for byte and checked. New runs write to new folders (`outputs-local/v1/cosine_then_llm/`, `direct_llm/`), never into the saved `judge/` and `suggest/`. Details: [`PROMPT_VERSIONS.md`](PROMPT_VERSIONS.md).
- **`similarity_methods.ipynb`** additions:
  - "How the BM25 pieces curb boilerplate": label IDF vs a typical word; B3 roughly halves the label premium; the saturation curve; a worked pair.
  - Every method's full ranking for the ten showcase targets (`rankings_showcase.csv.gz`).
- **Golden set round 2:** `golden_set_showcase.ipynb` and `GOLDEN_SET_ROUND2.md`, with three neutral reviewer slots, the six-reason rubric and source-checked multi-business scope. `similarity_eval.py` gained `reviewer_sheet` and `check_reviewer_sheet`, and `reviewer_sets` takes any three reviewer names.
- **`outputs-local/v1/` is shared through Git.**

| new file | what it does |
|---|---|
| `scripts/method1_candidates.py` | B3's comp lists as a candidates run (one-way top 10, `mutual`, `selected`, z); no API calls |
| `scripts/check_prompt_versions.py` | Rebuilds every saved selector prompt at the saved version and compares fingerprints; exit code 0 = all match |
| `notebooks/golden_set_showcase.ipynb` | Round 2: pool, blind sheet (never overwritten), checks, the agreed reviewer rule, hit and rank charts for all seven reviewed targets |
| `PROMPT_VERSIONS.md`, `GOLDEN_SET_ROUND2.md` | Teammate guides (prompt versions; reviewer guide) |

**2026-11-03, similarity methods** ([`notebooks/similarity_methods.ipynb`](notebooks/similarity_methods.ipynb)).
This notebook tests how the facets are combined into one similarity score. Team decisions it applies:
- Company size (F9) is out of the similarity.
- "Not applicable" ("none") counts as missing, not as a 1.00 match.
- Comps are the mutual top 10, topped up to 3. This replaces z ≥ 2.
- The reviewers' scores are used under a written rule: majority grade as the main set, unanimous pairs as a strict check, unlabeled comps never counted as 0.
- Sol's grades are an alternative evaluation that no decision rests on.

| file | what it does |
|---|---|
| `notebooks/similarity_methods.ipynb` | Method 1 (TF-IDF-blended facet scores, information weights with BM25-style saturation) and method 2 (FAME-inspired: per-facet heads, a fixed-rule gate, `;`-piece matching), built up from v0's B0. Evaluated on the reviewers' golden set, Sol's holdout grades and valuation APE. Writes `outputs-local/v1/similarity_methods/<run>/`, including a top-up label sheet. No API calls. |
| `scripts/facet_weighting.py` | The methods: facet list (`facets.py` minus `EXCLUDED_FACETS`, so new facets are picked up), TF-IDF/IDF, information, blend, pieces, gate, mutual top k, text-keyed embedding cache. |
| `scripts/similarity_eval.py` | The reviewer rule (`reviewer_sets`), list metrics with unlabeled comps skipped, strict check, Sol grade loading. |

**Result.** On the reviewed comps (PCTY, WEN), methods 1 and 2 keep every direct comp and recover the adjacent comps v0 missed, thanks to the "none" fix. They also drop v0's non-comps, mostly through the mutual filter. Sol's grades on 156 holdout targets point the same way. Charts show each method's hits and each reviewed comp's rank, and method 2's facet weights and contributions for PCTY and WEN. Valuation doesn't move: median APE is 28.8% for v0's top 10, 30.0% for method 1 and 30.3% for method 2, with every interval including 0. Method 2 ends up close to method 1. Details are in the notebook.

**2026-11-03, renamed LLM selectors.** These scripts choose comps, so they are named after their route; "judge" (LaaJ) now means only the evaluators, `graded_peer_selection.py` (Sol, 0–2) and `peer_evaluation.py`.
- `judge_comps.py` → `cosine_then_llm.py`: the LLM keeps the good comps from the cosine shortlist.
- `suggest_comps.py` → `direct_llm.py`: the LLM picks up to 10 from the whole pool.
- Their tests were renamed too. The saved output folders `outputs-local/v1/judge/` and `suggest/` keep their names, because the saved files record those paths.

**Dropping F9 from the selectors' prompt** was deferred here on 2026-11-03 and done on 2026-11-04 with the old version pinned wherever saved work is read or replayed (see the 2026-11-04 entry above and [`PROMPT_VERSIONS.md`](PROMPT_VERSIONS.md)).

The rest of this file is v0's README, unchanged; read its `v0/` paths as `v1/scripts/` for code.

---


**Downstream peer evaluation:** after `notebooks/comps_and_valuation.ipynb`,
open [notebooks/peer_evaluation.ipynb](notebooks/peer_evaluation.ipynb). It
evaluates accepted cosine → LLM peers with the agreed 0–3 business-fit rubric,
saved website passages, and either Codex CLI or Claude Code CLI. The final
matching-notebook cell exports a frozen judgment snapshot and input handoff.
See [PEER_EVALUATION.md](PEER_EVALUATION.md) for setup, saved outputs and limits.
`peer_evaluation.py` holds evaluation logic; `cli_models.py` holds subprocess
transport. This evaluation is separate from `cosine_then_llm.py`'s peer selection.

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
| `notebooks/comps_and_valuation.ipynb` | **The updated baseline model (2026-10-27), with fixed-holdout extensions.** Sections 1-5 run the SIC2 split and four original matching routes on the training firms. Section 6 replays the source-cited 0–2 judge's two peer-selection rules. Section 7 compares six routes under the general facets and Fiona's complete sector-facet configuration on the same holdout, with one no-matching control. Sections 8-10 analyze facets, size and golden-set targets. Writes to `outputs-local/comps_pilot_targets/` (README there). |
| `notebooks/golden_set.ipynb`, `golden_set.py` | **The golden set (2026-10-27).** Builds the pool to label for PCTY and WEN (the union of the four routes' comps: 36 pairs), writes a blind, shuffled CSV sheet to `outputs-local/comps_pilot_targets/golden_set/labels/golden_set_labels.csv` (never overwritten once it exists), checks the hand scores (2 direct, 1 adjacent, blank = 0 with one of five reasons) and prints precision@10, direct hits@10 and NDCG@10 per route. No API calls. Metrics wait until every pair is reviewed. Tests in `tests/test_golden_set.py` |
| `reviewer_gold_eval.py` | Scores the four saved routes separately against Riya, Barbara, and Matthew's 36 reviewed pairs, without forcing a consensus or changing their reasons. Writes reviewer metrics and a pair-disagreement table; no API calls |
| `judge_gold_eval.py`, `graded_peer_selection.py` | Score peers directly with the shared 0–2 rubric and saved website citations. The first file compares 36 pairs with the three reviewers; the second tests grade-based selection on the fixed candidate pool, keeping the original routes unchanged. |
| `business_split_refinement.py`, `source_split_benchmark.py`, `holdout_split_candidates.py`, `split_peer_eval.py`, `notebooks/business_split_refinement_eval.ipynb` | Corrects dated activity status and groups current business activities under one company ID; checks ten selected profiles against primary sources; compares the unchanged peer judge with added scope context on ten development and six fixed-holdout targets. The executed notebook shows reviewer, source, peer, and valuation results. The tested context raises median valuation error on both subsets and is not adopted as the v0 default |
| `facet_eval.py`, `notebooks/gold_and_holdout_integration.ipynb` | Reuses saved per-facet embeddings to compare the existing facet set and single-facet removals against each reviewer's scores; presents those results alongside source checks and the fixed holdout |
| `sector_facet_candidates.py` | Reuses Fiona's `generic + all sector facets` variant on the fixed holdout: eleven general facets plus FF49, SIC4, filled sub-sector text and sector-specific categories, with equal available-facet weights. It keeps the original peer pool and candidate rule; it does not impose a same-sector filter. |
| `holdout_llm_routes.py`, `holdout_batched_routes.py`, `holdout_evaluation.py` | Runs the two LLM selection stages on all 160 fixed-holdout targets, then evaluates cosine, cosine → LLM, direct LLM, and LLM → cosine against the same 373-company pool and no-matching control. The holdout uses Codex CLI rather than the original Haiku training backend. The batch runner evaluates targets independently while sharing the large direct-LLM pool prompt; the inference protocol is recorded |
| `source_scope_sensitivity.py` | Flags selected peers among 40 source-audited companies that have multiple businesses, and reports how excluding them changes coverage and error. This is a diagnostic; it does not change the default peer lists |
| `notebooks/holdout_test.ipynb` | **The holdout test (2026-10-27), not yet scored.** Applies the baseline's cosine, LLM-judged and same-SIC rules to new targets with comps from the training firms only. `MODE = "training"` is a reference run (never reads a holdout multiple); `MODE = "holdout"` needs `holdout/freeze.json` (settings and one `PRIMARY_RULE`, written by the notebook), stops until the frozen judge has been run once, and refuses a second score under one freeze. Reports the usual measures plus 95% bootstrap intervals (`valuation.bootstrap`). Writes to `outputs-local/comps_pilot_targets/holdout/` |
| `notebooks/history/comps_and_valuation_size_stratified.ipynb` | The previous baseline, kept unchanged (apart from a banner) for reference: the split stratified on company size and the original ten showcase targets. Its outputs are in `outputs-local/comps/` |
| `direct_llm.py` | Step 4 without embeddings: the LLM picks up to ten comps per target from the whole training pool; writes `suggest/tables/suggestions.csv` |
| `llm_then_cosine.py` | Reverse hybrid: retains and reranks the direct LLM peers by cosine; the existing valuation code uses their cosine scores as weights |
| `cosine_then_llm.py` | Step 6: Claude Haiku 5.5 marks each z ≥ 2 candidate good (1) or bad (0) with a reason; writes `judge/tables/judgments.csv` |
| `split.py` | The training/holdout split: stratified on any strata series (company size in the previous baseline, SIC2 in the updated baseline), fixed seed, showcase targets in training; balance tables |
| `candidates.py` | Step 4: per-facet embeddings (model loaded from the local cache, no Hub request), combined similarity, ranking with z, candidates (top k or z level) |
| `valuation.py` | Step 7 and the evaluation: weighted mean or median of the comps' multiples, the no-matching baseline, error summary |
| `notebooks/facet_fill_runs.ipynb` | Development record for step 3, not a v0 output: every prompt version and what changed, the model choice, the pages-fill-gaps rule, the API checks, every fill run (tokens, time, cost, fill %) and the fill test |
| `check_claude_api.py` | Checks on the Claude API with made-up companies only (~$0.003 a run): the no-digits rule, the schema, caching, guessing from the name; results in `outputs-local/comps/api_checks/<time>/` |
| `universe.py` | Steps 1-2 |
| `facets.py` | The twelve facets, defined once: prompt, answer schema and checks are built from them |
| `fill_facets.py` | Runs the model (Claude Haiku 5.5 by default, or Codex CLI) over the universe and writes the facet tables |
| `tests/` | `python -m pytest tests -q` from this folder |

The 2026-10-28 reviewer and split analysis is in
`conversations/2026-10-28-reviewer-and-split-refinement.md`. Run the two
deterministic stages with `python v0/reviewer_gold_eval.py`,
`python v0/business_split_refinement.py`, and
`python v0/source_split_benchmark.py`. The fixed-holdout candidates can be
regenerated with `python v0/holdout_split_candidates.py`. The saved paired
model calls can be replayed with `python v0/split_peer_eval.py` (Codex CLI is
needed only for missing responses). None of these stages changes the main v0
notebook.

For the full holdout extension, run `python v0/holdout_split_candidates.py --all`,
then `python v0/holdout_batched_routes.py --workers 2`, then
`python v0/holdout_evaluation.py --require-llm`, and finally
`python v0/source_scope_sensitivity.py`. Saved LLM answers resume by
batch and exact prompt hash, with a 20-minute call timeout; `holdout_llm_routes.py` retains the original
one-target-per-call format for protocol checks. `v0/build_holdout_report.py` rebuilds the report
notebook, which reads the saved outputs. The reviewer-label facet comparison
uses `facet_eval.py --saved-cache-run` with the four exported reviewer files;
its inputs and results are in the notebook. No financial multiple is passed to
the peer-selection calls.

The sector-facet holdout comparison keeps these six routes and the fixed split.
It reuses Fiona's `generic + all sector facets` definition without a sector
restriction; `notebooks/comps_and_valuation.ipynb` reports the six new rows
beside the saved general-facet rows. With the local Codex CLI login:

```text
python v0/fill_sector_facets.py --stage comps_pilot_targets --include-holdout --backend codex --out outputs-local/comps_pilot_targets/sector_facets
python v0/sector_facet_candidates.py
python v0/holdout_batched_routes.py --candidates-run outputs-local/comps_pilot_targets/sector_facets/holdout_candidates --sector-facets outputs-local/comps_pilot_targets/sector_facets/tables/sector_facets.csv --out outputs-local/comps_pilot_targets/sector_facets/holdout_llm
python v0/graded_peer_selection.py --mode holdout --execute --candidates outputs-local/comps_pilot_targets/sector_facets/holdout_candidates --llm-dir outputs-local/comps_pilot_targets/sector_facets/holdout_llm --out outputs-local/comps_pilot_targets/sector_facets/holdout_grades
```

The saved run has 533 company profiles, 160 holdout targets and 2,470 graded
candidate pairs. Its six valuation rows and paired changes are in the main
notebook and `outputs-local/comps_pilot_targets/sector_facets/comparison/`.

The completed local holdout covers 160 SIC2 targets. On the 107 targets
estimated by all four routes, median EV/EBITDA APE is 36.83% for cosine,
37.50% for cosine→LLM, 37.79% for direct LLM, and 37.93% for LLM→cosine.
No paired route difference is established by the bootstrap intervals.
The executed `notebooks/gold_and_holdout_integration.ipynb` shows the full
comparison, gold-label facet check, source-backed business grouping, coverage,
and example peer decisions. Its holdout LLM calls use `gpt-6.1-sol` in batches,
whereas the original training run used one-target Haiku calls; compare methods
within the holdout, not across those inference protocols.

To test the optional 0–2 judge selection route, run
`python v0/graded_peer_selection.py --mode gold --execute --workers 2`, then
`python v0/graded_peer_selection.py --mode holdout --execute --workers 3`.
Completed target calls are reused on rerun. To rebuild the comparison tables
from the shared grades without model calls, use `--evaluate-saved` with each
mode instead of `--execute`. The method scores the unchanged
cosine z ≥ 2 candidate pool from saved website passages, then compares direct
peers (2 only) with direct-first/adjacent-second peers (2 then 1). Scores 0
and insufficient evidence are excluded. Grade orders peers; the existing
cosine weight and `valuation.estimate` produce the multiple. The original four
routes remain unchanged. Results and pairwise common-target comparisons are
in `outputs-local/comps_pilot_targets/holdout_completion/graded_peer_selection/`.

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
  seed 2026, not re-drawn for balance (**superseded 2026-10-27, proposed: the updated baseline stratifies on SIC2, see "Updated baseline" below**). The ten showcase targets (PCTY, BV,
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
- **Step 6, the model** (`cosine_then_llm.py`): Claude Haiku 5.5 marks every
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
- **Comps without embeddings** (`direct_llm.py`, notebook section 4,
  2026-10-25): the LLM picks up to ten same-business comps for each
  target from the whole training pool (all 373 firms in a cached system
  prompt, ~99k tokens, with core offering, products, services, customers
  and revenue model; candidates alphabetical, labeled P001..). 1,194
  picks, median 3 per target, 32 targets with none; about $0.55. 89% of
  its picks are cosine z ≥ 2 candidates anyway (median cosine rank 3,
  8% past rank 20), so the embedding shortlist rarely hides a comp the
  LLM would choose. Same-SIC peers (no model): SIC4 / SIC3 / SIC2.
  Errors, on the 277 targets where all four routes give an estimate: LLM
  direct 30.8% (equal-weighted mean), LLM then cosine 30.6%,
  cosine then LLM good comps 31.1%, cosine z ≥ 2.5
  30.2%, cosine z ≥ 2 31.1%, no matching 31.9%, same SIC 33.1-34.4%
  (Spearman 0.28-0.30, the lowest). Every comp rule lands within about
  30-33%, as in pre-v0: choosing comps doesn't look like the bottleneck.

## Sector sub-models and facet add/drop (2026-10-27, recipe steps 5-6)

Michael's open tasks of 2026-10-27: recipe #5/6 (specialized sub-models;
sector / sub-sector as extra facets; rerun the evals) and general demand
#1 (another add/drop review of facets, judged by how close the chosen comps
are to the golden set, not by valuation error). Built on branch
`fiona/sector-submodels`; nothing here changes step 3-7 code.

| file | what it does |
|---|---|
| `sectors.py` | SIC → Fama-French 49 industry (`reference/Siccodes49.txt`, Ken French's file) → one of eleven sector groups (`SECTOR_GROUPS`); the sector facet as a similarity (1 same FF49, 0.5 same group, 0 otherwise) |
| `sector_facets.py` | the sub-sector text facet for everyone, plus 2-5 category facets per sector group, taken from Barbara's "Comprehensive Company Facet Framework" section 2 (software, manufacturing, financials, healthcare, consumer, energy, business services; distribution/transport, construction/real estate and telecom/media are ours); prompt, answer schema and checks |
| `fill_sector_facets.py` | fills them from saved website evidence with Claude Haiku or Codex CLI (`--backend codex`); `--evidence` adds a deeper crawl and web search. Each facet cites supporting lines; model-memory fills are flagged `from_memory`. No financials; training firms only unless `--include-holdout`. |
| `facet_eval.py` | ranks every labeled training target's pool under each variant (generic step 4; generic minus one facet, for each facet; + sector; + sub-sector (SIC4, no LLM: 1 same 4-digit SIC, 2/3 same 3-digit, 1/3 same 2-digit); + LLM sub-sector; + sector-specific facets; sub-model = comps only from the target's sector group) and scores the ranking against the golden set (2/1/0) and the step 6 judge: pairwise accuracy, recall@10 and MRR of the best comps, top-10 label mean and how much of the top 10 is labeled; `outputs-local/<stage>/facet_eval/<run>/`, where `--stage` picks the split and judge: `comps` (previous baseline) or `comps_pilot_targets` (updated baseline) |

Decisions and notes:
- **Sector comes from the SIC code** (CapIQ gives one for private companies
  too); it is not a financial field. EV/EBITDA is never read in these files.
- **Sector-specific facets are compared category by category** (Jaccard
  overlap), and only between two companies of the same sector group;
  across groups the facet is left out of the pair, like an unknown facet.
- **Sub-model:** a target searches only its own sector group when the group
  has at least 8 training firms (`facet_eval.MIN_POOL`), else the whole pool.
- **Frozen design:** the fill defaults to training firms. The fixed-holdout
  comparison fills holdout companies only after the facet definitions are fixed;
  training-label evaluation still drops any label touching a holdout firm.
- **Golden-set file:** `.csv` or `.xlsx` with a target column (`target`,
  `target_ticker` or `target_iq_id`), a comp column (likewise) and a score
  (`score`, `label`, `grade` or `rating`; 0-2 is halved, 0/0.5/1 kept).
- Equal weights for every facet in a variant, as in step 4.

Run, after the step 3-4 outputs exist:

```
python v0/fill_sector_facets.py --tickers AAON PCTY ROAD   # check a few first
python v0/fill_sector_facets.py --workers 4                # all training firms (~$0.2)
python v0/facet_eval.py --gold golden_set.csv              # + the judge's labels if judged
python v0/facet_eval.py --stage comps_pilot_targets        # updated baseline (SIC2 split)
```

Results so far (2026-10-27, LLM judge labels only, training targets;
updated baseline `comps_pilot_targets/facet_eval/20261027T211617Z`, 373
targets, 4,996 labeled pairs; pairwise accuracy):

| variant | updated baseline | previous baseline |
|---|---|---|
| generic (step 4) | 0.899 | 0.910 |
| + sub-sector (SIC4) | 0.911 | 0.918 |
| minus F3 primary services | 0.911 | 0.911 |
| minus F8 geography | 0.906 | 0.918 |
| + sector (FF49) | 0.895 | 0.892 |
| + sector + SIC4 | 0.888 | 0.886 |
| sub-model (same sector group) | 0.78-0.79 | 0.75-0.76 |

- The SIC4 sub-sector helps a little; FF49 does not; the sector sub-model
  hurts because many judge-good comps are in another sector group (PCTY,
  software, and ADP, business services).
- Dropping F3 helps, matching Michael's finding that "none" pairs match
  exactly (notebook section 11, not fixed).
- Caveat: the judge labeled only the generic model's candidates, so a
  variant that brings new firms into the top 10 is scored on fewer labels
  (labeled share falls from 0.97 to 0.77-0.90), while the labeled ones score
  higher (top-10 label mean 0.158 to 0.19). A golden set from pooled
  candidates is needed to settle it.
- The 2026-10-27 results above preceded the sector-facet fill. The current
  fixed-holdout comparison and its 36-pair reviewer check are in
  `notebooks/comps_and_valuation.ipynb`.

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

## Updated baseline: SIC2 split and the pilot's ten targets (2026-10-27, proposed)

`notebooks/comps_and_valuation.ipynb` is the updated baseline model. It runs the
method of the 2026-10-25 decisions above on a different split, to line the v0
pipeline up with the business-structure pilot's ten targets and to test company
size. The previous baseline notebook is kept, unchanged apart from a banner, in
`notebooks/history/comps_and_valuation_size_stratified.ipynb`, and its outputs
stay in `outputs-local/comps/`. The split decision is a proposal until the team
reviews it.

- **Showcase targets:** the pilot's PCTY, WEN, CSL, AFG, BOC, NWSA, AZZ, BBCP,
  BUKS and SNFC.A, in training. The notebook lists each with the reason the
  pilot picked it (related products, a completed exit, or a current
  multi-business group). They were chosen as source challenges, not at random.
- **Split:** 70/30, seed 2026, stratified on SIC2 with groups under 6 firms
  merged into "other" (26 strata), instead of company size. Size is left free
  so its effect can be tested, which means it is not balanced between the
  samples (large 54% of training against 46% of holdout, among the largest
  12% against 18%, small 3% against 6%). 271 of the 373 training firms are the
  previous baseline's. Not re-drawn for balance.
- **Re-runs:** z is relative to the pool, so a new split changes almost every
  target's candidate list. The judge (`cosine_then_llm.py`) and the direct picks
  (`direct_llm.py`) were re-run on it, Claude Haiku 5.5, prompt 2026-10-25a,
  373 of 373 targets.
- **Outputs:** `outputs-local/comps_pilot_targets/` (see the README there for
  the layout and which run is which), not `comps/`. `cosine_then_llm.py` and
  `direct_llm.py` default to the latest candidates run in `comps/`, so a run
  written there would silently redirect them; run them here with
  `--candidates <run> --out <folder>`. `direct_llm.py` now finds the split
  beside the candidates run's own folder (the same result for `comps/`).
- **Sharing:** `.gitignore` shares every `outputs-local/comps*/` folder by
  default (so a new stage folder needs no new line) and ignores only logs,
  dry-run prompts, `*_history` folders, raw Codex output and a top-level
  `history/` of superseded notebook reruns. The rest of `outputs-local/` (raw
  website HTML, `matching/`, `scraps/`) stays local: the repository is public,
  so sharing it is a team decision.
- **Results (training targets, development only):** median absolute %
  error 31.9% with no matching; cosine 28.8-32.1%; LLM good comps 30.5% (264
  targets); LLM direct and LLM then cosine 30.6% (343); same SIC 35.1-36.7%. As
  before, every way of choosing comps lands within a few points, and the split
  alone moves a rule by 2-4 points.
- **Facets (section 8):** the combined similarity separates the LLM's good
  comps from its bad ones with an AUC of 0.87; offering description (F1) is the
  best single facet (0.83), geography 0.53. Company size (F9), embedded the same
  way though it is not in the similarity, is 0.49 (chance) and lifts the
  top-10 comps by 0.01 cosine. A facet that does not apply is embedded as
  "none", so two firms with "none" match exactly (1.00): this inflates primary
  products and services (F2, F3; 13% and 19% of top-10 pairs), whose lift falls
  from 0.34 to 0.29 without those pairs. WEN shows it: its F3 is "none" and
  matches 17 of its 20 candidates, 16 of them judged bad.
- **Company size (section 9):** error falls as firms get bigger (cosine z ≥ 2:
  39.8% small, 34.3% mid-sized, 28.7% large, 24.0% among the largest), but the
  median multiple barely moves with size, size agreement does not predict the
  LLM's verdict (AUC 0.498), and requiring the same size category hurts (32.1%
  against 29.6%). Not a useful comp filter beyond excluding extreme gaps.
- **Golden set (section 10):** two of the ten targets will be chosen; the
  current pick is PCTY and WEN. `golden_set/<run>/target_choice.csv` compares
  the ten (candidates, LLM-good comps, direct picks, size of the pool to label).
- **To do (notebook section 11):** a facet that does not apply is embedded as
  "none", which the similarity has done since 2026-10-25; the stopgap (treat it
  as missing) and the fix at the source (tighten the facet prompt, re-fill all
  533) are described there, with costs. Neither is applied.
- **Status of this 2026-10-27 baseline:** holdout and human-label evaluations
  were still pending. The later fixed-holdout and reviewer-label results are
  reported above and in the companion integration notebook.

## Outputs (`outputs-local/comps/`)

This section describes the previous baseline's folder. The updated baseline's outputs are in `outputs-local/comps_pilot_targets/`, which has its own README; the layout of each stage folder is the same.

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
| `llm_then_cosine/<run time>/` | `pairs.csv` (direct LLM peers with their original rank and reason, cosine rank and score, and new rank) |
| `valuation/<run time>/` | `summary.csv` (one row per comp rule: errors, Spearman, % closer than no matching), `summary_llm_covered.csv` (the same on targets covered by both original LLM routes and LLM then cosine), `per_target.csv` (each rule's estimate, actual and error per training target), `run.json` |
