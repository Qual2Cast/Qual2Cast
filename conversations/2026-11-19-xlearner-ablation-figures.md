# 2026-11-19: X-learner as an ablation, figures and findings page (v1a 09)

Request (Michael): point to the X-learner outputs and graphs in the new pipeline, as Kethan did in v1, to use
the X-learner as an ablation mechanism; summarize the team's findings since v0 in simple technical English.

## Changes

- `v1a/09_analysis/scripts/facet_uplift.py`: new stage treatment `agent_grade` (the agent's overall grade 1/2 vs 0,
  from the current agent run's `verdicts.csv`; ungraded pairs omitted), adjusted for the 12 B3 signals, beside the
  existing `selector` treatment. Only with a human outcome. Estimator unchanged.
- Figures: first written as a separate script (`facet_uplift_figures.py`), then retired on Michael's direction:
  keep teammates' graph/table code close to the original, with results inline in the notebook. `analysis.ipynb`
  section 3 is now Kethan's stakeholder notebook ported cell by cell (run paths from `current.toml`; `score_barbara`
  -> `grade`; `NAMES` gains `sub_sector`; typed counts 44 / "11 complete" computed; missingness chart from his
  technical notebook saved with the other figures instead of the run folder) plus Method C (selector keep) and a
  stage-ablation plot made with his functions. 11 figures inline; copies under the rating run's `presentation/`.
- `v1a/current.toml`: `human_peer` -> `20261119T031027158914Z`, `human_rating` -> `20261119T031040215833Z`.
  Each equals the earlier pin (`...021242064364Z`, `...021253830100Z`, still on disk) plus the `agent_grade` row.
- `analysis.ipynb`: question 4 and the ablation framing in the intro, stage table (both stages, with the DR
  cross-check), two new checks; executed. README changelog updated.
- New test `test_agent_grade_is_a_stage_treatment_adjusted_for_b3_only`.

## Results (dev_293)

- Facet ablation: unchanged from the earlier pins (services +24 pp, end markets +21, customers +21, products +15
  for people; the selector keeps on sub-sector and offering description).
- Stage ablation: agent grade +49.9 pp (45.2-54.3; DR +48.3), +0.46 grade points; selector keep +4.0 pp
  (0.1-7.6; DR -9.7), +0.15 grade points (DR -0.06). The selector estimate disagrees with its DR check.
- Caveat: the agent grades with the reviewers' rubric and its ranking order was chosen on these labels.

## Tests and data

- v1a tests: 263 pass. Notebook checks 14/14. Snapshot `company_list_v3`; no model calls, no financial reads in 09.
- A first figure folder from this session (`20261119T031205470886Z`, a draft with clipped footnotes) and two empty
  folders from a failed render were deleted; the script now draws before it creates its folder.

## Outputs

- Figures: inline in `v1a/09_analysis/analysis.ipynb`; PNG copies in
  `outputs-local/v1a/09_analysis/facet_uplift/20261119T031040215833Z/presentation/`. The retired script's set is in
  `facet_uplift/history/figures_retired_2026-11-19/`.
- Findings page (private artifact, share from its Share menu): https://claude.ai/artifact/Qzu78vEfeptoNdvWthtrXp

## Next

- Same treatment for the other components, whose ports dropped most v1 plots: 03 retrieval (similarity_methods,
  8 figures), 08 valuation (comps_and_valuation, 23), 02 profiles (business split evals, 4), 07 judges
  (peer_evaluation, 2). Keep cells that fit the current facet data; leave Haiku-era-only parts in v1.

- Selector prompt that weighs services, customers and end markets; check it with the selector-outcome facet
  ablation (orange should move toward blue in figure 1).
- Report each new stage's lift beyond B3 before adopting it.

## Follow-up: every component (same day)

Michael: keep everyone's graph/table code as close to the original as possible, adapt to the current facet data,
results inline in the notebooks, nothing deprecated. Done per component (port scripts were one-off, in scratch):

| component | from v1 | adapted | left in v1 |
|---|---|---|---|
| 01 | comp_universe_and_facets 1-2 | dropped list without multiples | - |
| 02 | comp_universe_and_facets 3.1, 3.3 | Sonnet fills | facet_fill_runs, business split evals |
| 03 | similarity_methods; comps_and_valuation 2 | 12 facets incl. sub-sector (weight 1); readings rewritten; label share over all firms (fixes an empty-slice warning); mutual marks instead of z | method 2, Sol holdout, valuation, facet-label check, sheet |
| 04 | comps_and_valuation 8 | B3 facet scores, current selector | F9, shared-"none" view |
| 05, 07 | peer_evaluation 7.2 | 0-2 rubric; by Barbara's grade | 0-3 evaluator on v0 lists |
| 08 | comps_and_valuation 7 | current rules | v0 routes, holdout, size, integration 13-23 |
| 09 | facet_uplift_stakeholder (+ technical missingness) | 12 signals, Method C, stage ablation | - |

Checks: all notebooks execute with no stderr output; 03's B3 step equals the current list; v1a tests 267 pass.
Not done: 06 (v1 golden-set notebooks had no saved plots; tables already covered).
