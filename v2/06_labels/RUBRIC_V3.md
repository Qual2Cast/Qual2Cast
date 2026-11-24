# Rubric v3: an overall call, then four yes/no questions per pair

**For:** the reviewers (Barbara, Matthew, Riya), whoever prepares and collects the sheets, and whoever
changes an LLM grader or judge to ask the same questions. Code: `v2/06_labels/scripts/rubric_v3.py`.
Rubric v2 (`v1a/06_labels/RUBRIC_V2.md`) stays as the record of rounds 3 and earlier.

## Why v3

Rubric v2 gave four yes/no questions and derived the score. Three things needed fixing:

- **Question 2 was too loose.** "Same type of buyer" counted the same industry or the same payer as yes.
  On Matthew's 262 round-3 pairs, 120 were "product no, customers yes" and scored 1; Barbara's old grades
  split them 72 ones and 48 zeros. Most person-to-person disagreement sits in those pairs.
- **The score is a formula.** If the formula is off, every analysis built on it inherits the error. v3
  adds one overall call, answered first, as a check on the formula.
- **Nobody had worked examples.** v3 gives three per question (below): a clear yes, a clear no and a
  borderline case with a proposed ruling.

## The questions, in order

Answer **yes** or **no**. Nobody types a score.

**First, before reading the four questions:**

| column | question |
|---|---|
| `overall_call` | Would you put this company in the target's comp set? |

This is your own call. It is never part of the score; it is used to check whether the score's formula
agrees with reviewers' judgment. Do not change it after answering the four questions.

### What the overall call is, and what "blind" means

Two different things were both called "blind" in earlier drafts, so the question was renamed on
2026-11-24 (column `overall_call_<you>`, formerly `blind_<you>`):

- **The sheet is blind.** You don't see which method suggested a pair, its rank, its similarity score,
  any EV/EBITDA multiple or an earlier grade, and the pairs come in a random order. This was already true
  in rubric v2. *Why:* any of those would pull your answer toward what the pipeline already thinks, and
  the labels exist to check the pipeline, so they must not be shaped by it.
- **The overall call is your first impression of the whole pair.** It is not based on the facets or on
  any one column. Use the same evidence as for the four questions: the sheet's descriptions, the
  companies' websites and what you know. It is answered *before* you break the pair into product,
  customers, revenue model and chain step. *Why:* the 0/1/2 score is a formula we chose. If the formula
  is off (for example, if people would call a pair a peer that the formula scores 0), every result built
  on the score inherits the error. Comparing the overall call with the derived score shows whether the
  formula matches reviewers' own judgment, and it gives the X-learner a second outcome that no formula
  built. *Why first:* answered after the four questions, it would just repeat their sum.

**Then the four:**

| # | column | question | how to decide |
|---|---|---|---|
| 1 | `same_product` | Can a customer of the target buy the same kind of product or service from the comp instead? | Think of one actual buyer of the target. If that buyer can place the same order with the comp, yes. The same broad category is not enough. |
| 2 | `same_customers` | Would the target's own customers consider buying this kind of thing from the comp? | "This kind of thing" is what the comp sells. Yes when the same buyers, in the same buying role, buy from both (the plant engineers who buy the target's heaters also buy the comp's pumps). **The same industry or the same payer alone is not yes** (Medicare paying both a NICU physician group and a hospice). For consumer businesses, "both sell to households" is not enough: the same customer segment must buy for the same kind of need. |
| 3 | `same_revenue_model` | Does the comp earn money the same way? | The ways: sells goods, sells a service, subscription, commission or fees, insurance premiums, interest. Judge the comp by how most of its revenue is earned. |
| 4 | `same_chain_step` | Does the comp sit at the same step of the chain? | The steps: makes it, distributes it, sells it to the end user, services it. A brand owner that outsources production still "makes it". A marketplace that arranges the sale is not at the same step as the owner that sells it. |

Questions 1 and 2 can be met by any material business of the comp. Questions 3 and 4 describe the comp as
a whole company (its larger part). So a comp whose only matching unit is a minority of its business
comes out adjacent at most. This is a proposed rule; see the Boston Omaha anchor.

## The score comes from the answers

