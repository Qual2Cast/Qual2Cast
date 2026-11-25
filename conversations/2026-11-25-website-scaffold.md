# 2026-11-24/25: project website scaffold (site/)

Michael, with Claude Code. Branch `michael/site` (PR to `main`).

## Decided (medium grill, 2026-11-24)

- **What:** a Quarto book in `site/`, like Michael's EDAV site (bruno-neira/AI-Pulse), but Python, not R. Built by a
  GitHub Action, served on GitHub Pages at https://qual2cast.github.io/Qual2Cast/ (enabled by Michael, source:
  GitHub Actions). Built HTML is never committed.
- **For:** Aziz, handover **Dec 3**; class presentation **Dec 8** (must be airtight). Slides are made separately by
  the team; they copy numbers from the site's `facts.csv`.
- **About:** comp quality, whether comp B matches target A. EV/EBITDA appears once, as context. No single-target
  walk-through. No interactive comp explorer. v2 is the method; earlier versions get one "how we got here" box in
  chapter 4.
- **People write every sentence.** Agents build the scaffold, checks, facts and figures; no prose, captions or alt
  text. Unwritten slots are `.prose-todo` boxes, `CAPTION TODO`, `ALT TODO`.
- **No typed numbers.** Text prints named facts (`{python} f.name`) from `site/facts/ch*.py`, computed from files
  pinned with sha256 in `site/pins/ch*.toml`; a changed file stops the build until it is re-pinned on purpose.
- **Freeze:** numbers Nov 30 for Dec 3; one refresh by Dec 5 (rubric v3 labels, X-learner rerun); wording only
  after. `site/release.toml` holds the as-of date and the release switch.
- Chapter owners in `site/README.md` are drafts only.

## Built

- Seven chapters (Introduction, Data, Describing a company, Finding comps, Judging comps, Results, Limits and next
  steps) and three appendices (Glossary, Team, How to reproduce), each with draft-owner placeholders.
- 131 named facts from 37 pins, 8 figures, 4 tables, a pipeline diagram (Mermaid).
- `site/scripts/check.py` (pins, placeholders, a warn-only typed-number lint; release mode fails on placeholders),
  `pin.py`, `write_facts.py` (post-render → `_site/facts.csv`).
- `.github/workflows/site.yml`: on PR check + test + render; on push to `main` also deploy. Light `site` dependency
  group in `pyproject.toml` (no torch).
- Built by three parallel agents in hand-made worktrees (the Agent tool's worktree isolation fails on this machine).

## Tests and checks

- Full CI sequence run locally in a throwaway light env (`uv sync --locked --only-group site --only-group dev`,
  torch not installed): check.py OK (37 pins, 0 problems; 32 placeholders, allowed in draft), 50 site tests pass,
  all 10 pages render, `facts.csv` has 131 facts. Not yet run on Linux / GitHub Actions (the PR is the first run).
- No model or API calls. Data: `company_list_v3`; runs as pinned in `v2/current.toml`.

## Doc fixes the fact checks found (committed)

- README: no matching vs the four v0 routes on the same 107 holdout targets is 40.1% vs 36.8-37.9% (it compared
  different target sets: "about 40% vs 33-38%"); 533 usable websites (was 532).
- `v2/05_agent_grading/GRADING_REVIEW.md`: agent ≥ 1 vs Matthew kappa 0.36, not 0.37.

## Open issues

1. Stale docs, not fixed (the site uses computed numbers): the round-1 trait table in `v2/02_profiles/README.md` and
   PROJECT_STATE covers 531 companies, not 533 (yes rates move 0.1-0.3 points; "knows 525" is 527);
   `website_scrape/README.md` counts differ from `scrape_log.csv`; `v2/01_universe/scripts/split.py`'s docstring
   still says size-stratified (the current split is SIC2).
2. Not wired: the facet hand-check rate ("about 1 in 4") comes from an untracked file made on the old Haiku fills;
   financial-language removals are logged per page only (a tracked summary would make them pinnable).
3. Authors: a "finding" is decided by the shuffle test with BH, not the interval (large customers' direct-peer
   interval crosses zero but is a finding). `@tbl-traits` quotes the model prompt wording; drop that column if
   unwanted.
4. Rubric v3 refresh (by Dec 5): set the ledger cohort in `site/facts/ch6_results.py`, re-pin the ledger and trait
   runs, add per-question v3 kappas to chapter 5.
5. CI pins `actions/checkout@v7`, `astral-sh/setup-uv@v10.3.3`, Quarto 1.9.37; verify on the first PR run.

## Next

Merge the PR (deploys the draft site publicly); the team writes the chapters; UI grill on the look; set
`release = true` for the Dec 3 build.
