# Five-company growth-signals pilot

Run date: 2026-10-18

This pilot tests collection and high-precision rule extraction. A zero means
no supported event was extracted from the pages collected; it does not mean
the company had no growth events.

| ticker | sector example | collection | articles saved | dated articles | accepted events | review outcome |
|---|---|---:|---:|---:|---:|---|
| PCTY | HCM software | ok | 9 | 9 | 1 | Supported product launch; eight abstentions |
| BV | landscape services | ok | 3 | 2 | 0 | Three abstentions; one article date unknown |
| HRI | equipment rental | ok | 0 | 0 | 0 | News listing found, but no specific articles discovered |
| PRGS | infrastructure software | ok | 3 | 3 | 2 | Two supported product releases; acquisition article abstained |
| WING | restaurants | ok | 0 | 0 | 0 | Careers found; no News/Press entry discovered from homepage |

## Aggregate checks

- 5/5 homepages and at least one event-related page were collected.
- 3/5 companies yielded specific articles.
- 15 articles were saved; 14 had an explicit publication date.
- Three events survived rule extraction and manual evidence review.
- Every non-match is retained in the audit as an abstention.

## Defects exposed and fixed

1. `reducing repetitive data entry ... for employees` was initially matched
   as a layoff. Layoff rules now require the reduction action to directly
   modify workforce, employees, roles, positions, or jobs.
2. `announced it completed its acquisition ... data platform` was initially
   matched as a product launch. Announcement rules now require a product
   release or explicitly new capability/object.
3. Direct press-release links were initially treated as listing pages. They
   are now article records and receive the same evidence audit.
4. Dates such as `Sept. 30, 2026` and `Oct. 01, 2026` are now parsed from the
   top article blocks when standard metadata is absent.

## Remaining coverage gaps

- HRI uses an investor-relations news listing structure that the current
  article-link patterns do not yet traverse.
- WING exposes no News/Press link from its homepage; sitemap or a documented
  same-site discovery fallback is needed.
- Careers landing pages are collected but do not yet follow third-party job
  boards. Those sources require an allow-list and attribution policy.
- The rule extractor is intentionally low-recall. It is candidate generation
  for human review, not automatic validation.