| score | meaning | rule |
|---|---|---|
| **2** | direct peer | yes to all four |
| **1** | adjacent | yes to question 1 or question 2, but not all four |
| **0** | not a peer | no to both question 1 and question 2 |

Product or customers is a must-pass: whatever the other answers, a pair with no to both is 0. A direct
peer needs product **and** customers. Revenue model and chain step can only demote a direct peer to
adjacent; they never lift a pair. This is the same formula as v2, so earlier metrics keep working.

## Unsure

Each reviewer has one `unsure_<you>` column. List the questions you were unsure about, separated by
commas: `product`, `customers`, `revenue_model`, `chain_step`, `overall` (or `all`). It never changes an
answer. It is reported next to each question's kappa, so the team can see where the wording still needs
work.

## Anchor pairs (worked examples)

Twelve pairs from the round-3 sheet, three per question. Rulings are **proposed, team to confirm**. The
anchors stay in the sheet, flagged `is_anchor = 1`, and are **left out of scoring and agreement**. You
don't need to answer them. If you do, your answers are only used to check that everyone reads the
guide the same way.

"Matthew (v2)" is his round-3 answer to that question under the v2 wording. "Barbara" is her old 0/1/2
grade for the pair.

### Question 1: same product

| kind | sheet pair | target | comp | Matthew (v2) | Barbara | why | ruling |
|---|---|---|---|---|---|---|---|
| clear yes | P287 | NVR (NVR, Inc.) | DHI (D.R. Horton) | yes | 2 | Both build and sell single-family homes to individual buyers; a homebuyer can buy the same kind of home from either. | yes |
| clear no | P254 | PANL (Pangaea Logistics Solutions) | HTLD (Heartland Express) | no | 0 | Ocean dry-bulk shipping vs North American dry-van truckload; a miner cannot ship bulk ore by sea with Heartland. | no |
| borderline | P156 | DGII (Digi International) | ZBRA (Zebra Technologies) | no | 1 | Both design rugged connected hardware for enterprises, but cellular routers and embedded modules are not mobile computers, scanners or printers. The same category is not the same order. | no (customers still yes, so 1) |

### Question 2: same customers

| kind | sheet pair | target | comp | Matthew (v2) | Barbara | why | ruling |
|---|---|---|---|---|---|---|---|
| clear yes | P318 | THR (Thermon Group) | FLS (Flowserve) | yes | 1 | Different products (heat tracing vs pumps and valves), but the same plant engineering and maintenance buyers at oil and gas, chemical and power operators, and the same EPC contractors, buy both. Customers can be yes when product is no. | yes (score 1) |
| clear no | P095 | JBHT (J.B. Hunt Transport) | TRN (Trinity Industries) | no | 0 | J.B. Hunt's buyers are retailers and consumer-goods shippers; Trinity sells and leases railcars to railroads, lessors and chemical and energy shippers. | no |
| borderline | P109 | MD (Pediatrix Medical Group) | CHE (Chemed: VITAS hospice and Roto-Rooter) | yes | 0 | Under v2, "both paid by patients and Medicare" made this yes. NICU and maternal-fetal patients, and the hospitals that contract Pediatrix, do not buy hospice care or plumbing. A shared payer is not a shared buyer. | **no** (score goes 1 → 0) |

The borderline is the pattern behind the 120 "product no, customers yes" pairs. Other cases it settles
as no: Savers (thrift stores) vs Ingles (groceries), "both sell to households"; Akebia vs other
branded-drug companies with different patients, "both sell drugs to the same distributors".

### Question 3: same revenue model

