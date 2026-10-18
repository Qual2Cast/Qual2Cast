# Codex profiles (scraps)

**Set aside on 2026-10-18.** This used Codex to turn each company's scraped
pages into a structured profile (products, customers, end markets, business
model, ...), with every item backed by a verbatim quote. It was started
before the matching method was settled, so the field list was never agreed
with the people who would use it. The code still runs and its tests pass.
It reads the scrape's page text from `outputs-local/website_scrape/` and
writes to `outputs-local/scraps/codex_profiles/` (same `step2_extract/`,
`final_tables/`, `step3_audit/` folders as before).

**State when set aside:**
- **Profiles:** 219 of 560 companies profiled with prompt version
  2026-10-18e; 166 failed on the Codex usage limit, 17 were skipped (site
  text too thin) and about 158 were never tried.
- **SIC 35 pilot:** 38/38 profiles; every item passes validation.
- **Human audit (20 SIC 35 companies):** "yes + partly" was 85-100% for
  every stated field. "Partly" mostly meant correct but too generic.

## Step 2: `step2_extract_profiles.py` (structured profile)

A model reads the saved pages: cleaned page text only. **Since prompt
version 2026-10-18e it never sees the company's name or website.** The name,
its variants and the domain are replaced by "the Company" in the text; pages
are labeled P1, P2, ... without their URLs; and there is no SIC code, ticker
or financial field. A model that recognized the company could describe it
from memory, which it can't do for a private target. The masking covers:
- the name with and without legal suffixes and generic words
- the domain, its registered name ("home.quakerhoughton.com" → quakerhoughton),
  also written as words ("Quaker Houghton")
- the name's first word when the domain starts with it (from Riya's scraper;
  generic words like "Energy" excluded)
- web addresses containing the domain name

A domain stem written all in lowercase is left alone ("coastal waters",
"expeditions"), so 4 companies still show their name in lowercase marketing
copy: "a hayward pool", "parsons engineer", "liveramp", "freshpet". Quotes
are checked against this masked text.

By default the model is **Codex CLI**,
run with `codex exec` under each student's own ChatGPT sign-in, so it costs no
API credits. The script passes the output format as a JSON Schema
(`--output-schema`) and reads the answer from the file Codex saves (`-o`).
Codex runs in a read-only sandbox, in an empty folder outside the repo (so it
doesn't load the repo's AGENTS.md). `--backend anthropic` uses the Anthropic
API instead, if someone has an API key.

It fills in:

| field | content |
|---|---|
| `business_description` | 2-3 neutral sentences on what the company does |
| `products_services` | main products, product lines, services |
| `customers` | who buys them |
| `end_markets` | industries / markets served |
| `business_model` | how it makes money |
| `sales_channels` | direct, dealers, distributors, online, retail, ... |
| `geographic_footprint` | where it sells or operates |
| `brands` | brand / product-line names (identifying, so not a matching input) |
| `customer_types`, `revenue_streams`, `operating_roles` | tags from fixed lists, for filtering and matching |
| `matching_summary` | **built by the script, not the model**: a fixed template over the verified list and tag items (operating role, products, customers, customer types, end markets, sales channels, revenue streams; up to 8 items each), with "not stated on the website" for unknown ones. Every phrase traces to a quote; prose fields are left out. |
| `evidence_quality` | **computed by the script**: `sufficient` if products, customers and business model (or revenue streams) are stated; `partial` if products or the description are; else `insufficient` |

**Masking.** Every field except `brands` refers to the company as "the
Company" and describes products generically, without brand or product trade
names. The model also lists the company's identifying names. The script then
replaces any name left in those fields: the company's name with or without
legal suffixes, its domain, and the listed names and brands. Every
replacement is recorded in `masking_fixes`. Evidence quotes are verbatim
copies of the masked text the model read, so the company's own name appears
in them as "the Company".

**Validation (Pydantic, [profile_schema.py](profile_schema.py)).** One set of
Pydantic models defines the answer format. It generates the JSON Schema
Codex must follow, and validates every answer in two layers:

1. **Shape:** the whole answer must have every field, the right types, tags
   only from the fixed lists, and no extra keys. Otherwise it is rejected
   (`llm_status: invalid_answer`, errors saved).
2. **Rules, per item:** every list or tag item comes with its **own quote**.
   Each item is validated separately, and a failing item is dropped (kept in
   the JSON) with a named reason:

| reason | rule |
|---|---|
| `quote_not_found` | the quote must appear on a page the model was given (ignoring case, punctuation, ™/®) |
| `quote_too_short` / `quote_too_long` | 4–40 words (brands: the brand name itself is enough; a combined value like "SAPS; Space Alternated Phase Shift" passes if one name is quoted) |
| `brand_not_in_quote` | a brand's quote must contain the brand name |
| `financial` | no money amounts, headcount, tickers or stock-market language |
| `empty_value` | no blank values |
| `value_too_long` | list items are at most 20 words (names and short phrases, not prose) |

Each item's source is the page its quote was actually found on. Field-level
problems are recorded too (`stated_without_items`, `unknown_with_items`), as
are profile-level ones.

**Unknown instead of guessed.** Every field ends with a `status`:

