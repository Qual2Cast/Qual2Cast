# Handoff: growth-signal recall widening

## What changed

The first rule set was high-precision but missed common press-release
phrasing for contracts, hiring, layoffs, expansion, and credit events.
Collection also skipped `/stories/` and `/media-center/` articles and did
not follow listing pagination.

Completed:

- Wider action+object rules in `growth_signals/extract_events.py`, still
  abstaining on marketing language, job-board boilerplate, note issuance
  without a rating action, and “reducing data entry for employees.”
- Careers/Jobs pages may now yield only `hiring` or `layoff` events.
- Article URL shapes include `/stories/` and `/media-center/`.
- Collector fetches one same-site listing continuation (`rel=next` or
  Next/Older) when more articles are needed.
- Default `--max-articles` is 10.

## Checks

- `cd growth_signals && python -m pytest tests -q`: 84 passed.
- Phrase probe confirmed previous misses now hit, and the intended
  negative controls still abstain.

## Data version

- No source snapshot was read or modified.
- No live recrawl was run; `outputs-local/growth_signals/` is still empty
  in this workspace.

## Unresolved

- Third-party job boards (Workday, Greenhouse) still need an allow-list
  and attribution policy.
- Credit events remain rare on company sites; rating agencies are not
  collected.
- IR-host fallback is still a public-company convenience and does not
  apply to private targets.
- No labeled recall study on a new live sample after these rule changes.

## Next recommended action

Re-run the five-company pilot (and a few store/restaurant and industrial
names) with `--max-articles 10`, then review the new events against the
saved article evidence before any 560-company collection.
