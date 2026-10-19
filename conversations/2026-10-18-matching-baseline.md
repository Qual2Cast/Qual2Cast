# Handoff: embedding baseline in the matching notebook (2026-10-18)

Work done in Claude Code. This file is the summary.

## What was asked

Look at Riya's branch (`riya/wip`) for the method that turns the scraped
pages into embeddings and ranks companies by cosine similarity. Use it as a
baseline and get similarity results.

## Completed

- Riya's method (`similarities/comps_similarity_PCTY.ipynb`, embedding part)
  added to `matching/matching_methods.ipynb` as a **Baseline** section, before
  the placeholder section 3. Written inline in the notebook, so the pipeline
  does not import from `scraps/`.
  - Text: each company's cleaned page text (title, meta, blocks) as is, with
    no name masking and no template-sentence removal. These are left as open
    choices for section 3.
  - Matchable: at least 100 cleaned words. 535 matchable; 25 excluded, each
    with a reason.
  - Embeddings: `all-mpnet-base-v2`, 200-word chunks, mean-pooled and
    normalised. Cached in `outputs-local/matching/cache/` under the model and
    a text hash.
  - Cosine similarity for every pair; the top 25 for every company.
  - Checks: PCTY peer labels (`scraps/comps_first_pass/peer_labels.csv`)
    with NDCG/recall against 200 random orderings, the rank of each labeled
    peer, the SIC4/SIC2 top-5 check, and length bias.
- Each run saves to `outputs-local/matching/<run time>/`: universe_text,
  excluded_companies, similarity_matrix, all_comps, comps_PCTY, peer_check,
  peer_ranks, sic_check, run_info.json.
- The notebook ran top to bottom (nbconvert, kernel `qual2cast`).

## Results (run 20261018T215627Z, PCTY)

- Top 10: PAYC, ADP, ASUR, BBSI, INTU, RPAY, HURN, UPLD, KFY, FA.
- NDCG@10 0.89, NDCG@20 0.92, recall@10 0.64, recall@25 0.82 (random 0.02 /
  0.03 / 0.02 / 0.05). Labeled peers outside the top 25: HSTM (32), EFX (70).
- First pass on masked text, for comparison: NDCG@20 0.90, recall@25 0.91.
- SIC check, all companies: 24% of top-5 neighbours share SIC4 (chance 1.7%,
  14×); 48% share SIC2 (chance 7.2%, 6.7×).
- Spearman(word count, mean top-5 cosine) = 0.34.

## Data version

company_list_v3 (sha256 3ab9a43e…). Page text as re-parsed 2026-10-18.
Embedding cache `embed_all-mpnet-base-v2_200w_baf361554e82667f.npy`.

## Unresolved

- Peer labels exist only for PCTY. With one target, 0.92 against 0.90 is not
  a real difference.
