# Similarity methods: facet weighting (method 1) and a FAME-inspired gate (method 2)

## Request

Refine how the facet similarities are combined in v1, in a new notebook:
- **Problem 2, the updated baseline:** weight each facet by its text with TF-IDF/BM25, so thin and boilerplate facets stop counting as much as specific ones; use mutual comps.
- **Problem 1, method 2:** adapt FAME (Liu et al., arXiv 2411.01457; per-head prediction, gate, experts within heads) from recommendation to comp finding, as one version with no training.
- **Reuse the team's evaluations:** the reviewers' golden set under a clear rule, and Sol's grades kept as an alternative check.
- **Adaptability:** the notebook must survive new facets.
- **Rename the LLM selectors** so "judge" means evaluators only.
- **No API spend** until the method is settled or funded.

## Decisions (user, 2026-11-03)

- **Company size (F9)** is out (team finding from the comps notebook and Fiona's sector-facet work).
- **"None" (not applicable)** counts as missing.
- **Mutual top 10** replaces z ≥ 2; anything over 10 is excessive financially. A target with fewer than 3 mutual comps is topped up from its one-way list.
- **Reviewer rule:** majority grade (2 of 3) as the main set, unanimous pairs as a strict check, unlabeled comps never counted as 0. Using unanimous pairs only was considered and rejected: WEN's 7 are all non-comps and PCTY's 4 are all comps, so they can't separate methods.
- **Sol's grades** are an "alternative evaluation, not used for decisions" until the mentor gives direction.
- **Method 2** is one version, a fixed-rule gate, with no learned gate.
- **Names:** `judge_comps.py` → `cosine_then_llm.py`, `suggest_comps.py` → `direct_llm.py`.
- **HR@k** was dropped: it fits one-correct-item recommendation, not several good comps.

## Changes

- **Rename.** Modules, tests, imports (4 scripts), READMEs and notebook sources in `v1/`. Saved notebook outputs are untouched. The output folders `outputs-local/v1/judge/` and `suggest/` keep their names.
- **`v1/scripts/facet_weighting.py`** (new):
  - the facet list from `facets.py` minus `EXCLUDED_FACETS`;
  - "none" as missing;
  - BM25-IDF TF-IDF per facet, with saturated information `raw/(raw+K)`, K = the median;
  - an embedding/TF-IDF blend (α = 0.5, not tuned);
  - information-weighted combine;
  - `;`-piece best-match scores;
  - sharpness and gate, gated similarity;
  - mutual top k with top-up;
  - a text-keyed embedding cache seeded from v0's.
- **`v1/scripts/similarity_eval.py`** (new): the reviewer rule, list metrics (unlabeled skipped), strict check, Sol grade loading (first run wins; agreement between runs reported).
- **Tests:** `test_facet_weighting.py` (12, including a made-up 12th facet run end to end) and `test_similarity_eval.py` (6).
- **`v1/notebooks/similarity_methods.ipynb`** (new, executed, 41 cells): inputs; diagnostics; method 1 built up B0 → B3; method 2; reviewer golden set; Sol (alternative); valuation with diagnostic one-way rows; facet-label check; top-up sheet; saved outputs. EV/EBITDA is read only in the valuation section.
- **Docs:** `v1/README.md` (changes section, test count), root `README.md` (status row), `PROJECT_STATE.md`.

## Results (373 training targets)

| | B0 one-way (v0) | B0 mutual | B1 | B2 | B3 = method 1 | M2 = method 2 |
|---|---|---|---|---|---|---|
| median APE % | 28.82 | 30.18 | 32.05 | 32.35 | 29.99 | 30.26 |
| reviewer precision@10, PCTY / WEN | 0.67 / 0.30 | 1.0 / 1.0 | 1.0 / 1.0 | 0.86 / 1.0 | 1.0 / 1.0 | 1.0 / 0.8 |
| Sol precision@10 (156 holdout targets) | 0.67 | 0.76 | 0.81 | 0.80 | 0.81 | 0.82 |
| comps per target (median) | 10 | 6 | 6 | 6 | 7 | 7 |

- **Golden-set analysis (follow-up request):**
  - Every method finds all direct comps. Methods 1 and 2 find all adjacent comps (PCTY 7/7, WEN 4/4), while v0 misses BBSI (rank 17) and BDL (rank 12). Both rise once "none" counts as missing, which removes false penalties as well as false 1.00 matches.
  - v0 lists 3/5 of PCTY's and 7/16 of WEN's non-comps. Method 1 lists none and method 2 one (Lamb Weston). Most of these are still in the top 10 by similarity but are dropped by the mutual filter.
  - From B1 on, WEN's 4 good comps rank above all 16 reviewed non-comps.
  - The TF-IDF blend lifts Lamb Weston (a fries supplier) on shared words.
  - Barbara's and Matthew's own grades agree with the majority. Riya's, which count food makers as adjacent to WEN, don't separate the methods.
  - Sol: the new lists keep 81–82% of Sol-direct comps (v0 84%) with a third of the non-comps.
  - The notebook also defines B0–B3 in one table (each step changes one thing) and works the gate through as information × sharpness ÷ total, for WEN and PCTY.
- **Charts (third follow-up), in `figures/` of the run:**
  - `golden_hits_by_method.png`: each method's list, coloured by reviewer grade;
  - `golden_ranks_by_method.png`: every reviewed comp's rank across methods;
  - `m2_facet_weights_pcty_wen.png`: gate vs information alone;
  - `m2_facet_separation_pcty_wen.png`: each facet's share of the gap between good comps and non-comps;
  - `sol_hits_by_method.png`.
  - Colours were checked with the dataviz validator: a diverging blue/gray/red scale for grades (ordinal blue arm) and categorical slots 1–2 for targets.
- **Facet findings:** for WEN, revenue model separates most (0.050 of a 0.171 gap) and also gets the top gate (14.0%, +1.9 from sharpness). For PCTY, the separation is spread (0.009–0.023), and the top gate (offering description, 12.0%) is not the best separator; customer segment separates third-best but gets a low gate (7.9%).
- **Valuation against v0.** Every difference from B0 one-way has an interval including 0: method 1 −1.2 (−4.0 to +2.6), method 2 −1.4 (−3.1 to +2.7). With one-way top 10, B3 scores 29.70% and M2 30.15%, so the mutual filter's shorter lists aren't the cause. The saved LLM routes score 30.5–30.6%. B0 one-way reproduces v0 exactly (28.82%; no matching 31.92%).
- **Where the ranking gain comes from:** mostly "none" as missing (B1) and the mutual filter. The TF-IDF weights and blend add no measurable ranking gain over B1. On WEN, v0's seven packaged-food and beverage matches are gone, and all four reviewer-majority comps are listed.
- **Method 2:** sharpness is 2.8–3.5 SD on every facet, so the gate tracks information. Its lists are close to B3's.
- **Facet-label check:** information doesn't differ between facets labeled correct (0.497) and not fully correct (0.507). The labels checked an earlier fill (0–8% exact text match), so this is indicative only.
- **Sol:** its two saved runs agree exactly on 91% of the 1,457 pairs both graded.

## Tests

`uv run pytest v1/scripts/tests v1/scripts/verification/tests -q`: 200 passed. The notebook runs end to end in about 2.5 minutes with no errors and validates with nbformat.

## Data version

- `company_list_v3`; universe `20261025T060358Z`; facets `2026-10-25k`; split `20261027T204930Z`.
- Embeddings: v0 cache `facets_all-mpnet-base-v2_6f4ce4373bfbc08a.npz` and the new text cache `texts_all-mpnet-base-v2.npz` (5,620 facet texts, 9,847 pieces, computed locally).
- Reviewer snapshot fetched 2026-10-28T11:25Z.
- Sol runs `holdout_completion/graded_peer_selection` and `sector_facets/holdout_grades`.
- Run: `outputs-local/v1/similarity_methods/20261104T052054Z`. Earlier runs from this session are in `history/`.
- No API calls.

## Open issues

- **F9 is still in `cosine_then_llm.py`'s prompt.** Dropping it needs a `PROMPT_VERSION` bump. That bump would hide the saved verdicts from `--tables-only` and `facet_eval.py`, which filter on the current version, and would change the prompt hashes the holdout replays use. Do it with the next paid run and pin the old version in those readers.
- **The human evidence is two targets.** NDCG penalizes short mutual lists, so precision is the fairer comparison across list lengths.
- **Better comps don't give better estimates** here. Any further gain in valuation error likely needs more than comp choice.
- **Nothing from this session is committed** (on `michael/wip`). Git shows the renames as deletions plus new files until they are staged.

## Next step

Reviewers score the 2 new WEN pairs (HQI, PLNT) in `labels_topup/topup_sheet.csv`. Then add golden-set targets where the methods disagree most, and the team decides whether method 1 (or B1, its simpler core) becomes v1's comp-finding baseline.
