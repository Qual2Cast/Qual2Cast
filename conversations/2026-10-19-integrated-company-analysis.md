# 19-company integration experiment

Added a standalone notebook integrating the main website/matching pipeline and
the separately pinned growth-recall branch. The original ten-company notebook
is retained unchanged. Main is pinned at `7f1f1fc`; recall at `023caabe`.
The approved `company_list_v3` snapshot is unchanged.

The combined sample contains 19 targets. Added selection adapters, common-pool
representation comparisons, whole-business activity comparisons, permitted
financial-factor reranking, source/time gates, a decimal-window regression
repair, and blind review queues. The notebook has 134 primary, 56 common-529
representation and 18 conditional profile configurations. Previous methods
remain explicitly labeled as reference experiments.

Validation: 33 code cells executed, zero errors, five figures; 14 new regression
tests passed, including extracted-bundle checks. Main website/growth tests:
96 passed. Recall branch tests: 169 passed. Default replay uses cached model
outputs and recomputes selection, valuation, event extraction and features.

Unresolved: no independent human labels, uncertain valuation dates/definitions,
DOX profile failure, business-role mismatches after factor reranking, sparse
eligible growth evidence, and missing historical predictor/revenue panels.
The supplied current evidence does not support a growth forecasting claim.

Recommended next step: label the shared review pool, resolve mismatches, obtain
historical data, and evaluate on later unseen observations before adopting a
method. This integration does not merge or rewrite the team's baseline modules.
