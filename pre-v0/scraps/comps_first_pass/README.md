# First matching pass (scraps)

**Set aside on 2026-10-18.** A port of Riya's comps notebook (TF-IDF, LSA,
embeddings and a combined score), plus an embeddings-only notebook, run on
the scraped website text. The real matching method is being designed
separately. This is kept as a reference point and a baseline: PCTY NDCG@20
0.90 for embeddings, against 0.02 for a random ordering. The code still
runs and its tests pass. It writes to `outputs-local/scraps/comps_first_pass/`.

`peer_labels.csv` (Riya's graded PCTY peers, written before any ranking was
seen) is still usable to check any method on PCTY.


Treat a company as if it were private, then rank the other companies in the
list by how similar their **website text** is. Inputs are the website scrape only
(name + website, Aziz's rule); SIC codes are used only for checking, and
financial fields are never read.

Ported from Riya's proof of concept (branch `riya/wip`,
`similarities/comps_similarity_PCTY.ipynb` and its README), so it reads this
repository's website scrape (snapshot v3) instead of her own scrape. The method
and checks are hers. The port fixes the four known issues her README lists
(see below).

**Notebook, embeddings only:** [comps_embeddings.ipynb](comps_embeddings.ipynb)
walks through the write-up steps for one target: candidate pool, information
collected, embedding ranking, evidence sentences with source URLs, and checks.
It uses the website text only, never the Codex fields. Each run saves to
`outputs-local/scraps/comps_first_pass/notebook_embed/<run time>/`. Use the kernel "Python 3.14
(Qual2Cast)" (`python -m ipykernel install --user --name qual2cast` with
the interpreter that has `requirements.txt` installed). PCTY on 2026-10-18:
NDCG@20 0.90, recall@25 0.91.

## Two text sources

| `--source` | text | from |
|---|---|---|
| `pages` | the scraped, cleaned page text, with the company's own name removed | `outputs-local/website_scrape/page_text/` |
| `profiles` | `matching_summary`, the fixed-format summary built from verified Codex profile items | `outputs-local/scraps/codex_profiles/final_tables/matching_inputs.csv` |

Running both through the same checks shows whether the structured profiles
find better comparables than raw marketing text (her suggested next step 3).
`profiles` only covers the companies Codex profiled before it was set aside
(219).

## Method

1. Split the text into sentences. Drop leftover boilerplate (cookies, sign-up
   and login text, ...) and, for page text, any sentence found on 3 or more
   companies' sites (shared templates).
2. Represent each company three ways:
   - **TF-IDF** of 1-2 word phrases (generic and marketing words removed)
   - **LSA**: 150-dimension SVD of the TF-IDF
   - **sentence embeddings** (`all-mpnet-base-v2`, averaged over 200-word
     chunks), if `sentence-transformers` is installed
3. Cosine similarity to the target per method. Each method's scores are
   z-scored and averaged into an **ensemble** (equal weights; don't tune them
   on PCTY alone).
4. `why_similar`: the TF-IDF terms contributing most to each match.

## Checks (`--validate`)

- **Peer labels** ([peer_labels.csv](peer_labels.csv)): graded peers per
  target (2 = direct competitor, 1 = adjacent). NDCG@10/20 and recall@10/25
  per method, against the mean of 200 random orderings. Labels must be written
  **before** a target is run and never edited after seeing results. Only
  PCTY's labels exist (Riya's).
- **SIC4 check, all companies**: how often a company's top-5 neighbours share
  its SIC4 code, against chance. This is a weak signal, since SIC is coarse
  and sometimes wrong.
- **Per target** (`run_info.json`): overlap of the methods' top-20 lists, and
  Spearman correlation of similarity with text length.

## Fixes to the notebook

| notebook issue | fix here |
|---|---|
| #1 boilerplate regex had no word boundaries ("quarter" matched "headquarters"; "investor", "stock", "privacy" removed core text of finance and privacy firms) | word boundaries; public-company terms removed from this list (the scrape's filters already remove them); "privacy" only as "privacy policy/notice" |
| #2 embedding cache reused whenever the row count matched | cache file named after the model and a hash of the texts |
| #3 marketing stop-words partly picked from PCTY output | kept as they are, frozen; flagged in the code. Validate on new targets before changing anything |
| #4 relative and per-laptop paths | paths come from `src/project_data.py` |
| SIC read as numbers (BrightView 700) | read through `normalize_sic_codes` (0700) |

## First results (2026-10-18, `pages`, 535 companies matchable, 25 excluded)

| PCTY | NDCG@10 | NDCG@20 | Recall@10 | Recall@25 |
|---|---|---|---|---|
| TF-IDF | 0.67 | 0.70 | 0.45 | 0.64 |
| LSA | 0.77 | 0.78 | 0.45 | 0.55 |
| embeddings | 0.82 | 0.85 | 0.64 | 0.91 |
| ensemble | 0.80 | 0.80 | 0.55 | 0.64 |
| random | 0.02 | 0.03 | 0.02 | 0.05 |

- Top 5 for PCTY: Paycom, Barrett (a PEO), Asure, First Advantage, ADP. These
  are close to Riya's results on her scrape (ensemble NDCG@20 0.76,
  embeddings 0.87).
- All companies: about 24% of top-5 neighbours share their SIC4 code, against
  1.7% by chance (14× better).
- As in the notebook, TF-IDF and LSA mostly agree (90% top-20 overlap), so
  word overlap effectively gets two of the three votes. Embeddings do best on
  their own.
- Similarity rises with text length (Spearman 0.66 for TF-IDF, 0.32 for
  embeddings).
- Shared page templates still leak in. For example, SPS Commerce ranks 5th
  for Paycom on "Forrester consulting" case-study text.

## Run

```bash
pip install -r requirements.txt
python comps_similarity.py --source pages --target PCTY --validate
python comps_similarity.py --source profiles --validate   # only 219 companies profiled
python -m pytest tests -q
```

Outputs go to `outputs-local/scraps/comps_first_pass/<source>/`:
- `comps_<TICKER>.csv`: ranked comps with per-method scores and `why_similar`
- `universe_text.csv`: the exact text each company was matched on
- `excluded_companies.csv`: every company left out, with the reason
- `peer_validation.csv` and `sic_check.csv`
- `run_info.json`: settings and diagnostics

Embeddings are cached in `outputs-local/scraps/comps_first_pass/cache/`. The first run downloads
the model and embeds every company, which takes about 10 minutes on a laptop
CPU.

## Next steps (as written before it was set aside)

1. Peer labels for 3-5 more targets in other industries (e.g. healthcare,
   industrials, insurance), written by someone before running them.
2. After a full Codex extraction run, compare `pages` and `profiles` on the
   same labels.
3. Only then choose ensemble weights (Riya suggests embeddings 0.5, TF-IDF
   0.25, LSA 0.25), using the multi-target labels.
4. Filter or re-rank by the profile tags (`customer_types`, `revenue_streams`,
   `operating_roles`) to separate, for example, a PEO from payroll software.
