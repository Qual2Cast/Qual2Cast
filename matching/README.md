# matching/

Comparable-company matching. Treat one company as private, find its comps in
the 560-company list using only website text, then estimate its EV/EBITDA
from the comps' multiples.

Two notebooks:

- **`matching_methods.ipynb`**: the methods, each shown on one example
  target (`TARGET`, PCTY). Each method is one section and ends with its own
  valuation of every company, so methods can be compared on the same
  numbers.
- **`matching_evaluation.ipynb`**: compares the methods at the same number
  of comps (3-10) and on ten chosen targets. Its first cell runs
  `matching_methods.ipynb` (output hidden), so the methods are defined in
  one place, and it writes its files to the same run folder.

`matching_methods.ipynb`:

| Section | What it does |
|---|---|
| 1. Data | Loads the required snapshot (non-financial columns only, checksum-checked) and every scraped page from `outputs-local/website_scrape/page_text/` |
| 2. What the scrape gives us | Scrape status, pages per company, page categories, word counts, and the target's pages |
| 3. Method 1: embedding similarity (cosine z-score cut-off) | The baseline (below), ending with the valuation of every company (3.5) |
| 4. Method 2: mutual k-nearest neighbours (mutual kNN) and UMAP + HDBSCAN clusters | Step 1 mutual kNN, step 2 HDBSCAN clusters with a fallback (below), each scored the same way |
| 5. Method 3: agglomerative clustering (hierarchical similarity tree) | Comps = the target's smallest group in the tree with at least 5 others (below) |

`matching_evaluation.ipynb`:

| Section | What it does |
|---|---|
| 1. Setup | Runs `matching_methods.ipynb`; sets `TARGETS` |
| 2. Every method at 3-10 comps | Each method gives every company exactly m comps, m = 3-10, scored and compared with method 1 at the same count |
| 3. Ten targets | PCTY plus nine chosen targets: each method's comps, estimate and error, and how consistent the methods are across them |

## Methodology