| kind | sheet pair | target | comp | Matthew (v2) | Barbara | why | ruling |
|---|---|---|---|---|---|---|---|
| clear yes | P211 | ED (Consolidated Edison) | AVA (Avista) | yes | 2 | Both are regulated utilities billing customers at regulator-set tariffs. | yes |
| clear no | P181 | IMKT.A (Ingles Markets) | BROS (Dutch Bros) | no | 0 | A grocer sells goods; a drive-thru coffee chain sells made-to-order drinks, a food service (as in v2's food-maker vs restaurant example). | no |
| borderline | P117 | SHEN (Shenandoah Telecommunications) | BOC (Boston Omaha) | no | 1 | Boston Omaha's broadband unit sells the same subscriptions as Shentel, but most of the company's revenue is billboard advertising and insurance premiums. | no: judge the comp by its larger part; product and customers stay yes (score 1) |

### Question 4: same chain step

| kind | sheet pair | target | comp | Matthew (v2) | Barbara | why | ruling |
|---|---|---|---|---|---|---|---|
| clear yes | P018 | OC (Owens Corning) | CSL (Carlisle) | yes | 2 | Both manufacture roofing, insulation and waterproofing products sold through contractors and distributors. | yes |
| clear no | P169 | ACH (Accendra Health) | RMD (ResMed) | no | 1 | ResMed makes the CPAP devices and masks that Accendra supplies to patients at home; ResMed's main buyers are home medical equipment providers like Accendra. One step up the chain. | no |
| borderline | P224 | ABNB (Airbnb) | INN (Summit Hotel Properties) | no | 1 | A traveller can book either, but Airbnb arranges the stay for a fee while Summit owns and runs the hotels. | no: a marketplace is not at the owner-operator's step; product and customers yes (score 1, not 2) |

## Targets with several businesses (unchanged from v2)

Answer the four questions against the **one** target business the comp matches, and name that business
in `business_graded_<you>` (for example "concrete pumping" for BBCP, or "whole company"). The sheet's
`target_business_scope` column lists the businesses. Whether a comp matching only a minor business is
capped at 1 is a rule in the code, not a judgment in the sheet.

## Two reviewers per pair, then a tie-break

- Every pair gets two human reviewers on this rubric. Agreement is measured **per question** with Cohen's
  kappa, next to each reviewer's yes rate (when almost everything is yes, kappa can be low even at high
  agreement).
- Where the two agree, that answer stands. Where they split on a question, the question is listed as
  disputed (`rubric_v3.py consensus`).
- **Tie-break:** a GPT-Terra LLM judge (`gpt-5.6-terra`) answers the same overall call and four questions
  on **all** pairs, not only the disputed ones. It breaks ties only on the questions where it has earned it:
  its kappa against the humans is at least the humans' kappa with each other (`--earned-only`). On the
  others, Riya breaks the tie.
- Tie-broken pairs are flagged (`tie_broken`). The headline numbers use pairs the humans agreed on; the
  tie-broken pairs are a sensitivity row. Single-reviewer pairs stay usable for tuning but are marked
  (`single_reviewer`).

The judge reads websites, not our facet fills, so it adds no circularity with the facet tests. Running it
(about 323 Codex calls on the subscription) needs Michael's approval and comes after the first human round.

## What this replaces: the 12-facet count

The plan to answer yes/no on all 12 facets per pair and map the count to a grade (10-12 direct, 7-9
adjacent, 1-6 not a peer) is replaced, for three reasons:

1. **A count lets the minor facets outvote the business.** Geography, channels, regulation and chain step
   are yes on most B3 pairs. On Matthew's sheet a 2-of-4 count already made 38 pairs peers with no product
   and no customer overlap; with 12 facets it gets worse.
2. **It puts the facets on both sides of the test.** The facets are what the X-learner (09_analysis) tests
   as explanations of peer judgments. If the score is built from facet matches, the test finds them
   because we put them there.
3. **Effort.** About 3,500 answers for 293 pairs instead of about 1,500, and long sheets are where
   reviewers drift.

Facet matches still exist: they come from Sonnet's company-level fills (02_profiles), compared by code.
Reviewers never answer facet or trait questions and never see gates or tags.

## Two lists: definition and test

Every facet has one job:

- **Definition list** (decides "peer"): product, customers, revenue model, chain step. These are the four
  questions. They are never tested as explanations.
- **Test list** (tested against the score): the economic traits (recurring revenue, cyclical demand,
  big-ticket, people-delivered, large customers, asset-heavy) and the general facets. They are never
  added to the rubric while being tested.

Some general facets mirror a definition question (customer segment ≈ same customers, primary products ≈
same product). Lift on those is a check that Sonnet's fills agree with what people judged, not a finding.
A new facet is put on one list before anyone tests it.

## Filling in a sheet