| status | meaning | in `matching_inputs.csv` |
|---|---|---|
| `stated` | at least one item passed (its quote is on the company's pages) | passing items filled in |
| `unknown` | the model says the website doesn't say | blank |
| `unverified` | items were given but none passed | blank (kept in the JSON for review) |

**The output tables are validated too.** Before `final_tables/` is written,
every `matching_inputs.csv` row is checked against a Pydantic model
(`MatchingRow`): a value is filled only when its status is `stated`, every
stated field has a source URL, tags are from the allowed lists, no column
mentions money or stock information, no company name is left unmasked,
`evidence_quality` follows its rule, and there are no extra columns (so no
financial ones). Every `financial_fields.csv` row must hold only the ID and
five numbers (`FinancialRow`). If any row fails, nothing is written and
the run stops with the list of problems. `notes` is also checked for
financial language.

**Tests.** `python -m pytest tests -q` runs 52 tests covering each rule,
each problem found while building the pipeline ("stickers" vs "ticker",
™ symbols, combined brand names, generic company names in masking), the
table checks, and the page-text filters, including every false hit found
when Riya's filters were ported. Run them after any rule change.

`validation_report.csv` summarizes this per column: companies stated /
unknown / unverified, items proposed vs passed, and counts per drop reason.

**What validation does and doesn't show.** Passing shows a value is
well-formed and backed by a real quote from the company's own website. It
does not show the quote actually supports the value: a real quote about
distributors could be attached to the item "mowers". That is measured by
human audit (step 3, below). The model is also told not to use outside knowledge of
the company.

## Step 3: human audit ([step3_audit_profiles.py](step3_audit_profiles.py))


`python step3_audit_profiles.py sample` picks 30 random companies (fixed seed, so
the sample can be reproduced) and writes a CSV: one row per item, with the
value, its quote and the source link, up to 2 items per field (1 brand). It
also has a row for each "unknown" field (to check the site really doesn't say
it), about 15 rows per company. There is no summary row: the summary is
built from the audited items. A teammate marks each
row `yes` / `partly` / `no`, then `python step3_audit_profiles.py score <sheet>`
reports accuracy per column.

When profiles are redone after a sheet was judged (new filters, re-scrape),
`python step3_audit_profiles.py carry <judged sheet>` builds a new sheet for
the same companies from their current profiles:
- same value and quote as a judged row: the judgment, comment and auditor
  are copied (`carried_from` = old `audit_id`)
- same value with a new quote: blank, with the earlier judgment and quote in
  `previous_judgment` / `previous_quote` for a quick confirmation
- new items: blank

The earlier sheet and its `_scores.csv` are kept as the score of the earlier
version.

**Financial fields are kept apart.** `matching_inputs.csv` holds only the
non-financial identifiers (IQ ID, name, ticker, exchange, website, SIC codes)
plus the profile. `financial_fields.csv` holds only `IQ_COMPANY_ID` and the
five supplied financial columns (revenue, EBITDA, margin, debt/revenue,
EV/EBITDA). Join on `IQ_COMPANY_ID` only when evaluating or forecasting, never
as matching inputs. Ticker and exchange are identifiers, not matching
features (they reveal that a company is public).

## Setup and run

Once per laptop:

```bash
pip install -r requirements.txt
npm install -g @openai/codex       # Codex CLI
codex login                        # sign in with your own ChatGPT account
```

Put the company-list snapshot from the data maintainer at the path in
`data_manifest.json` (the scripts check its checksum). Never commit
`~/.codex/auth.json`, `data-local/` or `outputs-local/`.

Then, from this folder:

```bash
python step2_extract_profiles.py --sic2 35 --dry-run # write the prompts only, no model calls
python step2_extract_profiles.py --sic2 35           # step 2 for one group (check results first)
python step2_extract_profiles.py                     # step 2 for every scraped company
python step2_extract_profiles.py --tables-only       # rebuild final_tables/ only
python step2_extract_profiles.py --reverify          # re-check saved answers after a rule change
python step3_audit_profiles.py sample                # audit sheet for 30 random companies
python step3_audit_profiles.py carry <judged sheet>   # after profiles were redone: reuse judgments
```

Both stages resume where they left off; `--refresh` redoes companies already
done (earlier versions are archived, not deleted). Stage 2 runs 2 companies at
a time (`--workers`) with Codex's configured model (`--model`, `--effort` to
change). Each call counts against the signed-in student's Codex usage
allowance, so a large run can be split across students by `--sic2` or
`--tickers`.

A profile is current only if it was made with the current prompt version
from the current page text: each profile stores a fingerprint (sha256) of
the exact text the model read. After a re-scrape or `--reparse`, step 2 redoes
just the companies whose text changed, and outdated profiles are left out of
`final_tables/` until then.

Status (2026-10-18):
- Riya's filters were added and all 548 companies re-parsed. Model input
  changed for 412, including 28 of the 38 SIC 35 companies.
- Codex redid those 28: all ok, 38/38 SIC 35 profiles current.
- Prompt version 2026-10-18e: the model no longer sees the company name or
  website. All 38 SIC 35 profiles were redone: 38/38 ok, every item passes.
- The audit of 20 SIC 35 companies (305 rows judged, scores in
  `step3_audit/audit_sheet_scores.csv`) was carried over to
  `audit_sheet_20261018T174552Z_carried.csv`: 133 judgments reused, 53 to
  confirm, 127 to judge.
