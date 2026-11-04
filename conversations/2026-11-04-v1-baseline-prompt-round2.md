# v1 baseline (B3), F9 out of the selector prompts, golden set round 2, shared outputs

Follows `2026-11-03-similarity-methods.md` (same session, continued).

## Requests and decisions (Michael, 2026-11-04)

- **Remove company size (F9) from the LLM selectors' prompt** without breaking Fiona's `facet_eval`, Kethan's `peer_evaluation`, or the holdout replays. Document it heavily for teammates.
- **B3 (method 1) is the v1 baseline.** Add a flag so the LLM selector can screen B3's lists.
- **A chart/markdown on how BM25 curbs boilerplate in B3.**
- **Golden set round 2:**
  - targets: five of the ten showcase targets, CSL, AFG, AZZ, BBCP and BUKS (about 65 pairs), then adjust;
  - pool: the union of all six methods' lists (B2 included);
  - reviewers: neutral slots A, B, C;
  - multi-business rule: proposed, with a **stub for Eric** (the business split is his work).
- **The business split**, answered: it adds no rows. One Capital IQ ID and one facet profile per company; the groups are source-cited metadata in `outputs-local/v1/business_structure_refinement/`.
- **Share `outputs-local/` through git** so teammates have the data and sheets without contacting Michael.
- **Commit and open a PR** when done.

## Changes

### F9 prompt fix (`v1/PROMPT_VERSIONS.md`)

- **Prompt versions.** `cosine_then_llm.py` and `direct_llm.py` have:
  - `PROMPT_VERSION = 2026-11-04a`: company size left out;
  - `SAVED_PROMPT_VERSION = 2026-10-25a`: all twelve facets;
  - `PROMPT_EXCLUDES` per version.

  `describe()` takes `exclude`, and `build_prompt()` takes `prompt_version`. There is a CLI `--prompt-version`.
- **Separate output folders.** New runs default to `outputs-local/v1/cosine_then_llm/<candidates run>_<version>/` and `outputs-local/v1/direct_llm/<split run>_<version>/`. The saved answers stay in `judge/` and `suggest/`, and `DEFAULT_OUT` remains as an alias for older imports.
- **Table guard.** `write_tables` filters on the run's version and refuses to write an empty table over answers of another version.
- **Pinned to the saved version:**
  - `holdout_batched_routes.py`, `holdout_llm_routes.py` and `split_peer_eval.py` (replays);
  - `facet_eval.py` (Fiona) and `peer_evaluation.py` (Kethan);
  - the notebooks `comps_and_valuation`, `holdout_test` (including the command it prints), `history/comps_and_valuation_size_stratified` and `similarity_methods` (sources only; saved outputs untouched).
- **Verified:** hashes taken before the change, then rebuilt at the saved version after it. All identical:
  - 533 facet descriptions;
  - 533 descriptions with the sector summary;
  - 373 saved verdicts and 373 saved direct picks, each also matching its saved fingerprint.
- **New `scripts/check_prompt_versions.py`:** run on 2026-11-04, it reports 373/373 for each selector at the saved version and 0/373 at the new one (a new run means new calls, as expected).
- **Tests:** the two versions differ only in the company-size line; a table is never emptied.

### B3 as baseline, and `--b3`

- **`facet_weighting.method1_similarity`:** B3 in one call.
- **New `scripts/method1_candidates.py`:** writes B3's lists for the training targets (or `--targets all`) to `outputs-local/v1/candidates_method1/<time>/`. Each run has `ranking.csv.gz`, plus `candidates.csv` (the one-way top 10 with `mutual`, `selected` and `topped_up`) and `run.json`. Run `20261104T074915Z`: 373 targets, 3,730 one-way pairs, 2,396 selected (median 7 per target), identical to the notebook's B3 lists.
- **`cosine_then_llm.py --b3`:** uses the latest run there and screens each target's `selected` list (`pick_pairs`, tested). Its output goes to `outputs-local/v1/cosine_then_llm/b3_<run>_<version>/`. The dry run for PCTY and WEN was checked: no company-size line, and WEN's list is BROS, BDL, HQI, PLNT, TXRH, STKS.

### `similarity_methods.ipynb`

