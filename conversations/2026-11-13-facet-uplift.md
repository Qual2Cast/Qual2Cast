# Exploratory X-learner for facet lift

User selected option 1: compare which facet signals are associated with favorable
human comp labels, analyzing B3 components and agent evidence ratings separately.
Work is on the `main` worktree, based on `44727659`; no edits in `kethan/wip`.

Implementation: `facet_uplift.py` builds a numerical pair-feature table from the
same Sonnet general profiles as the saved agent run and the agent's saved 293-pair
facet ratings. Company size stays excluded. Overall agent grades, S/E, total B3,
rank and label notes never enter models. Neither the matching routes nor their
default rankings changed. Candidate selection was the Sonnet + Fiona sub-sector
shortlist; the selected sample is not representative of arbitrary company pairs.

Five outer folds split by target. Inner target folds generate pseudo-effects
without own-target outcomes. Logistic response/propensity and ridge effect models
use equal target weights and fixed regularization. Primary B3 treatment is above
versus below/equal training median; primary agent treatment is 75/100 versus
0/25/50. Sensitivities use extreme thirds or 75/100 versus 0/25. Missing treatment
scores and strict-contrast middle values are excluded, not imputed as controls.
Covariates use training-only imputation/indicators/scaling. Small arms/folds are
recorded as unsupported. See `v1/FACET_UPLIFT.md` for full definitions.

Executed run: `outputs-local/v1/facet_uplift/20261113T190330202875Z/`, notebook
pinned to that run. Input/script/cache hashes and library versions are saved.
First exploratory run was moved under the ignored history folder. Text embedding
cache is local-only; newly needed embeddings used the locally installed MPNet
model with `local_files_only=True` and offline environment flags. No model API,
network search or financial table access.

Complete primary analyses: B3 11/11; agent 5/11. Agent products (4 folds) and
services (3 folds) are partial; distribution channels, regulation, revenue model
and specialization lack sufficient arm support. Missing estimates are retained
in the summary. Conditional fixed-prediction bootstrap ranges are not full CATE
confidence intervals; reviewer, fitting, selection, threshold and multiplicity
uncertainty remain. The comparisons have different eligible populations and
treatments, so cross-source magnitudes are not directly comparable. Uplift is not
absolute comp quality and should not replace the current score or be summed.

Validation: five test functions passed via a direct runner (pytest not installed
in the existing Python 3.14 venv); notebook executed with nbclient and chart
visually reviewed. Local socket permission was needed for its Jupyter kernel.
The project's pinned Python 3.12 environment/full suite was not run. No packages
were installed. Existing data and saved pipeline outputs remain unchanged.

Next: inspect effect/support and sensitivity diagnostics with the team. More
independent reviewer labels and target coverage are needed before a claim of
stable facet usefulness. Pipeline changes require a separate controlled ablation
on new labels. A randomized information experiment would answer a different,
causal question about exposing reviewers to facets.
