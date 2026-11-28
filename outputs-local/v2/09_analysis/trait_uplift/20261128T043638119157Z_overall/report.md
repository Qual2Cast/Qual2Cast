# Trait X-learner (20261128T043638119157Z)

Pre-registered in `v2/09_analysis/PREREG_TRAITS.md`. Cohort `v3_final`: 311 pairs, 67 targets. Traits table `outputs-local/v2/02_profiles/traits_new/tables/traits.csv` (prompt ['2026-11-24a']).
Shuffles 1000 and refit bootstrap draws 200 per trait and outcome. Benjamini-Hochberg across 30 tests at q = 0.1; unsupported tests count as p = 1.

Lift = percentage-point difference in the probability of the outcome between pairs that match and pairs that differ on the trait, adjusted for the 12 B3 signals and the other traits. An adjusted association within B3's lists, not a cause and not a pipeline improvement.

## Cross-check (own family): overall

| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| recurring_revenue | all | supported | 258 | 52 | -4.8 | -14.2 to +1.5 | 0.170 | 0.317 | no |
| recurring_revenue | services_yes | supported | 166 | 34 | -4.0 | -16.2 to +2.4 | 0.335 | 0.478 | no |
| recurring_revenue | services_no | supported | 92 | 18 | -6.1 | -19.5 to +9.4 | 0.145 | 0.310 | no |
| recurring_revenue | consumers_yes | supported | 137 | 28 | -5.8 | -16.1 to +3.2 | 0.095 | 0.259 | no |
| recurring_revenue | consumers_no | supported | 121 | 24 | -3.5 | -16.9 to +2.5 | 0.368 | 0.501 | no |
| cyclical_demand | all | supported | 273 | 58 | -4.1 | -10.6 to +6.4 | 0.180 | 0.317 | no |
| cyclical_demand | services_yes | supported | 164 | 36 | -5.6 | -15.4 to +6.5 | 0.119 | 0.295 | no |
| cyclical_demand | services_no | supported | 109 | 22 | -1.6 | -11.0 to +11.6 | 0.674 | 0.743 | no |
| cyclical_demand | consumers_yes | supported | 143 | 32 | -1.3 | -10.1 to +9.2 | 0.669 | 0.743 | no |
| cyclical_demand | consumers_no | supported | 130 | 26 | -7.5 | -15.9 to +6.3 | 0.039 | 0.130 | no |
| big_ticket | all | supported | 110 | 43 | +9.5 | -6.2 to +18.2 | 0.038 | 0.130 | no |
| big_ticket | services_yes | supported | 71 | 29 | +8.3 | -8.7 to +17.1 | 0.128 | 0.295 | no |
| big_ticket | services_no | supported | 39 | 14 | +12.0 | -3.0 to +28.4 | 0.029 | 0.130 | no |
| big_ticket | consumers_yes | supported | 44 | 19 | +9.6 | -9.9 to +20.9 | 0.034 | 0.130 | no |
| big_ticket | consumers_no | supported | 66 | 24 | +9.4 | -7.3 to +20.1 | 0.067 | 0.201 | no |
| people_delivered | all | supported | 114 | 41 | +5.5 | -6.0 to +21.3 | 0.207 | 0.327 | no |
| people_delivered | services_yes | supported | 95 | 31 | +6.6 | -2.6 to +20.3 | 0.205 | 0.327 | no |
| people_delivered | services_no | supported | 19 | 10 | +2.0 | -14.0 to +26.4 | 0.693 | 0.743 | no |
| people_delivered | consumers_yes | supported | 57 | 20 | +9.0 | -5.2 to +21.2 | 0.038 | 0.130 | no |
| people_delivered | consumers_no | supported | 57 | 21 | +2.2 | -10.4 to +23.7 | 0.661 | 0.743 | no |
| large_customers | all | supported | 242 | 51 | +8.1 | -1.5 to +14.7 | 0.012 | 0.130 | no |
| large_customers | services_yes | supported | 159 | 33 | +5.6 | -5.2 to +15.3 | 0.161 | 0.317 | no |
| large_customers | services_no | supported | 83 | 18 | +12.6 | -2.2 to +17.5 | 0.001 | 0.030 | yes |
| large_customers | consumers_yes | supported | 117 | 26 | +8.0 | -2.1 to +13.7 | 0.015 | 0.130 | no |
| large_customers | consumers_no | supported | 125 | 25 | +8.1 | -4.1 to +16.5 | 0.035 | 0.130 | no |
| asset_heavy | all | supported | 213 | 47 | +2.3 | -5.3 to +10.0 | 0.502 | 0.628 | no |
| asset_heavy | services_yes | supported | 123 | 30 | +3.4 | -6.3 to +14.4 | 0.390 | 0.508 | no |
| asset_heavy | services_no | supported | 90 | 17 | +0.4 | -9.9 to +11.4 | 0.896 | 0.896 | no |
| asset_heavy | consumers_yes | supported | 115 | 25 | +3.8 | -6.3 to +14.4 | 0.253 | 0.379 | no |
| asset_heavy | consumers_no | supported | 98 | 22 | +0.6 | -10.9 to +11.1 | 0.872 | 0.896 | no |

Every test is listed, including nulls and unsupported cells. Missing effects are not zero.
