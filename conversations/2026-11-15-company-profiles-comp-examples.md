# Company profiles and comp examples page — 2026-11-15

## Changes

- Added `v1/company_profiles_and_comp_examples.html`, a self-contained interactive review page for company profiles and selected comparable-company examples.
- For each target, the page keeps its filled facet profile visible, shows counts of the curated comps by Barbara's review grade, lets the reader select a grade and comp, and shows the selected pair's facet comparison.
- Each pair displays Barbara's grade and the agent's final label above the facet table.

## Data and provenance

- The 13 displayed pairs and their labels are drawn from the 45-target / 293-pair agent-ranking cohort. The page contains 18 profiles used by those examples.
- Counts are for the examples displayed on the page, not all reviewed pairs for each target.
- No source data, reviewer labels, model outputs, or selection logic were changed.

## Validation

- No tests run; this change adds a static HTML artifact with client-side controls only.
- Git status before commit contained only the new HTML page; this handoff and the `PROJECT_STATE.md` entry document the artifact.

## Open issues and next step

- The page is a local HTML artifact. Share or host it separately if Aziz needs a URL accessible outside the repository.
- Next: push this page and its handoff documentation on `main`.
