# v1 integration progress — 2026-11-10

- The integration remains local on `research/v1-integration` in `outputs-local/v1-eval-rebuild`. Nothing has been pushed or uploaded.
- The frozen development sample has 533 eligible company IDs, 373 training firms, 160 valuation targets, and 293 Barbara-reviewed peer pairs. The 293 scores are one reviewer's 0–2 labels, not consensus gold.
- The GPT-6.1 Sol general-facet run completed 533 unique B1 profiles under prompt `2026-10-25k`; all 533 calls succeeded, followed by 12 successful website gap-fill calls. `outputs-local/v1/facets_codex_gpt61sol/run.json` records the call count, model and token use.
- Official-site searches added usable lines for all 13 companies whose saved site records had none. Avista's company-information page is on its official investor subdomain; financial and filing paths are excluded. Each fallback page records a URL and retrieval time.
- The original 13 candidate-retrieval rules were run on both corrected Sonnet and GPT general facets. The GPT run retains full rankings, selected peers, 293-pair metrics and 160-target valuation results under `outputs-local/v1/integration/candidate_methods_gpt/`. Four whole-profile methods (MPNet, TF-IDF, LSA, RRF) were then added to the same fixed-pool runner; their full rerun and old-row equality check remain pending.
- Cited-only general facets and Yifan's eleven qualitative fields each passed a two-company call and schema pilot. The cited-only prompt was then tightened to remove the original model-knowledge instruction; the two-company rerun produced 17 filled facets, each with a verified labeled-line citation, and no current prompt retained the removed instruction. Its full run is in progress.
- Fiona sector facets completed on the full fixed universe: 533 unique company rows, all `ok`, all `gpt-6.1-sol` with prompt version `2026-10-27b`. Of 2,472 stated sector field values, 2,282 (92.3%) have a citation label; this is citation coverage, not verified factual accuracy. Four concurrent sector calls briefly exceeded the C-drive activity limit; the resumed two-call run completed without sustained disk pressure. Barbara's SIC2 full extraction is now running alongside the cited-only and Orbis-aligned passes, with four model calls in total.
- The main notebook preserves the team's first 65 cells exactly and appends an ordered integration study. It has not yet been executed against the complete new results. The ordered runner now lists 47 stages. Exact prompt, model and answer-schema fingerprints control new holdout answer reuse; a numerical MPNet cache audit is scheduled before downstream comparisons.
- The v1 script test suite has 184 passing tests and one unchanged assertion that expects `None` where the installed pandas version returns `NaN` for an unknown facet.

Remaining local work: complete SIC2, cited-only and Orbis-aligned extraction; audit reused embeddings; rerun the expanded fixed-pool methods; complete source and scope checks, GPT facet comparisons, source-citing judge, four-route valuation runs, growth extraction, error diagnosis, experiment matrix, notebook execution and manifest. A fresh independent final holdout, actual private-company outcomes and cutoff-valid growth outcomes are not present in the current local datasets.

## Later execution — 2026-11-10

- SIC2 extraction completed: 533 distinct companies, 5,331 field rows, 2,840 stated; every company has exactly its dictionary fields, and all model/prompt versions match.
- The numerical baseline embedding audit re-encoded 26,644 reused texts and two B0 matrices with the installed MPNet on the RTX 5090; maximum vector differences were under 0.0000003 against a 0.00005 tolerance. A full audit including cited-only and Orbis text remains scheduled after their complete tables exist.
- Four whole-profile fixed-pool retrievals (MPNet, TF-IDF, LSA, RRF) were added to each corrected Sonnet and GPT general run. All 13 pre-existing metric and valuation rows in each run reproduced exactly. Each run now has 17 methods; the paired source comparison was updated.
- GPT general plus the five specialized additions and their ablations produced 12 configurations. The base GPT B3 had 33.28% median APE on 160 targets; Fiona categories alone had 33.17% and all additions 35.74%. All paired bootstrap intervals versus base crossed zero.
- A blind ten-company scope check had 24/34 correct activity states and 4/9 exact groups. Only 2/10 cases had a benchmark source page in the saved website input; the result is an evidence-coverage diagnostic and does not replace Yiming's source-corrected scope.
- The 40-company first-pass facet verifier completed 480 checks: 339 supported, 133 not found and 8 contradicted under its model/source rubric. This is not a human-accuracy estimate.
- A complete GPT general four-route 160-target run had zero answer issues. B3 covered 160 at 33.28% median APE; direct LLM covered 127 at 31.99%. On common targets its paired gain against B3 was -0.49 percentage points with a bootstrap interval spanning zero.
- Growth event extraction on ten saved companies: rules 58% precision/43% recall; GPT LLM 57%/90%; hybrid 78%/43%. No cutoff-valid annual revenue outcomes are in the snapshot.
- Source-cited and Orbis-aligned 533-company extraction, Sonnet-content control and GPT all-additions four-route runs remain active. The 293-pair label-blind input is frozen for the source-citing judge. Nothing has been pushed or uploaded.

