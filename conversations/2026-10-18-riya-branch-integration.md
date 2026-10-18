# Handoff: integrating Riya's branch (2026-10-18)

Work done in Claude Code. The full session transcript can be added next to
this file with Claude Code's `/export`. This file is the summary.

## What was asked

- Review branch `riya/wip` (Riya's scraper v2 and comps-similarity
  notebook): what is new, and what can be pulled.
- Keep this repository's data as the source of truth. Use Riya's notebook as
  the start of the model (matching) pipeline.
- Port her five scraper fixes without wasting the SIC 35 audit that had just
  been judged.

## Review of the branch

- **Pulled:** the comps-similarity method and checks, ported to
  `p087_task6_matching/`, and the scraper ideas below.
- **Not pulled:** her data (`descriptions.csv`, `text/`, `raw/`), which was
  built from the raw v1 list (BrightView SIC 700, investor-relations
  websites, Smith Douglas "0"). Also not pulled: the cached embeddings and
  charts, and her plan to hand-write the 71 missing descriptions, which
  breaks the programmatic-collection rule.
- **Flag for the team:** the branch commits `company_list_for_interns.csv`
  *with the financial columns*, plus about 1,900 raw HTML files.

## Completed

- **Task 3 filters** (`collect_descriptions.py`), from Riya's
  `collect_descriptions_2.py`:
  - `scale_figure` and `deal_event` drop whole sentences.
  - `size_count`, `founding_year`, `history_date` and `bare_ticker` are cut
    inline; `size_count` is replaced by "multiple ...".
  - Each rule was narrowed after checking its hits. Nine audited quotes and a
    sample from all 560 companies turned up false hits: "sold to
    industries", "grow revenue", "5 million data points", "service bookings",
    "low turnover", "Your CTV Buys Might…", and customer-result percentages.
    Each is now a test.
  - Riya's headquarters rule was left out, since it removes
    `geographic_footprint` evidence.
- **Task 3 step 1:**
  - The bot-page check now runs for every method and during `--reparse`
    (status `blocked`, `block_page: true`). MSC Industrial's homepage had
    been a "Pardon Our Interruption" page saved as text.
  - `www.` / `http://` fallback addresses.
  - Pages are decoded from bytes with `UnicodeDammit`.
- **Reparse of all 548 companies** from saved HTML. Model input changed for
  412, including 28 SIC 35 companies; earlier page text is in
  `page_text_history/`.
- **Codex** redid the 28 changed SIC 35 profiles: 28/28 ok
  (`logs/extract_sic35_v5.log`), and 38/38 SIC 35 profiles are current.
- **Audit:**
  - `step3_audit_profiles.py carry` reuses judgments after profiles are redone.
  - The original sheet's scores were saved first (`audit_sheet_scores.csv`).
  - The carried sheet is `audit_sheet_20261018T043931Z_carried.csv`: 313
    rows, 177 judgments reused, 37 to confirm, 99 to judge (11 of those were
    blank in the original sheet).
- **Task 6:**
  - `p087_task6_matching/comps_similarity.py` offers TF-IDF, LSA and
    embedding methods plus a combined score, `--source pages|profiles`, with
    peer-label NDCG/recall, the SIC4 check, method agreement and the
    text-length check.
  - It fixes notebook issues #1, #2 and #4 and reads SIC codes zero-padded.
  - `peer_labels.csv` holds Riya's PCTY labels.

## Test results

- Task 3: 52 tests pass (`python -m pytest tests -q`, was 35).
- Task 6: 4 tests pass.
- Task 6 on `pages` (535 companies matchable):
  - PCTY combined score: NDCG@20 0.80, recall@25 0.64.
  - PCTY embeddings: NDCG@20 0.85, recall@25 0.91.
  - Random ordering: NDCG@20 0.03.
  - Top-5 neighbours share SIC4 24% of the time, against 1.7% by chance.
  - Riya reported 0.76 / 0.87 on her scrape.
- Task 6 on `profiles`: runs (38 companies only; PCTY not yet profiled).