- Questionable PCTY comps to sanity-check: RPAY (payments, #6), HURN
  (consulting, #7), DBX (#13), AJG (#16).
- Nothing committed.

## Later in the session: checks simplified

- Peer-label scoring (NDCG, recall, peer rank table) removed from the
  notebook. With one target and labels from `scraps/` (not adopted), the
  scores can't compare anything yet. The scoring code is still in
  `scraps/comps_first_pass/comps_similarity.py`.
- Kept: the SIC check, now at SIC4, SIC3, SIC2 and Division (lift 14.2,
  10.5, 6.7, 2.5), and the PCTY top 10 with Riya's grades shown as a
  reference only.
- Tables are indexed by rank; the lift column is labeled "times better than
  random (lift)".
- Added `matching/requirements.txt` (the notebook's packages only).

## Next recommended action

1. Decide whether peer labels join the pipeline. If so, write grading
   criteria and labels for 3-5 non-HR targets before running them.
2. Design the real method (section 3) and compare it to this baseline on the
   same labels.

## Later in the session: method 1 made into a full section with a valuation

Asked: top 12 instead of 25; a graph of how PCTY's cosine falls off across
every other company, with a threshold; a valuation from the comps' EV/EBITDA
against PCTY's actual multiple; delete the stale sections after the
SIC/Spearman checks to make room for another approach.

### Completed

- Notebook restructured: section 3 is now "Method 1: embeddings of the
  website text" with 3.1 Comps, 3.2 How similarity falls off, 3.3 Checks,
  3.4 Valuation. Section 4 "Method 2" is an empty placeholder. Deleted: the
  PCTY peer-grade table (Riya's labels) and the old placeholder sections 3-7
  (matching method, results, sanity checks, valuation, definitions).
- `TOP_K` 25 → 12 (`all_comps.csv` now has the top 12 per company).
- `z` column on every comps list: (cosine − target's mean cosine with all
  other companies) / its SD. Threshold comps: z ≥ `Z_MIN` = 2.0. Chosen over
  min-max scaling, which depends on the single least similar company.
- Plot `cosine_falloff_<TARGET>.png`: all 534 cosines by rank, and a top-40
  zoom with the threshold comps labeled, the z = 2 line and the top-12 line.
- Valuation: only `target_ev_to_ebitda` is read from the snapshot, after the
  comps are fixed, joined on IQ_COMPANY_ID. Estimate = median of comps'
  multiples (mean and IQR shown too); reference row = median of all other
  matchable companies (no matching).
- New run files: comps_<TARGET>.csv (now the full ranking with in_top_k /
  in_threshold), cosine_falloff_<TARGET>.png, valuation_<TARGET>.csv,
  valuation_comps_<TARGET>.csv; run_info.json gains top_k, z_min,
  threshold_cosine, threshold_comps, valuation.
- Notebook ran top to bottom (nbconvert, kernel `qual2cast`), run
  `20261019T012122Z`.

### Results (PCTY)

- PCTY row: mean cosine 0.345, SD 0.134; z = 2 at cosine 0.613. 14
  threshold comps = the top 12 + DBX, EVCM. The 12th comp (CSGS) has z 2.06.
- EV/EBITDA, PCTY actual 22.13:

  | comp set | comps | median | mean | median − actual |
  |---|---|---|---|---|
  | top 12 | 12 | 13.54 | 14.28 | −8.59 (−39%) |
  | threshold (z ≥ 2) | 14 | 13.54 | 14.43 | −8.59 (−39%) |
  | all others, no matching | 534 | 10.84 | 12.53 | −11.28 (−51%) |

### Unresolved

- One target. Whether the comps median beats the no-matching median in
  general needs the valuation run for every company.
- PCTY trades above every comp set's 75th percentile (18.9 at most): its
  multiple is high for its peers, which the text can't explain.
- No minimum number of threshold comps; a target with no close peers could
  get 0-2. Decide a floor (e.g. fall back to the top k) when running all
  targets.
- Nothing committed.

### Next recommended action

Run 3.4 for every matchable company (median absolute % error, top 12 vs
threshold vs no matching), then build method 2 in section 4 and compare on
the same numbers.

## Later still: comps defined by z only (no fixed top 12)

Asked: instead of a hard number of comps, use the companies whose cosine z
is 2 or more.

- Removed `TOP_K` and every top-12 piece (table, dotted line on the plot,
  `in_top_k` column, valuation row). `ranking(ticker)` gives every other
  company with cosine and z; `comps(ticker)` keeps z >= `Z_MIN` (2.0). z is
  now explained in 3.1; 3.2 is the plot only.
- `all_comps.csv` = the z >= 2 comps of every company. `comps_<TARGET>.csv`
  = full ranking with a `comp` flag. `run_info.json`: `z_min`,
  `comps_per_company` (summary), `target_z_min_cosine`, `target_comps`.
- Ran top to bottom, run `20261019T012714Z`.

Results: comps per company median 17, range 2-41; 1 company under 3 (APG,
APi Group: KFY and HURN, both poor fits). Most comps: healthcare / biotech
(BTMD 41, TCMD 40, BMRN 37), whose sites read alike. PCTY: 14 comps (same as
the earlier threshold set), median EV/EBITDA 13.54 vs actual 22.13 (−39%);
no-matching median 10.84 (−51%).

Unresolved: z >= 2 gives 2 comps for APG and 30-40 for life-science
companies. Worth checking whether a cap or floor helps once valuation error
is measured across all companies. This supersedes the "no minimum" note
above: the minimum observed is 2, not 0.

## Later still: a second level, z >= 2.5

Asked: run z >= 2.5 as well, through the whole flow.

- `Z_MIN` replaced by `Z_LEVELS = [2.0, 2.5]`. z >= 2.5 comps are a subset
  of z >= 2, so tables list the z >= 2 comps with a flag column per level
  (`comp_z2`, `comp_z2.5`): all_comps.csv, comps_<TARGET>.csv,
  valuation_comps_<TARGET>.csv. Comps-per-company printed per level; plot
  has a dashed line per level (filled dots z >= 2.5, open dots 2 <= z <
  2.5); valuation has a row per level. run_info: `z_levels`,
  `comps_per_company` (per level), `target_level_cosines`, `target_comps`.
- Ran top to bottom, run `20261019T013003Z`.

Results:
- Comps per company, z >= 2.5: median 7, range 0-23; 13 companies get none
  (APG, ASTE, CLMB, DHX, EVTC, FSS, FERG, INTU, POWL, RCMT, EML, UFPT, WEX),
  29 get one, 32 get two (74 under 3). z >= 2: median 17, range 2-41.
- PCTY: z = 2.5 at cosine 0.681, 6 comps (PAYC, ADP, ASUR, BBSI, INTU,
  RPAY). EV/EBITDA median 14.87 vs actual 22.13 (−7.25, −33%); z >= 2:
  13.54 (−39%); no matching 10.84 (−51%).

Unresolved: at z >= 2.5 a company with no comps gets no estimate (median of
nothing = unknown). When valuing every company, report how many have no
estimate at each level next to the error.
