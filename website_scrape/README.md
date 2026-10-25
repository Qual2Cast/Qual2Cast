# Website scrape

Collects each company's own website text, **programmatically**, from the
company name and website only (Aziz's rule: the method has to work for a
*private* target, so no 10-Ks, investor-relations pages, or stock data).
Public companies in the list are stand-ins for testing.

The scrape also covers the "use non-financial information only" requirement.
Its filters drop financial figures, size figures, tickers and other
public-company language before anything else reads the text. Every removal is
logged with its reason, and the raw text is kept next to the cleaned text.

| file | what |
|---|---|
| `scrape_websites.py` | the scrape: picks pages, tries fetch methods, saves raw HTML and text |
| `fetch_and_clean.py` | downloads (plain and headless browser), HTML parsing, text filters, company-list loading |
| `tests/` | one test per filter problem found so far (`python -m pytest tests -q`) |

## Output (`outputs-local/website_scrape/`; only `page_text/` and `scrape_log.csv` are in Git)

```
data-local/snapshots/company_list_v3_websites_fixed.csv   (name + website)
   │
   ▼ scrape_websites.py
outputs-local/website_scrape/
    raw_html/<IQ_ID>/<scrape time>/<method>/P<n>.html.gz   pages exactly as downloaded, every method tried
    page_text/<IQ_ID>.json        one per company: raw + cleaned text per page, removals, sources
    page_text_history/            earlier versions of page_text files (never overwritten)
    scrape_log.csv                one row per company
    logs/                         run logs
```

### `page_text/<IQ_ID>.json`

Company level:

| field | meaning |
|---|---|
| `IQ_COMPANY_ID`, `company_name`, `website` | from the snapshot |
| `status` | `ok`, `thin_content` (under 150 words), `blocked` (bot-check page), `robots_disallowed`, `investor_site`, `http_<code>`, `error: ...` |
| `method` | method that produced the pages: `html`, `rendered`, `stealth`, `wayback` |
| `attempts`, `attempt_details[]` | every method tried: `method`, `status`, `word_count`, `raw_html_dir` |
| `scraped_at`, `reparsed_at` | fetch time, and the last time the text was rebuilt from saved HTML |
| `max_pages`, `word_count` | page cap (3) and total cleaned words |
| `pages[]` | the pages kept (fields below) |

Per page:

| field | meaning |
|---|---|
| `page_id`, `url` | `P1`–`P3` and the page address (P1 is the homepage) |
| `category` | why it was picked: `home`, `about`, `offerings`, `markets`, `model`, `channels`, `locations`, `customer_stories` |
| `method`, `fetched_at`, `snapshot` | how and when it was fetched; `snapshot` = Wayback capture date, else blank |
| `raw_html_file`, `raw_html_sha256` | the saved HTML and its checksum |
| `raw_title`, `raw_meta`, `raw_blocks[]` | text before the filters |
| `removed[]` | `{text, reason}` for every sentence or phrase the filters took out |
| `title`, `meta`, `blocks[]` | text after the filters |
| `word_count`, `blocks_cut_at_word_cap` | cleaned words (pages are capped at 2,000) and how many blocks the cap dropped |
| `block_page` | `true` if the page was a bot check (its raw text is kept, it has no cleaned text) |

`scrape_log.csv` has one row per company: `IQ_COMPANY_ID, company_name,
website, status, method, attempts, pages, word_count, page_urls, scraped_at`.

## Current results (snapshot `company_list_v3`, re-parsed 2026-10-18)

All 560 companies were attempted.

| status | companies |
|---|---|
| `ok` | 532 |
| `thin_content` | 15 |
| `investor_site` (main domain redirects to an IR site) | 4: Avista, Black Hills, Simpson Manufacturing, IAC |
| `robots_disallowed` | 4 |
| `http_403` | 4 |
| `blocked` | 1 |

- **Pages per company:** 471 companies have 3 pages, 41 have 2, 36 have 1, and 12 have none.
- **Methods:** `html` 1,357 pages, `rendered` 116, `stealth` 45, `wayback` 13.
- **Words:** the median is 283 cleaned words per page.
- **Most common removal reasons:** `filler`, `history_date`, `site_chrome`,
  `cta_question`, `public_company`, `financial_figure`.

## How pages are picked

The homepage plus up to 2 more pages on the same site (`--max-pages 3`),
picked to cover different kinds of information: **about**, **offerings**
(products, solutions, services, brands, businesses), **markets** (industries,
customers, who we serve) and **model** (pricing, how it works, partners).
Three more page types compete for the same slots: **channels** (dealer /
where-to-buy / store locator), **locations** (offices, service areas) and
**customer stories** (case studies). The first extra slot always goes to a
core page (about / offerings / markets / model). On the first 116 companies,
3 pages captured most of what 6 did.