## Data version

company_list_v3 (sha256 3ab9a43e…; see data_manifest.json). Page text
re-parsed 2026-10-18; prompt version 2026-10-18e (was 2026-10-17d).

## Decisions (later on 2026-10-18)

- **robots.txt answering 401/403 counts as allowed** (RFC 9309). The current
  code stays; this is documented in the Task 3 README and PROJECT_STATE.
- **The extraction model must not see the company name.** Done as prompt
  version **2026-10-18e**. What changed:
  - `build_prompt` masks the name and website as "the Company" and drops the
    `Company:` / `Website:` lines and page URLs.
  - Quotes are checked against the masked text.
  - `name_variants` now uses the registered domain name (Quaker Chemical's
    `home.quakerhoughton.com` had made "home" a name), matches the stem
    written as words ("Quaker Houghton"), and adds the name's first word when
    the domain starts with it, capitals ("ASTEC") and a leading abbreviation
    ("CPI").
  - `mask` replaces web addresses containing the stem, and skips all-lowercase
    stems ("coastal waters").
  - Known gap: 4 companies' names still appear in lowercase marketing copy
    (hayward, parsons, liveramp, freshpet).
- **Financial columns in Riya's committed list:** keep for now, always
  separate from matching inputs; decide when training the model.

## Results after the masking change

- SIC 35 re-run: 38/38 ok, every proposed item passes. Brands are stated for
  34 (was 37), because brands that are the company's own name are now masked.
- Codex never wrote a company's own name in its answers. Its
  `identifying_terms` showed that "ASTEC" and "CPI" were still visible; both
  are now masked and those 5 profiles were redone.
- Audit: `carry` masks the old quotes the same way before comparing. The
  current sheet is `audit_sheet_20261018T174552Z_carried.csv`: 313 rows, 133
  judgments reused, 53 to confirm, 127 to judge. The two earlier `_carried`
  sheets are superseded.
- 54 Task 3 tests pass.
- Task 6 `pages` text now comes from the masked prompt text; its embeddings
  are recomputed on the next run (the cache is keyed by a text hash).

## Audit and full run (evening 2026-10-18)

- The auditor filled in the first carried sheet (`audit_sheet_carried.csv`,
  299 of 313 rows judged, for the version before name masking). Scores are in
  `audit_sheet_carried_scores.csv`. "Yes + partly" is 85-100% for every
  field; "partly" mostly means correct but generic. The rubric is kept as it
  is for the prototype.
- Full extraction: 181 new profiles, then the Codex usage limit was reached.
  219 of 560 are now current. step2 now stops at the first usage-limit error,
  tested with a stand-in Codex.
- Growth is measured from events and qualitative signals, not revenue
  figures. The matching collection removes event text by design, so growth
  needs its own collection. Open question: may sources found by the
  company's name (news, job boards) be used, or only its own site?

- Task 6 rerun on the masked page text (534 companies):
  - PCTY embeddings: NDCG@20 0.90, recall@25 0.91 (was 0.85 before masking).
  - PCTY ensemble: 0.72 (was 0.80; LSA fell).
  - SIC4 check: 14× chance.
- Profiles vs pages on the same 217 companies, SIC4 check: profiles 9.2-9.4×
  chance, pages 8.8-9.1×, so about equal. PCTY and 5 of its peers are not
  profiled yet (usage limit), so the peer-label comparison waits for the
  rest of the run.

## Unresolved

- About 324 companies still need Codex profiles (see PROJECT_STATE).
- Task 6 has peer labels for one target only.

## Next recommended action

1. Judge the 180 open rows of `audit_sheet_20261018T174552Z_carried.csv`
   (53 of them only need confirming), then run `score` on it.
2. Run the full Task 3 extraction (`python step2_extract_profiles.py`). This
   is about 2 hours of Codex time at 2 workers.
3. A teammate writes peer labels for 3-5 non-HR targets in `peer_labels.csv`
   before running them. Then compare `--source pages` and
   `--source profiles`.
