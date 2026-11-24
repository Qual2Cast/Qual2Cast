# v2 started: eval method, rubric v3, sub-segment traits — 2026-11-24

Michael, with Claude Code (Fable 5.2, then Opus 5.5). Branch `michael/wip`. Nothing committed.

## Request

Before v2 work: settle the north star (what we optimize and whether the metrics serve it), answer mentor Aziz's
question about facets that apply only to some sub-segments (product vs services, commercial vs consumer), add those
facets, fill them, and finalize the set for the eval group's first round. Then explain the whole method so the
team understands how the rubric, labels, facets and X-learner fit together, and start repo v2.

Michael first tried the /vision skill (installed at `~/.claude/skills/vision`); its review board needs
`npx.cmd` on this machine (PowerShell blocks `npx.ps1`). He dropped it for the grilling skill, 45 questions over
six rounds.

## Decisions (Michael)

- **North star:** overlap of the comp profile with human labels two reviewers agree on (precision and recall, any
  and direct peer, on labelled pairs only). Kappa gates which labels count; the X-learner is a diagnostic; EV/EBITDA
  is reported once.
- **No new holdout run** on the 160 targets (no labels, already scored). The locked 24 pairs stay the final check.
- **Diagnostic only this round:** B3, selector and agent unchanged; the new traits feed the X-learner only.
- **A direct peer is the same business** (same product and same customers). Economic traits are tested, not
  assumed; strong lift is the trigger to reconsider.
- **Two lists:** definition list (the four rubric questions) vs test list (traits). Never both. Outcome from
  people, treatment from Sonnet. An overall call ("would you put it in the comp set?", first called the blind question; renamed so it is not
  confused with the sheet being blind) first, as a second outcome.
- **Rubric v3:** overall call + four questions, question key at the top of the sheet, customers question tightened, three anchor pairs per question,
  optional unsure tick; 2 = all four yes, 1 = product or customers yes, 0 = neither. Reviewers answer nothing else;
  the eval group's 12-facet yes-count plan is replaced.
- **Ties:** GPT-Terra breaks ties only on questions where its kappa with the reviewers is at least the reviewers'
  kappa with each other; otherwise a third person. Headline on human-agreed pairs.
- **Traits and tags:** every company answers ten yes/no/unknown questions (tags T1-T4, traits E1-E6), filled by
  Sonnet on the subscription CLI. Gates became tags used only to slice the analysis; reviewers never see them.
  Rules: software is a product; the buyer is whoever chooses and receives; mixed companies answer for the larger
  part; unknown is never a mismatch; flip or unknown above 20% on a double fill drops a question.
- **X-learner:** pre-registered; one fit, then averaged by target tag (two levels: sells services, sells to
  consumers); shuffle test; refit bootstrap; Benjamini-Hochberg at q = 0.10; Matthew's v2 labels, direct peer
  primary, peer secondary; Barbara's old labels not used as an outcome; same run repeated on v3 labels.
- **Repo v2 is a full working copy of v1a** (first layered, switched the same day so the team works in one
  tree). v1a stays frozen. Existing runs are read in place from `outputs-local/v1a` (`paths.src()`), new runs go
  to `outputs-local/v2` (`paths.out()`); v1a's 199 MB of tracked outputs are not copied.
- **Rubric v3 sheet layout:** one .xlsx, one tab per reviewer; the reviewer's answer columns right after a frozen
  pair label (pair, target, comp, is_anchor), descriptions to the right; question key at the top of each tab with
  the reviewer's own column names; yes/no dropdowns. The first question is the **overall call** (renamed from
  "blind question" so it isn't confused with the sheet being blind).

- From v2 on, all of outputs-local/vN/ is committed (history, logs, caches); decided by Michael 2026-11-24; repo is public.

## What was built

