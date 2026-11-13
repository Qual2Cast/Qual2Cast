# Stakeholder notebook for the facet-lift experiment

User requested a new presentation notebook, preserving the original as the
raw/older version, and a detailed explanation of results. Work remains local
on the main worktree. `facet_uplift.ipynb` was not edited; its hash was checked
before and after authoring. No changes were made to model fitting or raw data.

`facet_uplift_stakeholder.ipynb` reads the pinned run
`20261113T190330202875Z` and creates a fresh `presentation/<timestamp>/` on each
execution. Six PNGs show the approach, review cohort, grouped train/evaluation
design, primary estimates and retained support, threshold sensitivity, and agent
evidence/match balance. Each export has a manifest with source CSV hashes. The
notebook is executed with saved charts and narrative, plus a technical appendix.

The label mix is 91 non-peers, 178 adjacent and 24 direct; combined peer outcome
202/293. Largest primary B3 estimates are services +23.7 pp, end markets +21.3,
customers +20.2, products +14.7. These remain positive under the stricter
contrast, but estimates refer to different retained populations. Their retained
primary counts are respectively 174, 274, 280 and 163. Geography is near zero,
sales channels are small/sign-sensitive, and value-chain position is negative.

Five agent facets have complete analyses: end markets +10.7 pp, geography +9.0,
customers +8.9, business model +8.3, value-chain position +8.2. Products/services
are partial, with only 20/19 strong-match pairs overall and 41/25 retained
effect-summary cases. Four facets have no supported estimates. Revenue-model,
regulation and channel evidence is mostly missing; specialization also lacks
strong-match examples. Do not infer zero usefulness from unsupported analyses.

Agent customers have a primary X-learner estimate +8.9 pp but DR diagnostic
-3.1 pp; this is presented as a sensitivity concern. B3/agent effect sizes cannot
be compared directly because treatment definitions, evidence and populations
differ. Intervals bootstrap fixed predictions and omit model refits, reviewer,
selection and threshold uncertainty. This is association with one reviewer's
labels, not identified causal CATE, a proven facet ordering or valuation uplift.

Validation: execute all notebook cells through nbclient; verify exported chart
count and source CSV hashes; inspect rendered figures; confirm original notebook
and experiment CSVs unchanged; run git diff whitespace checks. Existing local
Python 3.14 venv used; a Jupyter kernel required local socket permission. No
dependency installation, refitting, API calls, new reviewer data or full test run.

Next investigations are new independent labels and frozen ablations for the
four B3 priority hypotheses, additional agent evidence/support, and case review
of cross-source/diagnostic disagreements before changing pipeline weights.
