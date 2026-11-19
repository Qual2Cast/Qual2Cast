# Exploratory facet lift

293 pairs, 45 targets, cohort dev_293, features current.

Outcome: the LLM selector kept the comp (claude-sonnet-5-5, prompt 2026-11-04a). Effect units: probability difference.

Complete five-fold analyses: agent 5/11; b3 12/12. Partial and unsupported facets remain in facet_summary.csv; missing effects are not zero.

Brier/AUC (binary) or MAE/RMSE (rating) assess response predictions, not accuracy of treatment effects. DR bins are adjusted diagnostics, not effect ground truth. Do not use uplift to rank comp quality or add effects across correlated facets. No causal identification, unreviewed-universe generalization, or pipeline improvement is established.
