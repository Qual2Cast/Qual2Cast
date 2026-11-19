# 03_retrieval: Retrieval (B3)

Ranks every training company as a comp for each target. B3 compares each facet with 50% MPNet embedding cosine and 50% TF-IDF cosine, weights facets by information, and keeps mutual top-10 comps, topped up to 3. Company size is left out. The current variant adds Fiona's sub-sector facet.

**Status (2026-11-19): ported.** Scripts, tests and `retrieval.ipynb` are in place; the notebook reproduces the saved v1 numbers (4/4 checks pass).

## Current setting (`v1a/current.toml`)

- `method` = `B3`
- `variant` = `Sonnet + Fiona sub-sector`
- `rule` = `mutual top 10, topped up to 3`
- `excluded_facets` = `['company_size']`
- `candidates` = `outputs-local/v1a/03_retrieval/selector_candidates`

## Outputs (`outputs-local/v1a/03_retrieval/`)

- `facet_add_drop_eval/` (6 files)
- `selector_candidates/` (3 files)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/b3_facet_add_drop.py` (script): Eric: Sonnet + Fiona sub-sector (current list)
- `v1/scripts/candidates.py` (script): embedding helper used by B3
- `v1/scripts/facet_eval.py` (script): facet matrices/rank metrics
- `v1/scripts/facet_weighting.py` (script): B3 math
- `v1/scripts/method1_candidates.py` (script): B3 lists
- `v1/scripts/sectors.py` (script): FF49/SIC similarity
- `v1/scripts/similarity_eval.py` (script): method comparison
- `v1/scripts/tests/test_b3_facet_add_drop.py` (test)
- `v1/scripts/tests/test_comps.py` (test)
- `v1/scripts/tests/test_facet_weighting.py` (test)
- `v1/scripts/tests/test_similarity_eval.py` (test)
- `v1/scripts/reference/Siccodes49.txt` (reference): FF49 codes for sectors.py
- `v1/notebooks/similarity_methods.ipynb` (notebook)

Commit authors of these files (git): EFL-YL, mcschlatt.

## Notes

- `method1_candidates.py` builds the current variant from `current.toml` (new runs: `candidates/<time>/`). It
  reproduces `selector_candidates/`: the same 2,538 selected pairs; in the full ranking, 5 pairs of exact ties
  swap order, all beyond rank 10. In v1 the current list came from `b3_facet_add_drop.py --export-variant`.
- `b3_facet_add_drop.py` no longer reads v1's Sol grades of holdout pairs unless `--v1-holdout-diagnostic`. The v1a
  run `facet_add_drop/20261118T225043Z` (180 rows) equals v1's table without its 30 holdout rows; with the flag the
  210 rows are identical.
- Embedding vectors are read from the v1 caches; new ones go to `cache/` (kept local).
- Method 2 (FAME-inspired gate, 11-03) tied with B3 twice (11-03, 11-10) and was not kept as a second method; its
  code stays in `facet_weighting.py`. Details in the notebook's history.
- Run: `uv run pytest v1a/03_retrieval/tests -q`; open `retrieval.ipynb`.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `retrieval.ipynb` ported; v1 numbers reproduced.
- 2026-11-19: `v1/notebooks/similarity_methods.ipynb` ported into `retrieval.ipynb` sections 3.3-3.9 on the current
  facets (Sonnet + Fiona sub-sector): diagnostics, B0 -> B3 build-up (its B3 step equals the current list, checked),
  BM25 charts, list sizes, golden-set charts and tables, per-reviewer check, B3 per-facet contributions (redone from
  method 2's chart) and the build-up on dev_293. Left in v1: method 2, Sol holdout grades, valuation (08), the
  facet-label check on Haiku texts, the round-2 sheet. Finding: on the current facets B3 lists Lamb Weston (0) for WEN.
