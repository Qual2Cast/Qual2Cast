# Handoff: every company valued, method 2 step 1 (2026-10-19)

Work done in Claude Code. This file is the summary.

## What was asked

Method 2 ideas: a layered fallback, HDBSCAN to limit outliers, and a kNN
graph. Should they be one method or three? Agreed answer: one method with
three layers of the same structure. The kNN graph is the base, HDBSCAN's
cluster tree gives the layers, and a company HDBSCAN leaves unclustered
(its "noise" label, −1) falls back up the tree, then to its graph
neighbours. A supervised decision tree was ruled out: its only possible
target is EV/EBITDA, which must stay out of matching. LLM-extracted
categorical features weren't wanted either. Agreed to start small: mutual
nearest neighbours first, plus the valuation of every company so methods
can be compared.

## Completed

- `matching/matching_methods.ipynb`:
  - **3.5 Valuation for every company.** Each of the 535 matchable companies
    is valued from its own comps: the median of their positive EV/EBITDA.
    `score(comp_sets)` reports, per comp set: comps per company, no
    estimate, median absolute % error, % within 25%, Spearman(estimate,
    actual), % of companies closer than no matching, and comps sharing
    SIC4. It asserts that no company is its own comp. Reference rows: same
    SIC4, same SIC2 (checks only), and no matching.
  - **Section 4 Method 2, step 1: mutual nearest neighbours.** Same
    embeddings and cosines as method 1. j is a comp of i when each is in
    the other's top k, `K_LEVELS = [10, 20]`, set before scoring. 4.1 lists
    comps, PCTY's comps, and how many targets each company is a comp of
    (hubs). 4.2 scores method 1 and method 2 together.
  - `run_info.json` gains `valuation_all` and `method_2`.
- New run files: `valuation_all.csv`, `valuation_all_summary.csv`,
  `all_comps_mutual.csv`, `valuation_all_m2.csv`,
  `valuation_all_summary_m2.csv`.
- `matching/README.md`: 3.5 results, method 2 section, outputs, open issues.
- Ran top to bottom with nbconvert (kernel `qual2cast`), run
  `20261019T051304Z`. Method 1 numbers unchanged (cached embeddings).

## Results (run 20261019T051304Z, snapshot company_list_v3)

| Comp set | Comps median (range) | No estimate | Median abs % error | Spearman | Closer than no matching | Comps sharing SIC4 |
|---|---|---|---|---|---|---|
| Method 1, z ≥ 2.5 | 7 (0-23) | 13 | 35.9% | 0.29 | 51% | 22% |
| Method 1, z ≥ 2 | 17 (2-41) | 0 | 34.7% | 0.31 | 52% | 14% |
| Mutual, k = 10 | 5 (0-10) | 27 | 36.5% | 0.26 | 48% | 26% |
| Mutual, k = 20 | 11 (0-20) | 3 | 34.7% | 0.21 | 50% | 20% |
| Same SIC4 (check) | 4 (0-50) | 90 | 37.8% | 0.22 | 49% | 100% |
| Same SIC2 (check) | 16 (0-111) | 5 | 34.8% | 0.24 | 54% | 31% |
| No matching | 534 | 0 | 34.6% | | | 2% |

- No comp set beats no matching on error across all companies. PCTY's gain
  doesn't generalise.
- Comp medians do rank companies (Spearman ~0.3), better than SIC groups.
- Hubs in method 1: at z ≥ 2, CSW is a comp of 81 targets, SOLV 74,
  ICUI 70. Mutual kNN caps this at k, but error doesn't improve.
- All 535 matchable companies have a positive multiple in this snapshot.
- Prototype only (not in the notebook): SIC2 groups explain ~17% of the
  variance in log EV/EBITDA, so multiples in this list are mostly
  company-specific.

## Unresolved

- Whether better peers can help at all when the median of even the right
  peers is noisy. Changing the estimate (shrink toward the all-company
  median, weight comps by similarity) may matter more than step 2.
- Mutual k = 10 leaves 27 companies with no comps. Step 2's fallback is
  meant to cover them.
- Nothing from this session is committed.

## Next recommended action

(Superseded below: the user chose step 2.)

## Later: PCTY's mutual comps explained

