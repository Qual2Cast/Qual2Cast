# outputs-local/comps_pilot_targets/

Outputs of the main comps notebook, `v0/notebooks/comps_and_valuation.ipynb`
(written 2026-10-27). This folder is separate from `outputs-local/comps/`, which
keeps the outputs of the earlier version of the notebook
(`v0/notebooks/history/comps_and_valuation_size_stratified.ipynb`) plus the
shared universe, facets and embeddings that both versions read.

## What is different from `comps/`

| | `comps/` (earlier version) | here (main notebook) |
|---|---|---|
| split (70/30, seed 2026) | stratified on company size (F9) | stratified on SIC2, groups under 6 firms merged into "other" (26 strata) |
| showcase targets | PCTY, BV, ROAD, LMB, BRO, ADUS, DXPE, SLGN, BGS, WEN | the business-structure pilot's ten: PCTY, WEN, CSL, AFG, BOC, NWSA, AZZ, BBCP, BUKS, SNFC.A |
| judge and direct picks | run on that split | **re-run on this split** (Claude Haiku 5.5, prompt 2026-10-25a) |
| extra analysis | none | facet contribution including F9, what company size does, golden-set target choice |

271 of the 373 training firms are the same in both splits. Because z is
relative to the pool, almost every target's candidate list changed, so the
judge and direct picks could not be reused. The split decision is a proposal
until the team reviews it. Numbers from the two folders are not comparable
row for row: the split alone moves a comp rule by about 2-4 points.

`judge_comps.py` and `suggest_comps.py` default to the latest candidates run in
`comps/candidates/`, which belongs to the earlier version. To run them here,
pass `--candidates outputs-local/comps_pilot_targets/candidates/<run>` and
`--out outputs-local/comps_pilot_targets/judge` (or `.../suggest`).

## Which run is which

- **`20261027T204930Z`** is the final execution of the notebook. Every stage
  folder below has this run; its printed results are in the notebook.
- **`20261027T195135Z`** (in `split/` and `candidates/`) is the split and
  candidates run the Haiku calls were made on; `judgments.csv` and
  `suggestions.csv` name it in their `candidates_run` and `split_run` columns.
  The split is deterministic, so it has the same content as the final run.
- Seven rows of `judge/tables/judgments.csv` name run `20261027T190507Z`
  instead: three targets whose candidate list was identical under an earlier,
  size-stratified draw of this notebook, so those judgments were reused. That
  run is archived in `history/` (not shared).

## Layout

| path | contents |
|---|---|
| `split/<run>/` | `split.csv` (every universe company: SIC2 `stratum`, `size_stratum`, `sample` training/holdout, `showcase`), `balance_size.csv`, `balance_sector.csv`, `balance_numeric.csv`, `run.json` |
| `candidates/<run>/` | `candidates.csv` (training target-comp pairs in the top 10 or at z >= 2, with per-facet cosines `sim_<facet>`), `ranking.csv.gz` (every training pair), `similarity_falloff_<ticker>.png` (showcase targets), `run.json` |
| `judge/` | step 6, same layout as `comps/judge/`: `runs/<IQ_ID>/<time>/` (prompt, raw answer), `judgments/<IQ_ID>.json` (checked answer per training target), `tables/judgments.csv` (one row per target-comp pair: score 1/0, reason, rank, similarity, z). Files for targets that are not training under this split were moved to `judgments_history/not_in_current_split/` (not shared) |
| `suggest/` | direct LLM picks, same layout as `judge/`: `runs/`, `suggestions/<IQ_ID>.json`, `tables/suggestions.csv` (one row per pick, rank 1 = best; a row with no comp for a target given none) |
| `llm_then_cosine/<run>/` | `pairs.csv`: the direct LLM peers with their original rank, cosine rank and score, and new rank |
| `valuation/<run>/` | `summary.csv` (one row per comp rule: errors, Spearman, % closer than no matching), `summary_llm_covered.csv` (the same on the targets all LLM-containing routes cover), `per_target.csv`, `run.json` |
| `facet_contribution/<run>/` | notebook section 7: `facet_separation.png` (AUC of each facet, good vs bad, F9 included), `facet_lift_top10.png`, `facet_heatmap_PCTY.png`, `facet_heatmap_WEN.png`, `facet_summary.csv` (includes the lift without shared "none" pairs) |
| `size_effect/<run>/` | notebook section 8: `error_by_size.csv/.png`, `size_gap.csv/.png`, `size_restriction.csv` |
| `golden_set/<run>/` | notebook section 9: `target_choice.csv`, the ten showcase targets side by side (what each was picked to test, the pilot's split result, candidates, LLM-good comps, direct picks, size of the pool to label, and the current golden-set pick) |

## What `history/` and the `*_history` folders are

- **`history/` (here, not shared):** earlier executions of the notebook. Every
  run of it writes a new timestamped folder per stage, and the split and
  candidates are deterministic, so these are reruns of the same inputs (earlier
  chart drafts and intermediate versions of the analysis), 67 MB. Only the final
  run is kept at the top level. Nothing in them cannot be rebuilt by rerunning
  the notebook, which makes no API calls.
- **`judge/judgments_history/`, `judge/tables_history/`,
  `suggest/suggestions_history/`, `suggest/tables_history/` (local, not shared):** the
  scripts' own safety copies. Each time a checked answer or table is replaced
  (a target judged again on a new split), the old one moves here instead of being
  overwritten. These are real model answers, so they are kept on disk. About 9.6 MB. The
  files in `judgments_history/not_in_current_split/` are judgments for targets
  that are not training under this split.
- **`v0/notebooks/history/`:** the previous baseline notebook, kept for reference.

Not shared (ignored by Git, kept on disk): `history/` above, the `judge/` and
`suggest/` logs and `*_history` folders, `suggest/prompts_dry_run/` (114 MB of
prompts written by `--dry-run`, rebuilt by rerunning it) and the loose console
logs. Everything else here is shared.

## Headline results (training targets, development only; details in the notebook)

- Median absolute % error: no matching 31.9%; cosine 28.8-32.1%; LLM good comps
  30.5% (264 targets); LLM direct and LLM then cosine 30.6% (343); same SIC
  35.1-36.7%. The routes are still bunched within a few points.
- Facets: the combined similarity separates the LLM's good comps from its bad
  ones with an AUC of 0.87; offering description (F1) is best alone (0.83).
  Company size (F9), embedded the same way though it is not in the similarity,
  is 0.49 (chance). A facet that does not apply is embedded as "none", so two
  such firms match exactly; this inflates the products and services facets
  (their lift falls from 0.34 to 0.29 without those pairs).
- Company size: error falls as firms get bigger, but the median multiple barely
  moves with size, size agreement does not predict the LLM's verdict, and
  requiring the same size category hurts. It is not a useful comp filter.
- The holdout is untouched.

Source data: `company_list_v3` snapshot; universe run `20261025T060358Z` and the
facets in `comps/` (facets prompt version 2026-10-25k).
