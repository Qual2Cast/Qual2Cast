# 02_profiles: Company profiles (facets)

Each company's business-model profile. The 12 general facets are filled by Sonnet 5.5 from the company name and model knowledge, then gap-filled from the saved website pages (prompt `2026-10-25k`). Also Fiona's sector facets (her sub-sector feeds B3), Barbara's SIC2 industry facets (not in B3), the multi-business split, and facet evidence checks.

**Status (2026-11-19): ported.** Scripts, tests and `profiles.ipynb` are in place; the notebook reproduces the saved v1 numbers (7/7 checks pass).

## Current setting (`v1a/current.toml`)

- `general` = `outputs-local/v1a/02_profiles/facets_sonnet/tables/facets.csv`
- `general_prompt_version` = `2026-10-25k`
- `sector` = `outputs-local/v1a/02_profiles/sector_facets_sonnet/tables/sector_facets.csv`
- `industry` = `outputs-local/v1a/02_profiles/industry_facets_sonnet/tables/industry_facets_long.csv`
- `corrected_general` = `outputs-local/v1a/02_profiles/facets_sonnet_corrected.csv`
- `website_pages` = `outputs-local/website_scrape/page_text`

## Outputs (`outputs-local/v1a/02_profiles/`)

- `facets_sonnet/` (4 files)
- `facets_sonnet_corrected.csv` (1 file)
- `industry_facets_sonnet/` (1 file)
- `sector_facets_sonnet/` (1 file)

Seeded from v1 tables; raw per-call folders stay in `outputs-local/v1/` (see `outputs-local/v1a/seed_manifest.json`).

## Comes from v1

- `v1/scripts/business_split.py` (script): multi-business split
- `v1/scripts/business_split_refinement.py` (script): split refinement
- `v1/scripts/facets.py` (script): 12-facet schema, prompt 2026-10-25k
- `v1/scripts/fill_facets.py` (script): Sonnet fills (Matthew/Richard); --companies (Fiona); Codex wrapper (Kethan)
- `v1/scripts/fill_industry_facets.py` (script): Barbara SIC2 industry facets
- `v1/scripts/fill_sector_facets.py` (script): Fiona sector facets
- `v1/scripts/industry_facets.py` (script): Barbara SIC2 industry facets
- `v1/scripts/sector_facets.py` (script): Fiona sector facets
- `v1/scripts/source_split_benchmark.py` (script): split source check
- `v1/scripts/tests/test_business_split_refinement.py` (test)
- `v1/scripts/tests/test_sector_submodels.py` (test)
- `v1/scripts/verification/evidence.py` (verification)
- `v1/scripts/verification/gold_from_labels.py` (verification)
- `v1/scripts/verification/pages_only_fill.py` (verification)
- `v1/scripts/verification/README.md` (verification)
- `v1/scripts/verification/retrieve.py` (verification)
- `v1/scripts/verification/tests/test_gold_from_labels.py` (verification)
- `v1/scripts/verification/tests/test_retrieve.py` (verification)
- `v1/scripts/verification/tests/test_verification.py` (verification)
- `v1/scripts/verification/verify_with_evidence.py` (verification)
- `v1/scripts/reference/sic2_industry_facet_dictionary.md` (reference)
- `v1/notebooks/business_split_refinement_eval.ipynb` (notebook)
- `v1/notebooks/business_structure_eval.ipynb` (notebook)
- `v1/notebooks/facet_fill_runs.ipynb` (notebook)

Not from v1 on main:

- `v1/scripts/fill_facets.py` from `kethan/wip`

Commit authors of these files (git): mcschlatt, Fiona Shao, zynskibud.

## Notes

- 98.5% of the general facet values come from model knowledge; 10 companies have website-sourced values, because
  the website pass only runs for facets the first pass left unknown. The scraped pages are cited mainly by the
  agent loop (05) and Fiona's sector facets.
- `facets_sonnet_corrected.csv` is the Sonnet table with Yiming's divestiture corrections (42 companies, 116 values,
  flagged `divestiture_corrected`; built by v1's `integration_sources.py`). Kept, not the default.
- New fill runs write to `facets_new/`, `sector_facets_new/` and `industry_facets_new/`, never over the current
  tables. The business-split inputs (pilot snapshot, source corrections) and the Haiku fills stay in the v1 record.
- `split_peer_eval.py` and `source_scope_sensitivity.py` read EV/EBITDA, so they move to `08_valuation`.
- Run: `uv run pytest v1a/02_profiles/tests v1a/02_profiles/scripts/verification/tests -q`; open `profiles.ipynb`.

## Changelog

- 2026-11-18: component created; outputs seeded from v1.
- 2026-11-18: scripts, tests and `profiles.ipynb` ported; v1 numbers reproduced.