Asked why KFY is a k = 20 comp when it's 9th in PCTY's row and PCTY is 20th
in KFY's. A pair has one cosine (0.633), but each company ranks it against
its own neighbours. KFY's are consulting / staffing firms, so PCTY falls to
20th there. The rule needs both ranks ≤ k, so KFY passes at exactly 20.
HURN (7th / 23rd) and DOX (20th / 46th) don't. Weaknesses: a yes/no cut-off,
and no difference between borderline and strong pairs. The user deferred a
redesign (rank-based score, shared nearest neighbours, or requiring z too).

## Later: method 2 step 2, clusters with a fallback

- Neither `hdbscan` nor `umap-learn` was installed. Used scikit-learn 1.9's
  `HDBSCAN`, which doesn't expose the cluster tree. Instead it runs at two
  levels of the same tree (`leaf`, `eom`); every leaf cluster sits inside
  one eom cluster (asserted). Installed `umap-learn` 0.5.12 (+ numba 0.68,
  llvmlite 0.50, pynndescent 0.6) into the kernel's Python 3.14; added
  scikit-learn and umap-learn to `matching/requirements.txt`.
- Tried before writing the notebook (judged on noise share and cluster
  size, not error): HDBSCAN on full 768 dims, 83% noise; PCA 10-20 dims,
  30-60% noise even with low `min_samples`; UMAP 5-10 dims, 9-22% noise.
  Chosen: UMAP 10 dims, cosine, 15 neighbours, `min_dist` 0, seed 0;
  HDBSCAN `min_cluster_size` 5, `min_samples` 2.
- Notebook 4.3 (clusters, comps, PCTY) and 4.4 (scoring, seed stability).
  New run files: umap_embeddings.npy, clusters.csv, all_comps_clusters.csv,
  valuation_all_m2_clusters.csv, valuation_all_summary_m2_clusters.csv,
  cluster_stability.csv; run_info `method_2.step_2`.
- Ran top to bottom twice (second time after silencing scikit-learn's
  `copy` FutureWarning); identical results. Run `20261019T053557Z`.

Results:

| Comp set | Comps median (range) | Median abs % error | Spearman | Closer than no matching | Comps sharing SIC4 |
|---|---|---|---|---|---|
| Clusters from leaf | 9 (1-37) | 36.5% | 0.18 | 47% | 19% |
| Clusters from eom | 14 (1-37) | 34.7% | 0.24 | 50% | 18% |

- Leaf: 47 clusters (median 8), 92 noise; eom: 38 (median 10), 58 noise.
  Comps from leaf / eom / mutual: 443 / 34 / 58 (from leaf), 477 / 58
  (from eom).
- Seed stability (seeds 1-4 vs 0, Jaccard of comps): median 0.61 (leaf),
  0.71 (eom); 164 / 133 companies below 0.5.
- PCTY: same 7-company cluster at both levels (PAYC, ADP, ASUR, BBSI, FA,
  HQI, ALIT), overlap across seeds 0.91; 14.38 vs 22.13 (−35%).

Unresolved: no comp set, method 1 or 2, beats no matching on error. Cluster
comps depend on the seed. Nothing committed.

## Later: cluster tree plot and documentation

- Notebook 4.3 and `matching/README.md` now explain why UMAP and not PCA
  (10 dimensions is a design setting, not tuned), what eom is, and where
  the 768 embedding dimensions come from (new note before 3.1).
- New plot of HDBSCAN's cluster tree after the 4.3 clusters. Installed
  `hdbscan` 0.8.44 (wheel for Python 3.14) to rebuild the tree, since
  scikit-learn's doesn't expose it; added to `matching/requirements.txt`.
  Its `min_samples` 1 = scikit-learn's 2; same clusters at both levels
  (asserted in the notebook). New run files: cluster_tree.csv,
  cluster_tree.png.
- Reran the whole notebook: run `20261019T061656Z`. Every other output is
  the same as `20261019T053557Z`. PCTY: leaf 34 = eom 25 (ADP, ALIT, ASUR,
  BBSI, FA, HQI, PAYC).

## Later: SIC agreement at every level

- Asked: show comps sharing SIC1-4 as columns in every comparison table.
  `score()` (3.5) now reports comps sharing Division / SIC2 / SIC3 / SIC4
  instead of SIC4 alone. That covers the 3.5, 4.2 and 4.4 tables. "SIC1"
  is the Division (letter A-K): there is no official one-digit level, and
  3.3 already uses Division.
