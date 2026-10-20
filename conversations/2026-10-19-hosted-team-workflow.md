# Handoff: integrated company workflow

19 October 2026. Entry point: `notebooks/team_company_workflow.ipynb`.
Module guide: `pipeline/TEAM_WORKFLOW.md`. Tables and figures:
`reports/team_company_workflow/`. Earlier team notebooks are preserved.

## Implementation and provenance

`TeamPipeline`, `PipelineConfig` and stage registries integrate website collection,
matching, business review, permitted financial factors, growth extraction, EBITDA,
valuation and evaluation. The growth collector, rule extractor, labels and EDGAR
utility come from Xiaozhe's `growth-signals-recall` at `793cf63`; integration adds
package imports and the workflow/LLM adapters. Existing matching methods remain
available alongside TF-IDF, LSA and rank fusion.

The source is `company_list_v3`, SHA-256
`3ab9a43e7426c1f41a77055a6d3ca9553845cb3046a954e28dc5c2a82c934eae`.
Evidence policy `private-evidence-2026-10-19-v4` retains 538 companies. Explicit
target inputs are name/website and optional sourced revenue, EBITDA and debt.
Target multiples enter evaluation after prediction. Whole observed business
compatibility is required before scale ranking. Unknown companies require new
collection and identity alignment; public-comp 10-K enrichment is not implemented.

## Results

The fixed development experiment contains nine retrievers, direct/staged business
review, eight factor subsets and four aggregators, plus RRF few-shot/RAG/saved-review
arms: 672 configurations and 6,720 rows across ten previously inspected targets.
The shortlist is five and selected-peer maximum three. There are 324 source-checked
model pair judgments; verified quotations and hashes do not establish correctness.
The default RRF/staged/business-only/median route estimates 2/10 targets: PCTY
APE 22.9%, WING 84.4%. No independent method winner is established.

The progressive application preserves all 537 other candidates and reviews in
rank order until ten qualify, the corpus ends or the review budget is reached.
PCTY reviewed 50 and accepted PAYC, ASUR and ADP; 487 remain unreviewed. This is
separate from the fixed-budget comparison. Independent human queues remain blank.

On reused single-annotator growth labels, rules/LLM/intersection precision is
0.581/0.567/0.818 and recall 0.429/0.905/0.429. These are development results.
Event taxonomy and listing-page errors require adjudication; no growth forecast
or valuation premium is validated. The isolated public BrightView accounting case
checks EBITDA/LTM arithmetic without supplying private-target financial inputs.

## Validation and next work

294 tests passed. A fresh-directory notebook execution completed 17 code cells,
zero errors and eight figures, reproducing every reference configuration output.
Offline replay uses exact recorded responses from the authenticated CLI, requested
model `gpt-6.1-sol`, medium reasoning. Fresh calls require each user's own account
and are not guaranteed identical. No fine-tuning was performed.

Next: independently label peer relevance, freeze methods before testing untouched
companies, align financial periods/definitions, expand public-comp business
evidence, and extend dated event history before fitting growth outcomes.
Current estimates are development proxies, not verified private-company fair values.
