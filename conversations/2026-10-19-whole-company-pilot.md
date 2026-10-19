# Handoff: ten-company comparability and valuation pilot

## Contribution

Adds a frozen research notebook, inspectable implementation, results and review forms. Existing website collection, growth extraction, matching branches and authoritative input files are not changed.

- Start with [results and charts](../reports/whole_company_pilot/README.md).
- Open the [notebook](../notebooks/whole_company_pilot.ipynb) for method definitions, citations, code, results and interpretations together.
- Use [implementation and reproduction instructions](../experiments/whole_company_pilot/README.md) to run the saved analysis or inspect the separate modules.

The comparison contains 31 ranking variants, 279 compatible fixed-k/aggregation configurations and four direct valuation configurations. It includes text representations, whole-business activity profiles, financial-factor ablations, balanced/unbalanced transport, rank fusion and local LLM diagnostics. It builds on the team's existing representation baselines; Michael previously suggested unbalanced transport.

## Data and interpretation

The input is the approved `company_list_v3` snapshot and archived website text from the frozen team source. Snapshot checksums, source/model identifiers and experiment lineage are embedded in the notebook. Ten targets span SIC 7370 and 2834. The eligible source universe is 534; the common experimental candidate pool is 183, selected partly through constituent retrievers. All ten targets are development cases. The non-PCTY summary is not an independent holdout.

Under the revised sponsor permissions in `PROJECT_STATE.md`, supplied revenue, EBITDA and debt-derived factors are evaluated separately from website representations. Target EV/EBITDA is excluded from matching features. Financial-only and SIC-only methods are comparison controls, not automatic proof of same-business comparability. Public-comp filing enrichment is not implemented in this frozen comparison. Earlier broad bans in the agent instructions/data dictionary should not be interpreted as newer sponsor statements.

At k=5 with median aggregation, LSA has lower median snapshot error than the frozen dense baseline on nine non-PCTY cases (18.56% versus 46.87%): four improve, three tie and two worsen. Some factor/transport arms improve median error while worsening mean or individual-company errors. The current local LLM protocols do not approve peers. Source support alone does not establish complete business coverage or economic exposure. No general winner is claimed.

## Verification

The exact notebook SHA256 is `777f5d538bbc931fa117ed6cf7447656c8958941e450a068994146ef8bc4b23b`.

- Previously executed offline from an empty directory: 79 code cells, four figures, no execution errors, network attempts or external companion reads/writes.
- The preparation check reverified all 31 method cards and ten-company result tables, 89 packaged file hashes, 1,994 unchanged original payload members and 56 packaged implementation files. Five embedded files have wording-only changes to attribution labels or branch instructions; model logic, source observations and numerical results are unchanged.
- The published notebook passed offline replay after the wording changes: all 79 code cells executed, four figures, zero errors. Packaged checks passed: 114 tests and 19 subtests, with two Matplotlib deprecation warnings. These are implementation/reproduction checks, not validation of independent business relevance.
- Exact package bytes are protected from Git line-ending conversion by scoped `.gitattributes` rules. The replay used two numerical-library threads and a cooperative resource monitor; peak sampled C: activity was 14.33%. No models were retrained.

## Team alignment and remaining work

This contribution is independent of the unmerged `michael/wip` notebook. Michael's current notebook uses 535 eligible companies and per-target cosine z thresholds of 2 and 2.5, plus a no-matching universe-median valuation baseline. Those conditions are not the same as this pilot's fixed-k comparison. Harmonize eligibility, candidate sets and selection rules before comparing performance.

Growth tests use pinned team code `41aa0078acde16afbc66a1ddea238c29a742b1fc`: five official article attempts, two usable sources and one extracted event. They do not establish extraction precision/recall or forecast accuracy. The newer `growth-signals-recall` schema v2 has not been retested here. Historical revenue and feature vintages remain absent. The team outcome builder already supplies both cumulative growth and CAGR; choose the intended column explicitly.

Independent human peer review, aligned valuation dates/currency/definitions and unused-company evaluation are still needed. Strict aligned valuation indications remain withheld; displayed errors use the supplied financial snapshot as a diagnostic.

## Next recommended action

Review the useful method families and representative failed matches, agree on a common comparison setup, then evaluate a frozen shortlist on new companies. Reuse the notebook as an independent experiment entry point or connect selected modules through shared input/output contracts. No existing team entry point needs to be replaced.
