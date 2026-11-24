# Trait X-learner (20261124T111715563218Z)

Pre-registered in `v2/09_analysis/PREREG_TRAITS_R2.md`. Cohort `matthew_v2_262`: 262 pairs, 40 targets. Traits table `outputs-local/v2/02_profiles/traits_new/tables/traits.csv` (prompt ['2026-11-24a', '2026-11-24b']).
Shuffles 1000 and refit bootstrap draws 200 per trait and outcome. Benjamini-Hochberg across 40 tests at q = 0.1; unsupported tests count as p = 1.

Lift = percentage-point difference in the probability of the outcome between pairs that match and pairs that differ on the trait, adjusted for the 12 B3 signals and the other traits. An adjusted association within B3's lists, not a cause and not a pipeline improvement.

## Primary: direct

| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| maintenance_led | all | partial | 58 | 19 |  |  |  | 1.000 | no |
| maintenance_led | services_yes | partial | 24 | 11 |  |  |  | 1.000 | no |
| maintenance_led | services_no | partial | 34 | 8 |  |  |  | 1.000 | no |
| maintenance_led | consumers_yes | partial | 26 | 7 |  |  |  | 1.000 | no |
| maintenance_led | consumers_no | partial | 32 | 12 |  |  |  | 1.000 | no |
| publicly_funded | all | partial | 45 | 22 |  |  |  | 1.000 | no |
| publicly_funded | services_yes | partial | 33 | 16 |  |  |  | 1.000 | no |
| publicly_funded | services_no | partial | 12 | 6 |  |  |  | 1.000 | no |
| publicly_funded | consumers_yes | partial | 27 | 12 |  |  |  | 1.000 | no |
| publicly_funded | consumers_no | partial | 18 | 10 |  |  |  | 1.000 | no |
| serial_acquirer | all | partial | 87 | 26 |  |  |  | 1.000 | no |
| serial_acquirer | services_yes | partial | 76 | 22 |  |  |  | 1.000 | no |
| serial_acquirer | services_no | partial | 11 | 4 |  |  |  | 1.000 | no |
| serial_acquirer | consumers_yes | partial | 46 | 13 |  |  |  | 1.000 | no |
| serial_acquirer | consumers_no | partial | 41 | 13 |  |  |  | 1.000 | no |
| mission_critical | all | supported | 223 | 40 | +10.6 | +4.3 to +18.3 | 0.005 | 0.040 | yes |
| mission_critical | services_yes | supported | 141 | 26 | +10.5 | +4.6 to +19.3 | 0.008 | 0.051 | yes |
| mission_critical | services_no | supported | 82 | 14 | +10.8 | +0.6 to +19.3 | 0.021 | 0.084 | yes |
| mission_critical | consumers_yes | supported | 117 | 22 | +9.5 | +4.0 to +18.6 | 0.005 | 0.040 | yes |
| mission_critical | consumers_no | supported | 106 | 18 | +11.9 | +2.7 to +19.1 | 0.012 | 0.053 | yes |

## Secondary: peer

| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| maintenance_led | all | partial | 58 | 19 |  |  |  | 1.000 | no |
| maintenance_led | services_yes | partial | 24 | 11 |  |  |  | 1.000 | no |
| maintenance_led | services_no | partial | 34 | 8 |  |  |  | 1.000 | no |
| maintenance_led | consumers_yes | partial | 26 | 7 |  |  |  | 1.000 | no |
| maintenance_led | consumers_no | partial | 32 | 12 |  |  |  | 1.000 | no |
| publicly_funded | all | partial | 45 | 22 |  |  |  | 1.000 | no |
| publicly_funded | services_yes | partial | 33 | 16 |  |  |  | 1.000 | no |
| publicly_funded | services_no | partial | 12 | 6 |  |  |  | 1.000 | no |
| publicly_funded | consumers_yes | partial | 27 | 12 |  |  |  | 1.000 | no |
| publicly_funded | consumers_no | partial | 18 | 10 |  |  |  | 1.000 | no |
| serial_acquirer | all | partial | 87 | 26 |  |  |  | 1.000 | no |
| serial_acquirer | services_yes | partial | 76 | 22 |  |  |  | 1.000 | no |
| serial_acquirer | services_no | partial | 11 | 4 |  |  |  | 1.000 | no |
| serial_acquirer | consumers_yes | partial | 46 | 13 |  |  |  | 1.000 | no |
| serial_acquirer | consumers_no | partial | 41 | 13 |  |  |  | 1.000 | no |
| mission_critical | all | supported | 223 | 40 | +25.1 | +9.4 to +42.4 | 0.001 | 0.013 | yes |
| mission_critical | services_yes | supported | 141 | 26 | +28.3 | +11.8 to +47.3 | 0.001 | 0.013 | yes |
| mission_critical | services_no | supported | 82 | 14 | +19.0 | -2.7 to +42.1 | 0.009 | 0.051 | yes |
| mission_critical | consumers_yes | supported | 117 | 22 | +30.5 | +11.9 to +46.1 | 0.001 | 0.013 | yes |
| mission_critical | consumers_no | supported | 106 | 18 | +18.5 | +3.5 to +40.5 | 0.011 | 0.053 | yes |

Every test is listed, including nulls and unsupported cells. Missing effects are not zero.
