# site/

The Qual2Cast website: a Quarto book, built by CI and served on GitHub Pages. Decided in a design session on
2026-11-24 (handoff in `conversations/`).

- **For:** Aziz Lookman (Rational AI), handover on **Dec 3**; the class presentation on **Dec 8** (slides are made
  separately and copy their numbers from `facts.csv`, see below).
- **About:** whether comp B matches target A. EV/EBITDA appears once, as context.

## Rules

1. **People write every sentence.** Agents build the scaffold, the build and checks, and the facts and figures;
   they write no prose, captions or alt text. A slot still to be written is a `::: {.prose-todo}` box; a figure
   caption still to be written is `CAPTION TODO`, alt text `ALT TODO`.
2. **No number is typed.** Text prints numbers from named facts: `{python} f.n_universe`. Each chapter's facts are
   in `facts/ch*.py`, computed from files pinned (with their sha256) in `pins/ch*.toml`. A pinned file that
   changes stops the build until someone re-pins it on purpose.
3. **Freeze:** numbers freeze Nov 30 for Dec 3; one refresh by Dec 5 for Dec 8; after Dec 5, wording only.
   `release.toml` holds the as-of date and the release switch.

## Draft owners

Nothing here is settled: change it freely.

| chapter | draft owner | checked by |
|---|---|---|
| 1 Introduction | Michael | |
| 2 Data | Richard | Fiona |
| 3 Describing a company | Richard | Fiona |
| 4 Finding comps (incl. the "how we got here" box) | Kethan | |
| 5 Judging comps | Michael | Barbara, Matthew |
| 6 Results | Kethan, Michael | |
| 7 Limits and next steps | Eric | |
| Appendix (glossary, team, how to reproduce) | Eric | |

## Working on it

    uv sync
    cd site
    uv run quarto preview        # live preview in the browser, reloads on save

Pin a new source file: `uv run python site/scripts/pin.py add <chapter> <name> <path>`; check all pins:
`uv run python site/scripts/pin.py verify`.

## Build and deploy

_To be filled in with the CI workflow._
