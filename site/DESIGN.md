---
name: Qual2Cast
description: The Qual2Cast report site, a Quarto book in Rational AI's palette and type, set out like a field guide.
colors:
  accent: "#24628f"
  ink: "#0e1b26"
  ink-2: "#5c6b76"
  paper: "#f7f9fb"
  rail: "#eff3f7"
  rule: "#e4e9ec"
  rule-strong: "#c7d0d6"
  code-bg: "#f1f4f6"
  tab: "#c7d0d6"
  figure-plate: "#ffffff"
  accent-dark: "#4a90cc"
  ink-dark: "#e6e8ea"
  ink-2-dark: "#9aa3a9"
  paper-dark: "#121416"
  rail-dark: "#121416"
  rule-dark: "#2a2e32"
  rule-strong-dark: "#3a4046"
  code-bg-dark: "#1c1f22"
  tab-dark: "#2c3e4f"
typography:
  display:
    fontFamily: "'Source Serif 4', Georgia, 'Times New Roman', serif"
    fontSize: "clamp(5.85rem, 4.16rem + 5.2vw, 7.8rem)"
    fontWeight: 400
    lineHeight: 0.8
    letterSpacing: "-0.02em"
    fontFeature: "\"lnum\", \"tnum\""
  headline:
    fontFamily: "'Source Serif 4', Georgia, 'Times New Roman', serif"
    fontSize: "clamp(2.25rem, 1.6rem + 2vw, 3rem)"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "-0.015em"
  title:
    fontFamily: "'Source Serif 4', Georgia, 'Times New Roman', serif"
    fontSize: "1.65rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title-small:
    fontFamily: "'Source Serif 4', Georgia, 'Times New Roman', serif"
    fontSize: "1.3rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  site-name:
    fontFamily: "'Source Serif 4', Georgia, 'Times New Roman', serif"
    fontSize: "1.35rem"
    fontWeight: 600
    letterSpacing: "-0.005em"
  body:
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.65
    fontFeature: "\"lnum\""
  nav:
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.3
  caption:
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.45
  table:
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    fontFeature: "\"lnum\", \"tnum\""
    fontVariation: "\"wdth\" 85"
  label:
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    letterSpacing: "0.04em"
  label-meta:
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    letterSpacing: "0.08em"
  label-small:
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    letterSpacing: "0.1em"
  code:
    fontFamily: "'IBM Plex Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace"
    fontSize: "0.82em"
    fontWeight: 400
rounded:
  xs: "2px"
  sm: "3px"
  md: "4px"
spacing:
  cell: "0.5rem"
  rail-pad: "1rem"
  block: "2rem"
  section: "2.75rem"
  page-end: "3rem"
  measure: "38rem"
  grid-sidebar: "280px"
  grid-body: "720px"
  grid-margin: "230px"
components:
  link:
    textColor: "{colors.ink}"
  link-hover:
    textColor: "{colors.accent}"
  chapter-numeral:
    textColor: "{colors.accent}"
    typography: "{typography.display}"
  chapter-title:
    textColor: "{colors.ink}"
    typography: "{typography.headline}"
  as-of-line:
    textColor: "{colors.ink-2}"
    typography: "{typography.label-meta}"
  rail:
    backgroundColor: "{colors.rail}"
    width: "{spacing.grid-sidebar}"
  rail-link:
    textColor: "{colors.ink}"
    typography: "{typography.nav}"
    padding: "0.45rem 1.75rem 0.45rem 0"
  rail-link-hover:
    textColor: "{colors.accent}"
  thumb-tab:
    backgroundColor: "{colors.tab}"
    width: "6px"
  thumb-tab-hover:
    backgroundColor: "{colors.ink-2}"
    width: "12px"
  thumb-tab-active:
    backgroundColor: "{colors.accent}"
    width: "22px"
  plate-caption:
    textColor: "{colors.ink-2}"
    typography: "{typography.caption}"
    padding: "0.45rem 0 0"
  plate-rule-stub:
    backgroundColor: "{colors.accent}"
    width: "3rem"
    height: "3px"
  table-head:
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    padding: "{spacing.cell}"
  table-cell:
    textColor: "{colors.ink}"
    typography: "{typography.table}"
    padding: "{spacing.cell}"
  todo-box:
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "1rem 1.4rem 0.9rem"
  code-inline:
    backgroundColor: "{colors.code-bg}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.sm}"
    padding: "0.1em 0.3em"
  search-field:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.md}"
