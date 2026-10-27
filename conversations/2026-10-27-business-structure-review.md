# Business-structure pilot — 2026-10-27

Development branch: `research/business-structure`. Source snapshot:
`company_list_v3`. The current v0 universe, facets, peer judgments, and
valuation notebook remain unchanged.

## Deliverables

- `v0/business_split.py`: one company-level split method. It reuses the team's
  P/W evidence collector, accepts reviewed official web pages, saves source
  lines, prompts, raw model responses, business groups, and decision flags.
  Completed exits need dated affirmative evidence. A separate business needs
  different offerings and customer or operating-process evidence; an additional
  broad-group check keeps related products inside one economic business.
  Unproved splits default to one whole-company business and retain source-gap
  flags. No duplicate Capital IQ company IDs are created.
- `v0/notebooks/business_structure_eval.ipynb`: executed 40-company split
  review and paired ten-target v0 peer/valuation test. It includes the old
  split's actual processed count, source challenges, a chart, the teammate's
  available PCTY peer labels, and explicit no-matching fallback results.

## Results

- Split sample: 40 unique companies, 33 one-business and 7 multi-business;
  8 one-business cases have source-gap flags. Ten deliberately chosen source
  challenges have the expected direction. This is a development diagnostic,
  not independent split accuracy. The older F10 grades score different Haiku
  text and are not split ground truth.
- Official pages resolved several historical/current distinctions: AZZ's
  Infrastructure Solutions exit and current metal-coatings scope; AFG's
  completed exits; BBCP's new temporary-power activity; Butler National's
  aerospace products within one broad business and gaming in another.
- Paired downstream test: same ten targets, same v0 candidate sets, base
  prompt, model, and valuation formula. Appending full split scope changed
  10 of 142 candidate judgments. Matched-peer coverage changed from 7/10 to
  4/10. With v0's no-matching median when no peer survives, median absolute
  percentage error changed from 29.21% to 32.10%. On the four targets both
  judges valued from matched peers, medians were 20.91% and 21.74%.
  PCTY's five overlapping prespecified labels show one adjacent firm
  correctly rejected without losing three direct competitors. This narrow
  gain does not justify replacing the v0 peer judge.

Saved run inputs and per-company raw answers are under
`outputs-local/research/business-structure/`. Final CSVs are in its
`evaluation-20261027/` subfolder: `company_decisions.csv`,
`peer_judgments.csv`, and `valuation_comparison.csv`. The source manifest
`web_sources_pilot.json` is local and ignored. No API key was available;
official URLs were researched and selected, then page text was collected
programmatically. Search snippets were not accepted as evidence.

## Validation and next step

The notebook's seven code cells executed with no errors. The 40 IDs are
unique; all nine key-case assertions and both peer-coverage checks passed.
`git diff --check` passed. The result supports using split metadata as a
business-scope audit, while keeping current v0 peer selection for valuation.
Before replacing that rule, collect independent business-split and peer labels
and evaluate once on held-out targets.
