# Text-Based Comparable Company Matching — Proof of Concept (Paylocity / PCTY)

**Author:** Riya · **Notebook:** `comps_similarity_PCTY.ipynb` · **Status:** baseline model (working proof of concept; known issues listed in §8)

## 1. What this does and why

**Question:** If a company were private and all we had was its website, could we automatically find its closest public comparables?

**Why it matters for the project:** our goal is forecasting private-company revenue growth from qualitative signals. A reliable peer group gives us (a) a peer-based growth prior from the comps' realized growth and (b) a baseline to compute peer-relative features against (e.g., is this company hiring faster than its peers?).

**Test case:** Paylocity (PCTY), an HR/payroll (HCM) software company from Aziz's 560-company list, treated as if it were private. It fits the employee-management software profile Rational AI focuses on.

## 2. Data

| Input | Description |
|---|---|
| `descriptions.csv` | 560 companies: ticker, name, SIC codes, scrape status, word count, path to text file |
| `text/IQ<id>_<TICKER>.txt` | Scraped homepage / about / who-we-serve text, company name masked as `[COMPANY]` |

- 489 scrapes are `ok`; the rest are thin, robots-blocked, 403, or errored.
- After cleaning, **487 companies are matchable**; 73 are excluded with a stated reason (`comps_output/excluded_companies.csv`). Excluded ≠ dissimilar — they simply can't be scored yet.

## 3. Method

1. **Clean text.** Split into sentences; drop boilerplate (cookies, legal, CTAs) and investor-relations language (earnings, NYSE/Nasdaq, shareholder), which also prevents public-company leakage. Drop any sentence appearing verbatim on ≥3 sites (shared templates). Removes ~6% of words.
2. **Represent each company three ways:**
   - **TF-IDF** (1–2 word phrases, generic marketing words removed): distinctive vocabulary; fully transparent.
   - **LSA** (150-dim SVD of TF-IDF): co-occurring words grouped into latent topics.
   - **Sentence embeddings** (`all-mpnet-base-v2`, 200-word chunks, mean-pooled): meaning-level similarity.
3. **Score.** Cosine similarity between the target and every company, per method. Each method's scores are z-scored, then averaged into an **ensemble** score.
4. **Explain.** For every match, list the TF-IDF terms contributing most to the similarity ("why similar").
5. **Validate** (Section 5 below).

SIC codes are **not** used in scoring — only as a display column and a weak validation signal, because they're too coarse (SIC 7370 contains both Paycom and game studios).

## 4. Results for PCTY

| Rank | Company | Assessment |
|---|---|---|
| 1 | Barrett Business Services (BBSI) | Same customers and channel (SMB payroll/HR via brokers), but a PEO — different economics |
| 2 | Paycom (PAYC) | Direct competitor |
| 3 | Asure (ASUR) | Direct competitor |
| 4 | ADP | Direct competitor |
| 5–7 | Huron, First Advantage, Intuit | Mixed: FA and INTU are adjacent; Huron is consulting that *talks* about HR/payroll |
| 8+ | SS&C, Donnelley, Forrester, … | Mostly generic B2B-software vocabulary — not real comps |

The score curve drops sharply after ~rank 6: Paylocity has a small, distinct peer cluster. Running `find_comps("PAYC")` returns the same cluster (Asure, ADP, Paylocity, BBSI) from the other direction.

## 5. Validation — why we believe it

| Check | What it tests | Result |
|---|---|---|
| **Hand-labeled peers** (11 peers, written *before* seeing output; 3 direct, 8 adjacent) | Does it find known peers? | Ensemble: 9/11 in top 25, NDCG@20 = 0.76. Embeddings alone: **11/11**, NDCG@20 = 0.87. Random: 0.5/11, NDCG = 0.03 |
| **Universe-wide SIC agreement** | Does it work for all 487 companies, not just PCTY? | Top-5 neighbors share SIC4 ~22% of the time vs 1.8% random (**~12× lift**) |
| **Method agreement** | Do independent methods agree? | 55–85% overlap in top-20 lists |
| **Length bias** | Do long pages win just by having more words? | Some effect (ρ = 0.27 embed, 0.54 TF-IDF), but removing it keeps 20/25 of the top list and doesn't improve metrics |
| **Ablation** | Does focusing on one aspect help? | Product sentences only: slightly worse. Customer sentences only: near random (0.10) — every site describes customers generically |

## 6. Strengths

- **Clearly beats chance**, on both the target and the whole universe.
- **Explainable:** every match comes with the shared terms that drove it.
- **Robust:** three methods built on different ideas; ensembling covers individual failures (e.g., embeddings alone rank Paycom 16th; word methods rank it 2nd).
- **Leakage-aware:** names masked, IR/earnings text stripped.
- **Reusable:** `find_comps(ticker)` works for any matchable company; runs locally in about a minute.
- **Transparent exclusions:** every dropped company has a reason on file.

