# Qual2Cast

**Forecasting private-company revenue growth from qualitative signals.**
*Columbia University IEOR Industry Capstone, in partnership with Rational AI (Fall 2026).*

Private companies don't publish audited financials, so it's hard to estimate how fast they'll grow or what they're worth. They do leave a public trail: their own website, press releases, job posts, news. Qual2Cast turns that trail into numbers a model can use, with two aims:

1. **Find comparable public companies ("comps")** for a private company from its website alone, and use the comps' valuation multiples to estimate the private company's value.
2. **Forecast 3-year revenue growth** from dated events such as new contracts, hiring, layoffs, launches and credit trouble.

Every automated step, including any language model, is treated as a system under test: it's scored against known answers, and its errors are counted rather than trusted away.

_README last updated 2026-10-19. Times below are US Eastern (UTC−4)._

---

## Where things stand

| part | state on `main` | where |
|---|---|---|
| Company list | **Done.** 560 US public companies, used as stand-ins for private targets. | `data-local/snapshots/`, `data_manifest.json` |
| Website scrape | **Done for all 560.** 532 sites gave usable text. | `website_scrape/` |
| Comparable-company matching | **Three methods built and scored on all 535 usable companies.** Picking comps from website text finds real peers but doesn't yet beat a no-matching estimate on valuation error. | `matching/` |
| Ten-company research pilot | **Frozen comparison** of 31 ways to rank peers, on ten companies. Human review still pending. | `notebooks/`, `experiments/`, `reports/` |
| Growth signals | **First collector and rule-based event extractor**, tested on five companies. A revised version is on a branch (see below). | `growth_signals/` |
| Growth forecasting model | **Not started.** Needs past revenue for the outcome and point-in-time event history. | n/a |
| Report, definitions and limitations | **Not started.** | n/a |

## How it fits together

```mermaid
flowchart TD
    A["<b>Company name + website</b><br/><i>the only inputs a private target gives us</i>"]
    B["<b>Website scrape</b><br/><i>up to 3 pages per site<br/>financial and public-company text removed</i>"]
    C["<b>Comparable-company matching</b><br/><i>text → embeddings → comps</i>"]
    D["<b>Valuation estimate</b><br/><i>median EV/EBITDA of the comps</i>"]
    E["<b>Growth signals</b><br/><i>news / press / careers pages<br/>→ dated events</i>"]
    F["<b>Features at a cutoff date</b><br/><i>only events known by then</i>"]
    G["<b>3-year growth model</b><br/><i>not built yet</i>"]
    A --> B --> C --> D
    A --> E --> F --> G
    C -. "peer-relative features (planned)" .-> F
```

The two tracks share one starting point: a company's name and website. The **valuation track** (left) asks *what does this company look like, and who else looks like it?* The **growth track** (right) asks *what has this company done recently, and when?*

## Project rules

These decide what any method may use. The full list is in [`AGENTS.md`](AGENTS.md).

