# Five-company growth-signals pilot

Run date: 2026-10-18

This pilot tests collection and high-precision rule extraction. A zero means
no supported event was extracted from the pages collected; it does not mean
the company had no growth events.

| ticker | sector example | collection | articles saved | dated articles | accepted events | review outcome |
|---|---|---:|---:|---:|---:|---|
| PCTY | HCM software | ok | 9 | 9 | 1 | Supported product launch; eight abstentions |
| BV | landscape services | ok | 3 | 2 | 0 | Three abstentions; one article date unknown |
| HRI | equipment rental | ok | 3 | 3 | 0 | Three legitimate abstentions: earnings call, CSR report, and dividend |
| PRGS | infrastructure software | ok | 3 | 3 | 2 | Two supported product releases; acquisition article abstained |
| WING | restaurants | ok | 6 | 6 | 4 | Four supported launches/offers; earnings release and call announcement abstained |

## Aggregate checks

- 5/5 homepages and at least one event-related page were collected.
- 5/5 companies yielded specific articles.
- 24 articles were saved; 23 had an explicit publication date.
- Seven events survived rule extraction and manual evidence review.
- Duration review classified four WING launches as temporary and the three
  Paylocity/Progress software launches as durable.
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
5. Empty dynamic shells now trigger the rendered-browser fallback. This made
   HRI's JavaScript-rendered news listing collectible.
6. When a homepage exposes no News/Press entry, the collector may try only the
   conventional same-company `ir.<domain>` host, still subject to robots.txt,
   same-host validation, and event-link validation. This recovered WING.
7. Media-asset and investor-event pages are excluded from News/Press discovery,
   article-body dates override dates embedded in link titles, and duplicated
   HTML-title/site-suffix evidence is collapsed.
8. If a News page explicitly declares a same-company WordPress API, the
   collector requests a bounded, date-descending latest-post list. WING now
   returns five recent 2026 articles instead of the first-listed 2015 archive
   entries. API JSON is saved with its own provenance record, and robots.txt
   is still enforced.
9. Guarded product patterns now cover a named pass/card announcement, a named
   offering introduced with `Introducing the ...`, a product/flavor that
   `arrives nationwide`, and named new products `launching nationwide`.
   Generic staff availability, tentative future products, and PRNewswire
   source-link boilerplate are negative controls.
10. Product launches now carry a backward-compatible `signal_duration` field.
    Explicit limited-time or scarcity language produces `temporary`; explicit
    platform/service objects or integration produce `durable`; ambiguous cases
    remain `unknown`. Feature windows keep all three counts separate rather
    than applying an unvalidated fixed weight.

## Remaining coverage gaps

- Careers landing pages are collected but do not yet follow third-party job
  boards. Those sources require an allow-list and attribution policy.
- Duration is still a coarse label. Future human evaluation should check
  whether temporary launches predict growth at all and whether durable product
  releases need finer platform/service/capability subtypes.
- The rule extractor is intentionally low-recall. It is candidate generation
  for human review, not automatic validation.