## Completed local study — 2026-11-10

- The full source-cited and Orbis-aligned passes each cover 533 companies. Every one of 5,188 filled source-cited fields has a matching official-site line. Recomputed MPNet vectors for 40,495 texts and three B0 caches agree with the stored vectors within 2.81e-7, below the 5e-5 tolerance.
- The same 20 fixed-pool retrieval methods were run separately on corrected Sonnet, GPT general, and source-cited GPT facets. The facet ablations, reviewer-calibrated threshold, 144 factor/peer/aggregator combinations, three six-row LLM selection conditions, growth comparison, FF49 regressions, Orbis-aligned fields, expanded pool, and company report are recorded in 400 executed configuration rows. Pairwise intervals for the tested retrieval and facet changes cross zero.
- The label-blind GPT-6.1 Sol judge scored all 293 Barbara-reviewed pairs using source citations and 77 web searches. Exact agreement was 230/293 (78.5%), compared with 83.9% for the saved agent on 292 common pairs. A score-1-or-2 filter retained 186/202 reviewer-good pairs and 30/91 reviewer-bad pairs. On the same 44 reviewed targets, median APE changed from 30.84% to 31.02%; the paired interval crosses zero. The score-2-only filter covers ten reviewed targets and also has an interval crossing zero. These are single-reviewer development diagnostics, not a new holdout.
- The cited-only B3 run covers 159 targets with 33.69% median APE; the memory-first GPT result is 33.41% on the same 159, with a paired uncertainty interval crossing zero. The source-citing approach improves provenance, not measured valuation accuracy in this comparison.
- The main notebook has 101 cells. Its original 65 cells exactly match local HEAD, all 18 appended code cells execute without error, and the ordered study includes charts and the 400-row experiment matrix. A final ranking diagnostic reports labeled-subset precision@3 and nDCG@3 for 20 retrieval rules across each of three facet sources, explicitly excluding ungraded pairs from its denominators. `integration_validate.py` passed all checks; `integration_manifest.py` hashed 2,553 exact files. The suite has 220 passes and one pre-existing pandas `NaN` versus `None` assertion failure. All artifacts remain local; nothing has been pushed or uploaded.
- A new independent final holdout, real private-company valuations, and cutoff-valid growth outcomes remain unavailable in the supplied data. No method has demonstrated private-company accuracy from these development results.

## GitHub handoff — 2026-11-10