## 7. Limitations

- **Thin validation.** One target and 11 labels written by one analyst is a sanity check, not a benchmark. Ensemble weights have not been tuned, and should not be tuned on PCTY alone.
- **Marketing text ≠ business model.** Websites describe how a company wants to be seen. Text similarity finds who *sounds* alike, not who has the same economics (BBSI is the clear example: similar text, PEO economics).
- **Generic-language noise.** Below ~rank 8, matches are driven by shared B2B vocabulary ("automate," "platform," "clients").
- **Customer segment and pricing model are not captured** by the current text (see the ablation).
- **Equal-weight ensemble under-uses embeddings.** TF-IDF and LSA are highly correlated (ρ = 0.85), so word-based matching effectively gets two of three votes.
- **Fixed universe.** Real competitors not on the list (Paychex, Dayforce, Paycor) can't appear.
- **Scrape coverage and artifacts.** 73 companies are unscorable; browser-rendered pages score lower on average (possible artifact, not yet investigated).
- **Residual leakage.** Phrases like "Fortune 500" can still hint at public status.

## 8. Known issues in the code (read before building on it)

These are implementation issues, separate from the method's limitations above. None of them change the PCTY conclusions, but they matter when you reuse the notebook.

| # | Issue | Effect | Fix |
|---|---|---|---|
| 1 | **Boilerplate regex has no word boundaries.** `quarter` matches "head**quarter**s"; `investor`, `stock`, `shareholder` also strip sentences that describe the core business of asset managers, brokers, and exchanges; `privacy` / `browser` do the same for data-privacy and web-software firms. | Lower-quality text, and worse comps, for financial and privacy/web companies. Minimal effect on PCTY. | Add `\b` word boundaries; drop or narrow `investor` and `stock` (e.g., keep only "investor relations", "stock price"). |
| 2 | **Embedding cache can go stale.** `embeddings_mpnet.npy` is reused whenever the company count matches. | Changing `EMBED_MODEL` or the cleaning rules silently reuses old embeddings. | Delete `comps_output/embeddings_mpnet.npy` after any such change, or include the model name and a text hash in the cache filename. |
| 3 | **Some settings were tuned while looking at PCTY output.** The generic marketing stop-words ("smarter", "seamless", …) were partly chosen from PCTY's shared terms. | Slight optimistic bias in the PCTY peer-label metrics. The universe-wide SIC check is unaffected. `PEER_LABELS` itself was fixed before any rankings were seen. | Freeze settings, then validate on new targets (next step 1). |
| 4 | **`CSV_PATH` is a relative path** (`"../descriptions_output_riya/descriptions.csv"`). | Breaks if VS Code/Jupyter runs from a different working folder. | Use `CSV_PATH = BASE_DIR / "descriptions.csv"`. |

## 9. How to run

1. Set `BASE_DIR` in the config cell to the folder containing `descriptions.csv` and `text/`, and set `CSV_PATH = BASE_DIR / "descriptions.csv"` (see known issue #4).
2. `pip install pandas numpy scikit-learn matplotlib ipykernel sentence-transformers` (embeddings are optional; the notebook skips them if not installed).
3. Set `TARGET` in the config cell, then **Restart → Run All**.
4. Outputs go to `comps_output/`: `comps_<TICKER>.csv`, `excluded_companies.csv`, score-curve and map PNGs, cached embeddings. Delete the cached embeddings file if you change the model or cleaning rules (known issue #2).

To change the peer answer key, edit `PEER_LABELS` (2 = direct competitor, 1 = adjacent). Write it **before** looking at results.

## 10. Suggested next steps

0. **Fix known issues #1 and #4** (one-line changes each) before using `find_comps` on non-HR targets, so later improvements are measured against a clean baseline.
1. **Broaden validation:** write peer labels for 3–5 more targets in different industries (e.g., healthcare, industrials, insurance); report average metrics across targets.
2. **Re-weight the ensemble** (e.g., embeddings 0.5, TF-IDF 0.25, LSA 0.25), choosing weights on the multi-target labels from step 1, not on PCTY.
3. **LLM-standardized profiles:** have an LLM write a fixed-format profile per company (what they sell, who buys it, how they charge, value-chain position) from the text only, and embed that instead of raw marketing copy. This is the most likely fix for the customer-segment and business-model gaps.
4. **Business-model flags:** add simple tags (SaaS vs. services vs. PEO, SMB vs. enterprise) to filter or re-rank comps.
5. **Recover excluded companies** by re-scraping blocked/thin sites or using Capital IQ / PitchBook business descriptions.
6. **Connect to forecasting:** pull comps' realized 3-year revenue growth to build a peer-based prior, and compute peer-relative qualitative features for the growth model.
