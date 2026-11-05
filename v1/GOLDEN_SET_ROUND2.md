# Golden set, round 2: reviewer guide

**For:** the three round-2 reviewers, and whoever prepares and collects the sheet. The notebook that builds and scores it
is [`notebooks/golden_set_showcase.ipynb`](notebooks/golden_set_showcase.ipynb).

## What you're doing, and why

You'll score about 65 pairs: a **target** company and a candidate **comp**. For each pair, say whether the comp is a
good comparable company for valuing the target. Round 1 scored 36 pairs for two targets (Paylocity, Wendy's). Two
targets is too few to tell the comp-finding methods apart, so round 2 adds five:

| target | company | business structure |
|---|---|---|
| CSL | Carlisle Companies | one business: building envelope products (its other units were sold) |
| AFG | American Financial Group | one business: specialty commercial property and casualty insurance |
| AZZ | AZZ Inc. | one business: hot-dip galvanizing and metal coating |
| BBCP | Concrete Pumping Holdings | **two businesses** (see "Several businesses" below) |
| BUKS | Butler National | **two businesses** (see "Several businesses" below) |

The sheet also has the two Wendy's pairs round 1 didn't cover (HireQuest, Planet Fitness).

The pairs are every comp that any of six methods suggested, so expect a mix of good and bad. **You won't see which
method suggested a pair, how similar it scored, or any valuation multiple. Please don't look these up:** the point is an
independent business judgment.

## The scores (the team's shared rubric, unchanged from round 1)

| score | meaning | rule |
|---|---|---|
| **2** | direct competitor | same product **and** same customers |
| **1** | adjacent | overlapping product **or** customers, but not both |
| **0** | not a peer | no real overlap |

**Every 0 needs one of these six reasons** (type it exactly; capitals don't matter):

| reason for a 0 | use it when |
|---|---|
| Different industry | unrelated industry, no overlap in product or customers (e.g. an apparel brand vs. a restaurant) |
| Different business model | same or neighbouring industry, but it makes money a different way (e.g. a food manufacturer vs. a restaurant) |
| Different customers | similar kind of offering, but sold to a different buyer |
| Different scale | the business matches, but the size gap makes it useless |
| Generic wording only | the only link is buzzwords like "platform" or "solutions" |
| Wrong industry code | same SIC code, but a different business |

A 1 or a 2 takes **no** reason. Use your `notes_` column for anything else, such as which product line matches or what you
weren't sure about.

## Several businesses (BBCP, BUKS): confirmed scope and scoring

Keep **one company ID and one grade per target–comp pair**. The `target_business_scope` column lists all current businesses, grouped when their products, customers and operations belong to the same general business. Exited businesses do not count. Apply the **same 0–2 rubric above** to the whole company; the number of business groups does not mechanically set the grade. In the notes, name the matched and unmatched activities when the comp covers only part of the target.

- **2:** products **and** customers match across the target's material current businesses. An unmatched activity with a demonstrably small contribution does not by itself remove an otherwise direct match.
- **1:** there is real product or customer overlap, but a material current business is unmatched. Thus an aerospace-only or gaming-only comp for BUKS can be adjacent even when it closely matches that one division.
- **0:** neither product nor customer overlap is meaningful at the company level. A generic phrase or industry code alone is insufficient; a genuine match to one business is not automatically a 0.

**BBCP:** concrete pumping and concrete washout management form one related construction-site services group. Temporary power and supporting site infrastructure, acquired with Templant in April 2026, are a distinct adjacent activity. The [July 2026 10-Q](https://ir.concretepumpingholdings.com/all-sec-filings/content/0001437749-26-029623/bbpp20260731_10q.htm) reports $3.8 million of Templant revenue against $314.1 million consolidated revenue for the nine months ended July 31 (about 1.2%). It is kept in the scope, but its recent small contribution does not by itself downgrade a strong concrete-services comp. The filing's accounting segments are U.S. pumping, U.S. waste management and U.K. operations; these are **not** the economic business groups used here.

**BUKS:** aircraft engineering, modifications, avionics, electronics manufacturing and precision machining form the Aerospace Products group. Casino and gaming management form Professional Services. The [FY2026 company results](https://butlernational.com/butler-national-corporation-announces-fiscal-year-end-2026-financial-results/) report $60.6 million in aerospace revenue and $37.4 million in professional-services revenue (62% and 38% of the total). Both groups are material. The aerospace sub-lines are products and services within the same general aerospace business, not separate target companies.

The source-checked groupings agree with `outputs-local/v1/business_structure_refinement/source_benchmark/group_partitions.csv`. The `review_flags` in the split classifier record pair-level model disagreements; they do not overturn the current company scope established by the dated disclosures. No reviewer score is filled in by this source check.

## Filling in the sheet

- **Columns:** each reviewer has a column set, `score_reviewer_X`, `reason_if_0_reviewer_X` and `notes_reviewer_X`. Fill only your own, and don't look at the others' until everyone is done.
- **Names:** say who is A, B and C in `reviewers.csv`, beside the sheet.
- **What to rely on:** use the descriptions in the sheet, the companies' websites, and what you know. Five to ten minutes per pair is plenty.
- **Leave alone:** the `pair`, `target_…` and `comp_…` columns, and the two id columns at the right end.

## For whoever runs it

1. **Where the sheet is:** `outputs-local/v1/golden_set_showcase/labels/round2_sheet.csv`. It is written once by the notebook and never overwritten. `outputs-local/v1/` is shared through git, so a `git pull` gives everyone the sheet. Pull it, or upload it as a Google Sheet as in round 1 if that's easier to fill together.
2. **When all three are done:** export the filled sheet as CSV to `outputs-local/v1/golden_set_showcase/labels/round2_filled.csv` with the same columns, and commit it so the whole team has the scores.
3. **Run `golden_set_showcase.ipynb`.** It does four things:
   - checks the sheet: every score is 0, 1 or 2; every 0 has one of the six reasons; no reason on a 1 or 2;
   - applies the agreed rule: majority grade (2 of 3) as the main set, unanimous pairs as a strict check, unscored comps never counted as 0;
   - combines round 1 and round 2 into one set of seven targets;
   - draws the hit and rank charts for every method.

   The results go to `outputs-local/v1/golden_set_showcase/evaluation/<time>/`.
4. **What the notebook reads:** the comp lists from a pinned `similarity_methods` run (`20261104T075557Z`), so the pool and the evaluation always match. No API calls are made and no multiples are read.

## After round 2

- **If the methods are still close:** add more of the ten showcase targets (NWSA, BOC, SNFC.A), or targets where the methods disagree most.
- **Extend the same company-level rule** to the three- and four-business targets after checking their current source-backed scope; keep the same 0–2 reviewer rubric.