**The question.** Can a company's EV/EBITDA multiple be estimated from
comparable companies found using only its name and website, so that the
approach works for a private target (Aziz's rule)?

**Every public company takes a turn as the private target.** The list has
560 public companies whose multiples are known. Each matchable company (535;
25 have too little website text) is treated as private in turn: its comps
are found among the other 534 from website text alone, and its multiple is
estimated from theirs. Its actual multiple is the answer key. This gives
535 tests of each method instead of one.

**Pipeline.** The methods share every step except how comps are picked.

1. **Text:** the website scrape's cleaned page text, up to 3 pages per site.
   The scrape has already removed financial and size figures, tickers and
   public-company language.
2. **Similarity:** each company's text is split into 200-word chunks,
   embedded with `all-mpnet-base-v2`, and averaged into one vector of 768
   numbers. The similarity of two companies is the cosine of their vectors
   (1 = the same direction).
3. **Comps** (where the methods differ):
   - **Method 1, embedding similarity (cosine z-score cut-off):** the
     companies unusually similar *for this target*: at least 2 (or 2.5)
     standard deviations above its average similarity to everyone. The
     number of comps varies by target.
   - **Method 2, mutual k-nearest neighbours (mutual kNN):** j is a comp of
     i only if each is among the other's k most similar (k = 10, 20). This
     stops "hub" companies, whose generic sites look like everyone's, from
     being comps of everyone. Step 2 groups companies into clusters
     (UMAP + HDBSCAN) and takes the target's cluster-mates.
   - **Method 3, agglomerative clustering:** one similarity tree built by
     merging the closest groups, with no random seed; comps are the
     smallest group around the target with at least 5 others.
4. **Valuation:** the estimate is the median EV/EBITDA of the comps. The
   multiple is read only at this step, after the comps are fixed.

**How methods are judged.**

- **Every company:** median absolute % error of the estimate, the share
  within 25%, and Spearman between estimate and actual (do higher
  estimates go with higher multiples?). The benchmark is **no matching**:
  the median of all other companies. A method helps only if it beats that.
- **Noise:** a point or two of median error is within chance. Each method
  is compared with method 1 on the same resampled companies (paired
  bootstrap, 2000 resamples), and a difference whose 95% interval contains
  0 counts as none.
- **Equal comp counts:** the number of comps alone changes the median, so
  every method is also run at exactly 3, 4, … 10 comps per company.
- **Ten targets:** chosen to cover different kinds of business and hard
  cases (no real peer in the list, fine distinctions, an outlier multiple).
  Their comps are read against the companies' pages.
- **SIC codes are a check only:** the share of comps in the target's
  industry code shows whether the text finds same-industry companies. They
  are never a matching input.

**Discipline.**

- Every setting (z levels, k, UMAP and HDBSCAN settings, linkage, minimum
  comps, the counts 3-10) is fixed before scoring. Settings are chosen on
  the shape of the comp sets (how many comps, how many left out, SIC
  agreement), never tuned on valuation error. Variants tried and dropped are
  recorded in `conversations/`, so the number of looks at the answer key is
  known.
- Financial fields are never matching inputs.
- These rules are stricter than the project's current ones. The methods
  were built under the original name + website rule. Since 2026-10-19
  (Aziz's reply, see PROJECT_STATE.md) the target's LTM revenue, LTM
  EBITDA and debt may be compared with the comps' to favor similar scale,
  as a secondary criterion after same business, and the comps' 10-K detail
  may be used as similarity input. Neither is used here yet. EV/EBITDA
  stays the answer key and is never a matching input.
- Each run saves its settings, comps, estimates and scores to its own
  folder; embeddings are cached by a hash of the input text.

**What it shows so far.**

- **The text finds real peers.** A company's 5 nearest neighbours share its
  4-digit SIC code 14 times as often as chance. The targets with clear
  peers in the list get them (Sterling and Granite for ROAD; Baldwin,
  Gallagher and Ryan for BRO).
- **No method beats no matching on error:** about 35% for every method.
  Method 1's comps rank companies best (Spearman 0.31, against 0.22-0.24
  for SIC peer groups), and no other way of picking comps beats it, even at
  equal comp counts.
- **Right peers still give wrong values.** Multiples in this list are
  mostly company-specific (SIC2 groups explain about 17% of the variance),
  so even good peers' median is noisy. The next gains are more likely in the
  estimate (shrinking toward the overall median, weighting comps by
  similarity) or a rule for "no good match" than in picking peers.

## Running it

```
pip install -r matching/requirements.txt
python -m ipykernel install --user --name qual2cast
```

Open a notebook, pick the `qual2cast` kernel and run top to bottom. Set
`TARGET` (a ticker, the walk-through) in the first code cell of
`matching_methods.ipynb`, and `TARGETS` in the settings cell of
`matching_evaluation.ipynb`. The evaluation notebook runs the methods
notebook itself, so there's no need to run both. The first run downloads
`all-mpnet-base-v2` (~420 MB) and embeds all 535 companies (several minutes
on a laptop CPU). Later runs use the cached vectors.

The notebook needs the website text that's in Git
(`outputs-local/website_scrape/page_text/`) and the snapshot in
`data-local/snapshots/`. It doesn't scrape anything.

## Method 1, embedding similarity (cosine z-score cut-off): what changed from Riya's baseline

The starting point was the embedding part of Riya's proof of concept
(branch `riya/wip`, `similarities/comps_similarity_PCTY.ipynb`). The
embedding step is the same: 200-word chunks, `all-mpnet-base-v2`, chunk
vectors averaged and normalised to one vector per company, cosine
similarity between every pair. These things changed:

| | Riya's notebook | Here |
|---|---|---|
| Text source | Her own scrape (`descriptions.csv` + text files) | The pipeline scrape, `website_scrape/` page text (title, meta, cleaned blocks) |
| Text cleaning | Company names masked as `[COMPANY]`; boilerplate regex; sentences on 3+ sites dropped | Used as is: no name masking, no template-sentence removal. Left open for later methods to test |
| Representations | TF-IDF, LSA and embeddings, z-scored ensemble | Embeddings only |
| Matchable | ≥ 100 cleaned words | Same. 535 matchable, 25 excluded, each with a reason |
| Number of comps | Fixed top 25 | No fixed number (see below) |
| Validation | Hand-labelled PCTY peers, NDCG/recall | Removed: labels exist for one target only, and they come from `scraps/`, which hasn't joined the pipeline. Replaced by the SIC check and length check |
| Valuation | None | EV/EBITDA estimate from the comps (3.4) |
| Code | Reads files from her laptop paths | Finds the repo root, loads data through `src/project_data.py`, imports nothing from `scraps/` |

### Choosing comps: z levels instead of a top k

Each company's cosines to all other companies are scaled within its own row:

    z = (cosine − target's mean cosine to all others) / that row's SD

A company is a comp when its z reaches a level in `Z_LEVELS = [2.0, 2.5]`.
Both levels run through the whole section. Raw cosines don't compare well
across targets (longer sites look more similar to everything), and z does.
The number of comps then depends on the target. A company with a cluster of
close peers gets more comps, and one without gets fewer.

| | z ≥ 2 | z ≥ 2.5 |
|---|---|---|
| Comps per company, median (range) | 17 (2-41) | 7 (0-23) |
| Companies with fewer than 3 comps | 1 (APG) | 74 (13 with none) |
| PCTY comps | 14 | 6 |

Life-science companies get the most comps (BTMD 41, TCMD 40, BMRN 37)
because their sites read alike.

### Checks (3.3)

- **SIC check, all companies:** the share of each company's top-5
  neighbours that share its code. SIC is used for checking only, never for
  matching.

  | Level | Same code | If random | Lift |
  |---|---|---|---|
  | SIC4 | 24.3% | 1.7% | 14.2× |
  | SIC3 | 35.4% | 3.4% | 10.5× |
  | SIC2 | 48.3% | 7.2% | 6.7× |
  | Division | 68.3% | 27.1% | 2.5× |

- **Text length:** Spearman(word count, mean top-5 cosine) = 0.34. Longer
  sites look somewhat more similar to everything.

### Valuation (3.4)

`target_ev_to_ebitda` is the only financial field read, and it's read only
here, after the comps are fixed. It's joined on `IQ_COMPANY_ID`. The
estimate is the median of the comps' multiples (the mean and IQR are also
shown). Comps without a positive multiple are left out and counted. The
last row uses every other matchable company with no matching. That's the
number matching has to beat.

PCTY (actual 22.13):

| Comp set | Comps | Median | vs actual |
|---|---|---|---|
| z ≥ 2.5 | 6 | 14.87 | −33% |
| z ≥ 2 | 14 | 13.54 | −39% |
| No matching | 534 | 10.84 | −51% |

PCTY's comps at z ≥ 2.5: PAYC, ADP, ASUR, BBSI, INTU, RPAY. Also at z ≥ 2:
HURN, UPLD, KFY, FA, HQI, CSGS, DBX, EVCM.

### Valuation for every company (3.5)

Every matchable company takes a turn as the target and is valued from its
own comps (never itself). This is the yardstick for comparing methods. Two
rows use SIC codes as the comps, as reference points only.

| Comp set | Comps (median) | No estimate | Median abs % error | Within 25% | Spearman(est, actual) | Closer than no matching |
|---|---|---|---|---|---|---|
| Method 1, z ≥ 2.5 | 7 | 13 | 35.9% | 35% | 0.29 | 51% |
| Method 1, z ≥ 2 | 17 | 0 | 34.7% | 38% | 0.31 | 52% |
| Same SIC4 (check) | 4 | 90 | 37.8% | 33% | 0.22 | 49% |
| Same SIC2 (check) | 16 | 5 | 34.8% | 37% | 0.24 | 54% |
| No matching | 534 | 0 | 34.6% | 36% | | |

What it shows:

- **Across the whole list, comps don't beat no matching on error.** The
  typical estimate is about 35% off either way, and the comps' median is
  closer than the all-company median for only about half of companies.
  PCTY's gain in 3.4 doesn't hold in general.
- **The comps do carry information:** companies with higher comp medians
  have higher multiples (Spearman 0.29-0.31). That's more than SIC peer
  groups give (0.22-0.24), so the text finds better peers than industry
  codes do.
- **The multiples are mostly company-specific in this list.** SIC2 groups
  explain about 17% of the variance in log EV/EBITDA (measured in the
  prototype, not in the notebook). Peers' multiples are spread widely, so
  their median is noisy even when the peers are right.

## Method 2: mutual k-nearest neighbours (mutual kNN) and UMAP + HDBSCAN clusters

Method 2 keeps method 1's embeddings and cosines and changes only how comps
are chosen. It's built in steps, each scored like 3.5 before the next is
added:

1. **Mutual nearest neighbours** (done). Company j is a comp of target i
   only when each is among the other's k most similar companies,
   `K_LEVELS = [10, 20]`. The levels were set to give roughly method 1's
   comp counts, before scoring, and weren't tuned on error.
2. **Clusters with a fallback** (done, below).

### Step 1: mutual k-nearest neighbours (mutual kNN)

Why mutual: in method 1 a few companies are comps for many targets ("hubs").
At z ≥ 2, CSW is a comp of 81 companies, SOLV of 74 and ICUI of 70. A hub is
in many companies' top k, but its own top k has only k companies, so here it
can be a comp of at most k targets.

| Comp set | Comps (median, range) | No comps | Most targets one company is a comp of | Median abs % error | Spearman | Closer than no matching |
|---|---|---|---|---|---|---|
| Method 1, z ≥ 2.5 | 7 (0-23) | 13 | 39 | 35.9% | 0.29 | 51% |
| Method 1, z ≥ 2 | 17 (2-41) | 0 | 81 | 34.7% | 0.31 | 52% |
| Mutual, k = 10 | 5 (0-10) | 27 | 10 | 36.5% | 0.26 | 48% |
| Mutual, k = 20 | 11 (0-20) | 3 | 20 | 34.7% | 0.21 | 50% |

Mutual neighbours remove the hubs and agree more with SIC4 at a similar
comp count, but valuation doesn't improve. PCTY: k = 10 gives method 1's six
z ≥ 2.5 comps (14.87, −33%); k = 20 adds KFY, FA, HQI, DBX, ALIT and PRTH
(11.82, −47%).

### Step 2: UMAP + HDBSCAN clusters with a fallback

- **Reduce:** UMAP to 10 dimensions (cosine, 15 neighbours, `min_dist` 0,
  seed 0). HDBSCAN looks for regions denser than their surroundings, and in
  768 dimensions the companies are too spread out for any to stand out: the
  full vectors put 83% of companies in no cluster. PCA to 10-20 dimensions
  still left 30-60%, because it keeps the directions of greatest overall
  variance and leaves the companies about as evenly spread. UMAP keeps each
  company's nearest neighbours close and lets them pack tightly, which gives
  HDBSCAN dense groups. (Full-vector and PCA runs were tried while setting
  up, not in the notebook.) 10 dimensions is a design setting, not a tuned
  value.
- **Cluster:** HDBSCAN (`min_cluster_size` 5, `min_samples` 2) at two
  levels of the same cluster tree: `leaf` (finest; 47 clusters, median 8
  companies, 92 in none) and `eom` (38 clusters, median 10, 58 in none).
  Every leaf cluster sits inside one eom cluster (asserted). scikit-learn's
  HDBSCAN doesn't expose the tree, so the two levels stand in for walking
  it.
- **The tree and eom:** as the density HDBSCAN requires rises, all the
  companies start as one group that splits, and the pieces split again,
  while companies in thin regions drop out. A split counts only when both
  pieces keep at least 5 companies. Each cluster gets a stability: roughly,
  how many companies it holds and over how wide a range of density it
  lasts. `leaf` takes the tree's leaves. `eom` ("excess of mass",
  HDBSCAN's default) works up from the leaves and, at each fork, keeps the
  parent if its stability is at least the children's combined, otherwise
  the children. It has fewer companies in no cluster because a parent it
  keeps includes the companies that dropped out before the parent split.
- **Tree plot** (after the clusters in 4.3): the `hdbscan` package rebuilds
  the tree from the same UMAP vectors. Its `min_samples` doesn't count the
  company itself, so `min_samples` 1 there gives scikit-learn's clusters at
  both levels (asserted). Leaf clusters are numbered along the bottom, eom
  clusters are shaded bands, and PCTY's are red.
- **Comps:** the other members of the target's cluster. *From leaf*: leaf
  cluster, then eom cluster if the company is noise (−1) at leaf, then
  mutual k = 20 neighbours (443 / 34 / 58 companies). *From eom*: eom
  cluster, then mutual k = 20 (477 / 58).
- Settings were set on the clusters' shape (noise share, sizes) before
  scoring, not tuned on error.

| Comp set | Comps (median, range) | Median abs % error | Within 25% | Spearman | Closer than no matching |
|---|---|---|---|---|---|
| Clusters from leaf | 9 (1-37) | 36.5% | 34% | 0.18 | 47% |
| Clusters from eom | 14 (1-37) | 34.7% | 36% | 0.24 | 50% |
| *Method 1, z ≥ 2* | 17 (2-41) | 34.7% | 38% | 0.31 | 52% |
| *No matching* | 534 | 34.6% | 36% | | |

- **Clusters don't improve valuation either**, and they rank companies
  worse than method 1 (Spearman 0.18-0.24 vs 0.31). A cluster gives all its
  members the same comps, which suits a company at its centre more than one
  at its edge.
- **The clusters depend on the UMAP seed.** Rerun with seeds 1-4, a
  company's comps overlap with seed 0's at a median Jaccard of 0.61 (leaf)
  and 0.71 (eom). For 164 (leaf) and 133 (eom) of 535 companies, less than
  half the comps are the same.
- **PCTY** sits in a 7-company payroll / HR cluster at both levels: PAYC,
  ADP, ASUR, BBSI, FA, HQI, ALIT (overlap across seeds 0.91). Estimate 14.38
  (−35%).

### SIC agreement, every comp set

Share of each company's comps with the same code as it, at each level of
the SIC hierarchy, averaged over companies with comps. "No matching" is
the rate by chance. SIC is a check here, never a matching input.

| Comp set | Division | SIC2 | SIC3 | SIC4 |
|---|---|---|---|---|
| Method 1, z ≥ 2.5 | 67% | 45% | 32% | 22% |
| Method 1, z ≥ 2 | 61% | 35% | 24% | 14% |
| Mutual, k = 10 | 69% | 49% | 36% | 26% |
| Mutual, k = 20 | 64% | 42% | 29% | 20% |
| Clusters from leaf | 63% | 43% | 29% | 19% |
| Clusters from eom | 63% | 40% | 28% | 18% |
| No matching (chance) | 27% | 7% | 3% | 2% |

Tighter comp sets agree with SIC more, but that doesn't carry over to
valuation: mutual k = 10 agrees most at every level and has one of the
higher errors.

## Method 3: agglomerative clustering (hierarchical similarity tree)

Method 2's clusters depend on UMAP's settings (10 dimensions, 15
neighbours), which weren't chosen for a reason, and on its random seed.
Tried while setting up (details in
`conversations/2026-10-19-method2-mutual-knn.md`): over 2-50 dimensions and
5-50 neighbours, dimensions barely changed the clusters, more neighbours
merged groups into one cluster of 70-87 companies, and the seed moved
companies at every setting (adjusted Rand index between seeds 0.43-0.79).

Method 3 clusters method 1's cosines directly. There's no reduction, no
seed, and nothing to set but the linkage and the minimum number of comps.
The same input always gives the same tree.

- **Tree:** agglomerative clustering. Every company starts alone, and the
  two closest groups are merged until one holds everyone. Two linkages run
  through the section: `complete` (groups are as far apart as their least
  similar pair, so every pair in a group is at least that similar) and
  `ward` (the merge that adds least to the spread within groups, on the unit
  vectors). `average` was dropped on shape before scoring: a company unlike
  the rest joins a group only once it's large ("chaining"), so 37
  companies got more than 50 comps and OLPX got all 534.
- **Comps:** walk up from the target until its group has at least 5 other
  companies (`MIN_COMPS`, method 2's minimum cluster size, set before
  scoring). A per-company version of method 2's fallback, and every company
  gets comps.

| | Complete | Ward | *Method 1, z ≥ 2* |
|---|---|---|---|
| Comps per company, median (IQR, max) | 7 (6-9, 41) | 7 (5-8, 21) | 17 (13-21, 41) |
| Most targets one company is a comp of | 22 | 15 | 81 |
| Comps sharing SIC2 / SIC4 | 44% / 21% | 43% / 22% | 35% / 14% |

5.2 also compares every comp set with method 1, z ≥ 2, on the same
resampled companies (paired bootstrap, 2000 resamples), because a point or
two of median error is within noise.

| Comp set | Median abs % error | Difference (95% interval) | Spearman | Difference (95% interval) |
|---|---|---|---|---|
| Method 1, z ≥ 2 | 34.7% | | 0.31 | |
| Method 1, z ≥ 2.5 | 35.9% | +0.9 (−2.0 to +3.8) | 0.29 | −0.02 (−0.08 to +0.05) |
| Method 2, mutual k = 20 | 34.7% | +0.2 (−2.1 to +2.4) | 0.21 | −0.10 (−0.17 to −0.03) |
| Method 2, clusters from eom | 34.7% | +0.3 (−2.4 to +3.4) | 0.24 | −0.07 (−0.15 to 0.00) |
| Method 3, complete | 36.3% | +1.7 (−1.1 to +4.4) | 0.22 | −0.09 (−0.17 to −0.01) |
| Method 3, ward | 38.2% | +3.5 (+0.9 to +6.7) | 0.23 | −0.08 (−0.15 to 0.00) |
| No matching | 34.6% | +0.3 (−2.4 to +4.2) | | |

- **The tree removes the arbitrary settings and the seed, but values
  companies no better.** It ranks them worse than method 1, and ward's
  error is measurably higher. At the same comp count (7, method 1 z ≥ 2.5)
  it's still behind: 35.9% and Spearman 0.29 there.
- Tight groups agree with SIC as much as any comp set, again without better
  valuation.
- **PCTY:** complete gives PAYC, ADP, ASUR, BBSI, BLKB, DBX (13.05, −41%);
  ward gives PAYC, ADP, ASUR, BBSI, AJG, ALIT, CCC, CRVL, FA, HQY (18.14,
  −18%), the closest of any comp set for PCTY. One company, so not evidence.

## Every method at 3-10 comps (evaluation notebook, section 2)

Each method's own rule gives a different number of comps, and the number
matters by itself. So each method here gives every company exactly m comps,
m = 3-10: method 1 the m most similar; mutual kNN the m best by the worse of
the two ranks; HDBSCAN cluster-mates (eom, seed 0) first, then the mutual
kNN order; the tree the m most similar in the smallest group with at least
m others. Each count is compared with method 1 at the same count (paired
bootstrap).

| Comps per company | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|
| **Median abs % error** (no matching 34.6) | | | | | | | | |
| Method 1 (cosine z) | 36.4 | 36.3 | 35.5 | 34.5 | 36.0 | 36.6 | 36.5 | 35.1 |
| Method 2 (mutual kNN) | 36.6 | 35.1 | 34.3 | 34.1 | 35.4 | 35.7 | 36.0 | 35.3 |
| Method 2 (HDBSCAN, from eom) | 37.3 | 34.8 | 35.5 | 36.3 | 34.5 | 34.9 | 34.8 | 34.9 |
| Method 3, complete | 38.1 | 36.6 | 37.6 | 36.8 | 36.1 | 36.3 | 36.1 | 37.4 |
| Method 3, ward | 38.4 | 36.6 | 38.6 | 35.5 | 36.4 | 36.0 | 38.9 | 38.2 |
| **Spearman** | | | | | | | | |
| Method 1 (cosine z) | 0.25 | 0.27 | 0.27 | 0.28 | 0.25 | 0.25 | 0.25 | 0.27 |
| Method 2 (mutual kNN) | 0.25 | 0.28 | 0.26 | 0.26 | 0.22 | 0.23 | 0.20 | 0.21 |
| Method 2 (HDBSCAN, from eom) | 0.28 | 0.29 | 0.26 | 0.26 | 0.26 | 0.29 | 0.26 | 0.25 |
| Method 3, complete | 0.26 | 0.27 | 0.24 | 0.21 | 0.20 | 0.15 | 0.19 | 0.17 |
| Method 3, ward | 0.31 | 0.32 | 0.26 | 0.28 | 0.29 | 0.25 | 0.20 | 0.18 |

- **At the same count, no method beats method 1 on either measure.** Error
  differences are within ±3 points, except ward at 5 and 10 comps (worse:
  +3.8 and +3.0). Spearman differences are within ±0.06 at 3-5 comps; from
  6 comps on, the tree (complete) ranks worse at 6, 8 and 10, and mutual
  kNN and ward at 10.
- **No count from 3 to 10 lowers error.** Every method stays at 34-39%,
  around no matching, with no trend.
- Part of method 1's lead in 5.2 was its comp count: at a fixed 3-10 comps
  its Spearman is 0.25-0.28, vs 0.29 (z ≥ 2.5, median 7) and 0.31 (z ≥ 2,
  median 17) with its own rule.

## Ten targets (evaluation notebook, section 3)

PCTY plus nine targets chosen to cover different kinds of business (the
notebook gives the reason for each; Pool Corp was dropped from the list).
Each method uses its own rule.

| Target | Comps (method 1, z ≥ 2.5) | Actual | Error: M1 z ≥ 2.5 / mutual kNN / HDBSCAN / tree complete / no matching |
|---|---|---|---|
| PCTY | PAYC, ADP, ASUR, BBSI, INTU, RPAY | 22.1 | −33 / −47 / −35 / −41 / −51% |
| BV | TTC, GRBK, FOR, BDN | 6.7 | +62 / +17 / +23 / +17 / +63% |
| ROAD | STRL, CDNL, GVA, SMID | 16.5 | −29 / −38 / −30 / −36 / −34% |
| FIX | SPXC, CSW, AAON, LII, LGN, KBH, HDSN | 22.8 | −38 / −38 / −42 / −15 / −53% |
| BRO | BWIN, WRB, AJG, ASIC, PLMR, ORI, AFG, RYAN, THG | 17.7 | −43 / −42 / −43 / −37 / −39% |
| ADUS | AVAH, NHC, ENSG, UHS, AMN, ACH, … | 12.0 | −21 / −24 / −14 / −8 / −10% |
| LOPE | PXED, STRA, LGCY, APEI, PRDO, MH, GEO | 12.5 | −38 / −38 / −40 / −38 / −13% |
| ODFL | XPO, JBHT, PAL, OPLN, EXPD, MRTN | 18.5 | −32 / −39 / −33 / −41 / −41% |
| WING | WEN, MKC, TXRH, BGS, SMPL, STKS, HRL, BROS | 37.2 | −72 / −78 / −72 / −72 / −71% |
| DXPE | SPXC, ITT, CR | 9.9 | +119 / +28 / +81 / +40 / +10% |

- **Where the list has clear peers, every method finds them:** ROAD's first
  four are Sterling (STRL), Granite (GVA), CDNL and SMID; BRO gets Baldwin,
  Gallagher (not in the tree's 6) and Ryan; LOPE gets Strategic Education,
  APEI and Perdoceo; ADUS's closest is Aveanna in every method.
- **The finer or harder distinctions fail.** ODFL's comps mix XPO with the
  truckload carriers (Marten, Heartland). FIX gets HVAC equipment makers
  (SPX, CSW, AAON, Lennox) before contractors (Limbach only at z ≥ 2).
  DXPE gets industrial manufacturers (SPX, ITT, Crane), not distributors.
  BV, with no landscaper in the list, still gets comps under every rule
  (Toro, homebuilders, Forestar): no method says it has no good match,
  since z is relative to the target's own row.
- **Right peers don't make right valuations.** ROAD, BRO and LOPE have
  textbook peers and are still 29-43% off: ROAD and BRO trade well above
  their peers' median, and LOPE's peers trade well below the list. Most
  targets are underestimated. WING (37.2) is 71-78% off under every method.
- Across the ten, median abs error is 37-41% for every method and 40% for
  no matching: too few targets to rank methods.

## Outputs

Each run writes to `outputs-local/matching/<UTC run time>/`. That folder is
git-ignored, so rerun the notebook to get the files.

| File | Contents |
|---|---|
| `universe_text.csv` | The text each matchable company was embedded from, with its URLs |
| `excluded_companies.csv` | Companies not matched, and why |
| `similarity_matrix.csv` | Cosine for every pair |
| `all_comps.csv` | The z ≥ 2 comps of every company, with `comp_z2` / `comp_z2.5` flags |
| `comps_<TARGET>.csv` | The target's full ranking with cosine, z and flags |
| `cosine_falloff_<TARGET>.png` | Cosine by rank, with the z lines |
| `sic_check.csv` | The SIC table above |
| `valuation_<TARGET>.csv`, `valuation_comps_<TARGET>.csv` | Estimates per comp set, and each comp's multiple |
| `valuation_all.csv`, `valuation_all_summary.csv` | 3.5: every company's estimate and % error per comp set, and the summary table |
| `all_comps_mutual.csv` | Method 2: each company's mutual comps up to k = 20, with both ranks and a flag per k |
| `valuation_all_m2.csv`, `valuation_all_summary_m2.csv` | 4.2: the same scoring with method 2 step 1 next to method 1 |
| `umap_embeddings.npy` | 4.3: the 10-dimension UMAP vectors (rows in `universe_text.csv` order) |
| `clusters.csv` | 4.3: each company's leaf and eom cluster (−1 = noise), and where its comps came from |
| `all_comps_clusters.csv` | 4.3: each company's cluster comps, per starting level |
| `cluster_tree.csv`, `cluster_tree.png` | 4.3: HDBSCAN's condensed tree (one row per cluster or company leaving a cluster, with its λ) and the plot |
| `valuation_all_m2_clusters.csv`, `valuation_all_summary_m2_clusters.csv` | 4.4: scoring with every comp set |
| `cluster_stability.csv` | 4.4: each company's comp overlap across UMAP seeds 1-4 |
| `tree_linkage_<linkage>.csv` | 5.1: the tree's merges (two groups, height, size) for average, complete and ward |
| `tree_shape.csv`, `all_comps_tree.csv` | 5.1: comps per company, hubs and SIC agreement per linkage; every company's tree comps |
| `valuation_all_m3.csv`, `valuation_all_summary_m3.csv`, `valuation_vs_method1_m3.csv` | 5.2: scoring, and differences from method 1 z ≥ 2 with bootstrap intervals |
| `fixed_counts_comps.csv`, `fixed_counts_valuation.csv`, `fixed_counts_summary.csv`, `fixed_counts_vs_method1.csv`, `fixed_counts.png` | Evaluation notebook, section 2: every method's m comps for m = 3-10, the estimates, the scoring, differences from method 1, and the plot |
| `targets_comps.csv`, `targets_fixed_counts.csv` | Evaluation notebook, section 3: each target's comps, estimate and error per method (own rule, and fixed counts) |
| `run_info.json` | Settings, snapshot, cache file, and summary numbers (under `method_2`, `method_3`, `fixed_counts`, `targets`) |

Embeddings are cached in `outputs-local/matching/cache/`. The file name
includes the model and a hash of the input texts, so changed text never
reuses stale vectors.

The numbers above are from runs `20261019T080322Z` (`matching_methods.ipynb`
alone) and `20261019T080416Z` (`matching_evaluation.ipynb`, which includes a
run of the methods notebook), the outputs saved in the notebooks: the same
numbers as `20261019T075423Z`, before the split; snapshot `company_list_v3` (sha256 `3ab9a43e…`), page text as re-parsed 2026-10-18.

## Open issues

- **Comps don't beat no matching on error across all companies** (3.5),
  for method 1, either step of method 2, or method 3, though method 1's comps rank
  companies better than SIC does. Better peers alone may not fix this.
  Options: shrink the comps' median toward the all-company median, or
  weight comps by similarity.
- **Mutual-rank cut-offs are blunt.** KFY is a k = 20 comp of PCTY (PCTY
  ranks it 9th, it ranks PCTY 20th) while HURN (7th / 23rd) isn't. A score
  using both ranks, or shared nearest neighbours, could replace the yes/no
  rule. Deferred.
- **Cluster comps depend on the UMAP seed** (step 2). If clusters are kept,
  consider combining several seeds (comps = companies clustered with the
  target in most runs).
- **No floor or cap on comps.** At z ≥ 2.5, 13 companies get no comps, so
  there's no estimate (27 with mutual k = 10). At z ≥ 2, life-science companies get 30-40. A floor
  (e.g. fall back to the top k) or a cap may help.
- **PCTY trades above every comp set's 75th percentile.** Its multiple is
  high for its peers, and the text can't explain that.
- **PCTY comps to sanity-check:** RPAY (payments), HURN (consulting), DBX.
- **Peer labels:** if they join the pipeline, write grading criteria and
  label 3-5 non-HR targets before scoring methods on them.

Details and the full history are in
`conversations/2026-10-18-matching-baseline.md`.
