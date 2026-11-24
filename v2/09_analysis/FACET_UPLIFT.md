# Exploratory facet lift: X-learner

## Two outcome methods (updated 2026-11-13)

The stakeholder notebook now presents two separate analyses, with shared study
design followed by each method's definition, models, results, sensitivity and
diagnostics, then a comparison and recommendations:

- **A: original 0/1/2 rating**, run with `--outcome rating`. Non-peer=0,
  adjacent=1, direct=2. Separate ridge response models (alpha=10) predict expected
  grades, clipped to [0,2] before pseudo-effects and evaluation. Lift is in rating
  points; MAE/RMSE assess response predictions against a training-mean baseline.
  This assumes equal distance from 0 to 1 and 1 to 2; it is not a multiclass
  probability model or a direct-peer-specific analysis.
- **B: combined peer/non-peer**, `--outcome peer` (the unchanged default).
  Grades 1/2 map to peer=1, grade 0 maps to non-peer=0. Logistic response models
  predict peer probabilities; lift is a probability difference, displayed as
  percentage points. Brier/AUC assess response predictions.

Treatments remain binary in BOTH methods. Features, thresholds, propensity
model, target folds, missing handling, arm support, weighting, overlap filter,
ridge effect models and bootstrap settings are shared. The response estimator
changes appropriately with the outcome, so cross-method changes are not solely
the effect of label coding. The effect models are not clipped; effects outside
[-1,1] for peer or [-2,2] for rating are flagged, not literal probability/grade
changes.

Pinned rating run: `20261113T201612982633Z`; preserved binary run:
`20261113T190330202875Z`. The original technical notebook is byte-for-byte
preserved. The prior stakeholder edition was archived in the binary run's ignored
history directory. At the user's request the full X-learner outputs, embedding
cache and preserved history are shared in Git. Eight new presentation figures and a manifest for both inputs
are saved beneath the rating run's `presentation/<timestamp>/`.

For rating outputs, `outcome_value` is the original human grade and
`predicted_outcome` / `baseline_outcome` are expected rating predictions.
There are no probability-named rating prediction columns. Binary reruns also
retain the earlier probability-named columns for compatibility. The manifest
records outcome mode, effect units and response estimator. The older binary
description below remains the reference for the shared design and original run.

Question: within the reviewed candidate pairs, how does the probability of a human
peer rating differ between strong and weak matches on a facet, accounting for the
other facet scores? This is option 1, an offline diagnostic. It does not alter
B3, the LLM filter, the agent ranking, company profiles, or financial evaluation.

Run from the repository root:

```sh
uv run python v1/scripts/facet_uplift.py
```

For stakeholder review, open `v1/notebooks/facet_uplift_stakeholder.ipynb`.
The original `v1/notebooks/facet_uplift.ipynb` remains the technical/raw version.
Both read the same pinned saved result; neither calls models or executes the
experiment on Run All. The stakeholder notebook exports eight PNGs: approach,
cohort, target validation, separate outcome-specific effect/sensitivity plots,
and shared agent support. These go into a new `presentation/<timestamp>/` within
the rating run. An export
manifest pins the source CSV hashes. Recommendations are follow-up hypotheses,
not an automatic weight update or established causal conclusions.
The script needs the locally cached `all-mpnet-base-v2` model on its first run;
`local_files_only=True` prevents downloading it. Subsequent runs reuse an
experiment-specific text cache. No LLM, search, or financial data is used.

## Inputs and questions

- Human outcomes: `integration/review/pairs.csv`, 293 unique pairs, 45 targets,
  Barbara only. Peer = grade 1 or 2; grade 0 is non-peer. This is not consensus
  gold. Unreviewed pairs and earlier reviewer cohorts are not added as negatives.
- B3 source: Sonnet general profiles, the same profile condition used by the
  saved agent scoring run. Eleven per-facet signals are the existing 50/50
  embedding/TF-IDF blend, before information weighting and final combination.
  These are not pure embedding cosines. TF-IDF uses the frozen 533-company
  unlabeled universe, consistent with the current transductive retrieval setup.
- Agent source: the saved `ranking_45targets_sonnet/verdicts.csv` facet ratings.
  Null stays unknown; 0 remains an evidenced mismatch. Failed pairs contribute
  missing features, never inferred ratings. Overall grade, S, E, B3 total, rank,
  reviewer notes and identifiers are excluded from predictors.
