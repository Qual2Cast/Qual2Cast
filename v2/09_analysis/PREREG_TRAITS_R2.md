# Pre-registration, round 2: four more economic traits

**For:** the whole team, before the round-2 trait X-learner is run. Written 2026-11-24, after round 1's run and
before any round-2 run. Script: `v2/09_analysis/scripts/trait_uplift.py --round 2`. It follows round 1's plan
(`PREREG_TRAITS.md`) in every step except the ones listed here. A change after the first round-2 run is an
amendment, dated and listed at the end.

## Why a second round, and why its own family

Round 1 (`PREREG_TRAITS.md`, run `20261124T101142641398Z`) tested six traits. One of them, cyclical demand, split
true direct peers as often as non-peers (21.7% vs 20.5% of pairs disagree), and the model's reasons showed the two
facts that actually decided its answer: whether revenue comes from new builds or from maintaining an installed base,
and who ultimately pays (public budgets or private buyers). Round 2 asks those two facts directly and adds two
private-equity value drivers.

Because round 2 was designed **after seeing round 1's results**, it is a separate test family with its own
Benjamini-Hochberg correction, and its findings are **exploratory leads**: they become results only when the same plan,
unchanged, holds on the rubric v3 consensus labels (fresh labels from two reviewers). Round 1's plan and results
stay exactly as run; nothing in round 1 is re-tested or re-corrected here. Iterating like this is fine and intended:
each new set of traits gets its own written plan before its run, its own correction, and a confirmation on labels
it was not designed on.

## What is the same as round 1

Cohort `matthew_v2_262` (Matthew's rubric v2 answers on 262 pairs, 40 targets; one reviewer, loose v2 customers
wording); outcomes direct peer (primary, score 2, 60 of 262) and peer (secondary, score >= 1, 184 of 262); match =
both companies give the same yes/no answer, a pair with unknown on either side left out of that trait only; the
v1a X-learner (`facet_uplift.estimate_fold`) with five target-held-out folds, logistic response and propensity
models, ridge effect models, the 0.1-0.9 overlap filter and the support rule; one fit per trait and outcome,
out-of-fold effects averaged in five cells by the **target's** tags from the round-1 table (all pairs; offers
services yes / no; sells to consumers yes / no); 1,000 shuffles per trait and outcome for p-values (the trait's
answers shuffled across the 533 companies); a 200-draw refit bootstrap over targets for 95% intervals; every number
reported, nulls included.

## What is new

**Traits (round 2, prompt `2026-11-24b`, Sonnet 5.5 on the CLI, all 533 companies, questions in
`v2/02_profiles/scripts/traits.py` `ROUND_2`):**

| id | trait | question (short) |
|---|---|---|
| E7 | `maintenance_led` | most revenue from repairing, servicing or replacing an installed base, not new builds or first purchases |
| E8 | `publicly_funded` | most revenue ultimately paid by government (public works, Medicare/Medicaid, defense, schools) |
| E9 | `serial_acquirer` | grows mainly by buying other companies (roll-up or platform) |
| E10 | `mission_critical` | customers face real cost, risk or disruption switching away |

Table: `outputs-local/v2/02_profiles/traits_r2/tables/traits.csv`. All four passed the stability check on the
30-company double fill (at most 2 flips in 30, at most 1 unknown), so all four are tested.

**Covariates:** the 12 B3 per-facet similarities, the other three round-2 traits' matches, **and all six round-1
traits' matches** (recurring revenue, cyclical demand, big-ticket, people-delivered, large customers, asset-heavy),
each with a missingness indicator. So a round-2 lift is what the trait adds beyond B3 *and* beyond everything round
1 measured.

**Family:** 4 traits x 5 cells x 2 outcomes = **40 tests**, Benjamini-Hochberg at q = 0.10 across these 40 only. An
unsupported test counts as p = 1. With 1,000 shuffles the smallest possible p is about 0.001, below the strictest
bar 0.10 / 40 = 0.0025.

**Reading:** a round-2 finding on the direct-peer outcome is a lead to confirm on rubric v3 labels, not a result.
The rare-trait caution from round 1 applies: in the 30-company test, maintenance-led was yes for 3-7% of companies,
publicly funded 10-13% and serial acquirer 10%, so few pairs may differ on them and some cells may be unsupported.

## What would change this plan

- The 533 fill shows a trait unknown for more than 20% of companies: dropped by a dated amendment before the run,
  and the family shrinks by 10.
- Rubric v3 labels arrive: this plan reruns unchanged on the v3 consensus cohort, side by side with this run.

## Amendments

_None yet._
