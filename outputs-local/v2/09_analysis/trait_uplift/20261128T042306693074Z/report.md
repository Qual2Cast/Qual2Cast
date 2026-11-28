# Trait X-learner (20261128T042306693074Z)

Pre-registered in `v2/09_analysis/PREREG_TRAITS.md`. Cohort `v3_final`: 311 pairs, 67 targets. Traits table `outputs-local/v2/02_profiles/traits_new/tables/traits.csv` (prompt ['2026-11-24a']).
Shuffles 1000 and refit bootstrap draws 200 per trait and outcome. Benjamini-Hochberg across 60 tests at q = 0.1; unsupported tests count as p = 1.

Lift = percentage-point difference in the probability of the outcome between pairs that match and pairs that differ on the trait, adjusted for the 12 B3 signals and the other traits. An adjusted association within B3's lists, not a cause and not a pipeline improvement.

## Primary: direct

| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| recurring_revenue | all | supported | 258 | 52 | +8.5 | -1.8 to +16.4 | 0.023 | 0.172 | no |
| recurring_revenue | services_yes | supported | 166 | 34 | +7.1 | -3.5 to +16.0 | 0.101 | 0.288 | no |
| recurring_revenue | services_no | supported | 92 | 18 | +11.0 | -1.8 to +24.4 | 0.007 | 0.094 | yes |
| recurring_revenue | consumers_yes | supported | 137 | 28 | +6.1 | -2.2 to +19.9 | 0.092 | 0.276 | no |
| recurring_revenue | consumers_no | supported | 121 | 24 | +11.2 | -3.0 to +16.3 | 0.010 | 0.094 | yes |
| cyclical_demand | all | supported | 273 | 58 | +2.5 | -8.0 to +11.5 | 0.459 | 0.786 | no |
| cyclical_demand | services_yes | supported | 164 | 36 | -0.2 | -11.9 to +11.8 | 0.963 | 0.979 | no |
| cyclical_demand | services_no | supported | 109 | 22 | +6.8 | -10.4 to +16.9 | 0.054 | 0.270 | no |
| cyclical_demand | consumers_yes | supported | 143 | 32 | +4.0 | -8.7 to +14.7 | 0.192 | 0.480 | no |
| cyclical_demand | consumers_no | supported | 130 | 26 | +0.6 | -12.1 to +12.6 | 0.887 | 0.951 | no |
| big_ticket | all | supported | 110 | 43 | +1.5 | -14.0 to +11.5 | 0.740 | 0.925 | no |
| big_ticket | services_yes | supported | 71 | 29 | +0.6 | -16.2 to +11.2 | 0.903 | 0.951 | no |
| big_ticket | services_no | supported | 39 | 14 | +3.2 | -12.1 to +22.6 | 0.528 | 0.820 | no |
| big_ticket | consumers_yes | supported | 44 | 19 | +2.2 | -15.5 to +16.4 | 0.607 | 0.849 | no |
| big_ticket | consumers_no | supported | 66 | 24 | +0.9 | -16.6 to +11.2 | 0.865 | 0.951 | no |
| people_delivered | all | supported | 114 | 41 | +7.5 | +0.6 to +18.5 | 0.088 | 0.276 | no |
| people_delivered | services_yes | supported | 95 | 31 | +7.1 | -0.1 to +18.3 | 0.185 | 0.480 | no |
| people_delivered | services_no | supported | 19 | 10 | +8.8 | +0.3 to +23.8 | 0.068 | 0.276 | no |
| people_delivered | consumers_yes | supported | 57 | 20 | +9.4 | -0.2 to +17.7 | 0.032 | 0.192 | no |
| people_delivered | consumers_no | supported | 57 | 21 | +5.7 | -2.3 to +21.8 | 0.300 | 0.620 | no |
| large_customers | all | supported | 242 | 51 | -2.1 | -12.6 to +8.0 | 0.518 | 0.820 | no |
| large_customers | services_yes | supported | 159 | 33 | -4.1 | -16.9 to +8.0 | 0.316 | 0.631 | no |
| large_customers | services_no | supported | 83 | 18 | +1.6 | -10.2 to +11.2 | 0.608 | 0.849 | no |
| large_customers | consumers_yes | supported | 117 | 26 | +0.6 | -11.0 to +9.3 | 0.831 | 0.951 | no |
| large_customers | consumers_no | supported | 125 | 25 | -4.9 | -17.4 to +6.7 | 0.270 | 0.620 | no |
| asset_heavy | all | supported | 213 | 47 | +2.0 | -5.8 to +8.5 | 0.559 | 0.820 | no |
| asset_heavy | services_yes | supported | 123 | 30 | +2.6 | -5.9 to +11.5 | 0.537 | 0.820 | no |
| asset_heavy | services_no | supported | 90 | 17 | +1.0 | -11.1 to +9.8 | 0.764 | 0.933 | no |
| asset_heavy | consumers_yes | supported | 115 | 25 | +2.7 | -6.3 to +10.5 | 0.359 | 0.652 | no |
| asset_heavy | consumers_no | supported | 98 | 22 | +1.3 | -9.7 to +11.1 | 0.777 | 0.933 | no |

