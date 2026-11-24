# Trait X-learner (20261124T101142641398Z)

Pre-registered in `v2/09_analysis/PREREG_TRAITS.md`. Cohort `matthew_v2_262`: 262 pairs, 40 targets. Traits table `outputs-local/v2/02_profiles/traits_new/tables/traits.csv` (prompt ['2026-11-24a']).
Shuffles 1000 and refit bootstrap draws 200 per trait and outcome. Benjamini-Hochberg across 60 tests at q = 0.1; unsupported tests count as p = 1.

Lift = percentage-point difference in the probability of the outcome between pairs that match and pairs that differ on the trait, adjusted for the 12 B3 signals and the other traits. An adjusted association within B3's lists, not a cause and not a pipeline improvement.

## Primary: direct

| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| recurring_revenue | all | supported | 256 | 40 | +1.7 | -6.2 to +9.9 | 0.681 | 0.771 | no |
| recurring_revenue | services_yes | supported | 157 | 26 | +1.9 | -8.1 to +10.2 | 0.663 | 0.765 | no |
| recurring_revenue | services_no | supported | 99 | 14 | +1.3 | -9.7 to +11.5 | 0.783 | 0.824 | no |
| recurring_revenue | consumers_yes | supported | 141 | 22 | -1.7 | -9.4 to +9.0 | 0.649 | 0.764 | no |
| recurring_revenue | consumers_no | supported | 115 | 18 | +5.9 | -6.6 to +13.1 | 0.265 | 0.429 | no |
| cyclical_demand | all | supported | 246 | 40 | -6.8 | -14.9 to +5.6 | 0.069 | 0.148 | no |
| cyclical_demand | services_yes | supported | 148 | 26 | -10.5 | -19.3 to +7.2 | 0.008 | 0.048 | yes |
| cyclical_demand | services_no | supported | 98 | 14 | +0.1 | -16.3 to +10.9 | 0.976 | 0.976 | no |
| cyclical_demand | consumers_yes | supported | 134 | 22 | -4.5 | -14.8 to +7.4 | 0.163 | 0.279 | no |
| cyclical_demand | consumers_no | supported | 112 | 18 | -9.5 | -17.8 to +8.3 | 0.052 | 0.140 | no |
| big_ticket | all | supported | 70 | 26 | +8.4 | -4.4 to +13.6 | 0.082 | 0.165 | no |
| big_ticket | services_yes | supported | 53 | 20 | +10.3 | -4.5 to +15.4 | 0.047 | 0.140 | no |
| big_ticket | services_no | supported | 17 | 6 | +2.2 | -17.9 to +12.5 | 0.730 | 0.797 | no |
| big_ticket | consumers_yes | supported | 21 | 11 | +4.1 | -9.6 to +15.2 | 0.388 | 0.554 | no |
| big_ticket | consumers_no | supported | 49 | 15 | +11.6 | -5.7 to +15.8 | 0.049 | 0.140 | no |
| people_delivered | all | supported | 85 | 29 | +11.2 | +5.8 to +17.1 | 0.011 | 0.055 | yes |
| people_delivered | services_yes | supported | 77 | 24 | +9.9 | +5.8 to +17.7 | 0.051 | 0.140 | no |
| people_delivered | services_no | supported | 8 | 5 | +17.6 | +3.7 to +23.3 | 0.008 | 0.048 | yes |
| people_delivered | consumers_yes | supported | 43 | 15 | +8.6 | +2.2 to +14.6 | 0.069 | 0.148 | no |
| people_delivered | consumers_no | supported | 42 | 14 | +14.1 | +8.3 to +21.5 | 0.016 | 0.069 | yes |
| large_customers | all | supported | 232 | 40 | +8.6 | -0.3 to +15.4 | 0.022 | 0.088 | yes |
| large_customers | services_yes | supported | 142 | 26 | +7.0 | -2.5 to +13.3 | 0.087 | 0.168 | no |
| large_customers | services_no | supported | 90 | 14 | +11.6 | +3.4 to +21.5 | 0.012 | 0.055 | yes |
| large_customers | consumers_yes | supported | 124 | 22 | +9.8 | +1.2 to +15.6 | 0.003 | 0.022 | yes |
| large_customers | consumers_no | supported | 108 | 18 | +7.2 | -3.3 to +16.9 | 0.146 | 0.265 | no |
| asset_heavy | all | supported | 189 | 39 | +7.8 | +2.2 to +14.4 | 0.038 | 0.134 | no |
| asset_heavy | services_yes | supported | 112 | 25 | +7.5 | -0.0 to +14.9 | 0.056 | 0.140 | no |
| asset_heavy | services_no | supported | 77 | 14 | +8.4 | +0.0 to +18.9 | 0.056 | 0.140 | no |
| asset_heavy | consumers_yes | supported | 106 | 22 | +7.3 | -0.2 to +15.1 | 0.035 | 0.131 | no |
| asset_heavy | consumers_no | supported | 83 | 17 | +8.6 | +0.0 to +17.6 | 0.067 | 0.148 | no |

