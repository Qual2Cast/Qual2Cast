# 2026-10-28: team work and holdout integration (local)

## Team inputs checked

- **Michael / main v0:** 533 eligible public firms from the 560-company list;
  373 training and 160 holdout firms after the SIC2-stratified split. The
  candidate, Haiku judgment, direct-LLM, reverse-hybrid, and EV/EBITDA code is
  in `v0/` and its baseline notebook. The ten showcase firms are in training.
  His 27 October commit `2755582a` made the SIC2 notebook the updated baseline;
  this run reads its saved candidate stage `20261027T204930Z`.
- **Riya, Barbara, Matthew:** three separate 0–2 reviews of the same 36
  PCTY/WEN peer pairs. Riya also supplied a facet-fill rubric; the 36-pair
  sheet checks peer relevance, not facet extraction. Eleven pairs have
  unanimous scores, 25 do not. Thirty-two have an exact majority; four
  three-way ties remain unresolved. Matthew used 10-K business and competition
  sections to make his peer labels independently of the Haiku-filled profile,
  as he clarified to Aziz in Google Chat.
- **Fiona:** `v0/facet_eval.py` tests facet removals and sector alternatives
  against peer labels. Her ten-company audit flags sold businesses and weak
  geography/primary-services facets. We added a checked saved-embedding path,
  so the evaluator runs without refitting or downloading the model.
- **Yiming:** `v0/verification/` checks facet claims against dated website and
  search evidence. His 20-company check found 24.5% problematic among
  checkable facets and 61% fill using website-only private-company proxies.
- **Yifan/Richard:** `origin/verification/gold-labels` has a 40-company facet
  benchmark and RAG verifier. Its facet-fill results are a separate outcome
  from the 36-pair peer-selection reviews; the branch is not merged into main.
- **Kethan:** main has `v0/peer_evaluation.py`, a source-cited LLM-as-judge
  evaluation of accepted peers. Its completed 663-pair run uses the earlier
  size-stratified baseline, so it is not directly the SIC2 holdout result.
  `origin/kethan/wip` has a pipeline notebook, but it also uses that older
  split and does not contain a completed holdout run. Its root `pipeline.ipynb`
  and `v0/pipeline.py` are not in main; they are separate from Michael's updated
  SIC2 notebook.
- **Aziz:** explicitly permits a comp universe beyond 560 and asked whether
  the golden set evaluates facet fills or peer quality. These two evaluations
  are kept separate here; broadening the universe remains a later data step.

Matthew later answered Aziz's 8:02 AM Google Chat question explicitly: the 36
PCTY/WEN labels check comp selection by precision and NDCG@10; Riya's separate
40-company set checks facet fills. He used 10-Ks to keep the peer judgments
independent of the model's facet text. Aziz said this first explanation was
unclear and read like AI-generated prose. Matthew restated it plainly: the four
routes chose 36 pairs for Wendy's and Paylocity; he judged whether each pair
is a real comp from 10-Ks rather than the facet text. The Irrational AI
WhatsApp group ended
with Michael's 9:30 PM request to follow up on the report; his pinned task
distinguishes better-peer gold evaluation from valuation error and asks for a
fourth route, business-entity treatment, verification, and facet review. The
linked `10/28 Note: Qual2Cast` in Drive is still a heading template with
Aziz's writing instructions, not a completed team result. This local analysis
does not write the manager note or edit the team's document.

## Local integration

The 36 labels were snapshotted and checked without editing teammate files.
`v0/reviewer_gold_eval.py` exports each reviewer's scores and an exact-majority
set, while preserving four unresolved pairs. `v0/facet_eval.py` reuses and
checks the saved 11-facet embeddings; all 5,110 saved candidate pairs reproduce
their per-facet cosine scores within 7.44e-7.

`v0/holdout_split_candidates.py --all` ranks the complete 373-company training
pool for each of the 160 fixed holdout targets. `v0/holdout_llm_routes.py`
implements the v0 one-target-per-call protocol for checks. The final
`v0/holdout_batched_routes.py` shares the 373-firm pool prompt across small
batches while asking for an independent answer per target; the changed
inference protocol and Codex CLI backend are recorded. The two-target
direct-selection pilot retained 2/3 and 8/9 of the individually selected
peers, respectively, so the batch protocol is similar but not identical.
`v0/holdout_evaluation.py` computes the four
route estimates, a no-matching control, a same-SIC2 control, and the
reviewer-selected F3 ablation on identical holdout targets. The companion
notebook is `v0/notebooks/gold_and_holdout_integration.ipynb`.

The source-checked business grouping is stored under one company ID. Its
targeted source audit improved 27/34 to 34/34 activity statuses and 7/9 to
9/9 exact partitions. The tested scope-text insertion worsened median APE on
ten development and six pilot holdout targets, so that insertion is not the
default peer rule.

## Completed results

The batched `gpt-6.1-sol` holdout processed 160/160 targets against 373 fixed
training firms. It judged 2,138 cosine-shortlisted pairs, accepted 281, and
selected 311 direct-LLM pairs, with no missing or invalid pair labels. The
cosine→LLM route estimates 110 targets; direct LLM and LLM→cosine each estimate
119. The saved candidate cache was checked against all 5,110 training pairs.

On the 107 targets covered by all four routes, median absolute percentage
error (APE) is 36.83% for cosine z≥2 weighted mean, 37.50% for cosine→LLM,
37.79% for direct LLM, and 37.93% for LLM→cosine. The paired bootstrap
intervals for the three differences from cosine include zero. On their full
119-target common set, direct LLM and LLM→cosine both have 33.78% median APE;
the latter improves 40 firms and worsens 42, with zero median paired change.
The fourth route is implemented but has no demonstrated holdout advantage.

No matching has 39.92% median APE over all 160. The reviewer-selected F3
removal raises majority-label pairwise ranking accuracy from 0.851 to 0.921
on the two development targets, while cosine z≥2 weighted-mean holdout APE
falls from 37.32% to 33.29%. Its paired median-change 95% bootstrap interval
is −2.04 to +0.08 percentage points, and the z≥2.5 rule is worse on its
common 158 targets. F3 remains a candidate change, not a new default.

Excluding the eight source-confirmed mixed-business peers among 40 audited
companies is an exploratory sensitivity check. Cosine z≥2 median APE changes
from 37.32% to 37.98% over all 160 targets; of 48 affected targets, 27 improve
and 21 worsen. Only 4–6 targets are affected under each LLM route, and
filtering drops coverage by one target for each route. The
source-backed grouping remains metadata; the tested judge-prompt insertion
also worsened development and six-target pilot-holdout error. The full
holdout does not test private-company outcomes.

`v0/notebooks/gold_and_holdout_integration.ipynb` executed all 16 cells with
no errors. It contains the saved intermediate examples, three charts, and
the route, facet, split, and common-support result tables. Thirteen new
focused tests pass. No code or results from this local worktree have been
merged into main.
