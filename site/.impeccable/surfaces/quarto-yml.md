---
version: 1
slug: "quarto-yml"
primary_target: "_quarto.yml"
related_targets: ["theme.scss","theme-dark.scss","_plates.html"]
---

# Surface brief: Qual2Cast site (all book pages)

Scope: every page of the Quarto book in `site/` (seven chapters, an unnumbered Acknowledgements page, three
appendices). Mode: Read.

Audience and job: Aziz reads alone on a laptop after the 2026-12-03 handover; the team may present from the site on a
classroom projector on 2026-12-08. The reader wants to know whether the method finds comps that are really like the
target, and to trust every number.

Constraints: the book shape stays (sidebar, prev/next, numbered chapters/figures/tables, search). Agents write no
prose, captions or alt text; the theme adds no words. Drafting placeholders stay visible. Implemented as a Quarto SCSS
theme plus config only; chapter .qmd files are not edited for styling.

Unresolved: matplotlib figure styling (fonts, palette) to match the theme; whether a front page is added later;
Aziz's view on the site resembling Rational AI's look.

## Direction contract

THESIS: The book is a field guide to look-alike companies: each chapter is a thumb-indexed section and each figure or
table a numbered plate. It refuses the stock Bootstrap book (grey sidebar text, blue links, cosmo headings).

OWN-WORLD: Rational AI's public palette and type (rationalai.co), chosen by the user on 2026-11-25, inside a field-guide
book frame. Cool paper #F7F9FB, rail #EFF3F7, navy-slate ink #0E1B26 with secondary #5C6B76, hairlines #E4E9EC, and one
accent, their blue #24628F (blue-600; blue-500 fails 4.5:1 for small text). Quiet grey tabs #C7D0D6 on the rail's edge;
the current chapter's tab, chapter numerals, plate rules and link underlines in the accent. Source Serif 4 for the site
name, chapter titles, numerals and headings; IBM Plex Sans for text, labels and navigation (85% width in tables);
IBM Plex Mono for code. Dark mode (sidebar toggle, light by default): a neutral near-black ground #121416 with grey
text #E6E8EA; the rail is the same near-black behind a hairline; navy is the accent (user's choice): quiet tabs #2C3E4F
and the marks #4A90CC; figures sit on white plates. Drafts: plain 1px dashed hairline boxes, no colour (user's choice);
CAPTION TODO and ALT TODO unstyled. Quoted excerpts (the 10/28 v0 note): a 1px hairline on the left, the document's
own title on top, never edited. Not borrowed: their logo, name, contour motif or page layout.

STORY: The reader sees where they are (the tab), reads calm black-on-white text, finds numbers in tabular figures, and
can tell unwritten slots from finished ones at a glance.

FIRST VIEWPORT: Docked index rail on the left whose right edge is a column of grey chapter tabs, the current one widened
in the accent; the chapter opens with an oversized condensed numeral in the accent beside the title, an
as-of line in small caps under a hairline; the reading column follows at about 70 characters.

FORM: Field guide (thumb index, plate labels), position 5 on the ordered list; seed:1c595b9f2278aa2d.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