- Sources are analyzed separately using their own other-facet scores as context.
  Agent `business_model` and B3 `offering_description` have different meanings;
  they are not silently renamed into an equivalent feature. Unknown/not
  applicable products and services remain missing in B3.

## Estimator and validation

The standard X-learner needs binary treatment. Defaults are declared in advance,
not chosen by the best observed lift:

- Primary B3: above versus at/below the outer-training median for that facet.
  Sensitivity: upper versus lower third; omit the middle. Tied cutpoints in the
  sensitivity produce no estimate.
- Primary agent: 75/100 (strong) versus 0/25/50 (mismatch, weak, adjacent).
  Sensitivity: 75/100 versus 0/25; omit adjacent 50. Unknown is omitted from
  treatment assignment in both. The two sources have different contrasts and
  eligible populations, so their effect magnitudes are not directly comparable.

Five deterministic outer folds hold out whole target companies. Within each
outer training fold, three further target folds generate cross-fitted
pseudo-effects: D1 = Y - predicted control outcome, D0 = predicted treated
outcome - Y. The response models and propensity model are regularized logistic
regressions (C=0.1). Separate ridge regressions (alpha=10) model D0 and D1.
The final estimate is e(X)*tau0(X) + (1-e(X))*tau1(X).

Other-facet covariates use training-only median imputation, missingness indicators
and scaling. IDs never enter models. Models give each training target equal total
weight. At least 15 rows across five targets per arm are required, including for
second-stage usable pseudo-effects. Sparse folds are recorded, not force fitted.
Constant-response arms predict their observed constant. Treatment thresholds,
imputers and estimators never use held-out outcomes. A comp company can occur in
multiple target folds: this assesses new-target performance within the shared
company universe, not generalization to entirely unseen entities.

Only OOF cases with estimated propensity 0.1–0.9 enter effect summaries. Targets
with retained cases receive equal weight. The 1,000-replicate target bootstrap
holds fitted OOF predictions fixed; its interval excludes refit, threshold,
reviewer and candidate-selection uncertainty. It is not a full CATE confidence
interval or a multiple-testing-adjusted significance test.

The analysis also saves doubly robust pseudo-effects, using propensity clipped to
0.05–0.95, and descriptive uplift thirds. They are adjusted diagnostics, not
observed treatment-effect labels. Brier/AUC measure response prediction, not
accuracy of the uplift estimates. No method is chosen by these results.

## Outputs

Each execution creates `outputs-local/v1/facet_uplift/<timestamp>/`:

- `pair_features.csv`: only IDs, human outcome and the two numerical signal sets.
- `oof_effects.csv`: per-pair held-out effects, propensity, overlap flag, response
  probability and adjusted diagnostic. It is not a comp recommendation list.
- `fold_diagnostics.csv`: train/test counts, thresholds, unknown/middle exclusions,
  arm target counts and explicit unsupported reasons.
- `facet_summary.csv`: denominators, fold completeness, overlap, target-average
  lift, fixed-prediction bootstrap intervals, DR reference and response diagnostics.
- `uplift_bins.csv`: descriptive predicted-versus-adjusted differences by thirds.
- `manifest.json`: input/script hashes, commit and estimator settings.
- `report.md` and notebook plots explain the observed support and limitations.

All source labels/profiles and historical outputs remain untouched. A shared cache
under `facet_uplift/cache/` holds only text-keyed embeddings, included with the full
experiment outputs in Git so the saved representations are available to the team.

## Interpretation

Positive lift means a stronger facet match is associated with more favorable
human labels after adjustment, within this selected review cohort. It does not
establish causal CATE: match status is not randomized; facets overlap; candidate
selection and unmeasured company traits can confound the comparison. This also
does not measure valuation uplift or improvement of either matching pipeline.
Do not rank comps by uplift, sum effects across facets, treat missing agent
evidence as weak similarity, or claim a stable winner from narrow intervals.
Partial/unsupported analyses should guide additional labeling rather than a new
default weighting scheme.

Method reference: Künzel et al. (2019),
[Metalearners for estimating heterogeneous treatment effects using machine learning](https://pmc.ncbi.nlm.nih.gov/articles/PMC6410831/).
