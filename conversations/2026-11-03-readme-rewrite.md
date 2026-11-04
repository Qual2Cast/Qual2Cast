# README rewrite and push

## Request

Push to GitHub, and rewrite the README so the deprecated pre-v0 material is gone: comprehensive but brief enough for
a reader without a technical background to understand the structure.

## Changes

- `README.md` rewritten (about 310 lines to about 130): plain-language purpose; the recipe as four steps with a
  diagram; training/holdout split; status table and results in words; folder map (v1 current, v0 the 2026-10-28
  record, pre-v0 reference only); uv setup; rules; one line per teammate; next steps; terms.
- Removed: pre-v0 sections (matching methods, ten-company pilot, growth signals, team memo, integrated workflow),
  the merged-PR history and the branch table. Their detail stays in `pre-v0/README.md`, `v0/README.md` and git history.
- Stale claim fixed: retrieval tier `R` is on `main` (it was listed as not integrated).
- Committed with the rest of the 2026-11-03 working tree (v1/, uv files, v0 bootstrap and holdout notebook, handoffs).

## Tests

`uv run pytest v1/scripts/tests v1/scripts/verification/tests -q` : 182 passed. No code changed for the README.

## Data version

`company_list_v3`, unchanged.

## Open issues

- `v1/README.md` still carries v0's long README below its banner.

## Next step

Open a pull request from `michael/wip` to `main` when the team is ready.
