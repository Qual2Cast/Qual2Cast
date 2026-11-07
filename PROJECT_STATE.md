# Project state

Short, current summary. Detailed history is in conversations/; methodology
for the scrape is in website_scrape/README.md.

_2026-11-05, Kethan's saved-result error analysis:
- New `v1/notebooks/error_analysis.ipynb`, `v1/scripts/error_analysis.py` and
  `v1/ERROR_ANALYSIS.md`. Offline comparison of historical human facet labels,
  both current profile fills, saved similarity alternatives, B3, matched
  Haiku/Sonnet screens/direct picks and one-shot/agent grades.
- Executed the offline report builder (no model calls or financial-table
  reads): `outputs-local/v1/error_analysis/20261105T191342914598Z/`.
  Report, detailed facet review, hashed provenance, derived CSVs and 258 case
  packets; 193 screening disagreements across the same 2,396 B3 pairs.
- The 480 facet labels cover 40 companies; only 41 exact-current Haiku text
  matches, 10 outside company size. DORM end markets and LUCK primary services
  retain exact-text human partial-error labels; source rechecks are needed.
  Current-fill accuracy is not inferred from different historical text.
- Pair evaluation has 32 majority labels across two targets; round 2 is still
  absent. B3 retains all 11 known direct/adjacent peers in that reviewed pool;
  screens lose several. This identifies selection-policy questions, not proven
  facet causes. The older 663-pair 0–3 study remains separate.
- User chose saved-results analysis first and manual LLM diagnosis later.
  No live agent calls are attached to Run All; manual instructions and cited
  case packets are supplied. Module/notebook syntax and diff whitespace were
  checked. No tests or notebook execution. Existing v0 notebook edit preserved.
- Next: user reviews concrete cases, verifies exact current claims, then uses
  manual agent hypotheses to propose controlled experiments. No facet values,
  selection rules or source snapshots changed (`company_list_v3`).
Details: `conversations/2026-11-05-saved-result-error-analysis.md`._

_2026-11-05 (`fiona/agent-loop`), agent loop for checking high-scoring target-comp pairs (Fiona, with Riya).
- **New `v1/scripts/agent_loop.py`:** for each B3 pair, an LLM grades the pair with the team's 0–2 rubric after up to 4 steps, each one action: search the rest of a company's saved website, search the web, or answer. A grade must cite shown lines from both companies. The target is treated as private (no investor-relations, SEC or market-data results); no figures, multiples, similarity or rank reach the model. Runs through the Claude Code CLI; web search through its WebSearch tool, or the `.env` search key.
- **New `v1/scripts/agent_loop_eval.py`:** agreement with the reviewers and with the one-shot Sol grades, the filter's effect on B3's lists, and valuation with 20+ targets. Guide: `v1/AGENT_LOOP.md`.
- **Results (Sonnet):** round-1 golden set, 31/32 exact agreement with the reviewers' majority (one-shot Sol 26/32 on the same pairs), no labelled non-peer graded as a peer. The 35 round-2 pairs are graded and wait for `round2_filled.csv`. The model looked something up on only 3 of 71 pairs.
- **Tests:** 10 pass (`v1/scripts/tests/test_agent_loop.py`). Outputs: `outputs-local/v1/agent_loop/`.
- **Update:** the facet context is now Sonnet's fills (Haiku's still describe businesses CSL, AFG and AZZ sold; Yifan's check). Rerun: round 1 unchanged at 31/32; round 2, 7 of 35 grades changed (AFG 5, BBCP 2). Current runs: `gold_sonnet_facets/`, `round2_targets_sonnet_facets/`.
- **Next:** score round 2; choose the threshold; run all 373 training targets for the valuation check.

Details: `conversations/2026-11-05-agent-loop.md`._

_2026-11-04 (evening), stronger model for the fills and the selectors (plan item 3, Matthew and Richard).
- **New `claude-cli` backend** (`v1/scripts/cli_models.py`): the fill scripts and both LLM selectors can run through the Claude Code CLI under a student's own subscription (`--backend claude-cli`, default Claude Sonnet 5.5), with no API key. No MCP servers, settings or CLAUDE.md are loaded (about 1k tokens of overhead per call instead of 300k); the instructions go in the system prompt so the cache covers them.
- **Three fills with Sonnet, all 533 companies:** the twelve general facets (`outputs-local/v1/facets_sonnet/`), Fiona's sector facets including the holdout (`sector_facets_sonnet/`), and **Barbara's SIC2 industry facets** (new `industry_facets.py` + `fill_industry_facets.py`, reading `v1/scripts/reference/sic2_industry_facet_dictionary.md`; `industry_facets_sonnet/`: 5,331 facet rows, 48% stated, 29% not applicable, 23% unknown). The Haiku fills in `facets/` are untouched.
- **Both selectors with Sonnet and with Haiku on identical inputs** (B3 lists, Haiku facets, prompt `2026-11-04a`; 373 targets each): `cosine_then_llm/20261104T074915Z_2026-11-04a_{sonnet,haiku}/`, `direct_llm/20261027T204930Z_2026-11-04a_{sonnet,haiku}/`.
- **Results** (`model_selection_eval.py` → `outputs-local/v1/model_selection/`): the fills agree on the leading category 73–92% of the time per facet (customer segment 92%, company size 73%). The screen gives the same verdict on 92% of 2,396 pairs; both models are strict (Haiku leaves 161 targets with no comp, Sonnet 106) and both drop the adjacent comps. The direct picks are where the model matters: Sonnet lists 4.9 comps per target (Haiku 2.8), and on the round 1 labels finds 4/4 WEN and 6/7 PCTY good comps (Haiku 1/4 and 4/7) with no labeled non-comp.
- **Not done:** the selectors still read the Haiku facets; B3 and the valuation have not been re-run on the Sonnet or industry facets. F9 is still filled (schema), dropped downstream.
- **Tests:** 209 pass. No API spend; CLI calls under a subscription.
- **Next:** re-run B3 + valuation on the Sonnet fills; score both models' direct picks on round 2.

Details: `conversations/2026-11-04-sonnet-model-selection.md`._

