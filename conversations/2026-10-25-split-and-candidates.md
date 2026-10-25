# 2026-10-25: training/holdout split and step 4 candidates (Claude Code)

## Decided (Michael)

- Model: prompts plus weights fit on training pairs. No fine-tuning.
- Split stratified on company size categories (facet F9).
- Showcase targets: PCTY, BV, ROAD, LMB, BRO, ADUS, DXPE, SLGN, BGS, WEN
  (buyout-style: mature, cash-generating, execution question; PCTY and BV
  are the mentor's own examples). Picked on business type only, not on
  multiples or past errors; put in training because they are examined
  during development.
- Step 4: embeddings + cosine similarity as in pre-v0; candidates are the
  top k or those above a z-score level; the model chooses among them later
  (step 6, not built).

## Changes

- `v0/split.py`: stratified split (largest-remainder counts, fixed seed,
  forced training ids), SIC divisions, balance tables (shares, SMD).
- `v0/candidates.py`: facet texts (all facets but company size;
  not applicable → "none", unknown left out), per-facet embeddings with a
  cache, combined similarity (weighted mean of per-facet cosines, equal
  weights now), ranking with z over the pool, candidates (top 10 or
  z ≥ 2), per-facet cosines per pair for fitting weights.
- `v0/tests/test_split_and_candidates.py`: 10 tests on synthetic data.
- `v0/notebooks/comps_and_valuation.ipynb`: inputs, decisions table
  (D1-D8), why a holdout, section 1 split (built), section 2 step 4
  (built), sections 3-6 skeleton. Kernel `qual2cast` (the default
  `python3` kernel is Anaconda's, without sentence-transformers).
- `v0/notebooks/comp_universe_and_facets.ipynb`: numbered profile list
  (`#`, target, business, fill %) and a header row on each example
  profile; saves `universe.csv` (the 533, no financials) with each run.
- v0/README.md and PROJECT_STATE.md updated.

## Results

- Data: snapshot `company_list_v3`; universe run `20261025T060358Z`;
  facets version 2026-10-25k (533/533).
- Split `outputs-local/comps/split/20261025T061905Z/`: 373 training,
  160 holdout. Size shares equal to 0.5 points. SMDs: log revenue 0.04,
  margin 0.06, debt/revenue 0.13, EV/EBITDA 0.00. SIC divisions differ up
  to 5.5 points (construction 5.1% vs 1.2%; manufacturing 33.2% vs 38.8%).
- Candidates `outputs-local/comps/candidates/20261025T061905Z/`: 373
  training targets, training pool. z ≥ 2: median 14 per target (5-23),
  none below 3; z ≥ 2.5: median 7, 28 targets below 3. Top-10 share the
  target's SIC2 46.6% (random 7.2%). Showcase lists look right for PCTY,
  ROAD, LMB, BGS, SLGN; BRO mixes brokers with carriers; WEN mixes
  restaurants with packaged food; DXPE gets manufacturers (its distributor
  peers MSM and DSGR are in the holdout); BV gets contractors (no
  landscaping peer exists).
- Tests: `python -m pytest tests -q` in v0/: 89 passed.

## Open

1. Stratify on size × SIC division as well, to fix the sector imbalance?
   (Changes the split; do it before anything is tuned.)
2. The training-only pool removes real peers during development (ADUS
   loses AVAH, CHE, NHC, BKD; DXPE loses MSM, DSGR; BRO loses AJG, RYAN;
   WEN loses TXRH; LMB loses FIX; ROAD loses STRL; SLGN loses GEF).
3. D2: what the facet weights are fit to (human labels or closeness of
   multiples).

## Later the same day: restructure, plots, evaluation

Michael's decisions:
- Terms: a target's **profile** is its collection of comps; a company's
  facets are its **business-model / descriptive characteristics**.
- Recipe step 5 (profiles) is step 4's candidate list; step 6 (0-1 score)
  is the cosine similarity. Neither needs more code.
- The added step after the profiles is the model: an LLM hones the comps
  for each target from the candidates. That is where the prompts and the
  fitted weights (developed on training, frozen for the holdout) come in.
- Last step: ground truth from the financials; compare the LLM-honed comps
  with the cosine comps alone.

Changes:
- `v0/candidates.py`: the embedding model loads from the local Hugging
  Face cache (`local_files_only`), with the transformers progress bar off,
  so there's no unauthenticated-Hub warning or "Loading weights" bar; it
  downloads only if missing.
- `v0/valuation.py` + `v0/tests/test_valuation.py` (4 tests): weighted
  mean / median estimate, no-matching baseline, error summary.
- `comps_and_valuation.ipynb`: recipe-to-section map; fall-off plots per
  showcase target (as in pre-v0); section 3 (steps 5-6 covered); section 4
  the LLM step (design only); section 5 the evaluation.

Results (training targets, run `20261025T065131Z`; the split is
byte-identical across runs): no matching 32.7% median abs error, 38.6%
within 25%; cosine top 10 weighted 31.1% (Spearman 0.38), top 10 median
30.6%, z ≥ 2 weighted 32.4%, z ≥ 2.5 weighted 30.8% (Spearman 0.39).
Cosine is only slightly better than no matching, as in pre-v0. Tests: 93
passed.

Not changed: `comp_universe_and_facets.ipynb` section 3.3 was reworked by
someone else (review list, examples by review reason) and still calls a
row of facets a "profile", as do `facets.py`, `facets.csv` and the README
for step 3.

## Later still: the LLM good/bad step (recipe step 6)

Michael's decisions: remove the "steps 5 and 6 covered" section (its text
moved into section 2); the model step uses Claude Haiku 5.5 on every z ≥ 2
candidate; **binary good (1) / bad (0)** for now, no multi-level rubric;
the evals (manual review, rubric) are a separate notebook, later. Build
the pipeline so that notebook can start from its output.

Changes:
- `v0/judge_comps.py`: one call per training target (target + its z ≥ 2
  candidates: names, websites, all twelve facets; candidates labeled
  C1.. alphabetically; no similarity, rank, ticker or multiple), answer
  schema with label enum + boolean `good` + reason; code checks every
  label answered once. Reuses `fill_facets.call_claude`; keeps every
  prompt and response; skips targets already judged (fingerprint of
  prompt + model); `judge/tables/judgments.csv` one row per pair.
- `v0/tests/test_judge_comps.py` (4 tests). 97 tests pass.
- Notebook: section 3 = the LLM step (coverage, agreement with the cosine
  rank, showcase answers); section 4 = evaluation with the LLM rules and
  a second table on the targets the LLM rule covers.

Run 2026-10-25 (prompt 2026-10-25a): 373 targets, 5,293 pairs, 663 good
(13%); median 1 good comp per target, 96 with none. Good by step 4 rank:
57% at rank 1, 28% at 2-3, 16% at 4-5, 6% at 6-10, 1% past 10. Tokens
3.33M in (0.25M cached), 0.51M out, about $0.57 plus $0.02 for the
showcase test. Showcase: PCTY keeps ASUR, PAYC, ADP, ALIT; BRO keeps the
brokers, drops every carrier; WEN keeps BROS, NATH; DXPE keeps FERG,
TRNS; BV and SLGN keep none.

Evaluation (valuation `20261025T072249Z`), on the 277 targets with a good
comp: LLM similarity-weighted 31.1% median abs error (median 30.8%),
Spearman 0.39-0.40; cosine z ≥ 2 31.1%, z ≥ 2.5 30.2%; no matching
31.9%. The LLM's choice doesn't lower the error yet: BRO -39% → -14%,
LMB -11% → +10%, but WEN +6% → +94% (BROS, NATH), ADUS -3% → +28% (ENSG
only).

## Comps without embeddings (Michael's question)

Michael asked why the comparison used 277 targets (answer: nothing is
fitted; "training" = the firms we may look at; 96 of the 373 got no good
comp from step 6, so the second table scores every rule on the targets
all LLM rules cover) and whether comps could come straight from the base
data without embeddings.

- `v0/suggest_comps.py` + `tests/test_suggest_comps.py` (2 tests; 99
  pass): the whole training pool (373 firms; name, website, offering,
  products, services, customers, revenue model; alphabetical, P001..) in
  a cached system prompt (~99k tokens), the target's twelve facets after
  it; the model picks at most ten same-business comps, best first. Code
  drops the target itself (THG and WRB picked themselves), unknown labels,
  repeats.
- Run 2026-10-25: 373 targets, 1,194 picks (median 3; 32 with none).
  36.0M input tokens (35.8M cached), 0.29M output, about $0.52, plus
  $0.03 for the showcase test.
- Same-SIC peers (SIC4/3/2) added as a no-model baseline.
- Notebook: section 4 (comps without embeddings), section 5 evaluation;
  the second table is now the targets where both LLM rules give an
  estimate (277); intro says what "training" means.

Results (training targets): 89% of direct picks are cosine z ≥ 2
candidates (median cosine rank 3; 8% past rank 20); 54% were also marked
good in step 6. On the 277 common targets: LLM direct 30.8% median abs
error (Spearman 0.36), LLM good comps 31.1%, cosine z ≥ 2.5 30.2%, cosine
z ≥ 2 31.1%, no matching 31.9%, same SIC 33.1-34.4% (Spearman 0.28-0.30).

## Results notes, push, merge with main, PR (2026-10-25)

- Results markdown added after each section of `comps_and_valuation.ipynb`
  (steps 4, 6, no embeddings, 7); outputs unchanged.
- Committed on `michael/wip` (134a373) and pushed.
- Merged `origin/main` (25 commits: PRs #5-#7, Yikai's integrated company
  workflow and team memo, Xiaozhe's growth-signal updates). Michael chose
  to move that work into `pre-v0/` with the rest: `pipeline/`,
  `valuation/`, `experiments/integrated_company_analysis/`,
  `reports/team_company_workflow/`, `reports/integrated_company_analysis/`
  and the new files in `growth_signals/`, `matching/`, `notebooks/`.
  - Every file from main is byte-identical at its new path (one notebook's
    line endings had to be restored from main's blob) except three
    repo-root lookups (`pipeline/collection.py`,
    `growth_signals/edgar_revenue.py`, `pipeline/run_workflow.py`, one
    more `parents[...]` level) and the run instructions in
    `pipeline/TEAM_WORKFLOW.md` (`PYTHONPATH=pre-v0`).
  - `.gitattributes`: main's `-text` rules for the integrated workflow
    moved to the `pre-v0/` paths.
  - README / PROJECT_STATE conflicts: both sides kept, main's sections on
    the memo and the 19-company experiment with `pre-v0/` paths.
  - Tests after the merge: pipeline 50, growth_signals 218, v0 99,
    website_scrape 33, all passing.
- The teammates should know their work moved; their notebooks still run
  as before (they unpack their own code).

## Next

Open: a target with no good comp (fall back to cosine or "no estimate");
weights fit on training pairs; the evals notebook from `judgments.csv`.

## Earlier next step (done)

Build the LLM step (section 4): what it reads (facets of the target and
candidates; maybe 10-K detail and the target's revenue/EBITDA/debt), what
it returns (keep/drop, 0-1 score, reason), and the label the weights are
fit to (D2). Then add its rule to section 5 next to the cosine rules.
