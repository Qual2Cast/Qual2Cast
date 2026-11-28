# Rubric v3 tie-break, headline labels and the traits rerun — 2026-11-28

Michael, with Claude Code (Opus 5.5). Branch `michael/rubric-v3-labels` (from `origin/main`; the site edits in the
working tree stay out of it). Follows `2026-11-27-rubric-v3-labels-in.md`.

## Decisions (Michael, in a grilling round)

| question | decision |
|---|---|
| question 1 on partial overlaps | judge against the comp's **main business**, the one its description leads with (no revenue split is available, so not "largest segment"); a smaller line or the same broad category is no. Also settles divested businesses |
| question 2 | customers = who buys; new wording "Do the same buyers, in the same role, also buy from the comp, even if they buy something different from it?"; any business of the comp counts; P318 THR/FLS stays a yes |
| headline agreement set | same outcome (per outcome, not all four answers) |
| tie-break | an LLM judge on all 323 pairs; on a split outcome its outcome decides (2 of 3); agreed outcomes stand. No Riya, no targeted re-answer |
| judge model | GPT-Terra through the Codex CLI (a Claude judge would set the labels the Claude selector is scored on) |
| agent profile | stack the separately graded 30 extra B3 pairs (same prompt, model, settings) |
| baseline and X-learner | both on the final labels; X-learner unchanged, overall call as its own family |
| branch | `michael/rubric-v3-labels` from main; site set aside |
| selector traits | data lines only, one trait at a time: recurring revenue, then big-ticket, then both |

## What was done

| file | what |
|---|---|
| `v2/06_labels/RUBRIC_V3.md` | the rulings, dated; Boston Omaha anchor (product no, customers yes, score 1); tie-break section; note that reviewers answered the earlier wording |
| `v2/06_labels/scripts/judge_v3.py`, `judge_v3_prompt.py`, `tests/test_judge_v3.py` | the judge (built by a helper agent; model call mocked in tests) |
| `v2/06_labels/scripts/rubric_v3.py` | `final_labels`, `judge_vs_agreed`, `final` command (+1 test) |
| `v2/06_labels/scripts/cohorts.py` | cohort `v3_final` |
| `outputs-local/v2/06_labels/rubric_v3/judge/terra_20261128T030942Z/` | judge run: pilot 32, then 63 split pairs, then the rest; every prompt, response and usage kept |
| `outputs-local/v2/06_labels/rubric_v3/final/terra_20261128T030942Z/` | `final.csv`, `judge_vs_agreed.csv`, manifest |
| `v2/current.toml` | `[rubric_v3] judge, final`, tiebreak note; `[agent_grading] extra_verdicts`; `[analysis.progress] cohort = v3_final`; `[analysis.trait_uplift] v3_*` runs; `v3_final` in `[labels] cohorts` |
| `v2/09_analysis/scripts/progress.py` | agent profiles stack `extra_verdicts` (refuse overlap; hash every file); note for `v3_final` |
| `v2/09_analysis/scripts/headline_sets.py` | `v3_final` set; every profile on all 311 pairs (+1 test) |
| `v2/09_analysis/scripts/trait_uplift.py`, `facet_uplift.py` | `--cohort v3_final`; `--outcome overall` (own family); manifest names the cohort's label file |
| `v2/09_analysis/PREREG_TRAITS.md` | amendment fixing "the v3 cohort" as `v3_final`, before the run |
| `outputs-local/v2/09_analysis/trait_uplift/20261128T04*` | round 1, round 2, overall-call runs on `v3_final` |
| `outputs-local/v2/09_analysis/headline_sets/20261128T044100Z/` | headline table; replaced runs in `history/` |
| `outputs-local/v2/09_analysis/progress/ledger.csv` | five baseline rows on `v3_final` |
| `v2/06_labels/labels.ipynb` | section 3.8 (judge vs reviewers, trust, anchors, tie-breaks, final labels); 13/13 checks |
| READMEs | `v2/06_labels/README.md`, `v2/09_analysis/README.md` |

Tests: v2 318 pass. Data: `company_list_v3`. Model calls: 323 GPT-Terra calls (Codex CLI), no API spend.

## Results

- Judge vs reviewers (kappa): product 0.81 with Matthew, 0.53 with Barbara (they 0.61 with each other); chain step
  0.79 / 0.50 (0.63); direct 0.84 / 0.70 (0.76). Where the reviewers agree: direct 95% same outcome (0.88), peer
  88% (0.74), overall call 91% (0.80). On Barbara's 62 partial-overlap "product yes" pairs it says yes on 6.
- `v3_final`: 106 direct, 78 adjacent, 127 not a peer (311 pairs, 67 targets).
- Selector on `v3_final`: direct 87% / 87%, peer 96% / 61%. Its prompt asks for the same business, so low adjacent
  recall is by design (6 of 78 kept), not a rubric effect; on Matthew's v2 labels it kept 8 of 124 adjacents.
