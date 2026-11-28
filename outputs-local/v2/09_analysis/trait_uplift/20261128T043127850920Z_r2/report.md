# Trait X-learner (20261128T043127850920Z)

Pre-registered in `v2/09_analysis/PREREG_TRAITS_R2.md`. Cohort `v3_final`: 311 pairs, 67 targets. Traits table `outputs-local/v2/02_profiles/traits_new/tables/traits.csv` (prompt ['2026-11-24a', '2026-11-24b']).
Shuffles 1000 and refit bootstrap draws 200 per trait and outcome. Benjamini-Hochberg across 40 tests at q = 0.1; unsupported tests count as p = 1.

Lift = percentage-point difference in the probability of the outcome between pairs that match and pairs that differ on the trait, adjusted for the 12 B3 signals and the other traits. An adjusted association within B3's lists, not a cause and not a pipeline improvement.

## Primary: direct

| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| maintenance_led | all | partial | 86 | 27 |  |  |  | 1.000 | no |
| maintenance_led | services_yes | partial | 38 | 18 |  |  |  | 1.000 | no |
| maintenance_led | services_no | partial | 48 | 9 |  |  |  | 1.000 | no |
| maintenance_led | consumers_yes | partial | 40 | 11 |  |  |  | 1.000 | no |
| maintenance_led | consumers_no | partial | 46 | 16 |  |  |  | 1.000 | no |
| publicly_funded | all | partial | 43 | 21 |  |  |  | 1.000 | no |
| publicly_funded | services_yes | partial | 30 | 14 |  |  |  | 1.000 | no |
| publicly_funded | services_no | partial | 13 | 7 |  |  |  | 1.000 | no |
| publicly_funded | consumers_yes | partial | 23 | 11 |  |  |  | 1.000 | no |
| publicly_funded | consumers_no | partial | 20 | 10 |  |  |  | 1.000 | no |
| serial_acquirer | all | supported | 101 | 37 | +2.4 | -7.1 to +12.1 | 0.706 | 1.000 | no |
| serial_acquirer | services_yes | supported | 86 | 29 | +0.7 | -7.0 to +11.7 | 0.929 | 1.000 | no |
| serial_acquirer | services_no | supported | 15 | 8 | +8.8 | -17.8 to +18.4 | 0.161 | 1.000 | no |
| serial_acquirer | consumers_yes | supported | 48 | 17 | +6.6 | -7.6 to +15.1 | 0.251 | 1.000 | no |
| serial_acquirer | consumers_no | supported | 53 | 20 | -1.1 | -11.5 to +14.7 | 0.870 | 1.000 | no |
| mission_critical | all | supported | 252 | 50 | +3.4 | -8.7 to +19.3 | 0.331 | 1.000 | no |
| mission_critical | services_yes | supported | 160 | 34 | +1.4 | -9.9 to +20.7 | 0.742 | 1.000 | no |
| mission_critical | services_no | supported | 92 | 16 | +7.7 | -9.5 to +20.1 | 0.026 | 0.556 | no |
| mission_critical | consumers_yes | supported | 126 | 26 | +2.4 | -9.5 to +24.9 | 0.445 | 1.000 | no |
| mission_critical | consumers_no | supported | 126 | 24 | +4.4 | -10.0 to +21.2 | 0.325 | 1.000 | no |

## Secondary: peer

| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| maintenance_led | all | partial | 86 | 27 |  |  |  | 1.000 | no |
| maintenance_led | services_yes | partial | 38 | 18 |  |  |  | 1.000 | no |
| maintenance_led | services_no | partial | 48 | 9 |  |  |  | 1.000 | no |
| maintenance_led | consumers_yes | partial | 40 | 11 |  |  |  | 1.000 | no |
| maintenance_led | consumers_no | partial | 46 | 16 |  |  |  | 1.000 | no |
| publicly_funded | all | partial | 43 | 21 |  |  |  | 1.000 | no |
| publicly_funded | services_yes | partial | 30 | 14 |  |  |  | 1.000 | no |
| publicly_funded | services_no | partial | 13 | 7 |  |  |  | 1.000 | no |
| publicly_funded | consumers_yes | partial | 23 | 11 |  |  |  | 1.000 | no |
| publicly_funded | consumers_no | partial | 20 | 10 |  |  |  | 1.000 | no |
| serial_acquirer | all | supported | 101 | 37 | -7.7 | -27.0 to +2.8 | 0.333 | 1.000 | no |
| serial_acquirer | services_yes | supported | 86 | 29 | -3.9 | -22.5 to +7.7 | 0.677 | 1.000 | no |
| serial_acquirer | services_no | supported | 15 | 8 | -21.4 | -44.2 to +0.4 | 0.028 | 0.556 | no |
| serial_acquirer | consumers_yes | supported | 48 | 17 | -5.9 | -31.9 to +6.8 | 0.465 | 1.000 | no |
| serial_acquirer | consumers_no | supported | 53 | 20 | -9.2 | -28.1 to +5.3 | 0.332 | 1.000 | no |
| mission_critical | all | supported | 252 | 50 | -1.9 | -13.4 to +6.6 | 0.619 | 1.000 | no |
| mission_critical | services_yes | supported | 160 | 34 | -1.0 | -15.8 to +10.2 | 0.815 | 1.000 | no |
| mission_critical | services_no | supported | 92 | 16 | -3.8 | -24.4 to +12.4 | 0.449 | 1.000 | no |
| mission_critical | consumers_yes | supported | 126 | 26 | -2.5 | -17.3 to +10.5 | 0.508 | 1.000 | no |
| mission_critical | consumers_no | supported | 126 | 24 | -1.3 | -15.6 to +10.8 | 0.804 | 1.000 | no |

Every test is listed, including nulls and unsupported cells. Missing effects are not zero.
