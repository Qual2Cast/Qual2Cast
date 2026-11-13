# Preserve 0/1/2 outcomes alongside combined peer analysis

User requested retaining original grades, keeping the current combined analysis
and making the methodologies easily separable in the stakeholder notebook.
Changes remain in the main worktree; the original technical notebook is untouched.

The runner's `--outcome rating` fits ridge response models to human grades 0/1/2,
clipping expected outcome predictions to [0,2] before cross-fitted pseudo-effects
and evaluation. Ridge effect models are unbounded. It uses logistic propensity
and the same treatment assignment, feature sources, group folds, support checks,
missing treatment exclusions, weights, overlap and bootstrap as the peer version.
`--outcome peer` remains the default and keeps logistic response models. Binary
results reproduce earlier saved OOF effects/propensities/responses/DR scores to
1e-12 tolerance. No combined peer files were overwritten.

Rating requires treating score increments 0→1 and 1→2 as equally meaningful.
The result is expected-rating lift in rating points, not a three-class probability
distribution or direct-peer-only effect. MAE/RMSE and training-mean baseline errors
replace Brier/AUC in the rating response diagnostics. Generic prediction columns
avoid calling expected grades probabilities. Manifests record outcome and units.

Executed rating run: `20261113T201612982633Z`; binary run preserved:
`20261113T190330202875Z`. Both have identical pair features, folds and support;
retained overlap counts are also unchanged. Some effect differences reflect the
response-estimator change as well as the outcome change.

The stakeholder notebook is organized as shared design, Method A numerical
ratings, Method B combined peer/non-peer, shared evidence support, cross-method
comparison and appendix. Each method has separate explanations, plots, findings,
sensitivity and prediction diagnostics. The prior stakeholder edition is in the
binary run's ignored history directory. Eight exported figures plus a manifest
of both runs' inputs are saved under the rating run's presentation timestamp.

Main observations in rating points: B3 customers +0.247, end markets +0.242,
services +0.230, products +0.165 (positive in stricter contrasts too). Core
offering +0.002 and value-chain -0.001 are near zero, unlike their binary results.
Agent end markets +0.175, geography +0.140, business model +0.102, customers
+0.101, value-chain -0.005 among complete analyses. Agent products +0.446 and
services +0.349 are partial, retaining only 41/25 pairs and 18/9 targets. Do not
promote these large partial estimates into proven facet importance. Agent
customers' rating DR diagnostic is -0.106, opposite its X-learner estimate.

Validation: seven offline statistical checks, including a +0.6 known rating-point
effect and proper metrics/bounds; original binary parity comparison; executed
notebook; source hash/original-notebook integrity; visual inspection of figures.
No model API calls, reviewer data updates, financial reads or pipeline changes.
The available local venv was used; no packages installed or full suite run.