- Reran the whole notebook, run `20261019T065118Z` (includes the tree
  plot). Errors unchanged.

| Comp set | Division | SIC2 | SIC3 | SIC4 |
|---|---|---|---|---|
| Method 1, z ≥ 2.5 | 67% | 45% | 32% | 22% |
| Method 1, z ≥ 2 | 61% | 35% | 24% | 14% |
| Mutual, k = 10 | 69% | 49% | 36% | 26% |
| Mutual, k = 20 | 64% | 42% | 29% | 20% |
| Clusters from leaf | 63% | 43% | 29% | 19% |
| Clusters from eom | 63% | 40% | 28% | 18% |
| No matching (chance) | 27% | 7% | 3% | 2% |

- Also asked why 3.5 has "same SIC4 / same SIC2" rows: they are
  benchmarks (comps = the companies in the target's industry code, the
  conventional way to pick comps), to see whether text beats industry
  codes. Pending the user's decision whether to keep them.

## Next recommended action

Change the estimate rather than the peers: shrink the comps' median toward
the all-company median, or weight comps by similarity. Score with
`score()` against the existing table. Deferred by the user: the mutual-rank
redesign. Possible: comps from several UMAP seeds combined.

## Later: mutual-rank redesign, prototyped (not in the notebook)

Asked how to improve method 2 past the baseline: lower k, score pairs by
the worse of the two ranks, shared nearest neighbours (SNN), mutual rank
and z together; maybe split method 2 into a neighbour-rule method and a
cluster method; shrinkage / similarity weights later.

Prototype script in the session scratchpad (not kept), run on the saved
cosines and multiples of run `20261019T065118Z`. Variants and settings were
fixed before scoring; fixed-count variants use 7 and 17 comps (method 1's
medians) so sets compare at equal size; "top m by cosine" is the control
for fixed counts. 95% intervals: paired bootstrap over companies (2000
resamples; 1000 for Spearman), difference vs method 1 z ≥ 2.

| Comp set | Comps med (range) | No comps | Max uses | Median abs % error | vs m1 z ≥ 2 | Spearman |
|---|---|---|---|---|---|---|
| Method 1, z ≥ 2 | 17 (2-41) | 0 | 81 | 34.7 | | 0.309 |
| Top 17 by cosine (control) | 17 | 0 | 85 | 35.6 | +0.3 [−1.5, +2.2] | 0.285 |
| Mutual k = 5 | 2 (0-5) | 88 | 5 | 33.7* | −0.8 [−4.0, +3.8] | 0.316 |
| Mutual k = 20 | 11 (0-20) | 3 | 20 | 34.7 | +0.2 [−2.1, +2.3] | 0.211 |
| Top 7 / 17 by worse rank | 7 / 17 | 0 | 17 / 33 | 35.4 / 36.2 | +0.6 / +1.4 | 0.217 / 0.185 |
| Top 7 / 17 by SNN (k = 20) | 7 / 17 | 0 | 22 / 40 | 38.7 / 36.8 | +4.1 [+1.5, +6.9] / +2.2 | 0.189 / 0.196 |
| Mutual k = 20 and z ≥ 2 | 9 (0-20) | 8 | 20 | 34.4 | −0.0 [−2.3, +2.1] | 0.259 |
| No matching | 534 | 0 | | 34.6 | +0.3 [−2.4, +4.2] | |

\* only the 447 companies with comps; on those, method 1 z ≥ 2 gets 33.3.

- Median abs % error can't separate any of these: intervals are ±2-4
  points. With Spearman ≈ 0.3 the comps explain ~9% of the ranking, so
  even a perfect estimator built on them would gain only a point or two.
- Spearman does separate them. Every rule that caps hubs ranks companies
  worse than method 1: mutual k = 20 −0.10 [−0.17, −0.03], top 17 by worse
  rank −0.13 [−0.18, −0.07], top 17 by SNN −0.11 [−0.18, −0.05]; mutual and
  z together −0.05 [−0.12, +0.01].
- Scoring by the worse of the two ranks with a cut-off k is exactly mutual
  kNN; it differs only as a fixed count per target or as a weight.
- Shrinkage check (point 3, fixed 50/50 blend in logs with the all-company
  median): 35.1 for method 1 z ≥ 2, 33.9 for z ≥ 2.5; within noise of
  no matching too.
