# 2026-10-27: updated baseline notebook (SIC2 split, pilot targets)

Goal: line the v0 pipeline up with the business-structure pilot's ten targets
(PCTY, WEN, CSL, AFG, BOC, NWSA, AZZ, BBCP, BUKS, SNFC.A), test what company
size (F9) does, and prepare a golden set of target-comp pairs for PCTY and
Wendy's (WEN), chosen by Michael from the ten. The previous baseline notebook
and `outputs-local/comps/` are unchanged.

## Changes

- `v0/notebooks/comps_and_valuation.ipynb` is now the **updated baseline model**
  (untracked changes until committed). It was built as a copy of the previous
  notebook and then made the main one:
  - the showcase set is the ten pilot targets, listed at the top with the reason
    each was picked (from `business_structure_eval.ipynb`);
  - the split is stratified on SIC2 (groups under 6 firms merged into "other",
    26 strata) instead of company size, seed 2026, not re-drawn for balance;
  - outputs go to `outputs-local/comps_pilot_targets/`, judgments and direct
    picks are read from its own `judge/` and `suggest/` folders;
  - section 7: per-facet separation (AUC, good vs bad), lift of the top 10,
    heatmaps for PCTY and WEN, all including company size, whose text is
    embedded the same way though it is not in the similarity;
  - section 8: company size: error by size category, size gap against the
    LLM's verdict and the multiples, comps restricted by size;
  - section 9: choosing the golden-set targets: the ten side by side, current
    pick PCTY and WEN;
  - markdown refreshed to this run (results blocks, paths, commands).
- The previous baseline moved (not deleted) to
  `v0/notebooks/history/comps_and_valuation_size_stratified.ipynb`, with a banner
  and `history/README.md`.
- `v0/suggest_comps.py`: `load_inputs` reads the split from beside the
  candidates run's own folder instead of a fixed `outputs-local/comps/split/`
  (same result for the default layout), so it can run on the new outputs.
- `.gitignore`: every `outputs-local/comps*/` folder is shared by default; only
  logs, dry-run prompts, `*_history` folders, raw Codex output under a stage
  folder and a top-level `history/` of superseded reruns are ignored. Tracked
  files are unaffected. About 48 MB (6.7k files, largest 3.5 MB) of
  `comps_pilot_targets/` becomes visible to Git. A wider share-all rule (raw
  website HTML, `matching/`, `scraps/`, about 0.5 GB) was prepared and **not
  committed**: the repository is public, and the team had kept those local.
- Notebook section 10 is a stub: treat "not applicable" facets as missing
  (stopgap) or fix them at the source (tighten the facet prompt, re-fill all 533);
  neither is applied.
- `outputs-local/comps_pilot_targets/` was tidied: superseded notebook runs moved
  to an ignored `history/`, judgment and suggestion files for targets that are
  not training under this split moved to `*_history/not_in_current_split/`, the
  two tables rebuilt from the current files (no API calls), and a README added
  with the layout and which run is which.
- `v0/README.md`, `PROJECT_STATE.md`: the updated baseline, its outputs and results.

## Data and runs

- Snapshot `company_list_v3`; universe run `20261025T060358Z`; facets prompt
  version 2026-10-25k.
- Split and candidates run `20261027T195135Z` (the Haiku runs); the final
  notebook execution is `20261027T204930Z` (same content: the split is
  deterministic). Earlier executions are archived in
  `outputs-local/comps_pilot_targets/history/` (not shared).
- Judge (`judge_comps.py`) and direct picks (`suggest_comps.py`): Claude Haiku
  5.5, prompt 2026-10-25a, 373 of 373 targets, no failures. Judge about 3.25M
  input / 0.50M output tokens; direct picks about 36.6M input (36.0M cached) /
  0.29M output.
- 271 of the 373 training firms are the original split's.

## Results (training targets, development only)

- Median absolute % error: no matching 31.9%; cosine 28.8-32.1%; LLM good
  comps 30.5% (264 targets); LLM direct 30.6% and LLM then cosine 30.6% (343);
  same SIC 35.1-36.7%. On the 264 targets all LLM-containing routes cover:
  LLM then cosine 27.4%, LLM direct 27.5%, cosine top 10 28.3%, no matching
  31.6%. Routes are still bunched; the split alone moved the cosine rules by
  2-4 points, so differences of about a point are noise.
- Facets: combined similarity AUC 0.87; best single facet F1 0.83;
  geography 0.53; company size 0.49 (chance), lift 0.01.
- A facet that does not apply is embedded as "none", so two such firms match
  exactly (1.00): F2 and F3 lift falls from 0.34 to 0.29 without those pairs; WEN's
  F3 is "none" and matches 17 of its 20 candidates, 16 judged bad.
- Size: error falls with firm size, median multiple barely moves, the LLM's
  verdict does not track size (AUC 0.498), and the same-category restriction
  hurts (32.1% against 29.6%).

## Tests

`python -m pytest tests -q` from `v0/`: 99 passed. The notebook executed end
to end with no errors.

## Open issues

- Size is not balanced between training and holdout under SIC2 (large 54%
  against 46%, among the largest 12% against 18%, small 3% against 6%).
- The holdout is untouched here. The original split is the team's recorded
  decision (2026-10-25); whether this one replaces it is a team decision.
- The judge reads the same facet text the embeddings are built from, so the
  facet AUCs are agreement with the LLM, not independent evidence. The size
  categories are coarse (small n=10, unknown n=2).
- Seven rows of `judge/tables/judgments.csv` name an archived candidates run
  (`20261027T190507Z`): three targets whose candidate list was identical under an
  earlier draw, so their judgments were reused.

## Next step

Build the golden set for PCTY and WEN by pooled labeling: the union of the
z >= 2 cosine candidates, the direct LLM picks, the LLM-then-cosine picks, a
few cosine ranks just below the cutoff and same-SIC4 peers, labeled blind to
rank, z, model verdicts and EV/EBITDA on a graded scale. Then compare the
routes' precision and recall on it. Decide with the team whether the SIC2 split
replaces the size-stratified one.