- The curated study files were committed as `febe96ab` (`Integrate v1 results`) and pushed to `research/v1-integration`; the remote branch SHA matches. Pull request [#32](https://github.com/Qual2Cast/Qual2Cast/pull/32), titled `v1 integration`, is open against `main` and was not merged here.
- The pushed set contains the executed notebook, integration scripts, 2,553 manifest-listed exact input/output files, supplemental tables, source records and full rankings. Licensed WRDS workbooks, CLI logs, embedding caches, probe logs and temporary tests remain local. The notebook states that a fresh full run requires local WRDS sheets and Codex CLI authentication.

## Plan-to-run correction — 2026-11-10

- The 400-row experiment matrix is a union of stage experiments, not a full facet × retrieval × selector × grading × valuation Cartesian product. Four-route valuation was run for three facet/prompt conditions; the eight financial factor sets use one fixed Sonnet B3 top-ten shortlist. The WhatsApp summary should not describe this as every planned combination.
- GPT business-scope grouping achieved exact agreement on 4/9 groups in ten audited cases, with only two reference pages in the supplied input. Current scope extraction is not validated across all 533 companies. Historical Yiming corrections and their 44 review cases are retained separately.
- The same-input GPT/Haiku/Sonnet model effect is only partially isolated; activity/optimal-transport candidate rules were not rerun on the fixed 533 pool. The expanded Barbara pool has first-pass retrieval results, not the full downstream selection and valuation path.
- The factor/valuation study is a public-snapshot exploratory test. It does not reconcile target EBITDA, period, currency, leases or EV-to-equity for each company, and it has no actual private-company accounts. Event extraction is tested, but cutoff-valid 1–3-year growth prediction is unavailable. The 31-pair dual-reviewer file is absent and the 293-pair cohort is Barbara-only. New sector/size valuation slices were not produced.
- `integration_validate.py` confirms shape, coverage and execution integrity of saved stages; its `passed` result is not a certification that every item in the original integration plan is complete. A clarification was briefly pushed as `450a296e`, but the user requested the original notebook wording be retained. Commit `15459c33` reverted that clarification; the notebook and manifest exactly match `febe96ab`. The gap audit remains in this local progress record, not in the PR's notebook.

## Teammate component completion — 2026-11-10, local only

- Added eleven GPT facet-selection conditions to the existing v1 runner and
  main notebook. Each uses the team's six valuation rows on the same 160
  targets. The total is 14 conditions / 84 route rows; all model runs have
  160 targets and zero answer issues. An exact model, prompt and schema hash
  permits reuse of the unchanged direct LLM answers; all judge calls reran.
- Added Matthew and Richard's saved model comparison, Riya's merged agent
  result, and the team's mixed-business peer sensitivity to the main notebook.
  Fiona's sub-sector/categories and Barbara's SIC2 fields now have addition,
  combined-retrieval and leave-one-out comparisons. The original 65 team
  notebook cells are unchanged. The 39 appended cells contain 20 executed
  code cells, six plots and 71 tables, without errors.
- Ran Xiaozhe's event feature builder for rules, LLM and hybrid on ten saved
  firms (30 rows). Ran the team's SEC annual-revenue collector on the frozen
  560-company snapshot: 515 firms have revenue, 496 have 2022 cutoff labels,
  and 472 are v1 eligible. Eligible 1/2/3-year outcome counts are
  471/468/460. No forecast is fitted because the October 2026 event captures
  postdate the fiscal 2022 prediction cutoff.
- The experiment matrix has 466 executed configurations and the manifest
  hashes 2,734 exact files, including the new candidate rankings, peer lists,
  target errors and run metadata. `integration_validate.py` passed. The 15 targeted
  growth tests passed with a local pytest temp directory; modified scripts
  compiled. The old result versions are preserved in the local history folder.
- GPT general B3 median APE is 33.28% on 160 targets; all-additions retrieval
  is 35.74%, and Fiona categories alone is 33.17%. All 120 paired bootstrap
  intervals include zero. The result is no demonstrated valuation gain from
  these facet changes on this development cohort, even where raw medians
  differ. Coverage varies for LLM selection, so route medians are displayed
  with their denominators and common-target comparisons.

Remaining data and inference limits: Barbara's 293 scores are one reviewer;
the 160 public targets are development data; no actual private outcomes or
fresh final holdout are available; Barbara's expanded catalog has retrieval
results but not aligned multiples across the full pool; and historical event
features cannot be paired with the observed 2022-cutoff growth labels. The
factor-set study is not a full facet × retrieval × selector × factor product.
The merged teammate work is represented in the notebook; unmerged `riya/wip`
is excluded by instruction. Nothing in this extension has been pushed.

## Golden-set correction — 2026-11-10, local only

- Michael asked in WhatsApp to run the new facets and data through v1 and
  compare comp selection with the historical golden set. The 533-company GPT
  general, Fiona sector/sub-sector and Barbara SIC2 fills and the 12 B3 facet
  variants had run earlier, but the retrieval methods and facet variants had
  not been put on one common three-reviewer comparison.
- `integration_reviewed_ranks.py` now verifies the snapshot, split and facet
  source hashes. It evaluates 20 methods on each of corrected Sonnet, GPT
  general and source-cited GPT, plus 12 GPT facet variants. Its 432 rows are
  72 conditions × six separate label cohorts: 32 historical majority pairs,
  11 unanimous pairs, three individual 36-pair reviewers and Barbara's 293
  single-reviewer pairs. Unlabeled pairs are never negatives. Saved
  GPT-general B3 top-ten rankings and selections reproduce the independent
  GPT retrieval B3 result exactly.
- On the 32-pair majority set, corrected Sonnet B3 selects 10/11 labeled
  good peers and 1/21 labeled bad peers; GPT general B3 selects 9/11 and
  1/21; GPT plus Fiona categories selects 9/11 and 0/21. The majority labels
  cover only PCTY and WEN, so no default changes. Exact results are in
  `golden_method_metrics.csv` and `golden_target_metrics.csv`.
- The existing main notebook now has 106 cells: its original 65 are unchanged;
  21 integration code cells executed without errors, with seven plots and 73
  tables. The configuration matrix has 898 rows including the 432 golden
  comparisons. Validation passed, the manifest hashes 2,746 exact files,
  and 25 relevant tests passed with a local pytest temp directory.
- The four-condition partial factorial is archived under
  `outputs-local/v1/integration/history/aborted_factorial_2026-11-10/` and
  excluded from the notebook and conclusions. A full facet × retrieval ×
  selection × factor product and an independent final holdout have not run.
  Nothing was pushed or uploaded.

## Three remaining checks — 2026-11-10, local only

- `integration_retrieval_compatibility.py` confirms 20 common-field methods
  across corrected Sonnet, GPT general and source-cited GPT. Only B3's additive
  interface accepts the five specialized matrices without changing the original
  method. Twelve GPT B3 facet conditions each ran 8 factor sets × 3 peer budgets
  × 6 aggregators; the 1,728 summary rows use the same 160 development targets.
  The parameterized Sonnet control exactly reproduces all 144 saved rows.
- `integration_golden_routes.py` evaluated four selection routes × 12 facet
  conditions × five historical reviewer cohorts (240 rows). The new GPT calls
  hid reviewer grades; direct selection excluded the target from its 372-firm
  pool. On the 32-pair majority set, GPT-general B3 retained 9/11 good and
  1/21 bad, B3→LLM 3/11 and zero bad, and direct/LLM→B3 5/11 and zero bad.
  The shared-union binary screen differs from saved holdout batching.
- `integration_gpt_scope_alignment.py` checked 116 edited fields in 42 firms.
  Its first semantic pass returned 82 aligned, 23 possible outdated and 11
  uncertain; the strict named-business pass flagged four GPT general fields.
  Primary sources show HLTC retained outpatient medical assets after a partial
  sale, and ENSG still operated senior living after Pennant. TKR completed its
  belts sale; SKIL retained customer access to training through partnership.
  Sources: [NHP](https://investors.nhpreit.com/Investors/investor-news/news-details/2026/National-Healthcare-Properties-Announces-Definitive-Agreement-to-Sell-40-Additional-Outpatient-Medical-Facilities-for-531-Million-Signs-LOI-for-Remaining-Four-OMFs-and-Provides-SHOP-Acquisition-Pipeline-Update/default.aspx),
  [Ensign](https://investor.ensigngroup.net/news/news-details/2026/The-Ensign-Group-Adds-New-Operations-in-Colorado/default.aspx),
  [Timken](https://news.timken.com/2026-09-28-Timken-Completes-Sale-of-Belts-Business-to-Gates),
  [Skillsoft](https://investor.skillsoft.com/news-events/press-releases/detail/457/skillsoft-completes-sale-of-global-knowledge-business-advancing-focus-on-ai-native-skills-management-platform).

The eight-field source-cited sensitivity alternative leaves the original
teammate inputs unchanged. Each B3 comparison changes one of 160 peer lists;
majority-gold counts and rounded median APE remain the same. The fresh GPT
four-route sensitivity has zero answer issues. Relative to GPT general, direct
LLM changes from 127 targets/31.99% median APE to 124/31.88%, and LLM→B3 from
127/32.18% to 124/31.54%. Paired gains on the common 124 targets are 0.21 and
0.90 percentage points; both bootstrap intervals include zero.

The notebook has 110 cells, with the first 65 unchanged and all 23 added code
cells executed. The experiment matrix has 2,876 rows and the manifest hashes
2,931 exact local files. Validation records `three_requested_checks_executed:
true`, `scope_exceptions_applied_to_default: false`, and
`full_plan_complete: false`. No push or upload occurred.
