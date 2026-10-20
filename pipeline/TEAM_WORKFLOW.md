# Integrated company workflow

`TeamPipeline` joins the existing website, matching and growth-signal modules. It uses one input contract and saves every stage's result and evaluation. The notebook follows the execution sequence: sample, evidence, profiles, matching, business review, financial factors, growth evidence, EBITDA, valuation and final evaluation.

The notebook opens with a five-part analytical memo and a team contribution
appendix. Start with the [four-page memo](../reports/team_company_workflow/team_research_memo.pdf)
for the financial question and findings, then use the technical appendix for
the sequential implementation. The original code and recorded results are unchanged.

## Setup and reproduction

Use Python 3.12+ in a virtual environment for the recorded dependency versions.
Validation used Python 3.12.14. From the repository root:

```bash
python -m pip install -r pipeline/requirements-replay.txt
python experiments/integrated_company_analysis/extract_bundle.py notebooks/team_company_workflow.ipynb outputs-local/team-workflow
python -m pipeline.rank_targets --bundle outputs-local/team-workflow/bundle --output outputs-local/ranked-search --targets PCTY --review-limit 50 --simulate-financials
```

The extraction directory must be new or empty. The command above uses the repository's
current Python modules with the notebook's frozen data and inference cache. Open the
notebook and run cells in order for the complete report and comparison; its standalone
execution uses the embedded frozen modules. Repository edits therefore affect CLI
runs, while changing a notebook's frozen implementation requires rebuilding its bundle.
No model download or fresh inference occurs by default.

Results and figures are summarized in [the report index](../reports/team_company_workflow/README.md).
The growth collector, rule extractor and evaluation records are integrated from
`growth-signals-recall` at `793cf63`; existing team matching notebooks are preserved.

## Application interface

```python
from pipeline.team import TeamPipeline
from pipeline.stages import PipelineConfig

pipeline = TeamPipeline.from_bundle("outputs-local/team-bundle", live_llm=False)
config = PipelineConfig(
    profile_method="llm",
    matching_method="rrf",
    business_review_method="llm_staged",
    factor_method="business_only",
    valuation_method="median",
    llm_provider="cli",
    llm_model="gpt-6.1-sol",
    llm_revision=None,
    peer_search_policy="progressive",
    review_limit=50,
    peers=10,
)
report = pipeline.run("company name or website", config, financial_inputs=None)
pipeline.close()
```

The name or website must resolve within the prepared corpus. New companies first require collection, identity alignment and rebuilt representations. `financial_inputs=None` means unavailable financials, not a public-data fallback. Supply revenue, EBITDA and debt only with source metadata. `sponsor_simulation` is an explicit public-as-private development adapter.

## Stage interfaces

| Stage | Interface | Main choices |
|---|---|---|
| Target sample | `pipeline.sampling.run` | Team pilot; seeded random sample |
| Collection | `pipeline.collection.run` | Cached; robots-aware live HTTP |
| Profiles and business review | `BusinessReview` | Sentence evidence; direct, staged, few-shot, RAG; saved review; independent human |
| Candidates | `pipeline.matching.run` | MPNet, TF-IDF, LSA, RRF, z threshold, mutual neighbors, clusters, two trees |
| Factors | `pipeline.factors.run` | Business-only; seven revenue/margin/debt-ratio subsets |
| Growth signals | `GrowthStage.run` | Team rules; LLM; article/type agreement |
| Measurement | `pipeline.measurement.run` | NI bridge; four quarters; FY plus YTD; reviewed adjustments |
| Valuation | `pipeline.valuation.run` | Median; harmonic; geometric; rank-weighted |
| Evaluation | `pipeline.evaluation.run` | Valuation error/coverage; independently labeled ranking; event extraction |

Register a new candidate function with `pipeline.matching.register(name, function, description, source)`. It must return the candidate schema in `matching/retrieval.py`. All custom retrievers still pass through mandatory business review before financial reranking. Factor and valuation stages expose the same registration pattern. Method procedures, sources and limitations are in `pipeline/catalog.py`.

## Model execution

`local` uses an already cached Hugging Face model; `openai` uses an explicitly configured API key and model; `cli` uses the installed official CLI's normal login. Credentials are never read from files or bundled. Fresh calls require `live_llm=True`. The CLI receives only the assembled source evidence and schema, with optional tools disabled and tool-use events rejected. Evidence sent for analysis reaches the model service even though the database remains local.

CLI inference uses medium reasoning effort and the requested model alias. Exact model responses are cached by request; a future fresh call is not guaranteed bit-for-bit reproducible. The CLI does not enforce the local backend's output-token budget. These differences must be reported in model comparisons.

```bash
python -m pipeline.infer --bundle outputs-local/team-bundle --output outputs-local/inference --provider cli --model gpt-6.1-sol --workers 2
python -m pipeline.compare --bundle outputs-local/team-bundle --output outputs-local/comparisons --provider cli --model gpt-6.1-sol --growth-root growth_signals/eval/2026-10-19
```

Each teammate uses their own login and allowance. No shared token or separate account credential belongs in Git. [Official non-interactive interface](https://learn.chatgpt.com/docs/non-interactive-mode).

## Interpretation

Business compatibility is judged on function, operating role, customer use and the full observed scope. Three positive, approved public-peer multiples are required by the demonstration configuration. Public target outcomes are read only after prediction. Date/definition gaps limit valuation to a development proxy; equity value is withheld.

The team ten are development cases. Growth holdout C was inspected during prompt development and is consequently a development comparison for the added model. Independent human labels remain blank. Fine-tuning is documented as a future option, not a completed experiment. Source hashes and reproducible arithmetic establish traceability, not economic validity.

## Independent review

Complete `independent_human_review.csv` without seeing model verdicts or valuation errors. Preserve the supplied source hashes; record the four criteria, exact quotations, scope differences, reviewer and date. Grades are 0 (incompatible), 1 (partial overlap), 2 (plausible comparable) and 3 (strong comparable). Leave unjudgeable cases blank. `pipeline.import_human_reviews(path)` validates source ownership, quotations and the complete observed scope before importing completed rows. Any malformed completed row prevents the import; blank rows never count as approval. A reviewer name records an attestation and does not independently establish reviewer independence.

The application preserves the full ranked candidate pool and reviews down the list until ten pass. The Paylocity execution has a cumulative 50-candidate review budget. A larger `review_limit` resumes using cached responses; `None` continues until ten qualify or the corpus is exhausted. Unreviewed, incompatible and insufficient-evidence candidates remain distinct. The list never relaxes business criteria to reach ten. Fewer than three approved peers with valid multiples produce a valuation abstention.

The separate ten-target method experiment shortlists up to five candidates and selects three eligible peers. This fixed-budget design permits financial reranking to alter a selected subset when more than three candidates qualify. Its results do not evaluate the expanded ten-peer search policy. Selecting every approved candidate leaves unweighted aggregators insensitive to factor ordering.

The field/source/target-or-peer register is `pipeline/field_selection.py`. Public-comp 10-K enrichment and cross-vendor entity alignment remain future inputs, not completed data integrations.

```bash
python -m pipeline.rank_targets --bundle outputs-local/team-bundle --output outputs-local/ranked-search --targets PCTY --review-limit 50 --simulate-financials
```

The command defaults to cached replay. Add `--live` for new model calls; `--simulate-financials` explicitly supplies the public development target's permitted financials. Without that flag no target financials are inferred.