| file | what |
|---|---|
| `v2/` (all of v1a) | full working copy by a parallel agent: 135 v1a files, 67 scripts and 12 notebooks re-pointed at v2; `common/paths.py` with `out()`/`src()`/`latest()`; `v2paths.py` a shim; `pipeline/configs/v2.toml` |
| `v2/README.md`, `v2/current.toml` | v2 layout and rules; settings (v1a's + `[traits]`, `[rubric_v3]`, `[analysis.trait_uplift]`) |
| `AGENTS.md`, `README.md` | point at v2 (current method, getting started, tests, next steps) |
| `v2/EVAL_METHOD.md` | the team methodology (sections 1-8); page: https://claude.ai/artifact/YPre3LM2i4agexKtLBH6oy (private until shared) |
| `v2/02_profiles/` | `traits.py` (schema and prompt `2026-11-24a`), `fill_traits.py`, `trait_stability.py`, 8 tests, README |
| `v2/06_labels/` | `RUBRIC_V3.md` (reviewer guide, 12 named anchor pairs, overall call and blindness explained, sheet layout, v2-to-v3 changes), `rubric_v3.py` (build-sheet with key and per-reviewer tabs, check, scores, consensus; reads .csv or tabbed .xlsx), 11 tests, README |
| `v2/09_analysis/` | `PREREG_TRAITS.md`, `trait_uplift.py` (imports v1a's estimator unchanged), 7 tests, README (parallel agent) |
| `.gitignore` | `outputs-local/v2/` shared like v1a (same local-only exclusions) |

Tests: v2 293 pass (v1a's 267 + 26 new); v1a 267 pass (unchanged); all 12 v2 notebooks run with checks passing
(no model calls; 10 still locked). Data: `company_list_v3`; v1a current runs as in `v1a/current.toml`.

## Results

- **Trait test:** 30 companies (7 showcase + 23 random training, seed 2026) filled twice with Sonnet 5.5, 30/30
  ok both times. Every question keeps: flips at most 2/30 (asset-heavy 6.7%), unknown at most 1/30. Yes rates:
  products 77%, services 63%, consumers 40-43%, organizations 100%, recurring 80%, cyclical 37-40%, big-ticket
  7-10%, people-delivered 13%, large customers 53-57%, asset-heavy 37%. Runs:
  `outputs-local/v2/02_profiles/traits_test/run1|run2/`, comparison in `traits_test/stability/`.
- **Full trait fill (approved after the test):** 533/533 ok (2 refilled after hitting the CLI's 3-turn limit),
  `outputs-local/v2/02_profiles/traits_new/tables/traits.csv`, pinned in `v2/current.toml [traits]`. Unknown 0%
  on every question except large customers (2.1%). Yes rates: products 68%, services 62%, consumers 45%,
  organizations 91%, recurring 75%, cyclical 45%, big-ticket 12%, people-delivered 13%, large customers 42%,
  asset-heavy 39%. 14 reasons quote scale figures (flagged, not used downstream). ~27 min; 77% of input from cache.
- **Pre-registration committed** before the run: `41551066` (PREREG_TRAITS.md, trait_uplift.py, its tests, the
  estimator copy), on `michael/wip`, not pushed.
- **Trait X-learner, first run** (`outputs-local/v2/09_analysis/trait_uplift/20261124T101142641398Z/`, pinned;
  8 min on 14 workers): all 60 tests supported, 15 findings at BH q = 0.10 (7 direct, 8 peer). Large customers is
  the robust one (direct +8.6 pp, -0.3 to +15.4; peer +19.0, +7.6 to +35.9; 232 pairs, 40 targets, all bootstrap
  draws usable). People-delivered (direct +11.2) and big-ticket (peer +30.1) pass the correction but are rare traits
  with 55-76 usable bootstrap draws. Cyclical demand has two negative finding cells whose intervals cross zero:
  unexplained. Recurring revenue and asset-heavy: no finding. Full table and reading in `v2/09_analysis/README.md`.
- First attempt failed: four workers wrote the same temporary system-prompt file at once (Windows refused the
  second writer). Fixed in `fill_traits.py` by writing it before the workers start.
- **Rubric v3 sheet:** 323 pairs from 67 targets (262 round-3 + 31 round-2 + 30 extra B3), new ids P001-P323
  (old ids followed B3 rank), targets in random order with each target's comps together, 12 anchors excluded from
  scoring; column sets for matthew, barbara, riya; manifest with hashes. Written once.
- **Trait X-learner:** 60 tests in the BH family (6 traits × 5 cells × 2 outcomes; unsupported counts as p = 1).
  Shuffles raised from 200 to 1,000 before any real run (200 cannot reach p below BH's strictest bar, 0.10/60).
  Smoke run on the 30-company table (`outputs-local/v2/09_analysis/trait_uplift/20261124T091611619336Z_smoke/`):
  all cells unsupported, as expected; the full run should take about 15-20 minutes on 12 workers.

## Open issues

- **Watch points from the test:** "sells to organizations" is yes for all 30 (only "sells to consumers" slices);
  big-ticket and people-delivered are rare (support may be thin); two-sided marketplaces (Cars.com) flip on
  "consumer buyer".
- Third reviewer: Riya is the default but also tunes against these labels; someone outside the model group
  (Eric or Richard) would keep labelling and tuning separate.
- The tuning/checking split of labelled targets is recommended to the model group, not decided.
- Minor-business rule (cap at 1 or 0) still open from rubric v2.
- **New rule to confirm (rubric v3):** product and customers can be met by any material business of the comp;
  revenue model and chain step judge the comp by its larger part (the Boston Omaha anchor depends on it). All 12
  anchor rulings are proposed; the three borderlines most need the team's check.
- The GPT-Terra five-question judge prompt is not written; it comes after the first human round, with approval.
- Who covers which pairs among the three reviewers is undecided.
- If the 533 stability check drops a trait, the pre-registration needs a dated amendment (BH family shrinks by 10).

## Next steps

Done tonight: the 533 fill (pinned), the pre-registration commit, the first trait X-learner run (pinned).

1. Send the rubric v3 sheet (`rubric_v3_sheet.xlsx`, one tab per reviewer) to Barbara and Matthew; Matthew
   re-answering the 120 "product no, customers yes" pairs shows what the tightened wording changes.
2. Team confirms the 12 anchor rulings and the comp-side "larger part" rule; decide the third reviewer.
3. GPT-Terra answers the same sheet (approval needed; Codex on the ChatGPT subscription), then consensus.
4. Rerun the pre-registered X-learner unchanged on the v3 consensus labels; compare with tonight's run.
5. Model-improvement group: score each prompt change in the improvement ledger (`v2/09_analysis/PROGRESS.md`);
   large customers is the first trait to try in the selector prompt if it holds on v3 labels.
6. Commit the rest of today's v2 work (only the pre-registration and X-learner code are committed).

## Added late (2026-11-24)

- **Trait round 2 (decision: cyclical demand replaced).** Cyclical demand split true direct peers as often as
  non-peers (21.7% vs 20.5% disagree) and its reasons showed the two facts that decided it, so round 2 asks them
  directly (maintenance-led, publicly funded) and adds serial acquirer and mission-critical. **Why rounds:**
  Michael wants the facet list to grow as we learn; each round gets its own committed plan, its own BH family and
  a confirmation on fresh (v3) labels, because a round designed after seeing results gives leads, not results.
  Round 1's plan got only a dated pointer to round 2; its results stand as run.
- Round 2: 30-company double fill all kept (flips <= 2/30); 533/533 filled (unknown <= 0.4%); plan committed
  `b3b5e309` before the run; run `20261124T111715563218Z_r2` (4 min): mission-critical direct +10.6 pp (+4.3 to
  +18.3), peer +25.1 (+9.4 to +42.4), a finding in all 10 tests, full support; maintenance-led, publicly funded and
  serial acquirer unsupported (4-6% yes, 21-31 mismatched pairs, one fold short of support). Peer-disagreement
  diagnostic (direct-peer vs non-peer pairs that disagree): mission-critical 8% vs 37%, maintenance-led 5% vs 14%,
  serial acquirer 12% vs 14%, publicly funded 7% vs 5%.
- Notebook: section 3.2 added (round 2, mirroring 3.1), ledger now 3.3, v1a results 3.4; 27/27 checks pass.

- **Results in the notebook** (sections later renumbered: 3.1 round 1, 3.2 round 2, 3.3 ledger, 3.4 v1a):
  `v2/09_analysis/analysis.ipynb` section 3.1 (headline table per trait, lift with
  intervals, lift by slice heatmap, the shuffle test and Benjamini-Hochberg as charts, a reliability table) and
  3.3 (improvement ledger). 22/22 notebook checks passed at that point, including that the run used the committed plan and that the
  ledger baseline matches GRADING_REVIEW. Figures for the website:
  `outputs-local/v2/09_analysis/trait_uplift/20261124T101142641398Z/figures/20261124T103038Z/`.
- **Improvement ledger** (parallel agent): `v2/09_analysis/scripts/progress.py` (score / record / show), 7 tests,
  `PROGRESS.md` how-to; `outputs-local/v2/09_analysis/progress/ledger.csv` seeded with the baseline (B3 all, B3 top
  7, selector, agent ≥ 1, agent 2 on Matthew's v2 labels). Pooled numbers match GRADING_REVIEW. MLflow was
  considered and not adopted: no shared server, and the run manifests already record settings and hashes.