- Traits: see `v2/09_analysis/README.md` "Rubric v3 rerun". The v2 leads (large customers, mission-critical) do not
  hold; big-ticket (peer, all pairs) and recurring revenue (direct, two cells) are the findings.

## Open issues

- The traits were found on the same 311 pairs the selector versions are scored on, so any gain is optimistic.
- The judge sees the anchors' rulings; its 12/12 is a reading check only.
- The judge cannot open websites (`call_cli` runs without tools); it uses the descriptions and its own knowledge.
- Site chapter 5 facts (on `michael/site`, uncommitted) still use the 11-27 numbers and pins to uncommitted files.
- Minor-business cap (1 or 0) still open.

## Next steps

1. Selector version `2026-11-28a` (+ recurring revenue line), scored in the ledger; then `28b` big-ticket, `28c` both
   (each shown to Michael before the next run).
2. Peer mix by industry: direct vs adjacent per target, what separates an adjacent from a direct peer; then decide
   whether to optimize a direct profile and a direct + adjacent profile separately.
3. Site: refresh chapter 5 facts from `v3_final` once this branch is merged.

## Added later (2026-11-28): peer mix, profile size, selector trait lines, recall audit

Decisions (Michael): test traits in the selector as data lines, one at a time, then all remaining traits (the
two-trait combination skipped); a comp profile should hold at least k = 3 comps: every direct peer, filled with the
best adjacents (flagged) when short, adjacents otherwise not shown; an experimental recall audit. All three are
**experiments**, not the method, until the team confirms (ask Aziz about k).

| file | what |
|---|---|
| `v2/09_analysis/scripts/peer_mix.py` (+ test) | direct / adjacent / not by sector group, adjacent patterns, B3 rank, overall call, keep rates; run `peer_mix/20261128T051409Z/` |
| `v2/04_selection/scripts/cosine_then_llm.py` (+ tests) | prompt versions `2026-11-28a`-`28k` (one trait line each; `28c` both, not run); `--traits`, `--traits-r2`, `--targets-file`; run manifest |
| `v2/04_selection/scripts/trait_line_experiments.py` | summary and flips of the trait runs against three unchanged runs; `trait_line_experiments_20261128/` |
| `outputs-local/v2/04_selection/b3_selector_candidates_*` | 10 trait runs and 2 reruns of `2026-11-04a` (67 targets, 443 B3 pairs each); a run on the wrong list (missing `--b3`) is in `history/` |
| `outputs-local/v2/09_analysis/progress/ledger.csv` | one row per run (12 selector rows on `v3_final`) |
| `v2/09_analysis/scripts/recall_audit.py` (+ test) | EXPERIMENTAL: GPT-Terra on 150 unlabelled comps below B3's lists for 10 targets; `recall_audit/20261128T055935Z_EXPERIMENTAL/` |
| `v2/09_analysis/analysis.ipynb` | sections 3.5-3.10 (headline sets, traits rerun, peer mix and profile size, selector experiments, trait lines vs noise, recall audit); 83/83 checks |
| READMEs | `v2/04_selection/README.md`, `PROMPT_VERSIONS.md`, `v2/09_analysis/README.md` |

Model calls: ~740 Claude CLI calls (Sonnet 5.5: 12 selector runs of 67 targets, plus one wrong-list run) and 150
Codex calls (GPT-Terra). No API spend. Tests: v2 345 pass.

Results:
- Selector trait lines: none beyond noise. The three unchanged runs span direct recall 82.7-89.2% and flip 10 pairs
  against each other; trait versions flip 8-16, about as often against the trait as with it.
- Profile size: the selector keeps 0 comps for 13 of 67 targets and 1 for 22 (over all B3 pairs). Of the 13, 2 are
  selector misses (DECK, SVV), 7 have only adjacents, 4 have nothing in B3's list.
- Recall audit: 0 new direct peers in 150; 21 new adjacents for the 7 thin targets, concentrated in B3's unselected
  top 10 and ranks 11-15. Thin profiles look like a small pool (B3 ranks within 373 training companies).

Open issues added:
- `PREREG_TRAITS.md` has mixed line endings since the 11-27 amendment; the v3 trait runs recorded the hash of that
  working-tree file, so a fresh checkout may hash differently (the notebook check compares ignoring line endings).
- `v2/common/cli_models.py` claude-cli: two workers can collide on the shared system-prompt file on Windows
  (PermissionError on rename); use `--workers 1` or make the write tolerate an existing file.
- Run driver for the trait runs lived in the session scratchpad (not kept); the commands are in each run's manifest.

Next:
1. Build the tier-2 fill as an experiment: for targets with fewer than 3 kept comps, a step that picks the best
   adjacents ("same buyers, different product") from B3's list and the next ranks; score tier-1 precision, tier-2
   "at least adjacent" precision, and the share of targets reaching 3.
2. Ask Aziz whether 3 is the right minimum.
3. Site chapter 5 facts after PR #45 merges.
