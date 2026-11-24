# Pre-registration: do economic traits go with people's peer judgments?

**For:** the whole team, before the trait X-learner is run on real labels. Written 2026-11-24, before any run on
the 533-company trait fill. The script is `v2/09_analysis/scripts/trait_uplift.py`; it implements exactly what is
written here. A change to anything below after the first real run is an amendment: dated, listed at the end of
this file, with the reason, and any result it touches is labelled exploratory.

## Question

Within the target-comp pairs that B3 already found, are pairs whose two companies give the same answer on an
economic trait (for example both recurring-revenue businesses, or both not) more likely to be judged peers by a
person, after adjusting for what B3's facet similarities already say? And is that difference larger for some kinds
of target (services vs not, consumer-facing vs not)? This is Aziz's question about facets that matter only for some
sub-segments, asked as a subgroup question.

Lift is an adjusted association, not a cause. Trait matches are not assigned at random; a lift says "pairs that
match on this trait are judged peers more often, beyond what B3 sees", not "matching on this trait makes a pair a
peer". It also does not show that the pipeline improves: the pipeline does not use the traits this round.

## Where the traits sit (definition list vs test list)

- **Definition list** (decides what "peer" means, through rubric v2/v3): same product, same customers, same revenue
  model, same chain step. Never tested here.
- **Test list** (tested as explanations): the six traits below. Never part of the rubric's score.

So the outcome (a person's grade) and the treatment (Sonnet's separate description of each company) come from
different sources, and no trait is built into the outcome.

## Data

- **Cohort:** `matthew_v2_262` (06_labels/scripts/cohorts.py): Matthew's rubric v2 answers on the 262 round-3 B3
  pairs, 40 targets. Derived score: 60 twos, 124 ones, 78 zeros.
  - **One reviewer.** No second reviewer has answered rubric v2 on these pairs, so results describe one person's
    judgments.
  - **Loose customers wording.** Matthew answered the v2 customers question ("same type of buyer"), which counts
    same industry or same payer as yes. Under rubric v3's tighter wording some of his 120 "product no, customers
    yes" pairs would be 0. His peer outcome (184 of 262 peers) is therefore inflated; the direct-peer outcome needs
    "same product" too and is much less affected. This is why direct peer is the primary outcome.
  - Barbara's old 0/1/2 labels (`dev_293`) are not used.
- **Traits:** the v2 trait table, `outputs-local/v2/02_profiles/traits_new/tables/traits.csv` (prompt `2026-11-24a`,
  Sonnet 5.5 on the CLI, all 533 companies), after the 30-company stability check. The exact file and its sha256 go
  into the run manifest.
- **B3 signals:** the 12 per-facet similarities of the current B3 variant ("Sonnet + Fiona sub-sector"), computed as
  in v1a's facet-uplift runs (`facet_uplift.b3_signals`, features `current`).

## Outcomes

| | outcome | definition | pairs with outcome 1 |
|---|---|---|---|
| primary | direct peer | Matthew's derived score = 2 | 60 of 262 |
| secondary | peer | Matthew's derived score >= 1 | 184 of 262 |

Both are binary; response models are logistic, as in v1a's peer runs.

## Treatments: six traits

E1 `recurring_revenue`, E2 `cyclical_demand`, E3 `big_ticket`, E4 `people_delivered`, E5 `large_customers`,
E6 `asset_heavy` (questions and rules in `v2/02_profiles/scripts/traits.py`).

- **Match = 1** when the target and the comp give the same answer (both yes or both no); **match = 0** when one says
  yes and the other no.
- **Unknown is never a mismatch.** A pair where either company answered unknown is left out of that trait's
  analysis (and only that trait's).
- One analysis per trait per outcome. A trait dropped by the stability check before the run (answer flips on more
  than 20% of companies between two fills, or unknown on more than 20%) is removed here by a dated amendment, and the
  test count below shrinks accordingly.

## Covariates (what the lift is adjusted for)

1. **The 12 B3 per-facet similarities.** B3 chose these pairs; adjusting for its signals asks whether a trait adds
   anything beyond the facet similarity retrieval already uses.
2. **The other five traits' match indicators.** Traits are correlated (big-ticket and cyclical demand often go
   together); without this, one trait's lift could be another's.