## Secondary: peer

| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| recurring_revenue | all | supported | 256 | 40 | -5.6 | -20.9 to +6.2 | 0.413 | 0.576 | no |
| recurring_revenue | services_yes | supported | 157 | 26 | -5.9 | -25.1 to +7.7 | 0.448 | 0.597 | no |
| recurring_revenue | services_no | supported | 99 | 14 | -5.0 | -26.5 to +13.9 | 0.521 | 0.652 | no |
| recurring_revenue | consumers_yes | supported | 141 | 22 | -6.3 | -24.8 to +11.7 | 0.363 | 0.531 | no |
| recurring_revenue | consumers_no | supported | 115 | 18 | -4.7 | -22.9 to +9.2 | 0.549 | 0.673 | no |
| cyclical_demand | all | supported | 246 | 40 | -8.4 | -20.7 to +14.2 | 0.177 | 0.295 | no |
| cyclical_demand | services_yes | supported | 148 | 26 | -1.9 | -19.2 to +19.1 | 0.817 | 0.831 | no |
| cyclical_demand | services_no | supported | 98 | 14 | -20.6 | -35.4 to +6.3 | 0.003 | 0.022 | yes |
| cyclical_demand | consumers_yes | supported | 134 | 22 | -9.4 | -25.0 to +10.5 | 0.120 | 0.225 | no |
| cyclical_demand | consumers_no | supported | 112 | 18 | -7.2 | -21.4 to +21.1 | 0.328 | 0.504 | no |
| big_ticket | all | supported | 70 | 26 | +30.1 | +9.6 to +47.6 | 0.003 | 0.022 | yes |
| big_ticket | services_yes | supported | 53 | 20 | +33.2 | +12.2 to +49.8 | 0.002 | 0.022 | yes |
| big_ticket | services_no | supported | 17 | 6 | +19.7 | -17.3 to +50.8 | 0.072 | 0.149 | no |
| big_ticket | consumers_yes | supported | 21 | 11 | +33.6 | +11.2 to +53.0 | 0.001 | 0.020 | yes |
| big_ticket | consumers_no | supported | 49 | 15 | +27.5 | +1.9 to +43.6 | 0.009 | 0.049 | yes |
| people_delivered | all | supported | 85 | 29 | -2.0 | -21.2 to +14.8 | 0.809 | 0.831 | no |
| people_delivered | services_yes | supported | 77 | 24 | -6.8 | -26.7 to +12.0 | 0.500 | 0.639 | no |
| people_delivered | services_no | supported | 8 | 5 | +21.0 | -10.8 to +37.3 | 0.043 | 0.140 | no |
| people_delivered | consumers_yes | supported | 43 | 15 | +4.9 | -21.7 to +22.8 | 0.593 | 0.712 | no |
| people_delivered | consumers_no | supported | 42 | 14 | -9.5 | -26.2 to +17.5 | 0.348 | 0.521 | no |
| large_customers | all | supported | 232 | 40 | +19.0 | +7.6 to +35.9 | 0.003 | 0.022 | yes |
| large_customers | services_yes | supported | 142 | 26 | +14.1 | -1.1 to +34.1 | 0.065 | 0.148 | no |
| large_customers | services_no | supported | 90 | 14 | +27.9 | +17.0 to +51.8 | 0.001 | 0.020 | yes |
| large_customers | consumers_yes | supported | 124 | 22 | +26.1 | +10.9 to +43.1 | 0.001 | 0.020 | yes |
| large_customers | consumers_no | supported | 108 | 18 | +10.2 | -4.7 to +33.6 | 0.155 | 0.273 | no |
| asset_heavy | all | supported | 189 | 39 | -4.7 | -24.7 to +7.0 | 0.468 | 0.610 | no |
| asset_heavy | services_yes | supported | 112 | 25 | -6.0 | -25.5 to +8.0 | 0.428 | 0.583 | no |
| asset_heavy | services_no | supported | 77 | 14 | -2.3 | -33.3 to +10.8 | 0.743 | 0.797 | no |
| asset_heavy | consumers_yes | supported | 106 | 22 | -6.4 | -28.8 to +6.1 | 0.311 | 0.491 | no |
| asset_heavy | consumers_no | supported | 83 | 17 | -2.4 | -25.5 to +11.8 | 0.744 | 0.797 | no |

Every test is listed, including nulls and unsupported cells. Missing effects are not zero.
