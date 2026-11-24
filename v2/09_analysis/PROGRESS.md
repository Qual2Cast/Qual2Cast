# Improvement ledger: is each pipeline version closer to the human labels?

**For:** the model-improvement group (Kethan, Riya, Fiona, Yiming), who change the selector and agent prompts, and
the website group, who show the result. Code: `v2/09_analysis/scripts/progress.py`. Started 2026-11-24.

## What it measures, and why

The north star of the project (`v2/EVAL_METHOD.md`, section 1) is the **overlap between the comps a pipeline
version keeps for each target and the comps reviewers call peers**. The ledger measures it the same way for every
version and keeps one row per version, so improvement can be shown version by version.

For each pipeline version ("profile") and each label set, on **labelled pairs only** (an unlabelled pair is never
counted as a non-peer), for **any peer** (score 1 or 2) and **direct peer** (score 2):

| number | what it answers |
|---|---|
| precision | of the comps it keeps, how many are peers? (mean over targets that kept at least one; also pooled) |
| recall | of the reviewers' peers, how many does it keep? (mean over targets that have a peer; also pooled) |
| kappa | agreement of keep with peer, beyond chance |
| coverage | share of targets left with at least one comp |

The target means come with 95% intervals (1,000 target-bootstrap draws). Read precision and recall together:
keeping everything gives 100% recall; keeping almost nothing gives high precision.

## Baseline (2026-11-24, Matthew's rubric v2 labels, 262 pairs, 40 targets)

| profile | kept | any peer: precision / recall | direct peer: precision / recall |
|---|---:|---|---|
| `b3_all` (B3 list, nothing filtered) | 262 | 67% / 100% | 21% / 100% |
| `b3_top7` | 218 | 71% / 90% | 26% / 99% |
| `selector` (04, prompt 2026-11-04a) | 61 | 92% / 34% | 73% / 85% |
| `agent_ge1` (05, grade >= 1) | 163 | 79% / 72% | 33% / 99% |
| `agent_2` (05, grade 2) | 23 | 100% / 14% | 100% / 40% |

Target means. These labels are one reviewer with the loose v2 customers wording; the same rows are recorded again on
the rubric v3 consensus labels when they arrive.

## Adding a row after a change

1. Run your changed selector or agent the usual way (on the subscription CLI, with Michael's approval for model
   calls).
2. Write a CSV of what it keeps, one row per pair it judged: `target_id,comp_id,keep` (keep = 1/0, yes/no or
   true/false). Pairs it didn't judge count as not kept; the ledger reports how many labelled pairs the file covers.
3. Record it, in one command:

```bash
uv run python v2/09_analysis/scripts/progress.py record \
    --keeps path/to/keeps.csv --profile selector --component "04 selection" \
    --prompt-version 2026-11-25a --model claude-sonnet-5-5 \
    --who Kethan --change "selector prompt weighs services, customers and end markets" \
    --targets path/to/checking_half.txt
uv run python v2/09_analysis/scripts/progress.py show
```

`score` takes the same options and only prints (nothing is written), for trying things. `--profiles selector
agent_ge1` re-scores the built-in runs named in `v2/current.toml` (after a new run becomes current there).

## Tuning half and checking half

Tune prompts on some targets and report on the others, so the number you show was not fitted to:

- Agree on a split of the labelled targets once, before tuning (a text file of target ids, one per line, or a CSV
  with a `target_id` column), and keep it fixed.
- Look at per-pair results only on the tuning half. Record ledger rows with `--targets checking_half.txt`; the
  ledger stores the file name and its sha256, so every row says which split it used.
- Never change a label, a prompt or a setting because of what the checking half shows.

## Label sets

- `--cohort matthew_v2_262` (default): Matthew, rubric v2, single reviewer, loose customers wording.
- When the rubric v3 labels are in: `uv run python v2/06_labels/scripts/rubric_v3.py consensus <sheet>.xlsx
  <consensus>.csv ...`, then `--cohort-file <consensus>.csv --cohort-name rubric_v3_consensus`. Only pairs two
  reviewers agree on count (anchors left out); add `--include-tiebroken` for the sensitivity row.
- Barbara's old 0/1/2 labels (`dev_293`) are refused as an outcome.

## For the website

`outputs-local/v2/09_analysis/progress/`:

- `ledger.csv`: every row ever recorded, oldest first.
- `latest.csv`: the most recent row per profile, label set and split: the table for the site.
- `progress.png`: precision and recall per ledger entry (target means with 95% intervals), any peer and direct peer
  side by side, for one label set and split (`show --cohort ... --split ...`).

## Rules

- **Append-only.** Rows are never edited or deleted. Recording the same run, label set, split and profile twice is
  refused; `--force` adds a new row anyway (say why in `--change`).
- **One row per change**, with a `--change` that says what changed in a few words.
- **Labels are never tuned on**, and the checking half is never looked at pair by pair.
