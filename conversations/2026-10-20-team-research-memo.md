# Team research memo — 20 October 2026

## Completed

- Added a four-page analytical memo in PDF and HTML, using the professor's
  five-section structure and placing individual contributions in an appendix.
- Consolidated Michael's collection/matching/evaluation, Riya's collection and
  peer-label work, Fiona's event extraction and SEC outcomes, Kethan's separate
  SIC experiment, Richard's initial collection, and Eric's integrated workflow.
  Requirements discussion and coordination are distinguished from evaluated code.
- Prepended the same memo and contribution/evidence register to
  `notebooks/team_company_workflow.ipynb`. Retained all technical method
  explanations, citations, code, outputs and figures.
- Compared the default workflow with controls on the same PCTY/WING cases:
  median APE 53.6%, versus no matching 61.1% and unreviewed MPNet 41.9%.
  These two cases were selected by the method; coverage remains 2/10.
- Kept the 535-company historical matching study separate from the 538-company
  integrated evidence policy and from the reused growth-extraction labels.
- Specified a proposed independent 20-target test with frozen candidate pools,
  two human reviewers, explicit endpoints and a decision rule.

## Validation and data

This is an editorial revision, not a new inference run. All 17 original code
cells (including outputs and metadata) match the pre-revision notebook.
Embedded inputs and all eight figures are unchanged. The previously completed
294 tests and notebook execution remain the implementation evidence; no claim
is made that those checks establish financial validity.

The PDF has four pages, each rendered and visually inspected. The compact
table is also available as `memo_comparison.csv`; `memo_evidence.json` records
the memo's sources and numerical comparison scope.

Data remain `company_list_v3`; original matching runs are
`20261019T080322Z` / `20261019T080416Z`. The integrated run is
`20261020T033357Z-f5389a`, with evidence policy
`private-evidence-2026-10-19-v4`. The SIC reference is the separate
`kethan/wip` commit `9c9d77b1edaaa0a6e203a972971ab8f46bb91e7c`.

## Open issues

- New peer-review labels, aligned financial dates/definitions and a genuine
  private-company validation set remain unavailable.
- Historical growth evidence is too shallow; EDGAR anomalies require review.
- Kethan's SIC work is summarized and linked, not claimed as an executed
  integrated arm. Public-comp 10-K enrichment, database crosswalks and WRDS
  Ask AI are extensions, not completed integrations.
- The contribution register attributes only work supported by the reviewed
  project update, group messages and repository records.

## Next action

Review the four-page memo as a team, then freeze the proposed business-review
test before collecting new targets or viewing their valuation outcomes.
The team's original notebooks and shared progress document are unchanged.
