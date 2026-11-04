# LLM selector prompt versions

**For:** anyone who runs, replays or reads the output of the two LLM comp selectors,
[`scripts/cosine_then_llm.py`](scripts/cosine_then_llm.py) and [`scripts/direct_llm.py`](scripts/direct_llm.py)
(called `judge_comps.py` and `suggest_comps.py` before 2026-11-03).

## What changed and why

The team decided on 2026-11-03 to drop **company size (F9)**: it is too generic and hurt the comps. It was already
out of every similarity score (`candidates.py`, `facet_weighting.py`, Fiona's sector-facet candidates). It was still
listed in the text the two LLM selectors send to the model. As of 2026-11-04 it is out of the prompt too, as a new
prompt version.

| version | name in the code | what the prompt lists | used for |
|---|---|---|---|
| `2026-10-25a` | `SAVED_PROMPT_VERSION` | all twelve facets, company size included | every **saved** answer: the 373 training verdicts in `outputs-local/v1/judge/`, the 373 direct picks in `outputs-local/v1/suggest/`, all fixed-holdout runs (`holdout_completion/`, `sector_facets/holdout_llm/`, the split test) |
| `2026-11-04a` | `PROMPT_VERSION` | the same, without the `- Company size: …` line | every **new** run (the default) |

Nothing else differs: the instructions, the order of companies and every other facet line are byte-identical. In
`direct_llm.py` only the target's description changes, because the pool lines never listed company size. The
exclusion lists are in `PROMPT_EXCLUDES` at the top of each script.

## Why the old version is kept

The scripts find saved work by the prompt itself:
- **A rerun skips finished targets** by comparing a fingerprint (model + prompt) with the one saved beside each answer.
- **The holdout scripts resume** saved batches by the exact prompt hash.
- **Readers keep only verdicts of one version:** `--tables-only`, Fiona's `facet_eval.py`, Kethan's `peer_evaluation.py`, and the notebooks.

So changing the prompt in place would have:
- made every saved answer look missing, so a replay would pay for new calls, about 160 holdout targets' worth;
- emptied those readers' tables.

The fix keeps both versions and makes everything that touches saved work ask for the saved one explicitly.

## Who uses which version

| file | version | why |
|---|---|---|
| `cosine_then_llm.py`, `direct_llm.py`: a new run | `PROMPT_VERSION` (default), or `--prompt-version` | new work goes without company size |
| `holdout_batched_routes.py`, `holdout_llm_routes.py`, `split_peer_eval.py` | `SAVED_PROMPT_VERSION` | replays of the saved holdout answers: the prompt must stay byte-identical |
| `facet_eval.py` (Fiona) | `SAVED_PROMPT_VERSION` | reads the saved verdicts in `<stage>/judge` |
| `peer_evaluation.py` (Kethan) | `SAVED_PROMPT_VERSION` (unless a handoff names another) | reads the saved verdicts as its upstream |
| `notebooks/comps_and_valuation.ipynb`, `notebooks/similarity_methods.ipynb`, `notebooks/history/…` | `SAVED_PROMPT_VERSION` | report the saved verdicts and picks |
| `notebooks/holdout_test.ipynb` | `SAVED_PROMPT_VERSION`, also in the command it prints | its holdout judge must match its training reference |

## Where outputs go

New runs no longer write into the saved folders, so they can't replace saved answers:

| | saved (`2026-10-25a`) | new runs (default) |
|---|---|---|
| `cosine_then_llm.py` | `outputs-local/v1/judge/` | `outputs-local/v1/cosine_then_llm/<candidates run>_<prompt version>/` |
| `direct_llm.py` | `outputs-local/v1/suggest/` | `outputs-local/v1/direct_llm/<split run>_<prompt version>/` |

`--out` still overrides this. Both scripts keep `DEFAULT_OUT` as an alias of the saved folder for older imports.

## Commands

```text
# a new run (paid): company size left out
uv run python v1/scripts/cosine_then_llm.py --workers 4
uv run python v1/scripts/direct_llm.py --workers 4

# look at the new prompts first, free
uv run python v1/scripts/cosine_then_llm.py --dry-run --tickers PCTY WEN

# screen the v1 baseline's lists (B3, mutual top 10) instead of v0's z >= 2 shortlist
uv run python v1/scripts/method1_candidates.py                 # free: writes outputs-local/v1/candidates_method1/<time>/
uv run python v1/scripts/cosine_then_llm.py --b3 --dry-run     # free: look at the prompts
uv run python v1/scripts/cosine_then_llm.py --b3 --workers 4   # paid: outputs-local/v1/cosine_then_llm/b3_<run>_<version>/

# rebuild the saved tables (free): name the saved folder and version
uv run python v1/scripts/cosine_then_llm.py --tables-only --out outputs-local/v1/judge --prompt-version 2026-10-25a
uv run python v1/scripts/direct_llm.py --tables-only --out outputs-local/v1/suggest --prompt-version 2026-10-25a

# check that the saved answers still match the saved prompt (free, about a minute)
uv run python v1/scripts/check_prompt_versions.py
```

**Safety net:** `--tables-only` refuses to write an empty table over answers made with another version, and tells
you which `--prompt-version` to pass.

## How this was checked (2026-11-04)

1. **Before the change,** every prompt the old code built was hashed:
   - the facet description of all 533 companies, plain and with Fiona's sector summary;
   - all 373 saved verdicts (each matched its saved fingerprint);
   - all 373 saved direct picks (each matched its saved fingerprint).
2. **After the change,** the same prompts were rebuilt with `SAVED_PROMPT_VERSION`. All 533 + 533 + 373 + 373 hashes were identical. The holdout scripts build their batches from these same two functions, so their prompts are unchanged too.
3. **`check_prompt_versions.py`** (above) repeats the fingerprint part on demand. On 2026-11-04 it reported, for each selector: 373 saved answers, 373 matching the rebuilt `2026-10-25a` prompt, 0 matching the current `2026-11-04a` prompt. The 0 is expected: a new run will make new calls.
4. **Tests:** `tests/test_cosine_then_llm.py` and `tests/test_direct_llm.py` check that the two versions differ only in the company-size line, and that a table is never emptied.

## Changing the prompt again

1. Add the new version to `PROMPT_EXCLUDES`, or extend `describe()` / `build_prompt()` with a new branch, and set `PROMPT_VERSION` to it. Leave `SAVED_PROMPT_VERSION` alone while saved answers depend on it.
2. Anything that reads or replays saved work must name the version it was made with.
3. Run `check_prompt_versions.py` and the tests, and add a row to the table at the top of this file.