_2026-11-04, v1 baseline = B3, F9 out of the selector prompts, golden set round 2, `outputs-local/v1/` shared.
- **Decisions:**
  - B3 (method 1) is the v1 baseline, chosen on comp quality, not valuation.
  - Golden-set round 2 covers CSL, AFG, AZZ, BBCP and BUKS, plus WEN's 2 unscored pairs.
  - Reviewers are three neutral slots (A, B, C).
  - The multi-business rule is proposed ("whole company; one-business match at most 1") and left as a **stub for Eric**.
  - `outputs-local/v1/` is shared through git, with the same local-only exclusions as `comps*/`.
- **F9 prompt fix:** `cosine_then_llm.py` and `direct_llm.py` default to prompt `2026-11-04a` (no company size). Every replay or reader of saved answers pins `SAVED_PROMPT_VERSION = 2026-10-25a`: the holdout scripts, `facet_eval`, `peer_evaluation` and the notebooks.
  - **Checked byte for byte:** 533 descriptions, 533 with the sector summary, 373 saved verdicts and 373 saved direct picks are identical before and after.
  - **New check script:** `check_prompt_versions.py` (373/373 for each selector).
  - **Safer outputs:** new runs write to new folders, and `--tables-only` refuses to write an empty table.
  - **Guide:** `v1/PROMPT_VERSIONS.md`.