## Secondary: peer

| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| recurring_revenue | all | supported | 258 | 52 | -8.2 | -24.4 to +0.6 | 0.092 | 0.276 | no |
| recurring_revenue | services_yes | supported | 166 | 34 | -9.2 | -23.8 to +2.7 | 0.089 | 0.276 | no |
| recurring_revenue | services_no | supported | 92 | 18 | -6.1 | -31.0 to +7.3 | 0.283 | 0.620 | no |
| recurring_revenue | consumers_yes | supported | 137 | 28 | -8.7 | -26.4 to +2.8 | 0.062 | 0.276 | no |
| recurring_revenue | consumers_no | supported | 121 | 24 | -7.5 | -25.9 to +3.0 | 0.158 | 0.430 | no |
| cyclical_demand | all | supported | 273 | 58 | +0.8 | -8.5 to +10.8 | 0.828 | 0.951 | no |
| cyclical_demand | services_yes | supported | 164 | 36 | -0.6 | -9.4 to +12.3 | 0.892 | 0.951 | no |
| cyclical_demand | services_no | supported | 109 | 22 | +3.1 | -14.4 to +14.8 | 0.488 | 0.813 | no |
| cyclical_demand | consumers_yes | supported | 143 | 32 | +0.1 | -10.8 to +13.0 | 0.989 | 0.989 | no |
| cyclical_demand | consumers_no | supported | 130 | 26 | +1.8 | -9.0 to +14.6 | 0.697 | 0.899 | no |
| big_ticket | all | supported | 110 | 43 | +17.2 | +0.5 to +32.1 | 0.008 | 0.094 | yes |
| big_ticket | services_yes | supported | 71 | 29 | +17.9 | -0.1 to +32.8 | 0.011 | 0.094 | yes |
| big_ticket | services_no | supported | 39 | 14 | +15.7 | -10.3 to +41.8 | 0.028 | 0.186 | no |
| big_ticket | consumers_yes | supported | 44 | 19 | +23.1 | +1.4 to +43.8 | 0.001 | 0.030 | yes |
| big_ticket | consumers_no | supported | 66 | 24 | +12.5 | -4.4 to +31.9 | 0.077 | 0.276 | no |
| people_delivered | all | supported | 114 | 41 | +2.5 | -13.0 to +28.6 | 0.665 | 0.899 | no |
| people_delivered | services_yes | supported | 95 | 31 | +7.2 | -8.3 to +26.7 | 0.263 | 0.620 | no |
| people_delivered | services_no | supported | 19 | 10 | -12.2 | -43.6 to +38.8 | 0.084 | 0.276 | no |
| people_delivered | consumers_yes | supported | 57 | 20 | +1.0 | -13.1 to +27.9 | 0.850 | 0.951 | no |
| people_delivered | consumers_no | supported | 57 | 21 | +3.9 | -13.9 to +27.8 | 0.560 | 0.820 | no |
| large_customers | all | supported | 242 | 51 | -1.6 | -10.8 to +9.5 | 0.676 | 0.899 | no |
| large_customers | services_yes | supported | 159 | 33 | -5.0 | -16.1 to +7.8 | 0.296 | 0.620 | no |
| large_customers | services_no | supported | 83 | 18 | +4.5 | -11.1 to +19.6 | 0.335 | 0.648 | no |
| large_customers | consumers_yes | supported | 117 | 26 | +0.3 | -10.8 to +13.8 | 0.947 | 0.979 | no |
| large_customers | consumers_no | supported | 125 | 25 | -3.6 | -16.7 to +9.7 | 0.458 | 0.786 | no |
| asset_heavy | all | supported | 213 | 47 | -7.5 | -20.6 to +7.0 | 0.040 | 0.218 | no |
| asset_heavy | services_yes | supported | 123 | 30 | -1.6 | -19.1 to +12.9 | 0.704 | 0.899 | no |
| asset_heavy | services_no | supported | 90 | 17 | -18.0 | -27.9 to +9.3 | 0.001 | 0.030 | yes |
| asset_heavy | consumers_yes | supported | 115 | 25 | -10.3 | -21.3 to +9.5 | 0.007 | 0.094 | yes |
| asset_heavy | consumers_no | supported | 98 | 22 | -4.3 | -23.9 to +14.1 | 0.346 | 0.648 | no |

Every test is listed, including nulls and unsupported cells. Missing effects are not zero.