- **Methods must work for a private company.** For the target that means name and website, plus three figures we may assume a buyer knows: last-twelve-months (LTM) revenue, LTM EBITDA and debt. Investor-relations pages and stock data are never used for the target. *(Updated 2026-10-19 after Aziz's reply. Before that the target was name + website only.)*
- **Public comps may use more**, including 10-K filings and other public detail. Same line of business comes first; similar size is a secondary check.
- **EV/EBITDA is the answer, never an input.** It's the multiple being estimated, so no method may use it to pick comps.
- **Collection is fully programmatic.** Nothing is written by hand. What a source doesn't say is marked unknown, never guessed, and every extracted fact cites its source URL.
- **Every stage's data is kept**: raw pages, cleaned text, model prompts and answers, and final tables. Nothing is overwritten.

---

## The parts in more detail

### 1. Company list (`data-local/snapshots/`, `src/`)

The list has 560 US public companies from Rational AI. They're public, so their real valuation multiples are known, which lets us check estimates. Each one is treated as if it were private.

- Code loads the snapshot named in `data_manifest.json` (currently `company_list_v3`) through `src/project_data.py`, which checks its checksum.
- Fixes to the raw list are made by a script ([`src/prepare_company_list.py`](src/prepare_company_list.py)) that writes a new snapshot. The raw list is never edited by hand. Example: BrightView's industry code (SIC) was stored as `700` and is now `0700`; without the leading zero it had been grouped with hotels.
- Column meanings are in [`docs/data_dictionary.md`](docs/data_dictionary.md); known problems are in [`docs/data_issues.md`](docs/data_issues.md).

### 2. Website scrape (`website_scrape/`), done 2026-10-18

Downloads each company's homepage plus up to two more pages chosen to cover different things (about, products and services, markets served, business model).

- **Getting past difficult sites:** each site is tried with up to four methods, stopping at the first that works: a plain download, a headless browser for JavaScript-heavy sites, a real Chrome browser for sites that block scripts, and finally the Internet Archive's latest snapshot. The site's `robots.txt` crawler rules are always respected.
- **Cleaning:** filters remove financial and size figures, stock tickers, "publicly traded" language, cookie banners and marketing filler. Each removal is logged with its reason, and the raw text is kept next to the cleaned text.
- **Result:** 532 of 560 sites gave usable text; 15 were too thin; 4 redirect to an investor-relations site (refused under the rules above); 9 were blocked or disallowed crawling. The median page has 283 cleaned words.
- Details: [`website_scrape/README.md`](website_scrape/README.md).

### 3. Comparable-company matching (`matching/`), on main since 2026-10-19 04:37

**The question:** if all we had was a company's website, could we find its comps, and would their multiples estimate its own?

**The test:** each of the 535 companies with enough text takes a turn as the "private" target. Its comps are picked from the other 534 using website text only, and its multiple is estimated as the median EV/EBITDA of those comps. Its real multiple is the answer key. That gives 535 tests of each method instead of one.

**Turning text into something comparable.** Each company's text is cut into 200-word pieces, and each piece is run through a sentence-embedding model (`all-mpnet-base-v2`). The model turns text into a list of 768 numbers, and passages with similar meaning get similar numbers. The pieces are averaged into one vector per company. Two companies' similarity is the cosine of their vectors: 1 means they point the same way, 0 means unrelated.

**Three ways to pick comps from those similarities:**

| method | idea in plain terms |
|---|---|
| 1. Similarity cut-off | Take the companies that are *unusually* similar to this target: at least 2 (or 2.5) standard deviations above its average similarity to everyone. The number of comps varies by target. |
| 2. Mutual nearest neighbours | Two companies are comps only if each is in the other's top 10 (or 20). This stops companies with generic websites, which look a little like everyone, from showing up as everyone's comp. A second step groups companies into clusters (UMAP + HDBSCAN) and uses the target's cluster-mates. |
| 3. Similarity tree | Repeatedly merge the closest groups into a tree; the comps are the smallest branch around the target with at least 5 others. No randomness. |

**How methods are judged:** the main benchmark is *no matching at all*, i.e. using the median multiple of every other company. A method only helps if it beats that. Methods are scored on median absolute % error and on Spearman rank correlation (do higher estimates go with higher real multiples?). They're also compared at equal comp counts (3 to 10), on ten hand-picked hard and easy targets, and against SIC industry-code peer groups. All settings are fixed before scoring, never tuned on the answer key.

**What it shows so far:**

- **The text finds real peers.** A company's five nearest neighbours share its 4-digit industry code 14 times as often as chance would. Targets with clear peers get them, e.g. Sterling and Granite for Construction Partners (ROAD), and Baldwin, Gallagher and Ryan for Brown & Brown (BRO).
- **But no method beats no matching on error.** Every method lands at about 35% median error, the same as no matching (34.6%).
- **Method 1 ranks companies best** (Spearman 0.31, against 0.21-0.24 for the other methods and 0.22-0.24 for industry-code groups), and nothing beats it at equal comp counts.
- **Right peers still give wrong values.** Multiples in this list are mostly company-specific: 2-digit industry groups explain only about 17% of the spread, so even good peers miss by 29-43%. The next gains are more likely in *how the estimate is formed* (pulling it toward the overall median, weighting closer comps more, flagging "no good match") than in picking comps.
- **Stricter than the current rules.** The methods were built under the original name + website rule. Since 2026-10-19 the target's revenue, EBITDA and debt may be used to favour similar-size comps, and comps' 10-K detail may be used too. Neither is in the methods yet.

Details, all saved outputs and the changes from Riya's first notebook: [`matching/README.md`](matching/README.md).

### 4. Ten-company research pilot (`notebooks/`, `experiments/`, `reports/`), on main since 2026-10-19 02:17

A separate, self-contained study by Yikai of many alternative ways to rank and value peers, run on ten development companies against a fixed pool of 183 candidates.

- **Scope:** 31 ranking variants (different text representations such as LSA, which groups co-occurring words into topics, and dense embeddings; financial distance; optimal-transport matching; combinations), 279 peer-count and averaging setups, and four direct valuation models. Each method cites the paper or source it comes from.
- **Findings so far:** on nine of the companies with five peers, the LSA representation had a median error of 18.6% against 46.9% for dense embeddings, though that's a small sample and no general winner is claimed. The local language models tried as automatic peer judges weren't reliable enough to approve peers on their own.
- **Reproducible offline:** the notebook replays saved model outputs by default, so it runs without a GPU, model downloads or API keys. Full re-inference is a separate opt-in step.
- **Still pending:** independent human review of the peers (forms are in `reports/whole_company_pilot/review/`), checking financial dates and definitions, and comparison with the latest matching notebooks.
- Start here: [results and charts](reports/whole_company_pilot/README.md) · [notebook](notebooks/whole_company_pilot.ipynb) · [code and reproduction](experiments/whole_company_pilot/README.md) · [handoff](conversations/2026-10-19-whole-company-pilot.md).

### 5. Growth signals (`growth_signals/`), on main since 2026-10-18 20:13

Records *what changed at a company and when*, from its own News, Press, Careers and Jobs pages. This is separate from the website scrape, which describes what a company does.

- **Events tracked:** new contract, customer loss, product launch, market expansion, hiring, layoff, credit improvement, credit stress. Each event records its date (and how exact that date is), source URL, the supporting sentence and a confidence score.
- **Extraction is rule-based for now:** explicit phrases ("will lay off 5% of its workforce", "opened 3 new branches") create events; anything vaguer is skipped and logged. This favours being right over catching everything.
- **No look-ahead:** features are built as of a cutoff date using only events published before it. Using later news would be cheating, since a real forecast can't see the future. Growth outcomes (1, 2 and 3-year revenue growth) come from a separate revenue file and are never filled in from later years.
- **Five-company pilot (2026-10-18):** 24 articles saved, 23 with a clear date, and 7 events that held up under review. See [`growth_signals/sample_evaluation.md`](growth_signals/sample_evaluation.md).
- Details: [`growth_signals/README.md`](growth_signals/README.md).

---

## Work on branches, not yet in `main`

| branch | author | last commit | what's there | state |
|---|---|---|---|---|
| `growth-signals-recall` | Xiaozhe | 2026-10-19 16:26 | Revised growth-signal extractor. Catches more phrasings (noun forms like "the launch of", "N new openings"); rule windows no longer stop at decimals or abbreviations ("$2.2 million", "Inc."); rejects sentences where another company is acting; adds five event types (acquisition, divestiture, funding round, guidance raised, guidance lowered); counts one event per article rather than per sentence; tags pages found only through an investor-relations site. | Not merged; 6 commits ahead of main, 10 behind. On new, unseen companies (held-out C) the rules are right 58-61% of the time and find 43% of true events. An LLM pass is in progress, not yet on the branch. Handoff: `conversations/2026-10-19-growth-signals.md` (also on main). |
| `riya/wip` | Riya | 2026-10-17 17:12 | Scraper v2 (leak filters, company-name masking, all 560 companies) and the first Paylocity comps notebook (TF-IDF, LSA and embeddings, combined). | Superseded but still useful: its ideas seeded matching method 1 and `scraps/comps_first_pass/`. The branch also carries large data folders, so pieces are copied over as code rather than merging the branch. |

Merged into `main` so far:

| when | pull request | what |
|---|---|---|
| 2026-10-18 20:13 | [#1](https://github.com/Qual2Cast/Qual2Cast/pull/1) `growth-signals` | Growth-signal collector, rule extraction, cutoff-safe features |
| 2026-10-18 23:36 | direct commit | Input rules updated after Aziz's reply on 10-Ks and financials |
| 2026-10-19 02:17 | [#2](https://github.com/Qual2Cast/Qual2Cast/pull/2) `research/company-analysis-pipeline` | Ten-company research pilot |
| 2026-10-19 04:37 | [#3](https://github.com/Qual2Cast/Qual2Cast/pull/3) `michael/wip` | Matching methods 1-3 and the evaluation notebook |
| 2026-10-19 04:47 | [#4](https://github.com/Qual2Cast/Qual2Cast/pull/4) `michael/wip` | README rewritten to show what is on main and what is on branches |
| 2026-10-19 16:23 | direct commit | Growth-signals handoffs merged into `conversations/2026-10-19-growth-signals.md` |

Earlier attempts that aren't part of the pipeline (structured profiles written by Codex, the first matching pass, the first collection script) are in [`scraps/`](scraps/README.md), with notes on why each was set aside.

## Next steps

1. **Matching:** change how the estimate is formed (pull it toward the all-company median, weight comps by similarity, add a "no good match" rule), then add size (target revenue, EBITDA and debt against the comps') as a secondary check, which the updated rules now allow.
2. **Growth signals:** fix the decimal-point bug and the listed misses on `growth-signals-recall`, score on a fresh set of unseen articles, then merge.
3. **Checks:** human review of top comps against their source pages, for both the matching notebooks and the pilot.
4. **Growth model:** build the point-in-time revenue and outcome table it needs.
5. **Write-up:** definitions and limitations, then the report.

Day-to-day status and open questions are in [`PROJECT_STATE.md`](PROJECT_STATE.md).

## Terms used here

| term | meaning |
|---|---|
| **Comps** | Comparable public companies: similar business, used as a pricing reference. |
| **EV/EBITDA** | Enterprise value (what the whole business is worth, including debt) divided by earnings before interest, taxes, depreciation and amortization. A standard valuation multiple: a company with EBITDA of $10M at 12× is valued at about $120M. |
| **LTM** | Last twelve months. |
| **SIC code** | A 4-digit government industry code (e.g. 7372 = prepackaged software). Too coarse to pick comps on its own, so it's used here only as a check. |
| **Embedding** | A list of numbers a model produces from text, where similar meaning gives similar numbers. |
| **Cosine similarity** | How closely two embeddings point the same way: 1 = identical direction, 0 = unrelated. |
| **Median absolute % error** | For each company, how far the estimate is from the real multiple as a %; the median across companies. |
| **Spearman correlation** | Whether higher estimates go with higher real values, from −1 to 1, regardless of exact size. |
| **Look-ahead bias** | Accidentally using information from after the forecast date, which makes results look better than they could be in real use. |
| **Precision / recall** | Of the events extracted, the share that are real (precision); of the real events, the share extracted (recall). |

## Repository layout

| path | contents |
|---|---|
| `AGENTS.md`, `CLAUDE.md` | working rules for Codex / Claude Code sessions (and people) |
| `PROJECT_STATE.md` | current decisions, status, open questions, next steps |
| `conversations/` | handoff notes per task: what changed, test results, what's next |
| `docs/` | data dictionary and data-issues log |
| `src/` | shared code: loading the data snapshot, list corrections |
| `data_manifest.json` | which data snapshot the code needs, with checksums |
| `website_scrape/` | collects each company's website text |
| `matching/` | comparable-company matching: methods notebook, evaluation notebook, write-up |
| `growth_signals/` | dated growth events and cutoff-safe features |
| `notebooks/`, `experiments/whole_company_pilot/`, `reports/whole_company_pilot/` | ten-company research pilot: notebook, code, results |
| `scraps/` | earlier attempts kept for reference, not part of the pipeline |
| `data-local/`, `outputs-local/` | data and outputs; only the input snapshots and current website text (`page_text/`) are in Git |

Each part has its own README with setup and run instructions.

## Deliverables

- Reproducible data pipeline and analysis
- Concise technical report
- Presentation of methods, findings, and limitations

## Acknowledgments

Developed under the guidance of Aziz Lookman, founder of Rational AI.