3. **Missingness indicators** for every covariate (the v1a pipeline's median imputer with indicators), so an
   unknown answer on another trait is kept as information and never imputed as a mismatch.

Company ids, tickers, the reviewer's notes, grades, selector or agent decisions and every financial field are not
covariates.

## Estimator

v1a's X-learner unchanged (`facet_uplift.py`, `estimate_fold`; copied from v1a into `v2/09_analysis/scripts/` with only its paths changed): five outer folds that hold
out whole targets (seed 42), three inner folds for cross-fitted pseudo-effects, logistic response and propensity
models (C = 0.1), ridge effect models (alpha = 10), equal total weight per training target, propensity-weighted
combination of the two effect models. Only held-out (out-of-fold) pairs with propensity between 0.1 and 0.9 enter
the summaries. A doubly robust difference is reported beside each lift as a check, not as the estimate.

**Support rule (v1a):** an outer fold is fitted only when each arm (match and mismatch) has at least 15 training
pairs from at least 5 targets, and the inner cross-fit leaves the same. A trait-outcome analysis is **complete**
when all five folds are fitted. A partial or unsupported analysis is reported as such, with no p-value; nothing is
forced.

## Subgroups: one fit, then averaged by tag

Tags of the **target** (from the same trait fill):

- T2 `offers_services`: yes / no
- T3 `sells_to_consumers`: yes / no

Each trait gets **one** fit on all pairs. Its out-of-fold per-pair effects are then averaged within each tag cell,
giving five cells per trait and outcome: all pairs, services yes, services no, consumers yes, consumers no. No
separate model is fitted inside a subgroup, because subgroups of 262 pairs would starve. A target with an unknown
tag is left out of that tag's two cells and kept in "all pairs". A cell needs at least 5 targets with overlap pairs;
otherwise it is reported as unsupported.

**Lift** in a cell = the mean over targets of each target's mean out-of-fold effect (overlap pairs only), in
percentage points of probability.

## Uncertainty and the shuffle test

- **Refit bootstrap (intervals).** 200 draws: resample the 40 targets with replacement, refit the whole estimator on
  the drawn pairs, recompute every cell's lift. The 95% interval is the 2.5th to 97.5th percentile of the draws that
  produced an estimate (their count is reported). Copies of a drawn target stay together in every fold, so a copy
  never predicts itself; model weights count each distinct target once and the cell average counts each draw. This
  replaces v1a's fixed-prediction bootstrap, which held the fitted models fixed and so gave intervals that were too
  narrow.
- **Shuffle (permutation) test (p-values).** 1,000 shuffles per trait and outcome: that trait's answers are shuffled across the
  533 companies (each company gets another company's answer; the share of yes/no/unknown is kept), the trait's
  matches are recomputed, and the full estimator is rerun. The shuffled lifts show how big a lift appears by chance
  on these pairs with this estimator. Two-sided p-value = (1 + number of supported shuffles whose |lift| is at least
  the real |lift|) / (1 + number of supported shuffles), per cell. With 1,000 shuffles the smallest possible p is
  about 0.001. That number is set by the correction below: BH's strictest bar across 60 tests is 0.10 / 60 ≈
  0.0017, and with only 200 shuffles (smallest p ≈ 0.005) a single strong result could never clear it.

## Multiple testing: Benjamini-Hochberg at q = 0.10

**The tests:** 6 traits × 5 cells (all pairs + 4 tag cells) × 2 outcomes = **60 tests**, one family. A test that is
unsupported counts as p = 1, so the family size stays 60 whatever the data do.

**What the correction means, in plain words.** Each test on its own is allowed a 5% chance of a false alarm. Run 60
of them when nothing is real and you expect about three false alarms, which would be reported as findings. Even
with 36 tests (6 traits × 3 cuts × 2 outcomes, the earlier plan) that is roughly two. Benjamini-Hochberg (BH)
controls the **false discovery rate**: among the results we call findings, it keeps the expected share of false ones
at or below 10%.

**How it works.** Sort the 60 p-values from smallest to largest. The smallest is compared with 0.10 × 1/60, the
second with 0.10 × 2/60, and so on up to 0.10 × 60/60 for the largest. Find the last p-value in this order that is
at or under its own bar; it and every smaller one are findings. The script also reports each test's BH-adjusted
p-value (`bh_q`): a test is a finding at 10% when `bh_q` ≤ 0.10. Why BH and not a stricter correction such as
Bonferroni: this is a diagnostic meant to point the next experiment, so accepting that about 1 in 10 findings is a
false lead is a fair trade for not missing real ones.

## What gets reported

Every number, including nulls and unsupported cells: for each outcome, trait and cell, the pairs and targets, the
lift, the doubly robust difference, the bootstrap interval with the number of usable draws, the shuffle p-value with
the number of usable shuffles, the BH-adjusted p-value and whether it is a finding at q = 0.10. The fold
diagnostics, the out-of-fold effects, every shuffled and bootstrapped lift and the input hashes are saved with the
run. No trait is dropped or added after seeing results.

**How to read a finding.** A trait that is a finding on the **direct-peer** outcome is evidence to test it next: as a
prompt change for the selector or agent, compared before and after on the same B3 lists, or, if it is strong, as a
candidate rubric question (moving it from the test list to the definition list, which then ends its use as a
treatment). A finding only on the secondary peer outcome is weaker because of the loose customers wording.

## What would change this plan

- The stability check on the 30-company test drops or rewords a trait: dated amendment before the run.
- The trait table at the 533 run is not at prompt `2026-11-24a`: the run stops (the manifest records the version).
- Rubric v3 labels arrive (two reviewers, tightened customers question, the overall call): the run is repeated
  **unchanged** on the v3 cohort (same outcomes, traits, covariates, cells, shuffles, bootstrap and BH family). The
  overall call ("would you put it in the comp set?", column `overall_call_<reviewer>`; called the blind question in the first draft) is analysed as a separate cross-check family, not added to these
  60 tests. Both results are reported side by side.
- If an amendment is needed after a real run, the earlier result stays as run and the new one is labelled
  exploratory.

## Amendments

_None yet._
