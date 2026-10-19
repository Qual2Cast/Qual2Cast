# Integrated company analysis

Open `../../notebooks/integrated_company_analysis.ipynb` and run all cells. The notebook is the
only required project file. A concise reading summary is in `../../reports/integrated_company_analysis/README.md`.
Install the Python dependencies in `requirements.txt` in a virtual environment.

The report combines the team's current website, peer-selection, valuation and
growth-event stages with the previous whole-business experiments. The two
ten-company lists share PCTY, so there are 19 unique development targets.

## Execution and scope

- Default execution uses embedded captures, embeddings, activity scores and
  cluster labels. It recomputes peer selection and valuation for 134 primary
  configurations, 56 common-pool representation configurations, and 18 activity
  configurations; it also reruns event extraction and temporal/source features.
- Model inference outputs are cached, not recreated by default. New model
  inference needs separately installed libraries and the pinned model weights.
- The optional website refresh cell collects new HTTP captures into a separate
  directory. It does not replace the frozen experiment or silently refit models.
- Current candidate pools differ: 535 for the primary experiment, 529 for the
  representation comparison, and a conditional 190-company profile pool. The
  profile comparison has 18 eligible targets because DOX extraction failed.
- Earlier 31-method findings are preserved with their original samples and
  citations. They are not reported as fresh 19-company experiments.

## Findings requiring attention

Scale reranking reduces median APE from 42.63% to 23.86% on the 19 targets, but
the paired interval includes zero and business mismatches remain. On a separate
common-529 comparison with five peers, LSA gives 29.13% median APE versus 37.32%
for current MPNet. Activity methods trade median error against tail/mean error.
None is independently validated as the best business-matching method.

Growth collection attempted all 19 companies and obtained 55 articles. Strict
source/time gates leave one current event candidate, which still has an
article-attribution concern. There are no independently approved events or
completed forecasts. Real historical predictor vintages and revenue outcomes
are required; missing evidence is not encoded as zero growth.

## Review and integration

`peer_human_review.csv` contains 221 priority pairs with no selector or valuation
shown. `peer_human_review_full.csv` pools top-ten peers across all current arms
for a fair shared relevance evaluation. `growth_human_review.csv` is deduplicated
and hides extractor outputs, including articles with extractor abstentions.
Labels remain blank. These files are review queues, not completed evaluations.

To inspect or edit the embedded source and data outside Jupyter:

    python extract_bundle.py ../../notebooks/integrated_company_analysis.ipynb ../../outputs-local/integration-19-replay

The output contains `integration19/` (adapters and replay code),
`outputs-local/integration-19/` (inputs, caches, tables and pinned team sources),
`src/modular_validation/` (profile/transport methods), and `legacy/` (reference
implementations and results). Every file is checksum verified. Saved capture
paths and historical refit scripts can refer to the original research workspace;
they are provenance/reference material, not portable fresh-inference commands.
The notebook replay is the tested portable entry point.

Team main: 7f1f1fc2ddbed8f172b3c89c262d0e44bdfc81bf.
Growth recall: 023caabe1b0f0f062a90695dc642306449b3328a.
Approved snapshot: company_list_v3, unchanged.
See `VALIDATION.json` for execution and `REPRODUCIBILITY.json` for test evidence.