**File:** `outputs-local/v2/06_labels/rubric_v3/rubric_v3_sheet.xlsx`. Upload it as **one** Google
Sheet. It has **one tab per reviewer** (`matthew`, `barbara`, `riya`): open your own tab and fill only
that. 323 pairs (the 293 dev pairs and 30 extra B3 pairs), 67 targets, 12 anchors, 311 scored, the same
pairs in the same order on every tab. Written once and never overwritten; earlier builds (the old `blind_`
column, then a single tab) are in `rubric_v3/history/`. `rubric_v3_sheet.csv` is the combined machine copy
(all reviewers' columns), not for filling.

**The key sits at the top of your tab**, above the header row: one row per column you fill, named with
your own column names, with the question, what yes means and what no means, then the score rule. The pairs
start below it, at the row whose first cell is `pair`. Leave the key rows in place.

**Columns, left to right** (your answer columns hug the left so you type without scrolling; the
descriptions are reading material on the right, target and comp side by side):

| group | columns | who fills |
|---|---|---|
| Pair label (frozen while you scroll right) | `pair` (P001...), `target_company`, `comp_company`, `is_anchor` (1 = worked example from this guide, not scored) | nobody |
| **Your answers** (shaded) | `overall_call_<you>`, `same_product_<you>`, `same_customers_<you>`, `same_revenue_model_<you>`, `same_chain_step_<you>` (yes/no dropdowns); `unsure_<you>` (optional list); `business_graded_<you>`; `notes_<you>` | you |
| Descriptions | `target_offering`, `comp_offering`, `target_customers`, `comp_customers`, `target_sic_industry`, `comp_sic_industry`, `target_business_scope`, `target_website`, `comp_website`, `target_ticker`, `comp_ticker` | nobody |
| Ids | `target_id`, `comp_id` | nobody |

**When everyone is done:** download the Google Sheet as .xlsx (File > Download > Microsoft Excel) and run
the commands below on it; the script merges the tabs back by pair.

Type `yes` or `no` (any capitals; `y` and `n` work). Fill only your own columns, and don't look at the
others' until everyone is done. Please don't look up the things the sheet leaves out (see "What the
overall call is, and what blind means" above).

**What changed from the rubric v2 sheet (Matthew's round-3 sheet):**

| | v2 (round 3) | v3 |
|---|---|---|
| Questions per pair | 4 yes/no | 5: the overall call first, then the same four |
| Customers question | "Does the comp sell to the same type of buyer?" | "Would the target's own customers consider buying this kind of thing from the comp?" (same industry or payer alone is no) |
| Unsure | ad hoc, in notes | its own column; never changes an answer |
| Worked examples | none | 12 anchor pairs in this guide, marked `is_anchor`, not scored |
| Key | in the guide only | at the top of your tab |
| Layout | one tab, every reviewer's columns side by side after the descriptions | one tab per reviewer; your answers right after the pair label, descriptions to the right |
| Pairs | 262 (round 3) | 323: round 3 + round 2 (31) + 30 extra B3 pairs |
| Pair ids and order | `THR-R3-01`..., following B3's rank | `P001`...`P323`; targets in random order, each target's comps together and shuffled |
| Reviewer column sets | matthew, barbara | matthew, barbara, riya (tie-break) |
| Comp with several businesses | not defined | product and customers: any material business; revenue model and chain step: the comp's larger part (proposed) |
| Unchanged | descriptions, `business_graded`, `notes`, score rule, no typed score | same |

## Commands

    uv run python v2/06_labels/scripts/rubric_v3.py check <filled sheet>.csv
    uv run python v2/06_labels/scripts/rubric_v3.py scores <filled sheet>.csv <out dir>
    uv run python v2/06_labels/scripts/rubric_v3.py consensus <filled sheet>.csv <out>.csv --tiebreak terra --earned-only

`scores` writes `scores.csv`, `agreement.csv` (per question, peer, direct and score: pairs, agreement, kappa,
yes rates, unsure count) and `overall_vs_derived.csv`. Every command reads the .csv or the .xlsx, with or
without the key rows. Tests: `uv run pytest v2/06_labels/tests -q`.

## Still open

- [ ] Team confirms the twelve proposed rulings, especially the three borderlines and the "comp judged by
      its larger part" rule for questions 3 and 4.
- [ ] Which two reviewers cover which pairs (all three columns are on the sheet).
- [ ] The GPT-Terra judge prompt with these five questions; run after the first human round (approval).
- [ ] Whether the minor-business cap stays at 1 or becomes 0 (carried from v2).