- 13 variants have now been looked at on the same 535 companies, so
  picking the best of them would be tuning on the yardstick.

Next recommended action: pending the user. Recommended: compare methods on
Spearman with a bootstrap interval (median error kept, but it can't
distinguish methods); find out why hubs help ranking before more
neighbour rules; don't split method 2 into two methods unless a neighbour
rule beats method 1.

## Later: how much do UMAP's settings matter?

The user questioned the cluster settings: 10 dimensions was a design
choice, 15 neighbours is UMAP's default. Prototype (session scratchpad, no
valuation numbers used): UMAP dimensions {2, 5, 10, 20, 50} × neighbours
{5, 10, 15, 30, 50}, seeds 0-2, HDBSCAN eom with the notebook's settings.
Measured: noise share, clusters, sizes, SIC2 agreement within clusters
(check), seed agreement (adjusted Rand index, ARI).

- Dimensions barely matter from 5 to 50: noise 6-11%, 33-47 clusters,
  median size ~10, SIC2 agreement 35-43%.
- Neighbours matter more: at 30-50 one cluster grows to 70-87 companies
  and SIC2 agreement falls to 35-37%; at 5 there's less noise (6-8%), more
  clusters, and SIC2 agreement ~42-43%.
- Seed dependence is there at every setting: ARI 0.43-0.79. No setting
  removes it.
- UMAP's neighbours setting is effectively the k of a kNN graph that UMAP
  builds and then lays out; the clusters come from that graph.

Options raised: cluster the cosines directly with a deterministic method
(agglomerative, average linkage: a full tree, no dimensions, no seed; comps
= walk up from the target until its group has at least m others), or
community detection on the kNN graph. Pending the user.

## Later: method 3, one similarity tree

The user asked for the agglomerative tree as its own method (not a step of
method 2).

- Shape check first (scratchpad, no valuation numbers): average linkage
  chains (37 companies with > 50 comps, OLPX gets all 534), so it was
  dropped; complete and ward give bounded groups with the same SIC
  agreement. `MIN_COMPS = 5` (method 2's minimum cluster size) set before
  scoring.
- Notebook section 5 (cells appended; section list in the first cell
  updated): 5.1 builds the three trees (scipy `linkage`; ward on the unit
  vectors), the shape table, comps by walking up from the target, and
  PCTY's walk up each tree. 5.2 scores methods 1, 2 (mutual k = 20, clusters
  from eom) and 3 with `score()`, plus a new `versus()`: paired bootstrap
  (2000 resamples, seed 0) of each set minus method 1 z ≥ 2, for median
  abs % error and Spearman.
- New run files: tree_linkage_{average,complete,ward}.csv, tree_shape.csv,
  all_comps_tree.csv, valuation_all_m3.csv, valuation_all_summary_m3.csv,
  valuation_vs_method1_m3.csv; run_info `method_3`.
- Ran top to bottom twice with nbconvert (second time after a wording fix):
  runs `20261019T073451Z`, `20261019T073559Z`, identical results. Methods 1
  and 2 unchanged from `20261019T065118Z`. No errors.

| Comp set | Comps med (IQR) | Median abs % error | vs m1 z ≥ 2 (95%) | Spearman | vs m1 z ≥ 2 (95%) |
|---|---|---|---|---|---|
| Method 3, complete | 7 (6-9) | 36.3% | +1.7 (−1.1 to +4.4) | 0.22 | −0.09 (−0.17 to −0.01) |
| Method 3, ward | 7 (5-8) | 38.2% | +3.5 (+0.9 to +6.7) | 0.23 | −0.08 (−0.15 to 0.00) |

- No gain: worse ranking than method 1, and ward's error is measurably
  higher. Still behind method 1 at the same comp count (z ≥ 2.5: 35.9%,
  0.29). SIC agreement 43-44% SIC2, 21-22% SIC4.
- PCTY: complete 13.05 (−41%); ward 18.14 (−18%, closest of any comp set
  for PCTY, one company only).
- README: method 3 section, outputs, run id. Nothing committed.

Next recommended action: every comp-picking change so far (mutual,
clusters, tree) ranks companies worse than method 1's plain z cut-off, and
none beats no matching on error. Before more methods, find what method 1
does that the others don't (its larger, hub-including comp sets?), e.g.
method 1 at fixed comp counts vs the tree at the same counts; or move to
the estimate (point 3: shrinkage, similarity weights) judged by `versus()`.