---

# Design System: Qual2Cast

Source of truth: `theme.scss` (light tokens and every rule), `theme-dark.scss` (dark values of the same tokens),
`_plates.html` (adds spans and classes, no words), `_quarto.yml` (book, docked sidebar, light/dark themes), `fonts/`.
Product facts: `PRODUCT.md`. Frontmatter values are normative; `-dark` keys are the `theme-dark.scss` values.

## Overview

**Creative North Star: "The Field Guide to Look-Alikes"**

A Quarto book set out like a field guide. Chapters are thumb-indexed sections, with tabs on the right edge of the
sidebar. Each chapter opens with an oversized numeral, and each figure and table is a numbered plate under a rule.
Flat, quiet and text-first: navy-slate ink on cool paper, one blue accent, hairline rules. Light by default; a sidebar
toggle switches to dark mode, which uses a neutral near-black ground with grey text and keeps navy for the
accent.

Brand commitment (PRODUCT.md, 2026-11-25): the palette and type follow Rational AI's public site (rationalai.co).
That means Source Serif 4, IBM Plex Sans and Mono, navy-slate ink on cool paper, and their blue as the only accent.
Their logo, their name as a brand, their contour motif and their page layout are not used. The frame stays
Qual2Cast's. There is no Columbia branding.

People write every sentence. The theme styles what authors wrote and adds no words. Drafting placeholders are
plain (a grey dashed outline around the authors' own text) because they are temporary.
Rejected looks: the stock Quarto/Bootstrap book (grey sidebar text, blue links, cosmo headings), marketing gloss,
dashboard panels and KPI tiles.

**Key Characteristics:**
- Thumb-index tabs on the sidebar's edge; the current chapter's tab is wide and in the accent.
- An oversized serif chapter numeral in the accent, set beside the title.
- Figures and tables as plates: a 1px ink rule over the caption, with a 3rem accent stub at its left end.
- Tabular lining figures wherever numbers are compared.
- Prose held to a 38rem measure; plates take the full body width.
- No shadows; structure comes from hairlines and the sidebar's tone.

## Colors

Navy-slate ink on cool paper with one blue accent. Every colour is
a `$q2c-*` `!default` token in `theme.scss`; `theme-dark.scss` gives each one its dark value.

### Primary
- **Index Blue** (accent, #24628f; dark #4a90cc): marks where the reader is and the numbers they point to. Used for
  the current chapter's tab, chapter numerals, section numbers (h2/h3), the plate rule stub, link underlines (60% mix)
  and link hover, the active "On this page" border, the focus outline, the caret, the selection tint (24% over paper)
  and the table row hover (7% over paper). Contrast 6.18:1 on paper and 5.85:1 on the sidebar. The dark value is a
  navy blue lightened to pass 4.5:1 (5.41:1 on the ground and on the sidebar, which shares the ground's near-black). Rational AI's blue-500 is not
  used because it is under 4.5:1 for small text.

### Neutral
- **Navy-Slate Ink** (ink, #0e1b26; dark #e6e8ea): body text, headings, link text, plate numbers, the rule over each
  caption, and the 1.5px rule under table heads. 16.53:1 on paper (dark 15.03:1).
- **Slate Grey** (ink-2, #5c6b76; dark #9aa3a9): captions, table column heads, the as-of line, chapter numbers in the
  sidebar, "On this page", title meta and sidebar icons. 5.21:1 on paper and 4.93:1 on the sidebar, the lowest text
  pair in the system (dark 7.20:1 and 6.80:1).
- **Cool Paper** (paper, #f7f9fb; dark #121416, a neutral near-black): page background, inputs, search field.
- **Rail Paper** (rail, #eff3f7; dark #121416, the same near-black as the ground, set off by a hairline): the docked sidebar and the narrow-screen
  header bar.
- **Hairline** (rule, #e4e9ec; dark #2a2e32): the h2 underline, table row rules, inactive TOC border, and the rule under
  the header bar.
- **Strong Hairline** (rule-strong, #c7d0d6; dark #3a4046): the as-of rule, the rule above prev/next, input and search
  borders.
- **Code Wash** (code-bg, #f1f4f6; dark #1c1f22): inline code.
- **Quiet Tab** (tab, #c7d0d6; dark #2c3e4f, navy-tinted): the other chapters' tabs and the scrollbar thumb. A separate
  token from rule-strong, even though the light values match.
- **Figure Plate** (figure-plate, #ffffff): dark mode only. Sits behind figure images, which are drawn on white.

### Named Rules
**The One Accent Rule.** Blue marks position and numbering only: where you are (current tab, active TOC entry, hover,
focus) and what to point at (chapter and section numerals, plate stubs, link underlines). Nothing else is blue.

**The Plain Drafts Rule.** An unwritten slot (the "To write" box) gets a 1px dashed Strong Hairline outline and
nothing else: no fill, colour, chip or mark. CAPTION TODO and ALT TODO read as the authors' plain placeholder text.

**The Token-Only Rule.** Every colour is a `$q2c-*` token with a value in both theme files. Tints are `color-mix()` of
the accent with paper or transparent, never new literals. The one literal is the dark-mode white figure plate.

## Typography

**Display Font:** Source Serif 4 (with Georgia, Times New Roman, serif), variable weight 200-900, optical sizing on.
**Body Font:** IBM Plex Sans (with -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif), variable weight 100-700,
width 85-100%.
**Label/Mono Font:** IBM Plex Mono 400 and 500.

All faces are self-hosted woff2 files in `fonts/` (SIL OFL 1.1, Latin subset, `font-display: swap`).

**Character:** a bookish serif for names and numerals over a plain technical sans for reading and navigation.

### Hierarchy
- **Display** (400, 2.6× the chapter title, 0.8, -0.02em): the chapter numeral, in the accent with tabular lining
  figures, baseline-aligned left of the title.
- **Headline** (600, clamp(2.25rem, 1.6rem + 2vw, 3rem), 1.05, -0.015em, balanced wrap): chapter titles. On the
  first page, a title without a chapter number drops to 1.5rem and reads as a running title.
- **Title** (600, 1.65rem, 1.2): h2, with a hairline underneath and its section number in the accent. h3 is
  **Title Small** (600, 1.3rem).
- **Site name** (600, 1.35rem serif): the sidebar title.
- **Body** (400, 1.0625rem, 1.65): reading text in lining figures, hyphens manual, limited to the 38rem measure
  (about 70-75 characters).
- **Nav** (400, 0.9375rem, 1.3): sidebar links. The chapter number is 600, tabular, in Slate Grey, or in the accent
  when active.
- **Caption** (400, 0.875rem, 1.45): plate captions. The "Figure 6.1:" number is 600 Ink, tabular.
- **Table** (400, 0.875rem, Plex Sans at 85% width): table text, tabular lining figures.
- **Label** (uppercase, Plex Sans): column heads 0.75rem/600/0.04em; the as-of line 0.75rem/500/0.08em; the "On this
  page" title 0.75rem/600/0.12em; sidebar group names ("Appendices")
  0.6875rem/600/0.14em.
- **Code** (Plex Mono 400, 0.82em): inline code and fact names.

### Named Rules
**The Tabular Figures Rule.** Numbers that get compared use tabular lining figures: tables, chapter and section
numerals, sidebar numbers, plate numbers and the fact lists in "To write" boxes. Body text uses lining figures.

**The Serif Names Rule.** Source Serif 4 carries names and numerals: the site name, headings, chapter numerals and
prev/next chapter numbers. IBM Plex Sans carries reading, labels and navigation, and is narrowed only in tables (85%)
and in draft fact lists (92%).

## Layout

- Quarto book with a docked sidebar. Grid: sidebar 280px, body 720px, right margin 230px ("On this page"). Below
  992px the sidebar collapses into a header bar (sidebar tone with a hairline under it) holding breadcrumbs and the
  menu toggle.
- Paragraphs, lists, blockquotes and h2-h4 are held to the 38rem measure. Figures, table plates and cell output take
  the full body width. A "To write" box is the measure plus 2.8rem.
- Chapter opener: numeral and title share a baseline. The title meta is 0.8125rem Slate Grey, and the as-of line
  closes the opener on a strong hairline with 2.25rem below it.
- Rhythm: h2 has 2.75rem above and 0.75rem below; h3 has 2rem above and 0.5rem below. Plates and "To write" boxes take
  a 2rem block margin. Table cells are padded 0.5rem. Prev/next sits 3rem down, under a strong hairline.
- Thumb index: the sidebar has 1rem of right padding. Each tab hangs into it, flush with the sidebar's right edge and
  inset 3px from the top and bottom of its link.
- Table plates are as wide as their table (min(100%, 24rem) up to 100%), and the caption wraps to that width. Cells
  of 24 characters or fewer never wrap. Below 768px every cell stays on one line and the table scrolls sideways
  inside its plate.

## Elevation & Depth

Flat. The theme adds no shadows and removes Bootstrap's table-cell shadows. Depth comes from tone and rules. In light
mode the sidebar is one step deeper than the paper; in dark mode it shares the ground's near-black, set off by a hairline. The rules are
hairlines, the 1.5px ink rule under table heads, and the 1px ink rule over captions.
Keyboard focus is a 2px accent outline offset 2px, not a glow.

### Named Rules
**The Rules Not Shadows Rule.** Structure comes from lines and the sidebar's tone. Nothing floats.

## Shapes

Square and ruled. Radii are small: 2px (dark-mode figure plate), 3px (inline code), 4px ("To
write" box, search field). Line weights: 1px hairline, 1.5px for emphasis (table head rule),
3px for the accent stub on plates. Dashed lines mean "unwritten".

## Components

### Thumb index (sidebar navigation)
- **Character:** a field guide's edge tabs, one per chapter.
- **Tabs:** each chapter link ends in a Quiet Tab band (6px) on the sidebar's edge. Hover widens it to 12px in Slate
  Grey; the current chapter gets 22px in the accent. Width animates over 160ms cubic-bezier(0.22, 1, 0.36, 1) and
  colour over 160ms ease-out, with no motion under reduced-motion.
- **Links:** chapter number and title side by side, so a long title wraps under itself. Ink, accent on hover, 600 Ink
  when active. Group names ("Appendices") are small uppercase labels with no tab.
- **Top row:** the site name in serif, with the GitHub and light/dark icons in Slate Grey (accent on hover) on the same
  row.

### Chapter opener
- Accent numeral (Display) beside the title (Headline), then the as-of line ("Results as of <date>", written by
  authors on every chapter) in small uppercase Slate Grey over a strong hairline.

### Plates (figure and table captions)
- Left-aligned caption in Caption type, Slate Grey, with a 1px ink rule above it and a 3rem × 3px accent stub over
  the rule's left end. `_plates.html` wraps the "Figure 6.1:" / "Table 6.1:" label so it sets in 600 Ink. Table
  captions sit on top; figure captions sit below.
- Dark mode: figure images sit on white plates (0.6rem padding, 2px radius).

### Tables
- Ruled, no zebra striping, transparent cells. Column heads in uppercase Label type over a 1.5px ink rule; rows
  separated by hairlines; cells padded 0.5rem; row hover is a 7% accent tint. Column widths follow content, not the
  Markdown source.

### Links
- Ink text with a 1.5px underline (accent at 60%, offset 0.18em). Hover turns text and underline fully accent over
  120ms ease-out. Sidebar, TOC and prev/next links have no underline; prev/next underlines the chapter title on hover.

### Unwritten slots
- **"To write" box:** a 1px dashed Strong Hairline border, 4px radius, no fill, page ink at 0.9375rem/1.55,
  padding 1rem 1.4rem 0.9rem. The author's bold lead stays plain bold. Fact lists use Plex Sans at 92% width,
  0.875rem, tabular figures.
- **CAPTION TODO / ALT TODO:** no styling.

### Excerpts (a dated team document quoted word for word)
- `::: {.excerpt}`: the team's 10/28 note to Aziz, quoted in the chapter each section belongs to, after the chapter's
  own content. A 1px Strong Hairline on the left, 1.4rem in (0.9rem on phones); no fill, no top or bottom rule.
- First line: the document's own title as a `.excerpt-source` span, 0.8125rem, 600, Slate Grey (not uppercased, so
  the title reads as written). The document's own numbered headings ("1. Data Prep", "4.1. Results") are unnumbered
  and kept out of the page TOC: h2 at 1.3rem with no rule, h3 at 1.1rem, ids `v0-<section>` so the note's
  cross-references ("#10. Assumptions and Limitations", "OQ #2.3") link across chapters.
- Its tables are as wide as their content (min 24rem), long cells wrap, and on phones a wide one scrolls sideways on
  its own. Their quoted captions ("Table 8.1: ...") get the plate treatment, label included. Its images carry a 1px
  hairline.
- The text is never edited (typos and typed numbers stay), so `check.py` does not look for typed numbers inside.

### Authors (first page, under the book title)
- The book's `author` list in `_quarto.yml` (each with a GitHub `url`), under Quarto's own "Authors" label in
  label-small uppercase. Names sit in an even grid (columns of at least 11rem, gaps 0.55rem × 2rem) within the text
  measure, Plex Sans 0.9375rem, ink, no underline; each is followed by the Bootstrap Icons GitHub mark in Slate Grey,
  and name and mark take the accent on hover.

### Inline code
- Plex Mono at 0.82em on Code Wash, padding 0.1em 0.3em, 3px radius, Ink text.

### On this page, prev/next, search
- **On this page:** Slate Grey links, no underline. The active entry is Ink with an accent left border. The title is
  a small uppercase label.
- **Prev/next:** the chapter number is in the serif, 600, accent, 1.3em. A strong hairline sits above, 3rem down.
- **Search:** paper field, strong-hairline border, 4px radius.

## Do's and Don'ts

### Do:
- **Do** take every colour from a `$q2c-*` token and give it a dark value in `theme-dark.scss`.
- **Do** keep the accent on position and numbering only (The One Accent Rule).
- **Do** set compared numbers in tabular lining figures.
- **Do** hold prose to the 38rem measure and let figures and tables take the full body width.
- **Do** add styling hooks as spans and classes only, the way `_plates.html` does.
- **Do** keep text at 4.5:1 or better on paper and on the sidebar, in both modes (lowest today: light Slate Grey on
  the sidebar, 4.93:1; dark accent on the ground and sidebar, 5.41:1).
- **Do** keep figures on white plates in dark mode.

### Don't:
- **Don't** add words from the theme: no CSS-generated text, labels or headings. Placeholders stay the authors' own text.
  Empty `content: ""` for drawn rules and tabs is fine.
- **Don't** use Rational AI's logo, name, contour motif or page layout.
- **Don't** use dashed lines for anything but unwritten slots.
- **Don't** edit the words inside an `.excerpt`, or add a label to it beyond the document's own title.
- **Don't** stripe tables or fill cells; use rules, plus the 7% accent row hover.
- **Don't** add shadows.
- **Don't** build dashboard panels or KPI tiles.
- **Don't** put uppercase labels above headings as kickers. Small uppercase is for metadata, column heads, navigation
  group names.
- **Don't** lighten the light-mode accent toward Rational AI's blue-500; it falls under 4.5:1 for small text.
