# Predictions for agent loop prompt 2026-11-05b

Riya, 2026-11-05. Written **before** any run with prompt `2026-11-05b`.

- **Baseline:** Fiona's runs with prompt `2026-11-05a`: `outputs-local/v1/agent_loop/round2_targets_sonnet/` (35 pairs) and `gold_sonnet/` (36 pairs).
- **What changed in 05b:**
  - Facet summaries can be out of date and never change a grade on their own.
  - A facet claim about the target that no target line shows is checked first (saved site, then web).
  - The multi-business cap needs a cited target line.
  - No lookups for what is already shown.
- **Why:** the facets list businesses the websites don't show: AFG annuities (sold 2021), CSL brakes and transportation, AZZ electrical products. In 05a the model capped AFG-ORI, AFG-ASIC and AFG-ACIC at 1 "because AFG also has annuities", while citing site lines that say AFG is P&C only. Its 3 lookups (RRR, SSD) were redundant searches on the comp.

These describe what the new prompt should **change**. They are not the correct grades; only the reviewers' `round2_filled.csv` can settle those.

## Round 2, prompt 05b, web search on

### AFG: most changes expected here

| Pair | 05a grade | Prediction |
|---|---|---|
| ORI | 1 (capped: annuities) | Looks up AFG about annuities first; annuity cap gone; may rise to 2 |
| ASIC | 1 (capped: annuities) | Looks up AFG about annuities first; annuity cap gone; may rise to 2 |
| ACIC | 1 (capped; narrow Florida property) | Annuity cap gone; stays 1 (narrow product overlap) |
| KINS | 1 (annuities as a side reason) | Stays 1; annuities no longer mentioned |
| SNFC.A | 1 (annuities as a side reason) | Stays 1 or drops to 0; annuities no longer mentioned |
| BRO | 1 (broker, different model) | Stays 1; annuities no longer mentioned |
| BOW | 2 | Stays 2 |
| FG | 0 | Stays 0 |
| BWIN | 0 | Stays 0 |
| BOC | 1 (comp is multi-business) | Stays 1; this cap is about the comp, not AFG |

### CSL: stale facet was only a side reason

| Pair | 05a grade | Prediction |
|---|---|---|
| CSW, OC, PPG, SPXC | 1 | Stay 1; no "non-building lines" reasoning unless a lookup confirms them |
| SSD | 1 (3 redundant comp lookups) | Stays 1; fewer comp lookups |
| EML, CR, LXU, ESAB | 0 | Stay 0 |

### AZZ: model already followed the website

| Pair | 05a grade | Prediction |
|---|---|---|
| CSW | 0 | Stays 0 |
| PPG | 1 | Stays 1 |
| EML | 0 | Stays 0 |

Few or no lookups.

### BBCP: no facet conflict

| Pair | 05a grade | Prediction |
|---|---|---|
| IESC, GVA, CDNL | 1 | Stay 1 |
| ROAD | 0 | Stays 0 |

No lookups.

### BUKS: control (the casino business IS on Butler's website, T:P1.6)

| Pair | 05a grade | Prediction |
|---|---|---|
| TXT, CNTY, ASLE, GOGO, MCRI, ACEL, ISSC | 1 (capped) | Stay 1, still capped, citing the casino line. **Any rise to 2 means the new rule is too loose.** |
| RRR | 1 (3 redundant comp lookups) | Stays 1; fewer lookups |
| WLFC | 0 | Stays 0 |

### Overall

- **More lookups than 05a** (2 of 35 pairs), mostly on the **target** side (AFG), not the comp side.
- **Few grade changes**, about 2-3 pairs, almost all on AFG. Changes on BBCP, AZZ or BUKS would be side effects to investigate.

## Round 2, prompt 05b, web search off (`--search none`)

- **Almost the same grades as web-on.** The AFG annuity question can be settled from the saved site alone: it never confirms annuities, so the model ignores them.
- **Differences**, if any, on pairs where the saved site could not settle a question.
- **If web-on and web-off are nearly identical**, the fix comes from the prompt rule, not from web search.

## Gold set (PCTY, WEN), prompt 05b, web search on

- **Still 31/32** exact agreement with the reviewers' majority grade.
- **Still no labelled non-peer** graded as a peer.
- **Near-zero lookups.** No facet-vs-website conflict like AFG's.

## How to read the results

- **Run-to-run noise.** The model is not deterministic, so one or two grades may flip with no real cause.
- **A real effect:** a grade change whose reasoning says why, e.g. "annuities not confirmed on the target's site".
- **Probably noise:** a change with the same reasoning as 05a.

## Addendum: Fiona's switch to Sonnet facets (written before any 05b run)

Fiona's PR #30 changed the defaults to Sonnet's facet fills and Sonnet for web search, and reran 05a as
`round2_targets/` and `gold/`. In those runs the stale facets no longer show up: AFG-ORI and AFG-ASIC are
already 2, annuities appear in 1 of 10 AFG reasons (the Sonnet fill records the annuity sale under
`divestiture_lines`), and no CSL reason uses Carlisle's sold businesses. The Sonnet facets still list
aerospace and medical OEMs as Carlisle customers (the Interconnect business, sold 2023).

So 05b is tested in four runs:

| Run | Folder | Settings | Compare with |
|---|---|---|---|
| A | `round2_05b_haiku_web/` | 05b, Haiku facets, Haiku web search | `round2_targets_sonnet/` (05a, same settings) |
| B | `round2_05b_haiku_noweb/` | 05b, Haiku facets, web search off | Run A |
| C | `round2_05b_web/` | 05b, Sonnet facets, Sonnet web search (new defaults) | `round2_targets/` |
| D | `gold_05b_web/` | 05b, new defaults, gold set | `gold/` |

- **Run A:** the round-2 predictions above apply as written. They were made against `round2_targets_sonnet/`.
- **Run B:** as in "web search off" above. Almost the same grades as Run A.
- **Run C:** almost no grade changes against `round2_targets/` (2 at most), and few lookups.
  - AFG stays as in the baseline (ORI 2, ASIC 2, BOW 2).
  - On CSL, the model may search Carlisle for aerospace or medical customers before grading CR or PPG; CR stays 0 and PPG stays 1.
  - BUKS casino caps are kept.
  - Any change on BBCP or BUKS is a side effect to investigate.
- **Run D:** still 31/32 against the reviewers, no labelled non-peer graded as a peer, and near-zero lookups.


## Results (fill in after the runs)

| Prediction | Held? | Notes |
|---|---|---|
| AFG: annuity caps gone, lookups on AFG | | |
| AFG-ORI / AFG-ASIC may rise to 2 | | |
| CSL / AZZ / BBCP grades unchanged | | |
| BUKS caps kept (control) | | |
| Lookups up, mostly target side | | |
| Web-off ≈ web-on | | |
| Gold set still 31/32, no non-peer as peer | | |