Investor-relations, news, careers, blogs, history, board/leadership and
translated pages are skipped. A site whose host (or redirect) is an IR site
is refused (`investor_site`).

## Fetch methods

Each site is tried with up to four methods, stopping at the first that gets
enough text. The last two are adapted from the
[everlane-sustainability-analysis](https://github.com/mwc2150/everlane-sustainability-analysis)
scraper.

| method | for | how |
|---|---|---|
| `html` | most sites | plain download |
| `rendered` | JavaScript sites | headless Chromium (Playwright) |
| `stealth` | sites that block scripts (403, Cloudflare) | real Chrome via undetected-chromedriver |
| `wayback` | sites that are down or still blocked | latest Internet Archive snapshot (max 2 years old); archive URL and date saved as the source |

- **robots.txt:** honored by every method. A site that disallows crawlers is
  marked `robots_disallowed` and not fetched any other way. A robots.txt that
  can't be read (including a 401/403 answer) counts as no restrictions, as in
  RFC 9309 (agreed 2026-10-18).
- **Bot checks:** every method checks for bot-check pages ("Pardon Our
  Interruption", Cloudflare, Incapsula).
- **Fallback addresses:** a site that can't be reached is retried at its
  `www.` and `http://` addresses. The browser's certificate-error screen
  ("Privacy error / Your connection is not private") counts as a failed load
  too, so the next address is tried and the screen is never saved as text
  (Englewood Lab, fixed 2026-10-24).
- **English homepage:** a homepage that lands on another language's locale
  (`/ko/home`) is replaced by its English copy (`/en/home`) when the site has
  one; translated pages are skipped as before.
- **Text encoding:** pages are decoded from their bytes, since requests
  guesses ISO-8859-1 when the server names no charset.

## Text filters

Text is read from headings, paragraphs, list items and "leaf" containers
(`div`, `td`, ... holding text but no other blocks). Then, per sentence:

| reason in `removed` | what | how |
|---|---|---|
| `financial_figure`, `finance_talk` | money amounts, revenue, cash flow, margins | sentence dropped |
| `public_company`, `ticker_tag`, `public_phrase`, `bare_ticker` | "NYSE: ABC", "publicly traded", dividends, earnings calls, investor links, "(CSWC)" when it is a listed ticker | sentence dropped or phrase cut |
| `scale_figure` | the company's own revenue, market share, growth rates, deal values | sentence dropped (product specs and customer results are kept) |
| `size_count` | counts of facilities, plants, offices, countries, customers | cut inline to "multiple ..." |
| `deal_event` | ownership and deal history ("acquired by ...") | sentence dropped |
| `founding_year`, `history_date` | "founded in 1919", "since 1955", "March 2022" | cut inline |
| `filler`, `site_chrome`, `cta_question` | values statements, careers, cookie text, addresses, phone numbers, promo terms, "Looking for brochures?" | sentence dropped |
| `too_short_after_cleaning` | fragments under 5 words | block dropped |

The filters were narrowed on 2026-10-17 and 2026-10-18 after checking what
they removed. "Investors" as customers, "public companies" as clients,
"subscribe to our software", "financial inclusion" and "non-profit" are kept.
The size, deal and date rules came from Riya's scraper (branch `riya/wip`).
Her headquarters rule is not used, because it would remove most
geography text.

## Run

Once per laptop:

```bash
pip install -r requirements.txt
playwright install chromium        # Google Chrome is also needed for 'stealth'
```

Put the company-list snapshot from the data maintainer at the path in
`data_manifest.json` (the script checks its checksum). Then, from this folder:

```bash
python scrape_websites.py --sic2 35            # one industry group
python scrape_websites.py --tickers KAI DE     # specific companies
python scrape_websites.py                      # all companies (resumes; skips 'ok' ones)
python scrape_websites.py --refresh            # redo companies already 'ok'
python scrape_websites.py --reparse            # rebuild all text from saved HTML, no downloads
python -m pytest tests -q
```

Earlier records are moved to `page_text_history/`, never overwritten.

## Known limitations

- **Imperfect filters:** the filters are rules, so unusual phrasing can slip
  through. Example: The Toro Company's homepage keeps "More events are coming
  soon." and an investor-conference fireside chat. The raw text is always
  kept, so filters can be tightened and re-run with `--reparse`.
- **Marketing copy:** website text says what a company offers, not how much
  each line brings in. Length and detail vary a lot between sites.
- **Unmatchable companies:** 4 companies have no non-IR website, and 8 refuse
  scripts (robots.txt or 403).
- **Staleness:** pages reflect the website at scrape time (2026-10-17/18).
  The date of the multiples in the company list is unconfirmed.
