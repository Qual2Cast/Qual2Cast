# Sector facets on the fixed v0 holdout — 2026-10-28

## Scope and data

This local comparison adds one feature configuration, Fiona's existing
`generic + all sector facets` variant, to the six existing peer-selection
routes. The general-facet results remain saved and unchanged. Company IDs and
financials use `company_list_v3`; the eligible universe is 533 public firms,
with 373 training peers and 160 fixed SIC2 holdout targets. Sector definitions
are `v0/sector_facets.py` version `2026-10-27b`. GPT-6.1 Sol filled the sector
values from saved website evidence; source profiles flag memory-only fields.

The added features are FF49, SIC4, sub-sector text, and sector-specific
categories. Equal available-facet weights and the original top-ten-or-z≥2
candidate rule remain fixed. The original binary and direct LLM stages were
rerun with the new features. The source-cited 0–2 judge retains the shared
rubric and grades the new candidate pool. EV/EBITDA valuation is unchanged.

## Results

The new ranking has 2,470 z≥2 pairs versus 2,138 with general facets. All 160
holdout targets completed; 2,315/2,470 candidate pairs received numeric 0–2
grades. The six new rows and the six saved comparison rows are in
`v0/notebooks/comps_and_valuation.ipynb`, Section 7. Results and raw calls are
under `outputs-local/comps_pilot_targets/sector_facets/`.

| Route | General facets: coverage, median APE | Fiona facets: coverage, median APE | Median paired APE change |
|---|---:|---:|---:|
| Cosine z≥2 | 160, 37.32% | 160, 34.97% | −1.94 pp (95% bootstrap −3.81 to +0.25) |
| Binary LLM judge | 110, 37.95% | 114, 32.82% | 0.00 pp (107 common targets) |
| Direct LLM | 119, 33.78% | 117, 34.00% | 0.00 pp (114 common) |
| LLM then cosine | 119, 33.78% | 117, 33.78% | 0.00 pp (114 common) |
| Graded judge: 2 only | 116, 37.18% | 120, 34.80% | 0.00 pp (113 common) |
| Graded judge: 2 then 1 | 155, 37.32% | 156, 36.64% | −0.02 pp (155 common) |

The no-matching control remains 39.92% on all 160 targets. On PCTY/WEN's 32
majority-labeled pairs, reviewer pairwise ranking accuracy rises from 0.851
to 0.904. That pilot has only two targets; lower unpaired holdout medians do
not establish a consistent improvement across the six routes.

## Verification and next step

The notebook is valid and every code cell parses. The new comparison cell
replays the saved grades and reproduces both result tables; the no-matching
target errors are identical across configurations. The 33 targeted tests pass.
The new candidate generator reproduces the saved generic embedding scores
within `7.44e-7`. No files were uploaded in this work. Next: team review of
the paired results and independent holdout peer labels before adoption.