## Later: every method at 3-10 comps, ten targets, method names

Asked: (1) evaluate every method at 3 to 10 comps; (2) put method names in
the titles (e.g. mutual k-nearest neighbours); (3) value the targets from
the user's list (an image of 10; Pool Corp dropped by the user) to see
whether methods behave consistently across targets.

- Names: section titles and comp-set labels now say "method 1 (cosine z)",
  "method 2 (mutual kNN)", "method 2 (HDBSCAN)", "method 3
  (agglomerative), complete / ward linkage". Every output file's comp-set
  labels changed accordingly.
- `TARGETS` setting added (first code cell); `TARGET` stays PCTY for the
  walk-through.
- Section 6: each method gives exactly m comps, m = 3-10 (rules in the
  notebook and README; HDBSCAN uses eom, seed 0, filled by the mutual kNN
  order). `score()` per count, `versus()` against method 1 at the same
  count. Plot `fixed_counts.png` (reference palette slots 1-5, validated;
  marker per line). Result: no method beats method 1 at any count; tree
  (complete) ranks worse at 6, 8, 10; ward's error worse at 5 and 10; no
  count lowers error.
- Section 7: the ten targets with comps, estimate and error per method's
  own rule, a % error table, and the ten targets' median error at each
  fixed count. The why-table from the user's image is in the notebook
  markdown (context only; expected peers are not scored).
- Ran top to bottom three times (layout fixes to the plot); final run
  `20261019T075423Z`, identical results to `20261019T075202Z`. No errors.
  Methods 1-3 numbers unchanged.

Target findings: clear peers are found (ROAD: STRL, GVA, CDNL, SMID; BRO:
BWIN, AJG, RYAN; LOPE: STRA, APEI, PRDO; ADUS: AVAH first). Finer cases fail
(ODFL mixes XPO with MRTN / HTLD; FIX gets HVAC makers SPXC, CSW, AAON, LII
before LMB; DXPE gets SPXC, ITT, CR, not distributors; BV gets comps though
no landscaper exists). Right peers still miss by 29-43% (ROAD, BRO, LOPE);
WING is 71-78% off everywhere.

Next recommended action: the comps are often right while the valuation is
not, so the next gain is more likely in the estimate or its inputs than in
picking peers. Options for the user: point 3 (shrinkage, similarity
weights), or a "no good match" rule from absolute similarity (BV), judged by
`versus()` and the ten targets. Nothing committed.

## Later: split into two notebooks

Asked: keep the one-example version as its own notebook and move the
fixed-count and ten-target evaluation to another.

- `matching/matching_methods.ipynb`: sections 1-5 again (PCTY walk-through,
  every-company scoring), with the new method names; `TARGETS` removed from
  its settings; first cell points to the evaluation notebook.
- `matching/matching_evaluation.ipynb` (new): 1. Setup runs
  `%run matching_methods.ipynb` under `%%capture` (output kept in
  `methods_output`), then sets `TARGETS` and checks they're matchable;
  2. Every method at 3-10 comps; 3. Ten targets (3.1 across targets).
  Cross-references now name the methods notebook. Writes to the methods
  run's folder.
- Ran both top to bottom: `20261019T080322Z` (methods alone; no evaluation
  files) and `20261019T080416Z` (evaluation). Results identical to
  `20261019T075423Z`. No errors.
- README (two notebooks, section tables, running, outputs, run ids) and
  PROJECT_STATE updated. Nothing committed.

## Later: methodology write-up and commit

Asked: commit and push everything, update the README and project state,
and explain the methodology.

- `matching/README.md`: new "Methodology" section near the top (question,
  every-company-as-target set-up, pipeline, how methods are judged,
  discipline, what it shows so far).
- `PROJECT_STATE.md`: new "Matching methodology (working approach)"
  section; matching status row, results row and next step 1 rewritten
  shorter.
- Committed and pushed to `michael/wip` (both notebooks, README,
  requirements, project state, this handoff). Run outputs stay in
  git-ignored `outputs-local/`.

Next recommended action: the estimate (shrinkage, similarity weights) and
a "no good match" rule, judged with `versus()` and the ten targets.
