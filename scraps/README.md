# Scraps: things we tried

Work that came before the main pipeline was settled. It is kept for
reference, not deleted, but **none of it is part of the pipeline**. The
pipeline's data comes from `website_scrape/` only.

Each folder still runs and has its own README. Its outputs are in the
matching folder under `outputs-local/scraps/`.

| folder | what it was | why it was set aside | state when set aside (2026-10-18) |
|---|---|---|---|
| [`codex_profiles/`](codex_profiles/) | Codex read each company's scraped pages and filled in a structured profile (products, customers, end markets, business model, sales channels, tags), each item backed by a verbatim quote and checked with Pydantic. Plus a human-audit tool. | Started before the matching method was settled, so the field list was never agreed. It also depends on each student's Codex usage allowance. | 219/560 profiled, 166 failed on the usage limit, 17 skipped, about 158 not tried. Audit of 20 SIC 35 companies: 85-100% "yes + partly" per field. |
| [`comps_first_pass/`](comps_first_pass/) | Port of Riya's comps notebook (TF-IDF, LSA, embeddings, combined score) and an embeddings-only notebook on the scraped page text. Includes a write-up draft. | The real matching method is being designed separately. | PCTY: NDCG@20 0.90 with embeddings (random: 0.02). Only PCTY has peer labels. |
| [`collect_descriptions_v0/`](collect_descriptions_v0/) | The first collection script: one text blob per company, tried on SIC 35. | Superseded by `website_scrape/`. Its outputs include 12 hand-written descriptions, which the project no longer allows. | 38 SIC 35 companies (26 scraped, 12 by hand). |

Outputs, all outside Git:

| folder | contents |
|---|---|
| `outputs-local/scraps/codex_profiles/` | `step2_extract/` (Codex prompts, raw answers, profiles), `final_tables/` (`matching_inputs.csv`, `financial_fields.csv`, `validation_report.csv`), `step3_audit/` (audit sheets and scores), `logs/` |
| `outputs-local/scraps/comps_first_pass/` | `pages/`, `profiles/` (script runs), `notebook_embed/<run time>/` (notebook runs), `cache/` (embeddings), `history/` |
| `outputs-local/scraps/scrape_6page_partial_2026-10-17/` | an early 6-pages-per-site scrape, stopped partway |

## Worth reusing

- `comps_first_pass/peer_labels.csv`: graded PCTY peers, written before any
  ranking was seen. Any matching method can be checked against them.
- `comps_first_pass/` results are a baseline that a new matching method
  should beat on the same checks.
- `codex_profiles/` masking (`name_variants`, `mask`) hides a company's own
  name and domain in its text.
