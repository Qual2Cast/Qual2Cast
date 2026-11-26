# Product

<!-- impeccable:product-schema 1 -->

Product record for the Qual2Cast website (`site/`), used by design work on the site. The method itself is described
in the repository README, PROJECT_STATE.md and v2/; this file covers only the website.

## Platform

web

## Users

- **Aziz Lookman (Rational AI), the project mentor.** Receives the site at the handover on 2026-12-03 and reads it
  alone, on a laptop, at his own pace. Works in valuation; reads equity research and company filings daily. Strict
  about AI-written text.
- **The Qual2Cast team.** Uses the site to prepare the class presentation on 2026-12-08. If the site is refined
  enough, the team presents from it directly, projected on a classroom screen.
- **Course staff and classmates**, reached by link (confirmed only as a secondary audience).

## Product Purpose

A report, in book form, on whether the team's method finds good comparable companies ("comps"): given target
company A, is comp B a business like it? Comp quality is judged against human reviewer labels. EV/EBITDA appears
once, as context; the site is not about valuation accuracy. Success is a reader who understands the method, trusts
every number, and can see where it works and where it doesn't.

## Positioning

- Comps are found from what a company's own website says about its business, not from industry codes or financials.
- Every number on the site is computed at build time from files pinned by sha256; no number is typed by hand.
- People write every sentence; agents build structure, checks, facts and figures only.

## Operating Context

- Quarto book in `site/`, Python only, rendered by GitHub Actions and served on GitHub Pages
  (qual2cast.github.io/Qual2Cast). Built HTML is never committed. Authors preview with `quarto preview`.
- Freeze: numbers 2026-11-30 for the handover; one refresh by 2026-12-05; wording only after.
- Slides for 2026-12-08 are made separately and copy numbers from the build's `facts.csv`.

## Capabilities and Constraints

- Seven chapters (Introduction, Data, Describing a company, Finding comps, Judging comps, Results, Limits and next
  steps), an unnumbered Acknowledgements page (thanks to the mentor), and three appendices (Glossary, Team, How to
  reproduce).
- The team's 10/28 note to Aziz (v0) is quoted word for word, section by section, at the end of the chapter each
  section belongs to (`.excerpt` blocks; site/README.md, rule 4). Why v1 gets little space (a content decision) is
  Michael's note at the end of the Introduction, so the reader knows before the first excerpt.
- **The book shape stays:** chapter sidebar with prev/next links, numbered chapters, figures and tables
  ("Figure 6.1"), search. No separate front page for now (it would need new human-written text).
- Drafts show visible placeholders: `.prose-todo` boxes listing named facts, `CAPTION TODO`, `ALT TODO`. They must be
  easy to spot while drafting; a release build refuses to deploy while any remain.
- Every page shows "Results as of <date>".
- Figures are matplotlib, made by `site/facts/ch*.py`; one Mermaid diagram (the pipeline). Tables are pandas →
  Markdown.
- Out of scope: an interactive comp explorer, a single-target walk-through.
- The repository and site are public.

## Brand Commitments

- Name: Qual2Cast. No logo of its own; the team's slides may borrow the site's colours and type.
- Look modelled on Rational AI's public site (rationalai.co), at Michael's request (2026-11-25): their palette and
  type (Source Serif 4, IBM Plex Sans and Mono, navy-slate ink on cool paper, their blue as the one accent). Not their
  logo, name as a brand, contour motif or page layout: the site stays Qual2Cast's. Aziz has not yet been asked about
  the resemblance.
- No Columbia branding.
- Must not read as: startup or marketing gloss, a default Quarto/Bootstrap template, an AI-generated page
  (decoration with no job), or a dashboard of panels and KPI tiles. It is a report people read.

## Evidence on Hand

- 131 named facts, 8 figures, 4 tables and 1 diagram (`site/facts/`, pinned sources in `site/pins/`).
- No photography, illustration, logo or testimonials exist; none may be invented.

## Product Principles

1. The numbers are the authority: show where each comes from, never decorate around it.
2. Human writing leads; the design frames it and never fills a gap with its own words.
3. Reads well alone on a laptop and holds up projected in a classroom.
4. One reading experience across all chapters; drafting placeholders are visible but clearly not the finished page.

## Accessibility & Inclusion

- Text and figure contrast must survive a classroom projector (WCAG 2.2 AA at minimum).
- Figures carry alt text written by the team (`ALT TODO` until then).
