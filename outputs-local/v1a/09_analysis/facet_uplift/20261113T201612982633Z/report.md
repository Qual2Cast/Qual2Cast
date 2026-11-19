# Exploratory facet lift

293 reviewed pairs, 45 targets, Barbara only.

Outcome: expected human grade on 0/1/2 scale. Effect units: rating points.

Complete five-fold analyses: B3 11/11; agent 5/11. Partial and unsupported facets remain in facet_summary.csv; missing effects are not zero.

Use the companion notebook for estimates, missingness and fold support. Unsupported facets are retained in the summary. Brier/AUC (binary) or MAE/RMSE (rating) assess response predictions, not accuracy of treatment effects. Rating analysis assumes equal spacing between grades; it does not estimate separate category probabilities. DR bins are adjusted diagnostics, not effect ground truth. Do not use uplift to rank comp quality or add effects across correlated facets. No causal identification, unreviewed-universe generalization, or pipeline improvement is established.