- **Moved:** the chart style cell now sits before section 2's charts.
- **New subsection "How the BM25 pieces curb boilerplate in B3"**, with three charts (`bm25_label_idf.png`, `bm25_label_premium.png`, `bm25_saturation.png`) and a worked pair:
  - **Label IDF:** "B2B" 0.12, "direct sales" 0.15, "related lines" 0.29, "medium" 0.46, "product sales" 0.58, "global" 0.67, "OEM / manufacturer" 1.07. A typical word in the same facets is worth 1.3–3.8, and a one-firm word 5.9.
  - **Label premium** (embedding alone → B3 blend): 0.06–0.26 → B3 keeps 53–71% (customer segment 0.105 → 0.057).
  - **Worked pair:** ESAB–PSIX share "B2B" and almost nothing else: embedding 0.93, TF-IDF 0.03, B3 0.48.
- **New output:** `rankings_showcase.csv.gz` (every method's full ranking for the ten showcase targets).
- **Current run:** `20261104T075557Z`. Valuation, reviewer and Sol numbers are unchanged. Earlier runs from this session are in `history/`.

### Golden set round 2

- **`similarity_eval.py`:**
  - `reviewer_sets(labels, reviewers)` takes any three names;
  - new `reviewer_sheet()` (the blind sheet with a column set per reviewer, pairs `<ticker>-R2-nn`);
  - new `check_reviewer_sheet()`;
  - `REASONS` now has the team rubric's six reasons, because `golden_set.REASONS` lacks "Different industry", which round-1 reviewers used.

  Tested.
- **New `notebooks/golden_set_showcase.ipynb`:**
  - **Inputs:** a pinned `similarity_methods` run; the target table includes Eric's business scopes.
  - **Pool:** 67 pairs (CSL 18, AFG 11, AZZ 11, BBCP 14, BUKS 11, WEN 2). B2 adds no pairs beyond the other methods.
  - **Sheet:** blind, with the target's business scope shown, written to `outputs-local/v1/golden_set_showcase/labels/round2_sheet.csv` (never overwritten). Also `reviewers.csv` (slots A, B, C) and `pool_with_methods.csv`.
  - **Scoring section:** checks the filled sheet; applies the rule; merges with round 1 for seven targets; summary table, hit chart and rank charts.
  - **Section 5:** the stub for Eric.
  - **Testing:** the scoring path was run on made-up scores via the `ROUND2_LABELS` / `ROUND2_EVAL_OUT` overrides, writing only to the scratch folder (a temporary notebook copy, deleted). The real notebook is saved in its waiting state.
- **New `v1/GOLDEN_SET_ROUND2.md`:** the reviewer guide (rubric, six reasons, the multi-business rule stub with Eric's checklist, filling and running steps).

### Sharing `outputs-local/v1/`

- **`.gitignore`** now shares `outputs-local/v1/` by default, with the same exclusions as `comps*/`: `codex_runs`, `logs`, `prompts_dry_run`, `*_history`, `history/` and `*.log`, at any depth.
- **Size:** 8,062 files, about 154 MB. The largest is the 37 MB text-embedding cache. Most of `v1/` is identical to `comps*/` files already in git, and git stores identical files once.
- **Checked:** no API keys, emails or local paths found.
- **Visibility:** the repo is public, so these files are public. The same kind of data (the Capital IQ list with financials, `comps*/` including `financials.csv`) was already published.
- **Still local:** `outputs-local/matching/` and `outputs-local/scraps/` (pre-v0).
- **Map:** `outputs-local/v1/README.md` now opens with a folder map.

### Docs

`v1/README.md` (a "Start here" table and the 2026-11-04 changes), the root `README.md` (status, folder map, next steps), `PROJECT_STATE.md`.

## Tests

`uv run pytest v1/scripts/tests v1/scripts/verification/tests -q`: 209 passed. Both notebooks run end to end with no errors.

## Data version

- `company_list_v3`; universe `20261025T060358Z`; facets `2026-10-25k`; split `20261027T204930Z`.
- `similarity_methods` run `20261104T075557Z`; `candidates_method1` run `20261104T074915Z`; round-1 labels fetched 2026-10-28.
- No API calls.

## Open issues

- **The multi-business rule** is unconfirmed (stub for Eric). BBCP has an open `B1|B3` review flag, and BUKS has three.
- **Round 2's sheet must reach the reviewers.** It is in git; a Google Sheet copy is optional.
- **Paid runs** (`--b3` selector, new-prompt `direct_llm`) wait for funding.
- **The text-embedding cache** (37 MB) will be re-committed whenever facet texts change; consider leaving it local if the repo grows.

## Next step

Eric confirms or edits the rule (the guide and section 5 of the notebook); the reviewers fill the sheet; commit `round2_filled.csv`; re-run `golden_set_showcase.ipynb` and decide whether to add NWSA, BOC or SNFC.A.
