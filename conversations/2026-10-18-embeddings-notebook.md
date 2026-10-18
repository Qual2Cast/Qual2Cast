# Handoff: embeddings notebook for matching (2026-10-18)

Work done in Claude Code. This file is the summary.

## What was asked

- Is the Task 3 audit step still necessary right now?
- Fill the write-up template up to "Results obtained" without waiting for the
  full Codex run.
- Build this as a Jupyter notebook, using embeddings of the raw website text
  as the first matching step, not the Codex fields.
- Stop the full Codex run (usage limit).

## Answer on the audit

The field audit (step 3) checks Codex's extracted fields. The first matching
pass doesn't use those fields, so the audit is paused. The write-up's "human
sanity check" asks for something else: whether the top comps' facts hold up on
their source pages and whether the pairings make business sense. The notebook's
evidence table is built for that.

## Completed

- **`p087_task6_matching/comps_embeddings.ipynb`**, reusing helpers from
  `comps_similarity.py`:
  1. Pool: snapshot v3 (checksum checked); financial columns never loaded
     (asserted).
  2. Text: Task 3 step 1 page text, cleaned and name-masked. Shared template
     sentences and boilerplate are dropped. Per-page URLs, fetch method and
     time are kept.
  3. Embeddings: all-mpnet-base-v2, 200-word chunks, averaged. Uses the cache
     in `outputs-local/task6/cache/`.
  4. Ranking: cosine similarity, with z-scores.
  5. Evidence: top-3 sentence pairs per comp for the top 15. Every sentence
     traces to its page URL (checked for PCTY, PAYC, ADP).
  6. Checks: peer labels, the SIC4 check, text length.
  7. Outputs go to a timestamped folder.
- **Write-up draft** up to results: `docs/comps_writeup.md`.
- The pre-masking `outputs-local/task6/pages/` run was moved to
  `outputs-local/task6/history/pages_20261018T044104Z_premask/` before
  re-running (the script overwrites its folder).
- **Kernel:** registered `qual2cast` (Python 3.14). The default `python3`
  kernel is Anaconda, which has no sentence-transformers.
- **Full Codex run stopped** (process tree killed) at 364/522: 181 ok,
  17 skipped, 166 `codex_error` (usage limit from #192 on), 158 not reached.

## Results (run 20261018T190530Z, PCTY)

- 534 matchable, 26 excluded.
- Top 10: PAYC, ASUR, BBSI, ADP, HURN, INTU, UPLD, FA, EVCM, KFY.
- Peer labels: NDCG@20 0.90, recall@25 0.91 (random 0.02 / 0.05). Equifax is
  the only labeled peer outside the top 25 (rank 53).
- SIC4 check: 24% of top-5 neighbours share SIC4, against 1.7% by chance.
  Spearman between score and word count: 0.31.
- The script on the same masked text gives an identical embedding score.
  TF-IDF scores 0.70 and the combined score 0.72 (was 0.80 before masking).

## Data version

company_list_v3 (sha256 3ab9a43e…). Page text as re-parsed 2026-10-18;
embedding cache `embed_all-mpnet-base-v2_200w_3d1e533a61e6db1b.npy`.

## Unresolved

- The evidence sentence pairs are often generic marketing lines, so they don't
  always explain a match. Possible fix: drop sentences that are close to many
  companies (a "generic" score) before picking pairs.
- Peer labels exist for PCTY only.
- `step2_extract_profiles.py` keeps calling Codex after a usage-limit error.
- `comps_similarity.py` overwrites `outputs-local/task6/<source>/` on each run.

## Next recommended action

1. Human sanity check of the PCTY comps: a reviewer opens the source pages
   for a sensible comp (e.g. Paycom) and a questionable one (Huron Consulting,
   #5, matched on consulting language) and records the verdict in the
   write-up.
2. Write peer labels for 3-5 non-HR targets, then run them in the notebook
   (`TARGET = ...`).
3. Re-run `step2_extract_profiles.py` after the Codex limit resets (6:33 PM
   per the error message).
