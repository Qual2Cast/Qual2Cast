# Qual2Cast

**Forecasting private-company revenue growth from qualitative signals.**
*Columbia University IEOR Industry Capstone, in partnership with Rational AI (Fall 2026).*

Private companies don't publish audited financials, so it's hard to estimate how fast they'll grow or what they're worth. They do leave a public trail: their own website, press releases, job posts, news. Qual2Cast turns that trail into numbers a model can use, with two aims:

1. **Find comparable public companies ("comps")** for a private company from its website alone, and use the comps' valuation multiples to estimate the private company's value.
2. **Forecast 3-year revenue growth** from dated events such as new contracts, hiring, layoffs, launches and credit trouble.

Every automated step, including any language model, is treated as a system under test: it's scored against known answers, and its errors are counted rather than trusted away.

_README last updated 2026-10-31 to reflect `main` through PR #22 (2026-10-28). Work from before v0 is in `pre-v0/`. Times below are US Eastern (UTC−4)._

**Current method (v0):** the mentor's recipe for comps, in [`v0/`](v0/README.md). Since the pre-v0
matching, v0 has grown from a candidate-and-estimate pipeline into a scored, held-out evaluation
with human labels, source-checked facets, an LLM judge and sector-specific facets (see
[What v0 has now](#what-v0-has-now)). Start with
[`v0/notebooks/comps_and_valuation.ipynb`](v0/notebooks/comps_and_valuation.ipynb), the baseline
and the fixed-holdout comparison, then
[`v0/notebooks/gold_and_holdout_integration.ipynb`](v0/notebooks/gold_and_holdout_integration.ipynb)
for the human-label and holdout report.

**Evaluate the cosine → LLM peers:** continue in
[`v0/notebooks/peer_evaluation.ipynb`](v0/notebooks/peer_evaluation.ipynb).
It grades accepted pairs against saved website passages using Codex CLI or Claude Code CLI.
The matching notebook's final cell exports its input handoff.
[Setup and interpretation](v0/PEER_EVALUATION.md).

**Team report (2026-10-20, before v0):** read the [four-page research memo](pre-v0/reports/team_company_workflow/team_research_memo.pdf)
and [contribution/evidence appendix](pre-v0/reports/team_company_workflow/team_research_appendix.html).
The memo reports the original team experiments alongside the newer integrated
workflow, with matching samples and explicit evaluation limits.

**Integrated workflow (before v0):** start with the [standalone notebook](pre-v0/notebooks/team_company_workflow.ipynb)
or the [results and figures](pre-v0/reports/team_company_workflow/README.md).
The [module guide](pre-v0/pipeline/TEAM_WORKFLOW.md) explains setup, method selection and
integration with the existing website, matching and growth modules. Default execution
replays recorded inference and recomputes downstream results. Business review is
mandatory before financial ranking; independent human validation remains pending.

---

## Where things stand

| part | state on `main` | where |
|---|---|---|
| Company list | **Done.** 560 US public companies, used as stand-ins for private targets. | `data-local/snapshots/`, `data_manifest.json` |
| Website scrape | **Done for all 560.** 532 sites gave usable text. | `website_scrape/` |
| Comps recipe (v0) | **Steps 1-7 built and the fixed holdout scored (2026-10-28).** Universe and EV/EBITDA 3-30 range (533 firms), twelve facets filled by Claude Haiku 5.5, a SIC2-stratified 373 training / 160 holdout split, candidates by facet embeddings, an LLM good/bad judge, an LLM that picks comps directly, the reverse hybrid (LLM then cosine), and estimates against the actual multiples. On the 160 holdout targets the no-matching control has a median error of 39.9% and the routes land at about 33-38% on the targets each can estimate; paired bootstrap intervals do not establish a winner. | `v0/` |
| Human labels and judge checks | **Three reviewers' 0-2 labels on 36 PCTY/WEN pairs** score the four routes separately (only 11/36 pairs are unanimous). A source-cited 0-2 LLM judge is checked against them and runs as an optional peer-selection route on all 160 holdout targets. | `v0/reviewer_gold_eval.py`, `v0/judge_gold_eval.py`, `v0/graded_peer_selection.py`, `v0/golden_set.py` |
| Facet checks | **Facet fills checked against evidence beyond the scrape** (saved pages, deeper site crawl, web search): 24.5% of checkable fills on a 20-company hand check had a problem. Facet add/drop evaluation against peer labels. | `v0/verification/`, `v0/facet_eval.py` |
| Sector sub-models | **Eleven sector groups from Fama-French 49, with sector-specific facets and a sub-sector description**, filled for all 533 firms. On the holdout, cosine median error moves from 37.3% to 35.0% (paired change -1.9 points, interval -3.8 to +0.3); other routes show no clear gain. | `v0/sectors.py`, `v0/sector_facets.py`, `v0/sector_facet_candidates.py` |
| Business-split refinement | **Source-checked grouping of multi-business firms** (40 companies; 8 have several current businesses). Improves the targeted source check but, as an extra prompt context, raised valuation error in the tests, so it is kept as metadata and not adopted as a v0 rule. | `v0/business_split_refinement.py`, `v0/notebooks/business_split_refinement_eval.ipynb` |
| Comparable-company matching | **Three methods built and scored on all 535 usable companies.** Picking comps from website text finds real peers but doesn't yet beat a no-matching estimate on valuation error. | `pre-v0/matching/` |
| Ten-company research pilot | **Frozen comparison** of 31 ways to rank peers, on ten companies. Human review still pending. | `pre-v0/notebooks/`, `pre-v0/experiments/`, `pre-v0/reports/` |
| Integrated team workflow | **Staged company workflow and team memo** (Yikai, on main 2026-10-20). | `pre-v0/pipeline/`, `pre-v0/valuation/`, `pre-v0/notebooks/team_company_workflow.ipynb`, `pre-v0/reports/team_company_workflow/` |
| Growth signals | **Revised 13-type extraction and SEC revenue outcomes integrated.** Rules/LLM/agreement comparison is exploratory; historical coverage and label review remain incomplete. | `pre-v0/growth_signals/`, `pre-v0/reports/team_company_workflow/` |
| Growth forecasting model | **Not started.** Needs past revenue for the outcome and point-in-time event history. | n/a |
| Report, definitions and limitations | **Four-page team memo complete (2026-10-20, before v0).** Detailed contributions, sources and reproducible workflow are in the appendix and notebook. | `pre-v0/reports/team_company_workflow/`, `pre-v0/notebooks/team_company_workflow.ipynb` |

## What v0 has now

The pre-v0 matching ended with "right peers still give wrong values". v0 replaced it with the mentor's recipe and then added the pieces needed to test it properly. Everything below is on `main` (PRs #8-#22). Each item has its own entry in [`v0/README.md`](v0/README.md).

**The recipe and baseline** (Michael, [#8](https://github.com/Qual2Cast/Qual2Cast/pull/8), [#11](https://github.com/Qual2Cast/Qual2Cast/pull/11), [#15](https://github.com/Qual2Cast/Qual2Cast/pull/15))
- 533-firm universe, twelve LLM-filled facets (no financial figures, no guessing from the name, saved pages fill gaps only), embeddings, a 373/160 SIC2-stratified training/holdout split, and the EV/EBITDA estimate. The SIC2 notebook is the updated baseline; the earlier size-stratified one is kept in `v0/notebooks/history/`.
- Facet and company-size analysis: company size (F9) and geography (F8) are the weakest facets.

**Four matching routes** (Yikai, [#12](https://github.com/Qual2Cast/Qual2Cast/pull/12), [#13](https://github.com/Qual2Cast/Qual2Cast/pull/13))
- Cosine z ≥ 2, cosine → LLM judge, direct LLM, and LLM → cosine, each named and compared against the no-matching control.

**Golden set and human labels** (Michael [#16](https://github.com/Qual2Cast/Qual2Cast/pull/16)/[#17](https://github.com/Qual2Cast/Qual2Cast/pull/17); Yikai [#19](https://github.com/Qual2Cast/Qual2Cast/pull/19))
- The 36 PCTY/WEN pairs pooled from the four routes, labeled blind by Riya, Barbara and Matthew, scored with precision@10, direct hits@10 and NDCG@10 per reviewer without forcing a consensus.
- Holdout evaluation: all four routes run on the 160 holdout targets against the training pool, with a bootstrap for paired differences. The LLM calls in the holdout use `gpt-6.1-sol` in batches, so compare routes within the holdout, not against the original Haiku training run.

**LLM as judge** (Kethan, direct commit `c2977824` on 2026-10-27; Yikai [#20](https://github.com/Qual2Cast/Qual2Cast/pull/20), [#21](https://github.com/Qual2Cast/Qual2Cast/pull/21))
- `peer_evaluation.py` grades accepted peers against saved website passages, with citations required from both companies, through Codex CLI or Claude Code CLI (`cli_models.py`). `judge_gold_eval.py` checks the shared 0-2 rubric's grades against the three reviewers on the 36 pairs.
- The same 0-2 rubric (`graded_peer_selection.py`) also works as an optional peer-selection route: it improves coverage over the binary judge (155/160 vs 110/160 targets) with no established error advantage over cosine.

**Facet verification** (Yiming, [#9](https://github.com/Qual2Cast/Qual2Cast/pull/9))
- `v0/verification/` collects evidence beyond the scrape: saved pages, a deeper crawl of the company's own site, and web search (Serper, Brave or Tavily). Every line is labeled with its source, investor-relations and market-data sources are dropped, and a stand-in verifier scores facet fills as supported, partly, contradicted, missed or not found, citing the lines. It also refills facets from pages alone with the company name masked, to see how a private company the model doesn't know would look.

**Sector sub-models and facet evaluation** (Fiona, [#18](https://github.com/Qual2Cast/Qual2Cast/pull/18); integrated by Yikai in [#22](https://github.com/Qual2Cast/Qual2Cast/pull/22))
- Fama-French 49 sector groups, sub-sector text and sector-specific facets, filled evidence-first from saved pages. `facet_eval.py` scores facet removals and sector additions against the reviewers' labels.

**Business structure** (Yikai, [#14](https://github.com/Qual2Cast/Qual2Cast/pull/14) and the 2026-10-28 refinement)
- Source-checked grouping of each firm's current businesses, with corrected activity status (a targeted primary-source check improves from 27/34 to 34/34 activity labels). Not adopted as a peer rule.

**Not in `main` yet** (open on branches, see below): the retrieval (RAG) step for facet verification, and the one-notebook pipeline refactor.

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

### 3. Comparable-company matching (`pre-v0/matching/`), on main since 2026-10-19 04:37

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

Details, all saved outputs and the changes from Riya's first notebook: [`pre-v0/matching/README.md`](pre-v0/matching/README.md).

### 4. Ten-company research pilot (`pre-v0/notebooks/`, `pre-v0/experiments/`, `pre-v0/reports/`), on main since 2026-10-19 02:17

A separate, self-contained study by Yikai of many alternative ways to rank and value peers, run on ten development companies against a fixed pool of 183 candidates.

- **Scope:** 31 ranking variants (different text representations such as LSA, which groups co-occurring words into topics, and dense embeddings; financial distance; optimal-transport matching; combinations), 279 peer-count and averaging setups, and four direct valuation models. Each method cites the paper or source it comes from.
- **Findings so far:** on nine of the companies with five peers, the LSA representation had a median error of 18.6% against 46.9% for dense embeddings, though that's a small sample and no general winner is claimed. The local language models tried as automatic peer judges weren't reliable enough to approve peers on their own.
- **Reproducible offline:** the notebook replays saved model outputs by default, so it runs without a GPU, model downloads or API keys. Full re-inference is a separate opt-in step.
- **Still pending:** independent human review of the peers (forms are in `pre-v0/reports/whole_company_pilot/review/`), checking financial dates and definitions, and comparison with the latest matching notebooks.
- Start here: [results and charts](pre-v0/reports/whole_company_pilot/README.md) · [notebook](pre-v0/notebooks/whole_company_pilot.ipynb) · [code and reproduction](pre-v0/experiments/whole_company_pilot/README.md) · [handoff](conversations/2026-10-19-whole-company-pilot.md).

### 5. Growth signals (`pre-v0/growth_signals/`), on main since 2026-10-18 20:13

Records *what changed at a company and when*, from its own News, Press, Careers and Jobs pages. This is separate from the website scrape, which describes what a company does.

- **Events tracked:** new contract, customer loss, product launch, market expansion, hiring, layoff, credit improvement, credit stress. Each event records its date (and how exact that date is), source URL, the supporting sentence and a confidence score.
- **Extraction is rule-based for now:** explicit phrases ("will lay off 5% of its workforce", "opened 3 new branches") create events; anything vaguer is skipped and logged. This favours being right over catching everything.
- **No look-ahead:** features are built as of a cutoff date using only events published before it. Using later news would be cheating, since a real forecast can't see the future. Growth outcomes (1, 2 and 3-year revenue growth) come from a separate revenue file and are never filled in from later years.
- **Five-company pilot (2026-10-18):** 24 articles saved, 23 with a clear date, and 7 events that held up under review. See [`pre-v0/growth_signals/sample_evaluation.md`](pre-v0/growth_signals/sample_evaluation.md).
- Details: [`pre-v0/growth_signals/README.md`](pre-v0/growth_signals/README.md).

---

## Work on branches, not yet in `main`

Checked against `origin/main` on 2026-10-31. Every other remote branch is fully merged, including `growth-signals-recall` (its revised extractor is now under `pre-v0/growth_signals/`).

| branch | author | last commit | what's there | state |
|---|---|---|---|---|
| `verification/gold-labels` | Yifan / Richard | 2026-10-27 23:32 | **The retrieval (RAG) step for facet verification.** `retrieve.py` picks, for each facet, the k evidence lines most related to it (BM25 by default, or hybrid with the same embedding model as `candidates.py`, using the facet name, the filled value and words that tend to settle it such as *sold* or *divested*), and the verifier judges against those lines as new tier `R`, so `R` against `PWS` measures what retrieval adds. `gold_from_labels.py` turns the team's 40-company, 480-facet label sheet into a gold file the scorer reads, and the verifier's "partly" rule is aligned with those labels. Two new test files, about 650 added lines. | One commit ahead of `main`; not merged. Builds on `v0/verification/` already on `main`; running it needs the evidence crawl and a search API key. |
| `kethan/wip` | Kethan | 2026-10-27 | One-notebook pipeline refactor: `pipeline.ipynb` and `v0/pipeline.py` run the v0 steps behind Codex or Claude CLI backends, with `requirements.txt` and tests. | One commit ahead of `main`. It is built on the earlier size-stratified split, not the SIC2 baseline, so it needs rebasing before it can replace anything. |
| `riya/wip` | Riya | 2026-10-17 17:12 | Scraper v2 (leak filters, company-name masking, all 560 companies) and the first Paylocity comps notebook (TF-IDF, LSA and embeddings, combined). | Superseded but still useful: its ideas seeded matching method 1 and `pre-v0/scraps/comps_first_pass/`. The branch also carries large data folders, so pieces are copied over as code rather than merging the branch. |

Merged into `main` so far:

| when | pull request | what |
|---|---|---|
| 2026-10-18 20:13 | [#1](https://github.com/Qual2Cast/Qual2Cast/pull/1) `growth-signals` | Growth-signal collector, rule extraction, cutoff-safe features |
| 2026-10-18 23:36 | direct commit | Input rules updated after Aziz's reply on 10-Ks and financials |
| 2026-10-19 02:17 | [#2](https://github.com/Qual2Cast/Qual2Cast/pull/2) `research/company-analysis-pipeline` | Ten-company research pilot |
| 2026-10-19 04:37 | [#3](https://github.com/Qual2Cast/Qual2Cast/pull/3) `michael/wip` | Matching methods 1-3 and the evaluation notebook |
| 2026-10-19 04:47 | [#4](https://github.com/Qual2Cast/Qual2Cast/pull/4) `michael/wip` | README rewritten to show what is on main and what is on branches |
| 2026-10-19 16:23 | direct commit | Growth-signals handoffs merged into `conversations/2026-10-19-growth-signals.md` |
| 2026-10-19 19:46 | [#5](https://github.com/Qual2Cast/Qual2Cast/pull/5) `research/company-analysis-pipeline` | Integrated company analysis pipeline |
| 2026-10-20 00:23 | [#6](https://github.com/Qual2Cast/Qual2Cast/pull/6) `research/company-analysis-pipeline` | Staged company workflow, growth-signal methods and SEC revenue outcomes |
| 2026-10-20 11:46 | [#7](https://github.com/Qual2Cast/Qual2Cast/pull/7) `research/company-analysis-pipeline` | Consolidated team research memo |
| 2026-10-25 | [#8](https://github.com/Qual2Cast/Qual2Cast/pull/8) `michael/wip` | v0 comps recipe (steps 1-7); earlier work moved into `pre-v0/` |
| 2026-10-26 | [#9](https://github.com/Qual2Cast/Qual2Cast/pull/9) `yiming/facet-evidence-verification` | Pages-only facet extraction and evidence collection for facet verification |
| 2026-10-27 | [#11](https://github.com/Qual2Cast/Qual2Cast/pull/11) `michael/wip` | v0 comps outputs shared (split, facets, judge, candidates) |
| 2026-10-27 | [#12](https://github.com/Qual2Cast/Qual2Cast/pull/12), [#13](https://github.com/Qual2Cast/Qual2Cast/pull/13) | The reverse hybrid (LLM then cosine); all four routes named |
| 2026-10-27 | [#14](https://github.com/Qual2Cast/Qual2Cast/pull/14) `research/business-structure` | Business structure split evaluation |
| 2026-10-27 | [#15](https://github.com/Qual2Cast/Qual2Cast/pull/15) `michael/wip` | Updated baseline: SIC2 split, pilot-target showcase set, facet and company-size analysis |
| 2026-10-27 | direct commit | Source-cited LLM peer evaluation (`peer_evaluation.py`, `cli_models.py`; Kethan) |
| 2026-10-27 | [#16](https://github.com/Qual2Cast/Qual2Cast/pull/16), [#17](https://github.com/Qual2Cast/Qual2Cast/pull/17) `michael/wip` | Golden-set notebook: pool to label for PCTY and WEN, label checks, metrics |
| 2026-10-27 | [#18](https://github.com/Qual2Cast/Qual2Cast/pull/18) `fiona/sector-submodels` | FF49 sector sub-models, sector facets and facet add/drop evaluation |
| 2026-10-28 | [#19](https://github.com/Qual2Cast/Qual2Cast/pull/19) `research/gold-label-split-evaluation` | Reviewer-label evaluation, business-split refinement, full 160-target holdout |
| 2026-10-28 | [#20](https://github.com/Qual2Cast/Qual2Cast/pull/20), [#21](https://github.com/Qual2Cast/Qual2Cast/pull/21) | 0-2 LLM judge in v0; graded judge routes in the main notebook |
| 2026-10-30 | [#22](https://github.com/Qual2Cast/Qual2Cast/pull/22) `research/v0-sector-facets-integration` | Sector facets integrated into v0 and the main notebook |

Earlier attempts that aren't part of the pipeline (structured profiles written by Codex, the first matching pass, the first collection script) are in [`pre-v0/scraps/`](pre-v0/scraps/README.md), with notes on why each was set aside.

## Next steps

1. **Merge the open branches:** bring in `verification/gold-labels` (retrieval tier `R`), run it on the 40 labelled companies, and decide whether `kethan/wip`'s pipeline refactor is rebased onto the SIC2 baseline or dropped.
2. **Independent holdout labels:** the 36 PCTY/WEN labels cover only two targets. Get peer labels for more holdout targets before adopting the sector facets or the graded judge as the default.
3. **Estimate formation:** every route still lands within a few points of no matching. Test pulling the estimate toward the all-company median, size as a secondary check, and a "no good match" rule.
4. **Facet quality:** act on the verification findings (sold businesses, weak geography and size facets) and agree the 20-company and 40-company label sets before trusting the scores.
5. **Growth model:** build the point-in-time revenue and outcome table it needs.
6. **Write-up:** definitions and limitations, then the report.

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
| `v0/` | **v0:** comparable-company selection following the mentor's recipe (universe, multiple range, facets, split, candidates, LLM comp steps, valuation), plus the evaluation layer: golden set and reviewer labels, LLM judge, holdout evaluation, sector facets, business-split refinement. Modules (`.py`) at the top; pipeline notebooks in `v0/notebooks/` |
| `v0/verification/` | facet verification: evidence collection (saved pages, deeper crawl, web search), a stand-in verifier scored against hand labels, pages-only refills |
| `data-local/`, `outputs-local/` | data and outputs; only the input snapshots and current website text (`page_text/`) are in Git |
| `pre-v0/` | work from before v0 (before 2026-10-21), kept for reference and still runnable; see [`pre-v0/README.md`](pre-v0/README.md) |
| `pre-v0/matching/` | comparable-company matching: methods notebook, evaluation notebook, write-up |
| `pre-v0/growth_signals/` | dated growth events and cutoff-safe features |
| `pre-v0/notebooks/`, `pre-v0/experiments/whole_company_pilot/`, `pre-v0/reports/whole_company_pilot/` | ten-company research pilot: notebook, code, results |
| `pre-v0/pipeline/`, `pre-v0/valuation/`, `pre-v0/experiments/integrated_company_analysis/`, `pre-v0/reports/team_company_workflow/`, `pre-v0/reports/integrated_company_analysis/` | integrated team workflow and memo (on main 2026-10-19/20, moved with the rest of pre-v0) |
| `pre-v0/scraps/` | earlier attempts set aside before the pre-v0 work above |

Each part has its own README with setup and run instructions.

## Deliverables

- Reproducible data pipeline and analysis
- Concise technical report
- Presentation of methods, findings, and limitations

## Acknowledgments

Developed under the guidance of Aziz Lookman, founder of Rational AI.
