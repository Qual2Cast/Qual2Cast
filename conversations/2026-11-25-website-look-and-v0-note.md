# 2026-11-25: website look, the 10/28 v0 note quoted, acknowledgements (site/)

Michael, with Claude Code. Branch `michael/site`, PR to `main`. Follows `2026-11-25-website-scaffold.md`.

## Decided (Michael)

- **Look:** Rational AI's palette and type (rationalai.co: Source Serif 4, IBM Plex Sans and Mono, navy-slate ink on
  cool paper, their blue #24628F as the one accent) in a field-guide book frame (tab index on the sidebar's edge,
  large chapter numeral, ruled plates). Not their logo, name, contour motif or layout. Aziz has not been asked about
  the resemblance yet.
- One accent, no per-chapter colours. Dark mode by a sidebar toggle, light by default; dark is a neutral near-black
  (#121416, sidebar too) with navy as the accent.
- Charts keep matplotlib defaults. Unwritten "To write" boxes are a plain dashed outline, no colour.
- Authors on the first page: the nine real names (English name first, Chinese name in brackets for Richard, Eric and
  Fiona), each linked to GitHub, in an even grid. Eric links to `Yikai-Li` (not `EFL-YL`).
- **The 10/28 note** ("10/28 Note: Qual2Cast v0", the last major mentor check-in) is quoted word for word, section by
  section, at the end of the chapter each section belongs to; no change to its language.
- **v1:** Michael's own note, grammar corrected with his permission, closes the Introduction: v1 was hill-climbing and
  new metrics, v2 streamlines development, so the book quotes v0 and covers v2 and does not write up v1.
- **Acknowledgements:** its own unnumbered page after chapter 7 (thanks to Aziz), draft owner Eric.

## Built

- `site/theme.scss` (every colour a token; fonts; rules for the rail, opener, plates, tables, drafts, authors,
  excerpts), `site/theme-dark.scss` (dark tokens), `site/_plates.html` (styling hooks only: caption labels, short
  table cells), `site/fonts/` (self-hosted, SIL OFL 1.1). `site/styles.css` removed.
- `site/PRODUCT.md`, `site/DESIGN.md` (+ `.impeccable/design.json`), `site/.impeccable/surfaces/quarto-yml.md`.
- Excerpts (`::: {.excerpt}`, `site/README.md` rule 4): section 1 in Data; 2, 3, 5, 8 in Describing a company;
  4, 4.1, 9 in Finding comps; 6, 7 in Judging comps; 10, 11 in Limits and next steps. The note's links are kept; its
  "#10. Assumptions and Limitations"-style references link across chapters (ids `v0-<section>`). Figure 5.1 and
  Barbara's two screenshots were taken from the note's PDF into `site/excerpts/2026-10-28-note/` (alt text
  `ALT TODO`). Left out: the note's header (team list, repo) and its part headings.
- `check.py` skips `.excerpt` blocks in the typed-number lint (a test covers it); `10/28` is on the allowlist.
- The "how we got here" box in Finding comps now covers only the v0 → v2 switch and points to the Introduction.

## Tests and checks

- 51 site tests pass; `check.py` OK in draft (37 pins, 0 problems; 36 placeholders in 11 pages; 0 typed numbers).
- Every word of the excerpts matches the PDF's text (a word diff; the only differences are caption positions and the
  PDF's page split of Table 6.1).
- Rendered locally; looked at light and dark at laptop width; no page overflows at phone width (wide quoted tables
  scroll inside themselves). No model or API calls; data unchanged.

## Open issues

1. The excerpts link the "11/1 Deliverable Tables" Google Sheet (the note's own link): once the site is public, so is
   the link. Remove it if the sheet should stay private.
2. The note's Table 2.1 lists the same twelve facets as the facets table built from data in Describing a company;
   both are kept.
3. Ask Aziz whether he minds the site resembling Rational AI's look.
4. The design finish review was last run on an earlier version of the look.

## Next

The team writes the "To write" boxes, captions and alt text (owners in `site/README.md`); numbers freeze Nov 30.
