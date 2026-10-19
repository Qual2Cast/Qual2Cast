# matching/

Comparable-company matching. Treat one company as private, find its comps in
the 560-company list using only website text, then estimate its EV/EBITDA
from the comps' multiples.

Everything is in one notebook, `matching_methods.ipynb`. Each method is one
section and ends with its own valuation, so methods can be compared on the
same numbers.

| Section | What it does |
|---|---|
| 1. Data | Loads the required snapshot (non-financial columns only, checksum-checked) and every scraped page from `outputs-local/website_scrape/page_text/` |
| 2. What the scrape gives us | Scrape status, pages per company, page categories, word counts, and the target's pages |
| 3. Method 1: embeddings | The baseline (below) |
| 4. Method 2 | Empty placeholder for the next approach |

## Running it

```
pip install -r matching/requirements.txt
python -m ipykernel install --user --name qual2cast
```

Open the notebook, pick the `qual2cast` kernel and run top to bottom. Set
`TARGET` (a ticker) in the first code cell. The first run downloads
`all-mpnet-base-v2` (~420 MB) and embeds all 535 companies (several minutes
on a laptop CPU). Later runs use the cached vectors.

The notebook needs the website text that's in Git
(`outputs-local/website_scrape/page_text/`) and the snapshot in
`data-local/snapshots/`. It doesn't scrape anything.

## Method 1: what changed from Riya's baseline

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
| `run_info.json` | Settings, snapshot, cache file, and summary numbers |

Embeddings are cached in `outputs-local/matching/cache/`. The file name
includes the model and a hash of the input texts, so changed text never
reuses stale vectors.

The numbers above are from run `20261019T013344Z` (the outputs saved in
the notebook), snapshot `company_list_v3` (sha256 `3ab9a43e…`), page text as re-parsed 2026-10-18.

## Open issues

- **One target so far.** Whether comps beat "no matching" in general needs
  3.4 run for every matchable company: median absolute % error at each z
  level vs no matching, plus how many companies get no estimate.
- **No floor or cap on comps.** At z ≥ 2.5, 13 companies get no comps, so
  there's no estimate. At z ≥ 2, life-science companies get 30-40. A floor
  (e.g. fall back to the top k) or a cap may help.
- **PCTY trades above every comp set's 75th percentile.** Its multiple is
  high for its peers, and the text can't explain that.
- **PCTY comps to sanity-check:** RPAY (payments), HURN (consulting), DBX.
- **Peer labels:** if they join the pipeline, write grading criteria and
  label 3-5 non-HR targets before scoring methods on them.

Details and the full history are in
`conversations/2026-10-18-matching-baseline.md`.
