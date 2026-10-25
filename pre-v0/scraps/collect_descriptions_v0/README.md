# First collection script (scraps)

`collect_descriptions.py` was the first attempt: a single script that
collected one block of description text per company (no per-page sources),
tried on the 38 SIC 35 companies. `descriptions.csv` and `text/` are its
outputs, including 12 descriptions written by hand. The project has since
ruled out hand-written data.

Its fetching and filters were split out into
`website_scrape/fetch_and_clean.py` and improved there. This copy is kept as
it was, so its outputs can be reproduced. It is superseded by
`website_scrape/`.

## What it does

For each company it reads:
1. the homepage: title, meta description, and main text
2. up to 2 pages on the same site that describe the business ("About",
   "Who we are", "Products", "Solutions", ...)

Then it cleans the text:
- skips investor-relations, news, careers, legal, contact, and PDF pages
- drops filler sentences (company values, careers, charity, cookie notices,
  "contact us", search-box text)
- drops sentences with financial figures or headcount ("a $1.4B company with
  5,000 associates", "shipments exceed $100 million"), keeping descriptions
  non-financial; product facts like plant size, patents, or units shipped stay
- removes public-company giveaways ("NYSE: ABC", "publicly traded",
  "listed on the NYSE under the symbol", "became a public company",
  "financial results", "dividend", "earnings call", investor-site links,
  stock-price widgets), so a public company's description looks like a
  private company's would
- drops talk about the company's own finances ("cash flow", "profit
  margins", "balance sheet", "stakeholder value")
- drops site chrome: street addresses, phone numbers, emails, promotion
  terms and conditions, product-filter counts, trade-show booths, dated news
  headlines, and short marketing questions ("Looking for brochures?")
- keeps at most 3 list items that start with the same three words, so long
  lists (e.g. 40 "Alamo Group acquires ..." lines) don't dominate

If a site builds its text with JavaScript, a plain download comes back nearly
empty. If Playwright is installed, those sites are re-loaded in a headless
browser and extracted again.

Only non-financial columns are written out (no revenue, EBITDA, multiples).

## Setup (once)

```bash
pip install requests beautifulsoup4 pandas
pip install playwright && playwright install chromium   # optional, for JavaScript sites
```

The script reads the company-list snapshot named in `data_manifest.json`
(`data-local/snapshots/`), or a file passed with `--input`.

## Run

```bash
python collect_descriptions.py --sic2 35             # one industry group (~38 companies)
python collect_descriptions.py --sic2 35 --refresh   # redo all of them, e.g. after a script update
python collect_descriptions.py                       # all ~560 companies
```

Re-running without `--refresh` only redoes companies that weren't `ok`.

## Output (`descriptions_output/`)

- `descriptions.csv`: one row per company with `status`, `method`
  (`html` or `rendered`), `word_count`, `pages_used`, a 250-word `excerpt`,
  and `text_file`
- `text/<IQ_ID>_<TICKER>.txt`: the full description (up to 1,500 words)

| status | meaning | what to do |
|---|---|---|
| `ok` | 150+ words collected | nothing |
| `thin_content` | under 150 words (usually a JavaScript site) | install Playwright, or copy the text by hand |
| `http_403` / `http_406` | the site refused the request | copy the text by hand |
| `robots_disallowed` | the site's robots.txt asks scripts not to read it | copy the text by hand |
| `error: ...` | site down, timeout, not a web page | check the URL |

## Results: SIC 35 sample (38 companies, Oct 17)

**38 / 38 companies have a description.**

| status | count | how |
|---|---|---|
| `ok` | 26 | collected by this script from the company website |
| `manual` | 12 | written by hand from the company website (see below) |

- The script reached 29/38 automatically (76%): 8 sites returned too little
  text (JavaScript-heavy) and 1 (Kadant) blocked scripts.
- Those 9, plus 3 whose scraped text was misleading (DMC Global covered only
  one of its three businesses; Crane NXT and Timken were mostly culture
  text), were replaced with manual descriptions: Alliance Laundry, Astec,
  Deere, Digi, Flowco, Kadant, Lindsay, Resolute, SPX, DMC Global, Crane NXT,
  Timken. Their source URLs are in the `pages_used` column.
- Manual descriptions are ~170-word summaries of the company's own website
  (products, customers, applications); they pass the same filters as the
  scraped text. They were not re-checked against the live sites by a second
  person.
- Full-text check of all 38 files: no dollar figures, revenue, headcount,
  tickers, earnings/dividend news, or investor-relations text remain.

**Note for matching:** the 12 manual entries are short, uniform summaries,
while the 26 scraped ones are raw website text (300-1,500 words). This style
difference could make the manual ones look more similar to each other than
they are. A consistent fix is to summarize all descriptions the same way
(e.g. an LLM pass to a standard ~150-word format) before embedding.

## Known limitations

- Rules can't fix a website that doesn't say what the company does. After a
  full read of the 29 SIC 35 descriptions: DMC Global's text covers only its
  building-products business (Arcadia), Crane NXT's is mostly culture text,
  and Timken's is vague. Zebra's includes customer case studies about other
  companies, and AAON's includes a generic HVAC FAQ. An LLM summary step
  (products, customers, business model) or a hand-written description would
  fix these.
- ITT, Veeco, AAON and Zebra hit the 1,500-word cap, so later parts of their
  sites are cut off (ITT's brand list stops at "L").

- The dollar/headcount filter is rule-based, so unusual phrasings can slip
  through (e.g. Crane NXT's "community of 5,000 passionate doers"). Whether
  company size should be used for matching at all is a team decision; if yes,
  it belongs in its own column, not in the description text.

- Website text is marketing language and varies a lot in length and detail.
- Some sites will still block scripts; those need manual collection.
- Descriptions reflect the website today, which may not match the date of
  the multiples in the sheet (that date is still unconfirmed).
- SIC codes in the sheet can be misleading (e.g. CPI Card Group is labeled
  "Computer Storage Devices" but is a payments company), so descriptions,
  not SIC, should drive matching.
