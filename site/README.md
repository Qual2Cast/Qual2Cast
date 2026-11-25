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

**CI** ([`.github/workflows/site.yml`](../.github/workflows/site.yml)) runs on every push to `main` that touches
`site/`, `outputs-local/`, `v2/current.toml`, `pyproject.toml`, `uv.lock` or the workflow: it installs the light
`site` dependency group (`uv sync --locked --only-group site`: pandas, matplotlib, Jupyter, no torch), runs
`scripts/check.py`, renders with Quarto 1.9.37 and deploys `_site/` to GitHub Pages. A pull request touching the same
paths is checked and rendered but not deployed. Built HTML is never committed.

**Checks** (`scripts/check.py`, before the render; one line per problem, then a summary):

- *pins*: every file in `pins/*.toml` exists, is tracked by git and matches its hash. A problem always fails.
- *placeholders*: `.prose-todo` divs, `CAPTION TODO` and `ALT TODO`, counted per page. Listed always; they fail only
  in release mode.
- *typed numbers*: digits in the prose (not code, facts, attributes, cross-references or placeholder boxes), listed
  as warnings, never failing; on a pull request they show on the changed lines. A token that is a name, not a
  quantity (`v3`, `E1-E10`), goes in `scripts/number_allowlist.txt`.

Run them locally (the main environment is fine):

    uv run python site/scripts/check.py              # draft or release, as release.toml says
    uv run python site/scripts/check.py --release    # what would block a release build now
    uv run pytest site/tests -q                      # tests of the checks and of facts/common.py

**Release mode:** set `release = true` in `release.toml` for the Dec 3 and Dec 8 builds. CI then fails, and nothing
deploys, while any placeholder remains.

**facts.csv:** after every render (full, single page or preview), `scripts/write_facts.py`, a Quarto post-render
script, writes every named fact (name, printed text, value, source pins and files, as-of date) to `_site/facts.csv`,
published with the site at `/facts.csv`. It loads all chapter modules together, so a fact name defined in two chapters
fails there.

**Render as CI does**, in the light environment (to make sure no chapter needs a heavy package). From the repository
root, in Git Bash or a Mac terminal:

    UV_PROJECT_ENVIRONMENT=.venv-site uv sync --locked --only-group site
    UV_PROJECT_ENVIRONMENT=.venv-site uv run --no-sync quarto render site
    rm -rf .venv-site                                # a throwaway environment; git ignores it

**Once, by a repository admin:** enable Pages under Settings > Pages > Build and deployment > Source: GitHub Actions.
Until then the deploy job fails; the checks and the render still run.
