# 2026-10-27: sector sub-models and facet add/drop eval (Fiona)

## Changes

- `v0/reference/Siccodes49.txt`: Ken French's FF49 definitions (the file
  Barbara used for growth base rates).
- `v0/sectors.py`: FF49 lookup, eleven sector groups, sector similarity.
  On the 560 list: Softw 73, BusSv 66, Drugs 35, Mach 31, Fin 28, Insur 26,
  MedEq 23, ...; no company falls in "other".
- `v0/sector_facets.py`: sub-sector (text) for every company; 2-5 category
  facets per group from Barbara's framework section 2 (ours where her
  framework has no section).
- `v0/fill_sector_facets.py`: Haiku fill, training only by default.
- `v0/facet_eval.py`: variants (generic, generic minus each facet, +sector,
  +sub-sector, +sector-specific facets, sub-model restricted to the sector
  group) scored against golden-set and judge labels.
- `v0/tests/test_sector_submodels.py`: 22 tests. Whole suite: 120 passed;
  `test_facet_texts_marks_not_applicable_and_unknown` fails on main too
  under pandas 3 (NaN vs None), not touched here.
- Smoke run of `facet_eval.py` on synthetic facets and a synthetic gold
  file (fake embeddings): every variant runs and writes its tables. No real
  numbers yet.

## Later the same day

- Sector facets made evidence-first after Aziz ("totally avoid relying on
  LLM memory only"): saved pages by default, `--evidence` for a deeper crawl
  and web search; cites per facet; memory flagged. 24 tests pass.
- `sectors.sic_similarity`: SIC4 sub-sector without an LLM.
- `facet_eval.py --stage comps_pilot_targets` runs on Michael's updated
  baseline (PR #15, SIC2 split). Results in v0/README.md. Michael's own
  per-facet analysis (notebook section 7) agrees: F9 size and F8 geography
  are weakest.
- Data: universe/facets from `outputs-local/comps/`, split and judge from
  `outputs-local/comps_pilot_targets/` (split run 20261027T204930Z).
- A Codex backend for `fill_sector_facets.py` was started and paused (not
  committed).

## Open / next

1. Needs Michael's `outputs-local/comps/` (universe, split, facets.csv,
   judge tables) and an API key to fill the sector facets.
2. Needs the golden set (Kethan) as a pairs file.
3. Then: fill, run `facet_eval.py`, keep the facets whose removal hurts and
   the sector additions that help; if the sub-model wins, use its ranking as
   the step 4 candidates and rerun the judge with the 2/1/0 rubric.
