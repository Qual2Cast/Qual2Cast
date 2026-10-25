# Comparable-company write-up (draft, scraps)

_Draft 2026-10-18, set aside with the first matching pass: it describes that
notebook's method and results, not the method now being designed. Covers
everything up to results; the human sanity check and valuation sections were
never written. Run: `outputs-local/scraps/comps_first_pass/notebook_embed/20261018T190530Z/`._

Target: **Paylocity (PCTY)**, treated as if private. It is the only target
with peer labels written before any ranking was seen (Riya,
`scraps/comps_first_pass/peer_labels.csv`), so it is the only one whose ranking
can be scored. The notebook takes any ticker (`TARGET` in its first cell).

## Candidate peer pool

The supplied universe: all 560 rows of `company_list_v3` (US public
companies, Rational AI list), minus the target. No pre-filter by SIC or size.

A company drops out only when its website gave too little usable text:
26 of 560, so **534 are matchable** (533 candidates for a given target).
Each excluded company is listed with its reason in `excluded_companies.csv`:

| reason | count |
|---|---|
| main domain redirects to an investor-relations site | 4 (Avista, Black Hills, Simpson Manufacturing, IAC) |
| robots.txt disallows scraping | 4 |
| HTTP 403 / bot-check page | 5 |
| under 100 words left after cleaning | 13 |

## Nonfinancial information collected

**Inputs per company: name and website only** (Aziz's rule). No 10-Ks,
investor-relations pages, or stock data, so the method would work the same
for a private target.

- **Website text** (`website_scrape/scrape_websites.py`). Up to 3 pages
  per site: the homepage plus the best-scoring products / solutions / about /
  industries / customers pages. Fetched as plain HTML, browser-rendered,
  stealth browser, or Wayback Machine. robots.txt is honored. Every page keeps
  its URL, fetch time and raw HTML (`source_pages.csv` lists them per
  company).
- **Cleaning.** Removed: site chrome and boilerplate, sentences shared by 3+
  companies' sites (templates), and sentences that reveal a public company or
  carry financial or size information (tickers, investor and earnings talk,
  revenue and headcount figures, deal history, founding dates). Each removal is
  logged with its reason. The company's own name and domain are masked as
  "the Company".
- **Not used in this pass:** the Codex-extracted profile fields
  (products, customers, business model, ...). Matching runs on the website
  text directly. The profiles can be compared against it later on the same
  checks.

What a site doesn't say simply isn't in the text; nothing is filled in by
hand or by a model. **Financial fields** (revenue, EBITDA, margin,
debt/revenue, EV/EBITDA) are never loaded by the notebook. SIC codes are used
only to check the results.

## Matching method

`scraps/comps_first_pass/comps_embeddings.ipynb`:

1. Each company's cleaned text is split into 200-word chunks. Each chunk is
   embedded with **`all-mpnet-base-v2`** (open-source sentence-transformers
   model, run locally). The chunk vectors are averaged into one vector per
   company.
2. Score = cosine similarity between the target's vector and each candidate's.
   Candidates are ranked by score.
3. Evidence: for each of the top 15, the three most similar sentence pairs
   (target sentence, comp sentence), each with its source URL.

No LLM is used in the ranking.

## Results obtained (PCTY)

| rank | comp | score | labeled peer? |
|---|---|---|---|
| 1 | Paycom (PAYC) | 0.856 | direct |
| 2 | Asure Software (ASUR) | 0.851 | direct |
| 3 | Barrett Business Services (BBSI), a PEO | 0.837 | adjacent |
| 4 | ADP | 0.829 | direct |
| 5 | Huron Consulting (HURN) | 0.792 | no |
| 6 | Intuit (INTU) | 0.779 | adjacent |
| 7 | Upland Software (UPLD) | 0.768 | no |
| 8 | First Advantage (FA) | 0.739 | adjacent |
| 9 | EverCommerce (EVCM) | 0.736 | no |
| 10 | Korn Ferry (KFY) | 0.727 | adjacent |

The full top 25 and all 533 candidates are in `comps_PCTY.csv` and
`ranking_PCTY.csv`.

**Checks**
- **Peer labels:** NDCG@20 0.90, recall@25 0.91 (10 of 11 labeled peers in
  the top 25). Random ordering: 0.02 and 0.05. All three direct competitors are
  in the top 4. The one miss is Equifax (rank 53, labeled for employment data).
- **SIC4, all 534 companies:** 24% of top-5 neighbours share the company's
  SIC4 code, against 1.7% by chance (14×).
- **Text length:** Spearman 0.31 between score and word count, so length
  matters only moderately.
- **Earlier methods for comparison:** on the same text, TF-IDF reaches NDCG@20
  0.70 and the combined TF-IDF/LSA/embedding score 0.72
  (`outputs-local/scraps/comps_first_pass/pages/`).

**Points for the human check**
- The evidence sentences are often generic marketing copy ("the best solution
  for your business"), so they don't always explain a match. Reviewers should
  open the source pages, not rely on the sentence pairs alone.
- Huron Consulting (#5) is matched on consulting-style language ("work side
  by side with clients"). It looks questionable as a payroll-software comp.

## Limitations (so far)

- Peer labels exist for one target only. HR/payroll has distinctive
  vocabulary, so the scores may be optimistic for other industries.
- Website text is marketing copy: it says what a company offers, not how much
  revenue each line brings in.
- 26 companies (4.6%) can't be matched from their websites.
- Valuation date of the supplied multiples: unknown.

## Code and output location

- Repository: Qual2Cast (`main`).
  - Notebook: `scraps/comps_first_pass/comps_embeddings.ipynb` (uses helpers in
    `comps_similarity.py`).
  - Collection and cleaning: `website_scrape/scrape_websites.py`.
- Outputs (not in Git): `outputs-local/scraps/comps_first_pass/notebook_embed/<run time>/`:
  `comps_<T>.csv`, `ranking_<T>.csv`, `evidence_<T>.csv`, `source_pages.csv`,
  `universe_text.csv`, `excluded_companies.csv`, `run_info.json`.
- Data: snapshot `company_list_v3` (`data_manifest.json`; not in Git).
- Environment: Python 3.14 with `requirements.txt`. The notebook kernel is
  "Python 3.14 (Qual2Cast)". The default `python3` kernel on this laptop is
  Anaconda, which lacks the packages.
