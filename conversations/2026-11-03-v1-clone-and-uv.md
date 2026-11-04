# v1 as a working copy of v0, and a shared uv environment

## Request

Pull main and see the latest work; set up v1 to continue from v0 without changing what was done on 2026-10-28;
keep the Python files in their own folder so v1 stays readable; install uv so Windows and Mac teammates share one
environment. (Earlier attempts the same day, a trimmed MVP, a similarity lab and rebuilt combined notebooks, were
dropped at the user's request; see `2026-11-03-v1-mvp.md` for the first.)

## Changes

- `main`: fast-forwarded to `07cd28b9` (PR #23, the merge of `michael/wip`). Nothing new from teammates on main.
  Unmerged: `kethan/wip` (single-notebook pipeline, set aside by the team), `riya/wip` (October 17, mostly data).
- `v1/`: copy of v0's working tree (including uncommitted `valuation.py` bootstrap and `holdout_test.ipynb`).
  `v1/README.md`, `v1/PEER_EVALUATION.md`, `v1/notebooks/` (saved outputs kept); `v1/scripts/` holds every `.py`,
  `tests/`, `verification/`, `reference/`, `requirements-judge.txt`, plus `seed_from_v0.py`.
- Edits, paths only: imports (`ROOT / "v1" / "scripts"`), repo-root anchors one level up, the team's working outputs
  (`comps_pilot_targets/`, and `comps/` universe, facets, embeddings, fill tests, API checks, sector facets, peer
  evaluation) to `outputs-local/v1/`. Reads of the size-stratified baseline (`comps/candidates/20261025T080854Z`,
  `comps/judge`) still use `outputs-local/comps/`. `notebooks/history/comps_and_valuation_size_stratified.ipynb` is an
  unmodified copy. Script and notebook clone: one scripted pass, repeatable.
- `outputs-local/v1/`: seeded by `python v1/scripts/seed_from_v0.py` (14,315 files, skips `history/`, `*_history/`,
  `prompts_dry_run/`; manifest `seed_manifest.json`). Label sheets moved in from the repo root:
  `gold_labels/source/facet_gold_labels - Labels.csv`, `golden_set/labels/golden_set_labels - labels.csv`.
- uv: `pyproject.toml` (core deps; extras `scrape`, `pre-v0`; dev group `pytest`), `uv.lock` (universal: Windows,
  macOS, Linux), `.python-version` = 3.12. `.venv/` was already git-ignored.
- Docs: root README (setup with uv, layout rows), `v1/README.md` banner, AGENTS.md points to v1, PROJECT_STATE.md.
- `.env`: `SERPER_API_KEY`, `TAVILY_API_KEY`, `BRAVE_API_KEY` added (git-ignored). The keys were pasted in chat;
  rotate them if that matters.

## Tests

`uv run pytest v1/scripts/tests v1/scripts/verification/tests -q`: 182 passed (Python 3.12.14, `.venv`).
`v1/notebooks/golden_set.ipynb` executed under uv into a scratch copy: imports from `v1/scripts`, reads
`outputs-local/v1/`, same output as v0's. The v1 notebooks themselves were not re-executed (they keep v0's outputs).

## Data version

`company_list_v3` (unchanged). Universe run `20261025T060358Z`, facets `2026-10-25k`, SIC2 split and candidates
`20261027T204930Z`, as in v0.

## Found while trying to replay (relevant when re-running v1 on Windows)

- `graded_peer_selection.evaluate_saved` checks input hashes recorded on a Mac; with `core.autocrlf=true` the universe
  CSV is checked out with CRLF, so the check fails although the content is the same (LF hash matches exactly).
- `holdout_split_candidates.py` reads `npz[name]` inside a per-pair loop; each access decompresses the whole array, so
  one call takes over 10 minutes. Reading each array once gives the same result in about 3 seconds.
- Re-running candidates on this machine reproduces the same pairs and ranks, with similarities differing by ~1e-7
  (BLAS), so files are not byte-identical; saved grades pin candidate files by hash.
- The sector-facet holdout routes (`sector_facets/holdout_llm/`) kept result tables only, no raw answers: replaying
  them needs about 20 Codex calls. The general-facet holdout routes replay completely from saved calls.
- `business_structure_eval.ipynb` reads `outputs-local/research/business-structure/`, which is not on this machine.
- Kethan's peer-evaluation run is on his machine (`peer_evaluation.ipynb` §7 shows its saved outputs).

## Next

The user works on the similarity (how facets are combined, BM25 / TF-IDF weighting, other approaches), dropping the
company-size facet and adding general facets. RAG verification and the LLM-as-judge live runs: later.
Teammates: `uv sync`, select `.venv` as kernel.
