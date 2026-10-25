# 2026-10-24: shorter facet answers (prompt version g), model choice

## Why

The Codex usage limit stops the facet fill (~200 calls per window). Token
counts in the saved `events.jsonl` files, per call:

| run | input | of which cached | output | reasoning |
|---|---|---|---|---|
| `fill_test/knowledge_only` (version f, 21 calls) | ~17.4k | median 0 | ~920 | ~70 |
| `facets/` (version a, website-only, 137 calls) | ~18.1k | ~13.7k | ~1,470 | ~100 |

The prompt itself is ~3k tokens; the other ~15k is Codex's own system
prompt and tools, cached only when calls run close together. On OpenAI's
Codex rate card (credits per 1M tokens, Standard speed): GPT-6.1 Sol 50 in /
2.5 cached / 250 out; GPT-6 Luna 2.5 / 0.25 / 12.5; GPT-6 Astra 250 / 25 /
1,250 (https://learn.chatgpt.com/docs/pricing). Output is ~60% of a Sol
call's cost. Reasoning is ~7% of output, so lower effort saves little;
more workers save nothing (same calls, limit reached sooner). Several
companies per call saves ~7% with a warm cache and up to ~45% cold, but
risks blending profiles; not done.

GPT-5.4/5.4-mini (retired 2026-08-31) and GPT-5.5 (2026-10-14) are gone
from Codex with ChatGPT sign-in (https://learn.chatgpt.com/docs/models.md).
No `~/.codex/config.toml` on this laptop, so runs used Codex's default model,
and `run.json` recorded it as blank.

## Changes (version 2026-10-24g)

- `v0/facets.py`: prompt asks for one-line JSON, details of about twelve
  words at most without repeating the category, empty value/detail for
  unknown / not_applicable, notes only for real gaps.
- Without pages the answer has no `source` or citations (code records
  "model knowledge" for every facet not unknown): two schemas,
  `answer_schema(pages)`, `FacetAnswer[pages]`.
- With pages every page line is labeled `[P1.3]` and the model lists 1-2
  labels in `cite`; code looks up the line text and URL. `quote_found` now
  means the label was in the prompt. The `norm()` quote matching and the
  `website_but_no_pages` flag are gone (that case can't happen now). A
  company without saved pages gets the same prompt as without `--with-pages`.
- `v0/fill_facets.py`: writes `answer_schema.json` and
  `answer_schema_with_pages.json` and picks one per prompt;
  `facet_quotes.csv` gains a `block` column.
- README, data dictionary, notebook source-check cell updated.

## Notebooks reorganized

`v0/notebooks/comp_universe_and_facets.ipynb` keeps only what v0 uses:
section 3 is 3.1 the facets, 3.2 what the model reads (labeled lines), 3.3
the full run. The development record moved to
`v0/notebooks/facet_fill_runs.ipynb`: findings so far; 1. fill runs (every
output folder x prompt version x model: fill %, median tokens, seconds,
credits per company at the Sol and Luna rates); 2. the fill test (fill
rates by group and facet, unknowns, splits, source mix, category agreement
against knowledge_only version f, side by side). New runs under
`fill_test/` show up there without edits.

Section 3 of the main notebook is now three sections: 3.1 the facets, 3.2
who does what (the model's steps and the code's fixed rules listed
separately; `quote_not_found` is a lookup, no model involved), 3.3 the
filled facets. Markdown only; code cells and outputs unchanged.

Options while Codex is out (not decided): wait for the reset and run Luna;
or the Anthropic API with Claude Haiku 5.5 ($0.10 / $0.50 per MTok,
Batch 50% off), roughly $0.3-1 for all 533 calls without Codex's ~15k
scaffolding (needs a Console API key and a new backend in
fill_facets.py). Claude Code on Pro is a poor fit: limits are shared
with claude.ai, unpublished, and each call carries Claude Code's own
large system prompt. Whatever is chosen, one model for all 533.

First Luna run (`fill_test/knowledge_only_g_luna`): the usage limit was
already reached ("try again at 9:05 PM"), two calls failed, nothing filled.
The stop worked, but `write_tables` then crashed on an empty table
(`KeyError: 'business_count'`); fixed, with a test.
`fill_facets.load_profiles(out_dir)` reads every profile version with its
run.json. Executed 2026-10-24 (wrote a new `universe/<run>/` folder).

Finding: the same default model at versions e and f agrees on revenue
model for 62% of companies (value chain 76%, distribution channels 86%,
others 86-100%). The prompt changed too, so it bounds run-to-run noise
from above; a model comparison needs a Sol-vs-Sol baseline, not 100%.

## Model decision: Claude Haiku 5.5 (later the same day)

Decided after the Codex limit stopped the Luna run: Claude Haiku 5.5
(`claude-haiku-5-5`) through the Anthropic API. Considered and set aside:
Claude Code on Pro (shared, unpublished limits plus Claude Code's own large
system prompt per call); Llama 3.1 8B/70B with search (stale knowledge to
end of 2023, 70B can't run on this laptop's 6 GB GPU, search brings
valuation figures and peer lists into the input); local models such as
gpt-oss-20b or Qwen3.5 4B (thin company knowledge; best only with pages).

`fill_facets.py` now has `--backend claude` (default, model
`claude-haiku-5-5`) and `--backend codex`:
- Claude: one `messages.create` per company, the same prompt as a user
  message, the answer schema in `output_config.format` without the
  company-size `pattern` (the API doesn't take string patterns;
  `quantity_in_value` still flags figures). Effort is the model's default
  (medium) unless `--effort`. No caching or Batch API: the whole run is
  well under $1.
- Saved per call: `response.json`, `api_response.json` (whole response),
  `run.json` with backend, model, `request_id`, `stop_reason`, tokens
  (`input_tokens` counts cached ones too, as Codex reports them).
- `refusal` and `truncated` (max_tokens) are their own statuses; an
  out-of-credit 400 or a refused key stops the run, like the Codex usage
  limit.
- The model is stored in each profile; `is_current` redoes a profile
  made with another model.
- API key: `ANTHROPIC_API_KEY` in the shell or in `.env` at the repo root
  (git-ignored). None is set on this laptop yet, so nothing was run
  against the API; the backend is tested with a stand-in client only.

Docs: v0 README (decision, key setup, run notes), data dictionary,
PROJECT_STATE (status, open question on who pays, next step), both
notebooks' text; `facet_fill_runs.ipynb` adds a "USD at haiku" column.

## API key and rule checks (later still)

- `.env` at the repo root holds the user's `ANTHROPIC_API_KEY` (git-ignored,
  confirmed with `git check-ignore`); a free models lookup confirmed it
  works for `claude-haiku-5-5`.
- Test calls (fictional company, under a cent): the API takes the pattern
  `^[^0-9$%]*$` on a one-field schema and Haiku then writes no digits, but
  spells them out ("one hundred twenty plants ... two billion dollars in
  revenue"). On the full answer schema any pattern (also `^\D*$`) is
  refused: "Schema is too complex". Without it the schema is accepted;
  the fictional company came back all unknown (5,669 input / 995 output
  tokens, about $0.001).
- New deterministic input check: `build_prompt` leaves out any page line
  the scrape's filters (FINANCIAL_FIGURE, SCALE_FIGURE, TICKER_TAG) match,
  page titles included (Dave's title "Get Up To $500 In 5 Minutes" got
  through before); `figures_in_input` rescans each prompt, stored as
  `input_figures` and issue `figures_in_input`. 0 of 533 prompts in either
  mode. It shows what the model was given, not what it remembers.

## Prompt version h (end of day)

- Company size (F9) is a one-of category with no detail: small,
  mid-sized, large, among the largest, within the company's own industry;
  the guide says it is scale only (F8 is where, F11 is how it sells).
  `Facet.detail=False` drops the detail field. The digit pattern,
  `QUANTITY_WORDS`, `quantity_in_value`, `words_only` and
  `claude_schema()` are gone: nothing left to strip or flag.
- Longer answers: core offering in two or three sentences; products,
  services and end markets up to about five; details about twenty words.
  No ordering by importance (embeddings later) and no effort change.
- `facet_fill_runs.ipynb`: the Copart / Con Ed side-by-side cells removed;
  the agreement table counts a facet only where both runs gave a category
  (company size is blank against runs before h).
- API test calls so far, by the API's own token counts: $0.00011 (digit
  test), $0.00106 (version g schema), $0.00101 (version h schema, 7.4 s);
  the two refused calls cost nothing. Total about $0.0022.
- Per call at version h: 5,812 input tokens, of which the answer schema is
  3,567 and the instructions ~2,200; on the fictional company 857 output
  tokens for an 849-character answer, so most output is thinking.

## Caching and the two-pass design (last)

- Caching: the instructions go in a cached system prompt, the company
  part in the user message. Tested with two fictional companies: call 1
  wrote 5,778 tokens to the cache ($0.00144), call 2 read all 5,778 and
  paid full price for 38 ($0.00088). The cache covers the answer schema
  too. Usage now records `cache_write_input_tokens`;
  `facet_fill_runs.ipynb` prices writes at 1.25x. API tests so far total
  about $0.0045.
- Pages only fill gaps (the user's rule, stated as final): pass 1, every
  company from name and website; pass 2, only companies with an unknown
  facet and saved page text, and `facets.fill_gaps` copies only the
  unknown facets (B1 with B1; nothing if the business counts differ,
  issue `gap_fill_business_mismatch`). Recorded as `gap_fill` in the
  profile and `filled_from_pages` in facets.csv. `--with-pages` is gone;
  `--no-gap-fill` skips pass 2. A rerun does nothing once both passes are
  done (tested end to end with a stand-in model).
- `facet_fill_runs.ipynb`: summary rewritten for the current setup; a cell
  says whether a run at the current prompt version exists (none yet).

## API check script and the fill-runs notebook rebuilt

- `v0/check_claude_api.py` repeats the API checks with two made-up
  companies and saves them (`outputs-local/comps/api_checks/<time>/`):
  no-digits rule on one field (accepted; the model spells the figures out),
  the rule on the full schema (refused, "Schema is too complex"), the
  current schema with the cached system prompt (accepted; the second call
  reads 5,778 tokens from the cache), and the same prompt as one message.
  Two runs so far, $0.0054 together.
- **New finding, open:** for the made-up companies Haiku filled 9-11 of 12
  facets from the name, and said so in its notes (company 1's answer
  echoes the facet guide's examples). The system prompt makes no
  consistent difference (3 of 12 unknown either way in the second run).
  Cause: version f's "best description instead of unknown". Options in
  PROJECT_STATE and `facet_fill_runs.ipynb` section 5; decide before the
  fill test.
- `facet_fill_runs.ipynb` rebuilt: where things stand; prompt versions a-h
  with what changed and why (b and c reasons not recorded); model choice
  (Codex vs Claude, alternatives set aside; no GPT-6 rate tables); pages
  only fill gaps, with the version e evidence; the API checks and the
  figure scan of all prompts; every run with tokens, time and US dollars
  for Claude runs; the fill test.

## Prompt version i: no guessing (decided by the user)

- The model first says whether it knows this specific company
  (`knows_company`, the answer's first field); a name or web address alone
  isn't knowing it, and it must not guess from the name or from what is
  typical for similar names. Without pages, "doesn't know" makes every
  facet unknown in `check_answer`, whatever the model wrote (issue
  `company_not_known`), so the company goes to the second pass; there the
  model may use only the pages, and `fill_gaps` takes the pages answer
  whole when nothing was known. For a known company it still gives its best
  description of that company, with doubts in the notes.
- `check_claude_api.py`: the made-up companies now have plausible names and
  addresses with nothing saying they're made up (the earlier
  "(fictional test company)" label gave the answer away), plus Paylocity
  as a known real company. Latest run (20261025T000547Z, $0.0026): both
  made-up companies "doesn't know", 12 of 12 unknown, with or without the
  system prompt; Paylocity known, 0 of 12 unknown. At version h the same
  checks left 1-3 of 12 unknown. Four check runs so far, $0.011 together.
- Notebooks, README, PROJECT_STATE updated; the fill test goes into
  `fill_test/knowledge_only_i_haiku`.

## Fill test at version i (Claude Haiku 5.5)

`python v0/fill_facets.py --workers 4 --out outputs-local/comps/fill_test/knowledge_only_i_haiku --tickers <the 31>`
- First pass: 31/31 ok. 29 known; AMETEK left primary services unknown.
  Cardinal Infrastructure Group and Englewood Lab not known (all unknown).
  Five splits: Albemarle (lithium, bromine, catalysts), St. Joe (real
  estate, hospitality, timberland), AZZ, Con Ed, SBC Medical (two each).
  Ingles and Huron one business each.
- Second pass, first try: all 3 refused, "The compiled grammar is too
  large": the with-pages schema (source + cite list per facet) was too big.
  Tested on Cardinal's prompt: without source still too big; one
  structured citations list too big; one list of strings accepted. Now the
  pages answer has a top-level `citations` list ("B1 primary_products:
  P1.3, P2.1") that `check_answer` parses (`citation_not_read` if it
  can't); the source is the cited pages' URLs, or model knowledge for an
  uncited facet of a known company. The first-pass prompt is unchanged, so
  the version stays i. Also fixed: a second pass that failed is retried on
  the next run (it had been marked as tried).
- Second pass, retry: AMETEK primary services filled from the pages;
  Cardinal filled entirely from its pages, all citations found; Englewood
  still unknown (its saved page is a browser certificate error).
- Fill 97.4% of 456 facets (100% without Englewood). $0.041 total
  ($0.035 first pass, $0.006 second); median 8.7 s per call.
- Against Codex f (20 companies, B1): any-of facets mostly differ in count
  (Haiku lists fewer, 95-100% share one category); one-of facets: geography
  90%, regulatory 85%, specialization 70% the same. Shown in
  `facet_fill_runs.ipynb` section 7, with a findings summary.

## Englewood Lab to 100%, repeated categories

- Englewood Lab (KOSDAQ 950140, a New Jersey cosmetics contract maker
  owned by Cosmecca Korea): Codex's runs (versions e, f) filled it from its
  own knowledge with only name and website in the prompt (checked in the
  saved prompts); Haiku doesn't know it. Its saved page was Chrome's
  certificate-error screen: the site's HTTPS certificate is a self-signed
  placeholder ("My Company Ltd"); HTTP serves a JavaScript cookie check
  that a browser passes, then redirects to /ko/home, with an English copy
  at /en/home. Only 4 of 560 companies hit a certificate error, and only
  Englewood kept the error screen.
- Scraper (`website_scrape/scrape_websites.py`): `CERT_ERROR_PAGE` makes
  that screen a failed load (next address tried; also in `BLOCK_PAGE`, so
  it is never kept as text); `english_version()` swaps a non-English
  locale homepage for its /en/ copy. 33 scraper tests.
- Rescraped Englewood only (`--tickers A950140 --refresh`; the old record is
  in page_text_history/): ok, rendered, 3 English pages, 713 words.
- `fill_facets.py`: `gap_fill.input_sha256` records the second-pass
  prompt; the second pass runs again when it changes (a rescrape). Rerun of
  the fill test: only Englewood's second pass ran, 12 of 12 filled from
  its pages, all citations found. The fill test is at 100%.
- `facets.clean_detail()`: a detail that starts with its own category and a
  colon loses that repeat ("medium: medium: ..."; 12 of 360 details in the
  fill test, 11 in regulatory exposure). Applies to new answers; the fill
  test's saved answers keep the repeat.

## First 100 of the full run; version j

- `python v0/fill_facets.py --workers 4 --limit 100` into `facets/` at
  version i: 103 calls, $0.118, median 9 s; every facet filled (3 unknown
  companies, Accendra Health, Andersen Group, Cardinal, filled from pages);
  one false flag (`website_without_quote` on a not_applicable facet: fixed,
  only filled facets need a citation). 17 companies split, several against
  the rule (ATN by region; Alamo, Astec, AAR, Balchem, Church & Dwight,
  BKV by segment) and some with businesses sold years ago.
- Version j: "describe the company as it is now; leave out businesses sold,
  spun off, closed or held as a minority stake", and a spelled-out list of
  what counts as one business ("when in doubt, it is one business"). Redid
  the 100: 11 companies split; the related-line splits are gone. Still
  wrong (checked in public sources): American Financial's annuities (sold
  to MassMutual, May 2021), AZZ's electrical products (into a 40%-owned JV
  in 2022), Carlisle's interconnect unit (sold to Amphenol, May 2024) and
  foodservice unit (sold to The Jordan Company, March 2018). Haiku's
  knowledge of company structure is out of date; prompting can't remove a
  business the model doesn't know was sold. Open: how to fix (see
  PROJECT_STATE next steps). The rest of the 533 not started.

## Third pass: business splits checked against the current website

- `fill_facets.check_split` / `facets.split_check_prompt`,
  `apply_split_check`: for a company split into several businesses, the
  model says per business whether the saved pages show it ("shown" with
  cited lines, or "not shown"), using only the pages. Code rules: shown
  needs a real cited line (labels read with or without brackets); a
  business not shown is removed only if another is shown and none of its
  own name words is in the pages; if its name words are there it is kept
  and flagged `split_disputed`; if no business is shown nothing changes
  (`split_not_checked`). Removed businesses stay in `split_check.removed`
  with their facets. Reruns when the pages change. `--no-split-check`.
- First try on the 10 split companies among the first 100: correct
  removals for AZZ (electrical), Carlisle (interconnect, foodservice),
  Albemarle (catalysts: controlling stake in Ketjen sold to KPS, March
  2026); a wrong removal for Boston Omaha (billboards on the pages, model
  said not shown); AFG and Cass not checked because of the bracket bug.
  After the fixes and a redo of those 10 from the first pass: Albemarle
  catalysts removed, Boston Omaha and five others confirmed; AFG, AZZ and
  Carlisle not split this time (first-pass splits vary between runs).
- Open: out-of-date knowledge inside a single business. AFG's one profile
  now lists "fixed and indexed annuities" (sold 2021) and AZZ's lists
  "electrical bus duct; switchgear enclosures" (moved to a 40% JV, 2022);
  the split check doesn't see these. Not solved; options in the reply of
  this session. The other 433 companies not started.

## Full run (2026-10-25)

- Divestiture flag added before the run (`facets.divestiture_lines`, no
  model): 13 of 533 companies flagged `pages_mention_divestiture`.
- `python v0/fill_facets.py --workers 4`, log in
  `facets/logs/fill_20261025T041958Z.log`: first pass 433 companies, second
  pass 15 (all Haiku didn't know; Englewood among them), third pass 46.
  Result: 533 companies, 599 business profiles, 7,186 of 7,188 facets
  filled (regulatory exposure unknown for Lumexa Imaging and Sucro).
  Issues: company_not_known 17, pages_mention_divestiture 13,
  split_disputed 13, split_not_checked 1, gap_fill_business_mismatch 1;
  flags: website_without_quote 2. All version j calls: 624, $0.657.
- Third-pass removals: Albemarle catalysts, LSB climate control (sold
  2016), MSG Entertainment restaurants and nightlife (Tao, sold 2023),
  Trinity highway products (sold 2021) look right; Flanigan's commercial
  real estate leasing arguable; **News Corp's book publishing and online
  property listings removed wrongly** (still owned; its scrape saved only
  the homepage, which mentions neither). Open: guard removals against thin
  pages, or make every removal a proposal for review. Not yet decided.

## Version k: one profile per company (2026-10-25)

- Decided by the user: no business splits for now; the group may add them
  later. `facets.SPLIT_BUSINESSES = False`: the answer schema has a single
  `company` instead of a `businesses` list (check_answer turns it into B1),
  the prompt says to describe the whole company as one business covering
  all its lines, largest first; the specialization guide drops its
  split-only sentence (`Facet.guide_when_split`). The third pass only runs
  for companies with more than one business, so it never runs now; its
  code and tests stay (tests use the `split_on` fixture).
- For the group, if they turn splitting on: first-pass splits vary between
  runs; the third pass needs a guard for thin pages (News Corp lost two
  real businesses because only its homepage was saved); the split
  tests show the rules.
- `check_claude_api.py` at k ($0.003): made-up companies unknown, Paylocity
  filled.
- Full run at k, `facets/logs/fill_20261025T045332Z.log`: 533 companies,
  533 profiles; first pass 533, second pass 19 (companies the model didn't
  know, all filled from pages except 7 facets on 6 of them). 6,389 of 6,396
  facets filled; 330 cited lines, all found; flags: website_without_quote
  1; issues: company_not_known 19, pages_mention_divestiture 13. $0.552 for
  552 calls, median 8.8 s. Out-of-date facts remain inside single
  profiles (American Financial lists annuities; AZZ electrical fittings;
  Carlisle brake components; Albemarle refining catalysts), as expected.
  The `business` name is often the company's own name rather than a short
  general one. Both notebooks re-executed; facet_fill_runs has rows j, k.

## Manual review list and example profiles

- `fill_facets.review_reasons` (no model): `described_from_pages_only`
  (company_not_known), `facet_unknown`, `facet_flagged`, plus every other
  issue. `facets.csv` gains `needs_review` and `review_reasons`; rebuilt
  with `--tables-only`: 32 of 533 need review (from pages only 19,
  divestiture 13, unknown facet 6, flagged facet 1).
- Main notebook 3.3: a review-list cell (counts by reason, the companies),
  and the example profiles now follow a fixed rule: the first company for
  each review reason, then the first with nothing to review; the markdown
  says they are examples, not a sample, and that PCTY, ROAD, ADUS were
  three fixed tickers kept from the fill test. The cell's other content
  (numbered profiles, fill rate, profiles with an unknown facet), edited
  outside this session, is kept.
- AdaptHealth's profile still lists diabetes supplies though its pages
  announce the sale of that business: what the divestiture flag is for.

## Tests and data

`python -m pytest tests -q` from v0/: 79 passed; from website_scrape/: 33 passed. Dry run (`--dry-run
--limit 3`, both modes, into the scratchpad) checked by eye; no Codex calls
were made. Snapshot `company_list_v3`.

## Open

- Version g is not run: every existing profile is now outdated. Old answers
  stay in `profiles_history/` and `codex_runs/`.
- Whether the shorter details lose information the matching needs, and
  whether Luna's facets agree with Sol's.

## Next

Set an Anthropic API key, run the 31 fill-test companies with Haiku 5.5
into `fill_test/knowledge_only_g_haiku`, and compare in
`facet_fill_runs.ipynb` with version f. If it holds up, the full 533 with
the same model. The first real call also confirms that the API accepts
the answer schema (only tested offline so far).