- **B3 for the selectors:** `method1_candidates.py` (run `20261104T074915Z`: 373 targets, 2,396 baseline pairs, identical to the notebook's B3 lists). `cosine_then_llm.py --b3` screens them; a dry run was checked.
- **`similarity_methods.ipynb`:** adds a BM25 boilerplate section (label IDF 0.12–1.07 vs a typical word's 1.3–3.8; B3 keeps 53–71% of the embedding's label premium; saturation curve; worked pair) and saves every method's ranking for the ten showcase targets. Current run `20261104T075557Z`; the results are unchanged.
- **Round 2:** `golden_set_showcase.ipynb` wrote the 67-pair blind sheet to `outputs-local/v1/golden_set_showcase/labels/round2_sheet.csv` (never overwritten). The reviewer guide is `v1/GOLDEN_SET_ROUND2.md`, with the team's six-reason rubric. The scoring cells were tested on made-up scores in a scratch folder; nothing from the test is saved.
- **Tests and cost:** 209 pass. No API calls.
- **Next:** Eric confirms the multi-business rule; send the sheet to the three reviewers; commit `round2_filled.csv`; re-run the notebook. Paid `--b3` selector run when funded.

Details: `conversations/2026-11-04-v1-baseline-prompt-round2.md`._

_2026-11-03, similarity methods (v1): new `v1/notebooks/similarity_methods.ipynb`, `v1/scripts/facet_weighting.py` and `v1/scripts/similarity_eval.py` (18 new tests; 200 pass).
- **Team decisions applied:** company size (F9) out of the similarity; "none" as missing; comps = mutual top 10, topped up to 3 (replaces z ≥ 2).
- **Reviewer rule:** majority grade as the main set (32 pairs), the 11 unanimous pairs as a strict check, unlabeled comps never counted as 0. Sol's grades are an alternative evaluation, not used for decisions.
- **Method 1:** a blend of embedding cosine and TF-IDF cosine (BM25 IDF) per facet, weighted per pair by information (summed IDF, saturated raw/(raw+K)).
- **Method 2 (FAME-inspired, no training):** facets as heads, a gate per target (information × sharpness), `;`-piece best-match scoring.

Results on 373 training targets:
- **On the reviewed comps,** every method finds all direct comps. Methods 1 and 2 also find all adjacent comps (PCTY 7/7, WEN 4/4), while v0 misses BBSI and BDL; both are recovered by the "none" fix. Methods 1 and 2 drop v0's non-comps (v0 lists 3/5 for PCTY and 7/16 for WEN; method 1 none, method 2 one), mostly through the mutual filter.
- **Precision@10 and robustness:** WEN goes from 0.30 to 1.0 and PCTY from 0.67 to 1.0. Barbara and Matthew agree on their own; Riya's broader grades don't separate the methods.
- **Sol (alternative check, 156 holdout targets):** the new lists keep 81–82% of Sol-direct comps (v0 84%) with a third of the non-comps.
- **Side effect:** the TF-IDF blend lifts Lamb Weston for WEN on shared words.
- **Charts and facet analysis:** the notebook now has charts of each method's list and of every reviewed comp's rank, plus method 2's facet weights and per-facet contributions. For WEN, revenue model does most of the separating (0.050 of a 0.171 gap) and gets the largest gate (14.0%). For PCTY, whose non-comps are other software firms, the separation is spread across facets.
- **Valuation doesn't move.** Median APE: v0 top 10 28.8%, method 1 30.0%, method 2 30.3%. Every interval against v0 includes 0, and with one-way top 10 the new methods score 29.7% and 30.2%.
- **Method 2 ≈ method 1.** The gate mostly follows information.

Other changes and state:
- **Rename:** the LLM selectors are now `cosine_then_llm.py` (was `judge_comps.py`) and `direct_llm.py` (was `suggest_comps.py`); "judge" now means the evaluators only.
- **F9 in the selector's prompt:** deferred to the next paid run (a version bump would hide saved verdicts from the readers that filter on the current version).
- **No API calls** were made; API spend is on hold until the method is settled or funded.
- **Data:** `company_list_v3`, facets `2026-10-25k`, split `20261027T204930Z`, run `outputs-local/v1/similarity_methods/20261104T052054Z` (earlier runs from the same session are in `history/`).

Next: reviewers score the 2 new WEN pairs (`labels_topup/topup_sheet.csv`), and the golden set gets more targets. Details: `conversations/2026-11-03-similarity-methods.md`._

_2026-11-03, README rewritten for non-technical readers: what the project does, the recipe in four plain steps, status and results, a folder map (v1 current, v0 the 2026-10-28 record), setup, rules, team contributions, next steps and terms. Pre-v0 sections, PR history and branch tables removed; `pre-v0/README.md` is linked for that history. Details: `conversations/2026-11-03-readme-rewrite.md`._

_2026-11-03, v1 = a working copy of v0, and a shared uv environment: `v1/` is v0 as left on 2026-10-28
(notebooks with their saved outputs, unedited apart from paths), with all code in `v1/scripts/` and outputs in
`outputs-local/v1/` (seeded from v0's `comps_pilot_targets/` plus universe, facets, fill tests, API checks and
embeddings by `v1/scripts/seed_from_v0.py`; v0's folders untouched). Reads of the size-stratified baseline still use
`outputs-local/comps/`. `pyproject.toml`, `uv.lock`, `.python-version` (3.12) at the root: `uv sync` gives every
machine the same environment; 182 tests pass under it, and a cloned notebook (golden set) runs under it.
AGENTS.md now points to v1. `main` was fast-forwarded to PR #23 first; Kethan's `kethan/wip` pipeline is set aside.
Label sheets: `outputs-local/v1/gold_labels/source/` (480 facet labels) and `outputs-local/v1/golden_set/labels/`
(three reviewers, 36 pairs). Search API keys (Serper, Tavily, Brave) are in `.env`. Not run: the RAG crawl, search
and verifier; Kethan's LLM-as-judge on the SIC2 baseline. Known when re-running on Windows: (a)
`graded_peer_selection.evaluate_saved` rejects saved grades because `core.autocrlf` changes the universe CSV's line
endings (content is the same); (b) `holdout_split_candidates.py` takes over 10 minutes (it re-reads the embedding
archive per pair); (c) the sector-facet holdout routes kept only result tables, not raw answers. Details:
`conversations/2026-11-03-v1-clone-and-uv.md`._

_2026-10-28, sector-facet holdout comparison (local branch): Fiona's frozen
`generic + all sector facets` configuration was filled for all 533 eligible
companies from saved website evidence using GPT-6.1 Sol. The fixed 373/160
SIC2 split and six existing peer-selection routes were reused; no peer rule,
0–2 rubric, or EV/EBITDA estimator changed. The new ranking has 2,470 z≥2
holdout pairs (general facets: 2,138). All 160 holdout targets completed
both LLM selection routes and source-cited grades; 2,315 pairs received a
numeric grade. In the main `v0/notebooks/comps_and_valuation.ipynb`, the new
six-row results sit beside the six saved general-facet rows. Cosine-only median
APE moves from 37.32% to 34.97% on all 160; the paired median change is
−1.94 percentage points (95% target-bootstrap interval −3.81 to +0.25).
Other routes have different coverage and no clear paired-median gain. The
PCTY/WEN reviewer-label pilot improves majority pairwise ranking accuracy
from 0.851 to 0.904 on 32 labeled pairs, but has only two targets. The
notebook validates, its code cells parse, and 33 targeted tests pass. Saved
inputs, raw calls and tables are in `outputs-local/comps_pilot_targets/sector_facets/`;
details: `conversations/2026-10-28-sector-facets-holdout.md`. Next: team review
the paired results and obtain independent holdout peer labels before adopting
the added facets as the default._

_2026-10-28, gold/holdout integration: Michael's 27 October SIC2 v0
candidate run was extended to all 160 holdout targets with the same 373-firm
training pool. The four routes processed 2,138 cosine→LLM candidate judgments
and 311 direct-LLM selections without invalid labels. On the 107 targets
covered by every route, median EV/EBITDA APE is cosine 36.83%, cosine→LLM
37.50%, direct LLM 37.79%, and LLM→cosine 37.93%; paired intervals do not
establish a winner. Removing F3 improves peer-label ranking on the two gold
targets but has threshold-dependent holdout effects. The source-backed split
improves its targeted source check, while tested downstream interventions do
not help consistently. Executed report and tables:
`v0/notebooks/gold_and_holdout_integration.ipynb` and
`outputs-local/comps_pilot_targets/holdout_completion/evaluation/`; details:
`conversations/2026-10-28-holdout-integration.md`._

_2026-10-28, reviewer and split refinement: three completed 36-pair
PCTY/WEN reviews score the four saved routes separately; only 11/36 pairs are
unanimous. A source-checked 40-company business grouping retains each current
activity once under its original company ID; 8 firms have multiple groups.
The targeted primary-source audit improves current/exited activity statuses
from 27/34 to 34/34 and exact group partitions from 7/9 to 9/9. In ten selected
development targets, adding split context changes 4/137 peer decisions and
raises median APE from 19.26% to 39.41% (coverage 7/10 both). In six firms
from the fixed holdout, it changes 1/72 decisions and raises median APE from
31.02% to 40.21% (coverage 4/6 to 5/6). The split is kept as source-linked
metadata; the tested prompt is not adopted as the v0 peer rule. Executed
notebook: `v0/notebooks/business_split_refinement_eval.ipynb`; details:
`conversations/2026-10-28-reviewer-and-split-refinement.md`._

_2026-10-27, holdout notebook built, not scored by this notebook (note added at merge: the fixed holdout was later scored by the team's 2026-10-28 holdout runs above, which use a different pipeline, and this notebook's own freeze is still unwritten): `v0/notebooks/holdout_test.ipynb` applies the baseline's rules to new targets (comps from the 373 training firms only, so a holdout multiple cannot reach an estimate). `MODE = "training"` is a reference run on the training firms (reproduces the baseline: no matching 31.9%, cosine top 10 weighted 28.8%, LLM good comps 30.5%); `MODE = "holdout"` needs `holdout/freeze.json` (settings plus one `PRIMARY_RULE`, written by the notebook), runs the frozen judge once through a printed `judge_comps.py` command, and refuses a second score under the same freeze. New `valuation.bootstrap` gives 95% intervals for each rule's error and its gain on no matching: on the 373 training targets no rule's gain interval excludes 0 (cosine top 10 weighted: +3.1 points, -1.5 to +5.5). The direct-LLM routes are not in the holdout notebook: `suggest_comps.py` has no target-set option. Holdout untouched; no freeze written; `PRIMARY_RULE` not chosen. 129 tests pass (1 new). Next: label the golden set, choose `PRIMARY_RULE` with the team, freeze, then score once. See `conversations/2026-10-27-holdout-notebook.md`._

_2026-10-27, golden set built, not labeled: `v0/notebooks/golden_set.ipynb` and
`v0/golden_set.py` pool every comp the four routes found for PCTY and WEN (36
pairs: 16 and 20), write a shuffled sheet with no rank, similarity, verdict or
multiple to `outputs-local/comps_pilot_targets/golden_set/labels/golden_set_labels.csv`,
and, once Michael has scored it (2 direct, 1 adjacent, blank = 0 with one of five
reasons), check it and print precision@10, direct hits@10 and NDCG@10 per route.
The notebook never overwrites the sheet and waits for every pair to be reviewed.
No API calls; data version `company_list_v3`, candidates run `20261027T204930Z`.
Tested with throwaway labels in a scratch folder (not the real sheet). 105 tests
pass (6 new). Next: label the sheet, re-run from section 3, then compare the
LLM judge's verdicts with the hand scores. See
`conversations/2026-10-27-golden-set-notebook.md`._

_2026-10-27, updated baseline (proposed): `v0/notebooks/comps_and_valuation.ipynb`
is now the updated baseline model. It uses the business-structure pilot's ten
targets as the showcase set (with the reason each was picked) and the split
stratified on SIC2 instead of company size, which is left free so it can be
tested. The previous baseline is kept in
`v0/notebooks/history/comps_and_valuation_size_stratified.ipynb`; earlier notes
below that name `comps_and_valuation.ipynb` describe it. Judge and direct picks
were re-run on the new split (Haiku 5.5, prompt 2026-10-25a, 373/373) and the
notebook executed with no errors. Training-target median absolute % error: 31.9%
no matching, cosine 28.8-32.1%, LLM routes 30.5-30.6%, same SIC 35.1-36.7%, so
the routes are still bunched. New sections: 7 (per-facet separation and lift,
heatmaps; company size has AUC 0.49 and lift 0.01; a shared "none" inflates the products and services facets), 8 (size is not a useful comp
filter) and 9 (choosing the two golden-set targets; current pick PCTY and WEN).
Outputs are in `outputs-local/comps_pilot_targets/` (README there), not
`comps/`, because the judge and suggest scripts default to the latest candidates
run in `comps/`; `suggest_comps.py` now finds the split beside the candidates
run. `.gitignore` now shares every `outputs-local/comps*/` folder by default (logs, dry-run prompts, `*_history`, raw Codex output and a `history/` of reruns stay local); the rest of `outputs-local/` stays local because the repository is public. A facet that does not apply is embedded as "none" (exact 1.00 match): the stopgap and the source fix are written up at the end of the notebook, not applied.
99 tests pass. `company_list_v3` remains the source snapshot; `comps/` is
unchanged. Holdout untouched. Size is not balanced between training and holdout
under SIC2. Next: decide how to treat "not applicable" facets (notebook section 10), build the golden set for PCTY and WEN and decide with the team
whether this split replaces the previous baseline's. See
`conversations/2026-10-27-updated-baseline-sic2-split.md` and `v0/README.md`._

## Downstream LLM peer evaluation — 2026-10-27

- Integrated with updated main at `e2bf5a2e`: kept its SIC2 baseline and all
  existing notebook cells; appended the evaluator handoff as section 11.
  Evaluator split lookup follows the candidate stage's output root so a new
  handoff can use `comps_pilot_targets/`. Defaults and the completed 663-pair
  results still refer to the original size-stratified baseline, not SIC2.
  Peer-evaluation raw runs and local analysis remain ignored by Git.
- Notebook section 7 now analyzes a saved run without model calls: coverage
  and pass metrics, grade/outcome and fit-dimension charts, target coverage,
  illustrative pairs and evidence/validation issues. Default analysis input:
  completed local run `20261027T190213461887Z` (663 pairs, 615 numeric grades,
  139 score-3 peers, 44 insufficient-evidence answers, 4 invalid answers).
  Derived outputs go to `analysis/`, with replaced versions archived.
  Added matplotlib to judge requirements. New cells have not been executed;
  no tests or model calls were run for this change. Next: user runs section 7.
- New notebook: `v0/notebooks/peer_evaluation.ipynb`; logic in
  `v0/peer_evaluation.py`, CLI transport in `v0/cli_models.py`, setup in
  `v0/PEER_EVALUATION.md` and `v0/requirements-judge.txt`.
- It evaluates the final accepted outputs of cosine → LLM, using the user's
  selected 0–3 business-fit rubric, with null for insufficient evidence.
  It matches the current z cutoff, selection prompt version, completed
  upstream target decisions and training-only peer pool.
- The evaluator sees company names/websites and saved cleaned source passages,
  not upstream facets, reasons, scores, ranks, SIC or financials. Citation labels
  resolve to actual text/URLs/dates. This is an automated evaluation aid, not
  independent human labels or measured accuracy.
- Codex CLI is the default; Claude Code CLI is selected with `claude-cli`.
  Each pair has a separate structured call, raw logs and checked response.
  Matching successful calls resume; replaced files are archived.
  Notebook setup now exposes optional executable overrides and prints the
  resolved CLI before live preparation. Codex also detects the macOS desktop
  app's bundled executable when the VS Code kernel PATH lacks `codex`.
  Both providers retain direct subprocess calls and their normal CLI login.
- The matching notebook now ends with a frozen judgment snapshot and handoff
  export for the evaluator. Its existing cells, results and valuation logic
  are unchanged. Per the latest user request, the evaluator now uses all
  training targets, no pair sampling limit and `RUN_JUDGE=True`. `RUN_DIR=None`
  starts a new manual run; a prior output directory can be supplied to resume.
- Validation: Python modules and notebook code cells parsed successfully;
  `git diff --check` passed. No automated tests, model calls, embedding runs or
  embedding runs were performed. Subsequently installed the judge requirements
  in the project `.venv` through VS Code's terminal. Full preparation succeeded:
  373 targets, 663 accepted pairs across 277 targets, zero missing upstream
  verdicts. Despite stale VS Code UI observations, the terminal launch took
  effect and a partial live batch ran. On the user's clarification to update
  code only, its runner and inference subprocess were stopped and process
  exit verified. Partial outputs remain in
  `outputs-local/comps/peer_evaluation/training_20261027`; they are not a
  completed full-training evaluation. Citation parsing now accepts displayed
  bracketed labels while still resolving only exact supplied passage IDs.
- Source data remains `company_list_v3`; saved input captures were not changed.
  Next: the user will manually Run All in VS Code, then calibrate against
  independent human scores. Changes are local on main; no commit or push.
  Handoff: `conversations/2026-10-27-llm-peer-evaluation.md`.

_2026-10-27, business-structure pilot:
`v0/business_split.py` and executed
`v0/notebooks/business_structure_eval.ipynb` are the two analytical files.
The method keeps one company ID, separates broad current businesses using
company-source evidence, groups related products, and removes only documented
completed exits. A thin page cannot silently delete a business. It classified
all 40 development companies: 33 one-business, 7 multi-business; 8 carry
source-gap flags. Ten deliberately chosen source challenges matched their
expected direction, but they are not independent accuracy labels. The old F10
Sheet concerns older Haiku descriptions and is not split ground truth.
The downstream paired v0 test changed 10 of 142 peer decisions. Matched-peer
coverage fell from 7 to 4 of 10 targets; median absolute percentage error with
the existing no-matching fallback was 29.21% for the original judge and 32.10%
with full split context. The new scope is therefore an audit aid, not a
validated replacement for v0 peer selection. `company_list_v3` remains the
source snapshot; the v0 533-company inputs and notebook were not edited.
Next: independent split/peer labels and a held-out test before changing the
valuation rule. Details and saved-output paths:
`conversations/2026-10-27-business-structure-review.md`._

_2026-10-24: repo reorganized. The comps recipe (v0) is in v0/; earlier
work (matching, growth signals, the ten-company pilot, scraps) moved into
pre-v0/, see pre-v0/README.md and conversations/2026-10-24-pre-v0-reorg.md._

_2026-10-24, later: v0 steps 1-3 built (universe, EV/EBITDA 3-30, twelve
facets F1-F12 filled by the LLM from its own knowledge, one profile per
business); fill test 99.7-100%. AGENTS.md trimmed to working habits; the
method lives here and in v0/README.md. See
conversations/2026-10-24-v0-steps-1-3.md._

_2026-10-25: training/holdout split (373/160, stratified on company size
F9, seed 2026, ten showcase targets in training) and recipe step 4
(candidate comps by per-facet embedding similarity, top 10 or z ≥ 2,
training pool only) built in `v0/notebooks/comps_and_valuation.ipynb`.
Model decided: prompts plus weights fit on training pairs. Steps 5-7 open.
See conversations/2026-10-25-split-and-candidates.md._

_2026-10-27: recipe steps 5-6 and the facet add/drop review started on
branch `fiona/sector-submodels`: SIC → FF49 → sector groups
(`v0/sectors.py`), sector-specific facets from Barbara's framework plus a
sub-sector facet (`v0/sector_facets.py`, filled by
`v0/fill_sector_facets.py`), and `v0/facet_eval.py`, which scores facet
variants and sector sub-models against the golden set and the judge. Run
on the judge labels of both baselines (updated baseline: generic 0.899,
+SIC4 sub-sector 0.911, minus F3 0.911, minus F8 0.906, +FF49 0.895,
sector sub-model 0.78). Sector-specific facets are evidence-first (website
pages, cited) and not filled yet (no API key). See v0/README.md and
conversations/2026-10-27-sector-submodels.md._

_2026-10-25, merge with main: the teammates' work merged into main on
2026-10-19/20 (PRs #5-#7: the integrated company workflow in `pipeline/`,
`valuation/`, the team memo and growth-signal updates) moved into pre-v0/
with the rest, at Michael's request; its two sections from main follow,
with paths updated. See conversations/2026-10-25-split-and-candidates.md._

## Team research memo (2026-10-20)

PR #6's integrated workflow is on main. A four-page memo now consolidates the
team's evidence under research question, data/assumptions, approach/rationale,
results/interpretation and limitations/next test. Individual contributions and
implementation records are in a linked appendix. The same material opens
`pre-v0/notebooks/team_company_workflow.ipynb`; its technical workflow follows unchanged.

The memo distinguishes the original 535-company matching study from the
538-company integrated evidence universe and the ten development targets.
The default integrated estimate covers 2/10 targets; its 53.6% median APE is
compared only with baselines on those same two cases. No new private-company
accuracy, independent peer review or growth forecast is claimed.

Validation of this revision is editorial: all 17 code cells, saved outputs,
embedded inputs and eight figures match the previously executed notebook.
See `pre-v0/reports/team_company_workflow/VALIDATION.json` and
`conversations/2026-10-20-team-research-memo.md`.

## Integrated 19-company experiment (2026-10-19)

New entry point: `pre-v0/notebooks/integrated_company_analysis.ipynb`; summary and
review queues: `pre-v0/reports/integrated_company_analysis/`. It combines the two
ten-company lists (PCTY overlaps), current team matching families, earlier
representation/activity alternatives, financial reranking and growth extraction.
The original ten-company notebook remains unchanged.

Validation: 33 code cells, zero errors, five figures; 14 new regression tests,
96 main website/growth tests and 169 recall tests passed. Independent relevance
labels, dated valuation definitions and historical growth panels are still
missing; lower development error is not evidence of approved business matches.
See `conversations/2026-10-19-integrated-company-analysis.md` for exact scope,
data version and next steps. Baseline code is unchanged; recall is pinned
separately rather than merged.

_Last updated before that: 2026-10-19 (`michael/wip` merged with main: see
conversations/2026-10-19-merge-main.md. Matching: three methods and an
evaluation notebook; methodology in pre-v0/matching/README.md; history in
conversations/2026-10-19-method2-mutual-knn.md. Methodology rules updated
after Aziz's reply on 10-Ks and financial inputs; growth-signal recall: see
conversations/2026-10-19-growth-signals.md)_

## Data

- Required snapshot: `company_list_v3` (see data_manifest.json). 560 US
  public companies, used as stand-ins for private targets.
- v3 = raw list + SIC zero-padding fix + website fixes (IR hosts → main
  domain; Smith Douglas website supplied). Built by src/prepare_company_list.py.
  BrightView Holdings was SIC 700 → 0700, Agricultural Services (it had been
  grouped with hotels under SIC 70). Only row affected. See docs/data_issues.md.
- Snapshot CSVs are CRLF and stored byte-for-byte (.gitattributes `-text`),
  so the manifest checksums match on every OS. Before 2026-10-18 (commit
  3a50a32) git stored them as LF and non-Windows checkouts failed the
  checksum check; anyone who cloned earlier should pull, then run
  `git checkout -- data-local/snapshots`.
- Data maintainer distributes snapshots outside GitHub: _TBD (name)_.

## Agreed methodology

- Aziz's rule (updated 2026-10-19 after his reply to Haoyan): the **private
  target** side is name + website, plus three figures we may assume are
  known: LTM revenue, LTM EBITDA, and debt. The **public comp** side may use
  10-Ks and other public detail (business description, segments, detailed
  financials, founding year, operating locations, etc.) as similarity
  inputs. Aziz's priority: comps must be in the same business as the target
  (public vet hospitals for a private vet hospital, not human clinics);
  scale similarity is secondary. Investor pages and stock data are still
  not used for the target.
- All collection is programmatic; nothing written by hand.
- v0 facets (decided 2026-10-24): the LLM fills all twelve facets from what
  it knows about the company, given its name and website. Each facet records
  its source ("model knowledge", or "website" with quotes and page URLs);
  "unknown" is a last resort. This replaces the earlier "unknown, never
  guessed; every fact cites a URL" rule for facets. The saved website pages
  only fill gaps: every company is first filled from what the model knows
  (name and website only); a company left with an unknown facet then gets a
  second call with its saved pages, and only the unknown facets are taken
  from it, so page text never replaces what the model knew. A company with
  unrelated businesses gets one profile per business.
- Financial fields: the target's LTM revenue, LTM EBITDA and debt (and
  derived margin, debt/revenue) may be compared with the comps' figures to
  favor similar-scale comps. EV/EBITDA is the valuation output and is never a
  matching input. Financials still live in separate columns or tables keyed
  by IQ_COMPANY_ID, not mixed into text inputs.
- Non-financial information only: the scrape's filters remove financial and
  size figures, tickers and public-company language from the text, and log
  every removal with its reason.
- Raw scrapes, intermediate text, model prompts/responses, and processed
  tables are all kept.
- robots.txt: honored. One that answers 401/403 counts as no restrictions
  (RFC 9309), decided 2026-10-18.

## Matching methodology (working approach)

On branch `michael/wip`, not yet reviewed by the team. Full write-up:
pre-v0/matching/README.md, "Methodology".

- Every public company takes a turn as the private target: comps are found
  among the other 534 from website text only, the estimate is the comps'
  median EV/EBITDA, and the actual multiple is the answer key.
- Benchmark: no matching (the median of all other companies). Measures:
  median absolute % error and Spearman(estimate, actual); differences from
  method 1 by paired bootstrap; methods also compared at equal comp counts
  (3-10) and on ten chosen targets.
- Settings are fixed before scoring, on the shape of the comp sets, never
  tuned on valuation error. SIC codes are a check only.
- Stricter than the current rules: the methods were built under the
  original name + website rule, so they use website text only on both
  sides. Since 2026-10-19 the target's LTM revenue, LTM EBITDA and debt may
  be compared for scale, and comps' 10-K detail may be used. Neither is in
  the methods yet. EV/EBITDA is still only the answer key.

## Status

| part | status | where |
|---|---|---|
| Comps recipe (v0) | **Steps 1-3 built and run (533/533 at version k). Split and step 4 candidates built 2026-10-25** (`v0/split.py`, `v0/candidates.py`, `v0/notebooks/comps_and_valuation.ipynb`; 89 tests). Earlier notes on steps 1-3: Universe = the 560 list (all US, 43 SIC2 codes); 27 dropped outside EV/EBITDA 3-30, 533 left. Twelve facets F1-F12, filled by an LLM from model knowledge (name + website): Claude Haiku 5.5 through the Anthropic API from 2026-10-24 (`fill_facets.py --backend claude`, the default; Codex CLI still a backend), not run yet, needs an API key; one profile per business, prompt version 2026-10-24i (the model describes only companies it knows: `knows_company`, and a company it doesn't know is all unknown in the first pass and goes to the pages; checked with made-up companies, which came back invented from their names at version h and all unknown at i, while Paylocity is still filled; one-line JSON; details of about twenty words, lists of up to five; company size a category with no text: small, mid-sized, large, among the largest; no source asked without pages; page lines labeled and cited by label; page lines with figures left out and every prompt checked for figures: 0 of 533). Fill test at version i done 2026-10-24 (`fill_test/knowledge_only_i_haiku`, 31 companies, $0.041 for both passes): 29 known and filled in the first pass (AMETEK's primary services from the pages), Cardinal Infrastructure and Englewood Lab unknown to the model and filled from their pages (Englewood after a rescrape: its first scrape had saved the browser's certificate-error screen), so 100% of 456 facets; 5 companies split (Albemarle 3, St. Joe 3, AZZ, Con Ed, SBC Medical 2); on the any-of category facets Haiku lists fewer categories than Codex f but shares at least one for 95-100% of companies. API key in `.env`; API checks in `v0/check_claude_api.py`. Fill test: 31 companies picked + random, 21 done before the Codex usage limit (100% filled at version f; 99.7% on 30 at version e); the 12 hard picks also once with the saved pages (99.3%, version e). Category facets move between runs: versions e and f (same default model) agree on revenue model for 62% of companies, distribution channels 86%. Notebook `v0/notebooks/comp_universe_and_facets.ipynb`; fill runs (model, tokens, fill %) and the fill test in `v0/notebooks/facet_fill_runs.ipynb`. First Luna run (2026-10-24) hit the usage limit on its first calls; nothing filled. Two passes: model knowledge for every company, then saved pages only for facets left unknown (run again when a company's pages change); instructions and schema cached (about $0.001 per company). 58 tests. Details and decisions in v0/README.md. | v0/, outputs-local/comps/ |
| Website scrape | **Done for all 560** (3 pages per site, re-parsed 2026-10-18; Englewood Lab rescraped 2026-10-24): 533 ok, 14 thin, 4 investor_site, 4 robots_disallowed, 4 http_403, 1 blocked. The browser's certificate-error screen counts as a failed load (next address tried), and a homepage in another language switches to its /en/ copy. 33 tests. | website_scrape/, outputs-local/website_scrape/ |
| Growth signals | **On main: first collector + rule extractor** (2026-10-18), 5-company pilot, 70 tests. **Improved rules are on branch `growth-signals-recall`, not yet merged:** recall widening, sentence-boundary fix, one event per article, other-company actor check, five new event types; 211 tests; about 58-61% precision / 43% recall on unseen companies. See conversations/2026-10-19-growth-signals.md. | pre-v0/growth_signals/ |
| Matching method | **Three methods and an evaluation, on branch `michael/wip`.** `pre-v0/matching/matching_methods.ipynb`: website text → `all-mpnet-base-v2` embeddings (535 matchable, 25 excluded) → comps by method 1 (embedding similarity, cosine z ≥ 2 / 2.5), method 2 (mutual kNN, k = 10 / 20; then UMAP + HDBSCAN clusters), or method 3 (agglomerative tree, complete / ward linkage) → estimate = comps' median EV/EBITDA (financials read only there). Each method is shown on PCTY and then values every company from its own comps. `pre-v0/matching/matching_evaluation.ipynb` (runs the methods notebook first): every method at 3-10 comps, and ten targets (PCTY, BV, ROAD, FIX, BRO, ADUS, LOPE, ODFL, WING, DXPE). **Results:** median absolute error ≈ 35% for every method, the same as no matching (34.6%); method 1 ranks companies best (Spearman 0.31 vs 0.21-0.24 for the others and 0.22-0.24 for SIC peer groups); at equal comp counts no method beats method 1; targets with clear peers get them (ROAD, BRO, LOPE, ADUS), finer distinctions fail (truckload types, contractors vs HVAC makers, distributors), BV gets comps though it has no real peer, and right peers still miss by 29-43%. Latest runs `20261019T080322Z` (methods) and `20261019T080416Z` (evaluation). `umap-learn` and `hdbscan` 0.8.44 are installed in the kernel's Python 3.14. | pre-v0/matching/, outputs-local/matching/ |
| Results across targets, sanity check, definitions / limitations | **Started:** valuation error for all 535 matchable companies, every method at 3-10 comps, and ten targets (`pre-v0/matching/matching_evaluation.ipynb`). Human check of comps against source pages, and definitions / limitations, not started. | pre-v0/matching/ |
| Ten-company research pilot | **Frozen ten-company research comparison available.** Independent human review and financial alignment remain pending; not integrated into the main matching workflow. | pre-v0/reports/whole_company_pilot/, pre-v0/notebooks/whole_company_pilot.ipynb |
| Integrated team workflow | **On main 2026-10-19/20 (PRs #5-#7), moved to pre-v0/ 2026-10-25.** Staged company workflow, integrated 19-company experiment and four-page team memo; see the sections above. | pre-v0/pipeline/, pre-v0/valuation/, pre-v0/notebooks/team_company_workflow.ipynb, pre-v0/reports/team_company_workflow/ |
| Earlier attempts | Set aside 2026-10-18, kept runnable for reference: Codex profiles (219/560 done), first matching pass, first collection script. | pre-v0/scraps/, outputs-local/scraps/ |

## Ten-company pilot contribution (2026-10-19)

- Uses the approved `company_list_v3` snapshot and archived website text. All ten targets are development cases; comparisons use a fixed 183-company candidate pool, partly selected by constituent retrievers.
- Includes 31 ranking variants, 279 compatible peer-count/aggregation configurations, four direct valuation configurations, citations, company-level results and human-review forms. The notebook is the independent experiment entry point; source modules are exposed in `pre-v0/experiments/whole_company_pilot/`.
- Default replay recomputes analysis from saved model outputs; full inference is an explicit separate workflow. Publication wording is normalized; numerical results and model logic are unchanged.
- Michael's newer `michael/wip` matching notebook uses a different eligible universe and z-threshold selection. This pilot does not establish superiority over that version. Growth diagnostics cover pinned `41aa007`, not `growth-signals-recall` schema v2, and do not validate a growth forecast.
- Validation and next actions: [handoff](conversations/2026-10-19-whole-company-pilot.md). The report distinguishes financial-only controls from approved business peers and automated source-based review from independent human judgments.

## Open questions

- Websites needed for 4 companies whose main domain redirects to an
  investor-relations site (docs/data_issues.md #3): Avista, Black Hills,
  Simpson Manufacturing, IAC.
- Who is the data maintainer, and where are snapshots stored (university /
  sponsor storage)?
- Size as a matching feature: answered 2026-10-19 for revenue, EBITDA and
  debt (allowed, secondary to same-business match). Headcount is still
  filtered out of the website text; undecided.
- Date of the multiples in the company list (needed to judge how stale the
  website text is relative to them). The recipe asks for year-end-2025
  financials; v0 uses the list's multiples as given until this is answered.
- Who pays for the API calls, and on whose Anthropic Console account (about
  $0.30 for all 533 with Claude Haiku 5.5, a few dollars with retries and
  tests). Decided 2026-10-24 to use Haiku 5.5 because the Codex usage
  window allowed only ~200 calls; the notes below are the background.
- Codex quota: about 200 facet calls fit in one ChatGPT account's usage window
  on 2026-10-24, so the 533-company fill needs a cheaper model, shorter
  answers, batching, several accounts, or an API. Measured per call (version
  f, name + website): ~17-18k input tokens, of which ~15k is Codex's own
  scaffolding (cached when calls run back to back), ~900 output, ~70
  reasoning. Output is most of the cost, so lower effort or more workers
  barely help. Version g shortens the answer; GPT-6 Luna (`--model
  gpt-6-luna`) costs ~1/20 of GPT-6.1 Sol per token on OpenAI's Codex rate
  card. Whether Luna's facets are good enough is untested (see the handoff
  2026-10-24-short-answers.md).
- Whether financial columns may stay in files like Riya's
  `company_list_for_interns.csv`: decide when training the forecasting model.
  For now financials are kept, but always in separate columns or tables from
  matching inputs.

## Next steps

v0 (current):

1. Full run at version k (2026-10-25): one profile per company, no
   business splits (`facets.SPLIT_BUSINESSES = False`; decided 2026-10-25,
   splitting left for the group to pick up, see v0/README.md "One profile
   per company"). **Done 2026-10-25** in `facets/` (log
   `facets/logs/fill_20261025T045332Z.log`): 533 companies, 533 profiles,
   6,389 of 6,396 facets filled (7 unknown on 6 companies the model didn't
   know); 19 companies filled from their pages; 330 cited page lines, all
   found; 1 flag (website_without_quote); 13 divestiture flags. $0.552 for
   552 calls, median 8.8 s. Version j (with splits, 599 profiles) is in
   `profiles_history/`. Known limit: out-of-date facts (American
   Financial's annuities, AZZ's electrical products, Carlisle's brake
   components) are only caught where the pages mention the sale; RAG is a
   possible later step. Next: the manual review, then recipe step 4.
2. Split and step 4: **built 2026-10-25** (`comps_and_valuation.ipynb`,
   split run `split/20261025T061905Z`, candidates
   `candidates/20261025T061905Z`). 373 training / 160 holdout; size shares
   equal, numeric SMDs 0.00-0.13 (debt/revenue 0.126), but SIC divisions
   differ by up to 5.5 points (construction 5.1% vs 1.2%, manufacturing
   33% vs 39%), because only size is stratified. Candidates for the 373
   training targets from the training pool: median 14 per target at
   z ≥ 2 (none with fewer than 3), 47% of top-10 share the target's SIC2
   (7% at random). Open: (a) stratify on size × SIC division too? (b) the
   training-only pool takes real peers out of development (ADUS loses
   AVAH, CHE, NHC, BKD; DXPE loses MSM, DSGR; BRO loses AJG, RYAN; WEN
   loses TXRH); (c) D2, what the facet weights are fit to.
3. Notebook restructured 2026-10-25 (later): a target's **profile** is
   its collection of comps; facets are **business-model
   characteristics**. Recipe steps 5-6 are covered by step 4 (profile =
   candidates, score = cosine). Added step: an LLM hones each target's
   candidates (prompts and fitted weights developed on training; not
   built). Last step built for cosine comps and no matching, on the 373
   training targets (`valuation/20261025T065131Z`): no matching 32.7%
   median abs error; cosine rules 30.6-32.4%, Spearman 0.32-0.39, closer
   than no matching for 52-56%. The LLM step has to beat these. Fall-off
   plots per showcase target; embedding model now loads from the local
   cache (no HF Hub warning). 93 tests.
4. Step 6 built and run 2026-10-25 (`v0/judge_comps.py`, prompt
   2026-10-25a, Claude Haiku 5.5, ~$0.57): every z ≥ 2 candidate of the
   373 training targets marked good (1) or bad (0) with a reason; 663 of
   5,293 pairs good, 96 targets with none. Notebook section 3 removed
   (steps 5-6 text moved into section 2); section 3 is now the LLM step,
   section 4 the evaluation. On the 277 targets with a good comp: LLM
   31.1% median abs error, cosine z ≥ 2 31.1%, cosine z ≥ 2.5 30.2%, no
   matching 31.9%. The LLM's choice doesn't lower the error yet. 97 tests.
5. Comps without embeddings, tested 2026-10-25 (`v0/suggest_comps.py`,
   notebook section 4; evaluation is now section 5): the LLM picks up to
   ten comps from the whole training pool (cached ~99k-token list, ~$0.55
   for 373); median 3 per target, 32 with none; 89% of its picks are
   cosine z ≥ 2 candidates anyway. On the 277 targets both LLM rules
   cover: LLM direct 30.8%, LLM good comps 31.1%, cosine z ≥ 2.5 30.2%,
   no matching 31.9%, same-SIC peers 33.1-34.4%. All comp rules within
   ~30-33%, as in pre-v0. 99 tests.
6. Next (open): what to do for a target with no good comp (fall back to
   cosine, or report "no estimate"); weights fit on training pairs; then
   the evals notebook (manual review from `judgments.csv`, rubric).
7. Evals (separate notebook, later): manual review of 100-200 target-comp
   pairs with a rubric of at most 4 levels.

pre-v0 matching (reference):

1. Picking peers doesn't look like the bottleneck: no comp rule beats method 1,
   even at equal comp counts, and right peers still give large errors. Next:
   change the estimate (shrink the comps' median toward the all-company
   median; weight comps by similarity) and try a "no good match" rule from
   absolute similarity (BV). Judge with `versus()` (bootstrap vs method 1)
   and the ten targets, settings fixed before scoring.
2. Under the updated rules: use scale (target LTM revenue, EBITDA, debt
   against the comps') as a secondary filter or weight after the
   same-business match, and consider 10-K business descriptions on the
   comp side. Fix settings before scoring, as above.
3. Results obtained, and how they are checked (peer labels for more targets
   than PCTY, written before running them).
4. Human sanity check of the top comps against their source pages.
5. Definitions and limitations.
6. Supply websites for the 4 IR-only companies (or accept "unknown").


## Integrated company workflow — 19 October 2026

Entry point: [notebook](notebooks/team_company_workflow.ipynb),
[module guide](pipeline/TEAM_WORKFLOW.md), and
[results](reports/team_company_workflow/README.md).
The workflow integrates the existing website and matching work with
`growth-signals-recall` at `793cf63`; the source snapshot remains unchanged.
It adds interchangeable stages, mandatory business review, explicit private-target
financial inputs, progressive peer search, EBITDA measurement and evaluation.

The 538-company evidence bundle supports a ten-target development comparison:
672 configurations and 6,720 target/configuration rows. The default fixed-budget
route estimates only 2/10 targets. The separate progressive PCTY run reviews 50
of 537 ranked candidates and accepts three; 487 remain unreviewed. Independent
human labels, aligned financial periods and private-company validation remain
outstanding. Growth extraction is evaluated; a growth forecast is not validated.

Validation: 294 tests passed; standalone cached replay completed 17 code cells,
zero errors and eight figures, reproducing all reference configuration outputs.
See [handoff](conversations/2026-10-19-hosted-team-workflow.md) for scope and next work.

## v0 fourth baseline — 27 October 2026

Section 5 of `v0/notebooks/comps_and_valuation.ipynb` adds LLM then cosine:
the existing direct LLM selections are reranked and weighted by the saved
cosine scores. The original valuation remains Section 6 (recipe Step 7), with
unchanged evaluation measures. On the 373 development targets, this route
covers 341 and has 32.69% median absolute percentage error; on the common
277-target cohort it has 30.57%. The original 14 evaluation rows reproduce
exactly. Source snapshot: `company_list_v3`; saved source run:
`20261025T080854Z`. Holdout and human evaluation remain open. See
`conversations/2026-10-27-v0-fourth-baseline.md`.

## Reviewer labels and business grouping — 28 October 2026

The local [evaluation notebook](v0/notebooks/business_split_refinement_eval.ipynb)
compares the four saved v0 routes against Riya, Barbara, and Matthew's 36
PCTY/WEN labels separately. Only 11 pairs received the same score from all
three. The source-corrected grouping retains one company ID and assigns every
current activity once; 8 of 40 firms have multiple groups. The targeted
primary-source check scores 34/34 activity statuses and 9/9 exact partitions,
versus 27/34 and 7/9 in the saved decisions. Development median APE changes
from 19.26% to 39.41% with split context; fixed-holdout median APE changes
from 31.02% to 40.21%. The context prompt is not adopted as the v0 default.
Details and reproduction steps:
`conversations/2026-10-28-reviewer-and-split-refinement.md`.
