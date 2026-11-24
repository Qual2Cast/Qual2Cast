# Agent grading review: the grade as a peer filter, and Barbara's ranking

**For:** the team writing the report, and whoever reworks the ranking or the rubric next.
Reviewed by Michael on 2026-11-19. Numbers come from saved runs only (no model calls):

```bash
uv run python v1a/05_agent_grading/scripts/filter_comparison.py
```

The run is saved in `outputs-local/v1a/05_agent_grading/filter_comparison/20261119T033731Z/`, with tables
`filters.csv`, `agreement.csv`, `by_rank.csv`, `questions.csv` and `pairs.csv`.

## Decisions

1. **The agent's 0/1/2 grade stays, as the any-peer filter (grade 1 or 2).** It is the best any-peer filter
   we have (below).
2. **Barbara's C / S / E scores are not used to rank in v1a or v2 for now.** The ranking idea stays, but the
   mechanism has to be reworked before it means anything (see "Next steps"). Until then the code computes the
   numbers but nothing downstream should rely on `final_rank` or `e_rank`.
3. **No 0/25/50/75/100 facet scale in new work.** Five levels per facet is finer than people can agree on:
   Barbara and Matthew already disagree on three levels (kappa 0.18, below). New facet judgments should be
   yes/no, like Matthew's rubric v2.

## The two LLM filters

Both read the same candidates, the current B3 list ("Sonnet + Fiona sub-sector", mutual top 10, topped up to 3).

| | Selector (04_selection) | Agent grade (05_agent_grading) |
|---|---|---|
| Model | `claude-sonnet-5-5`, Claude Code CLI (subscription) | `sonnet` CLI alias, resolved to `claude-sonnet-5-5` in every saved call; web search through the CLI, also Sonnet |
| Prompt | `2026-11-04a` | `2026-11-05b`, with `--facet-scores` |
| Unit | one call per target; it judges the whole list at once (listed alphabetically, no ranks or scores) | up to 4 calls per pair (look-ups, then a final answer) |
| Sees | facet summaries (company size removed), names, websites; may use its own knowledge | 450 words of each saved website, BM25 search of the rest, web search (target treated as private); facet summaries for context only, not citable; may **not** use its own knowledge |
| Question | "good: in the same business, so its multiple says something about the target's" / "bad" | team rubric: 2 same product AND customers, 1 product OR customers, 0 no overlap; cite a line from each company |
| Ran on | all 373 training targets, 2,538 pairs | the 45 labelled targets, 293 pairs |

Neither prompt was tuned on the 293 labelled pairs. The agent's prompt was set on the round-1 golden set
(PCTY, WEN).

## Efficacy against the reviewers

Peer = grade 1 or 2. Precision = share of kept pairs that the reviewer calls peers; recall = share of the
reviewer's peers that are kept. The 95% intervals come from 2,000 bootstrap resamples of targets.

**Any peer, Barbara (293 pairs, 202 peers):**

| Filter | Kept | Precision | Recall | Cohen's kappa |
|---|---:|---:|---:|---:|
| B3 list, keep all | 293 | 68.9% | 100% | – |
| B3 top 7 | 245 | 74.3% | 90.1% | 0.24 |
| Selector keep | 69 | 95.7% (87.8–100) | 32.7% (25.2–40.1) | 0.21 (0.13–0.30) |
| **Agent grade ≥ 1** | **183** | **91.8% (86.5–96.2)** | **83.2% (76.4–89.0)** | **0.63 (0.52–0.74)** |
| Agent grade 2 | 26 | 100% | 12.9% | 0.08 |
| Agent ≥ 1 OR selector | 186 | 90.9% | 83.7% | 0.62 |

**Any peer, Matthew rubric v2 (262 of the same pairs, 184 peers):** agent ≥ 1 keeps 163, precision 83.4%
(75.8–90.5), recall 73.9% (64.6–82.8), kappa 0.37 (0.24–0.49); the selector keeps 61, precision 95.1%,
recall 31.5%, kappa 0.19.

**Direct peers (grade 2).** The selector behaves as a direct-peer filter, not an any-peer one:

| Filter | vs Barbara's 24 twos | vs Matthew's 60 twos |
|---|---|---|
| Selector keep | keeps all 24; precision 34.8%; kappa 0.45 | precision 82.0%, recall 83.3%; kappa 0.77 (0.67–0.86) |
| Agent grade 2 | precision 73.1%, recall 79.2%; kappa 0.74 (0.50–0.90) | precision 100%, recall 38.3%; kappa 0.49 |

**What to say in the report:**
- For **any-peer filtering the agent grade is clearly better than the selector.** At about the same precision
  (92% vs 96%), it keeps 83% of Barbara's peers against 33%. Adding the selector on top (OR) gains one peer.
- The selector is not a worse any-peer filter so much as **a stricter question**: "same business" is closer to
  a direct peer. It keeps every one of Barbara's 24 twos, and it agrees best of all with Matthew's twos.
- The two filters answer different questions, so v2 can use both: the agent for "is it a peer at all", the
  selector (or agent grade 2) for "is it a direct peer".
- The cost differs: one selector call covers a whole target; the agent needs 1 to 4 calls per pair.
- The agent's agreement with Barbara (kappa 0.63) is higher than Barbara's with Matthew (0.19, next section),
  partly because the agent's rubric text is the one Barbara labelled with. Against Matthew, who used rubric
  v2, it drops to 0.37.

## How much the reviewers agree

Cohen's kappa: 0 = no better than chance, 1 = full agreement.

| Raters | Pairs | Peer yes/no agreement | Peer kappa | 0/1/2 kappa | 0/1/2 kappa, linear weights |
|---|---:|---:|---:|---:|---:|
| Barbara vs Matthew v2 | 262 | 65.3% | 0.19 | 0.18 | 0.29 |
| Barbara vs agent | 290 | 83.8% | 0.64 | 0.64 | 0.67 |
| Matthew v2 vs agent | 259 | 71.4% | 0.36 | 0.31 | 0.41 |
| Barbara vs selector | 293 | 52.6% | 0.21 | – | – |

Barbara and Matthew used different rubrics (old 0/1/2 judgment vs four yes/no questions), so 0.19 mixes person
and rubric. Their disagreement sits almost entirely in Barbara's 1s:

| Matthew's answers | Barbara 0 | Barbara 1 | Barbara 2 |
|---|---:|---:|---:|
| same product: yes | 1 | 42 | 21 |
| product no, customers yes | 48 | 72 | 0 |
| product no, customers no | 36 | 42 | 0 |

When Matthew says "same product", Barbara agrees it is a peer 63 times out of 64. When he says neither product
nor customers match, she still gives a 1 on 42 of 78 pairs. **The open question is what counts as "adjacent",
not which comps are direct peers.**

## Barbara's ranking (C / S / E): model and assumptions

What it is: in the same final answer as the grade, the agent also scores 11 facets 0/25/50/75/100, citing a line
from each company or leaving the facet null. `agent_ranking.py` turns the scores into coverage C, observed
similarity S and evidence points E (Barbara's Similarity Scoring Standard). The final order is grade, then S,
then B3 similarity; `e_rank` is the order by E.

**Model and run:** as in the agent column above (Sonnet, prompt `2026-11-05b`, `--facet-scores`, general facets
only, `max_steps` 4, 450 starting words per site, 5 lines per site search, 5 snippets per web search, financial
figures stripped). Run `ranking_45targets_sonnet`, 293 pairs, all `ok`, one run per pair. The CLI also made
some internal Haiku calls (62 records), and no temperature is set, so the run is not deterministic and
repeat-run variance was never measured.

**Assumptions:**

1. **Her standard is a proposal.** The policy file (`policy/barbara_scoring_policy_v3.json`, her v3.1) marks
   itself `PROPOSED_NOT_APPLIED_TO_LEGACY_SCORES`, and its weights are "explicit analyst starting weights; not
   empirically calibrated".
2. **Only part of the standard is used:** 11 of her 32 general facets, 66 of her 100 points, renormalized to
   100%. Her Customer Type (5) and Customer Segment (4) are merged into one facet (9). The 34 points left out
   include the facets closest to valuation: recurring revenue (4), capital intensity (3), pricing structure
   (3), delivery model (3), switching costs (3), customer size (3), contract duration (2), customer
   concentration (2), plus 11 points of minor facets.
3. **Her industry block (general 60% / industry 40%) is off.** It was tried on 3 targets (26 pairs), with 34%
   industry coverage and no gain.
4. **Her coverage threshold is not applied.** She requires 80% overall coverage; only 27 of 293 pairs reach
   it (mean 59.5%). Pairs below it are ranked anyway.
5. **Coverage is set by how much the website happens to say.** The agent is told not to look things up just
   to fill a facet. Three of the 11 facets are blank almost every time: revenue model 88%, distribution 84%,
   regulatory 89%.
6. **Unknown is null, never 0.** S averages only the observed facets; E counts unknown facets as no similarity.
7. **The score is linear:** a weighted sum, with the facets treated as additive and independent and the five
   levels as equally spaced. The same weights apply to every target.
8. **The grade and the facet scores come from the same answer by the same model, with shared wording** ("50 =
   adjacent" on one scale, "1 = Adjacent" on the other). S is therefore not an independent signal. Median S is
   29 / 50 / 79 for grades 0 / 1 / 2, the ranges barely overlap, and the rank correlation is 0.83.
9. **The order is lexicographic** (grade, then S, then B3), chosen on Barbara's 293 labels and scored on the
   same labels; nothing was held out. "Peer" means label ≥ 1, scored by pairwise accuracy.
10. **One reviewer**, who also wrote the standard. Her sheet showed Sonnet-written summaries, and the agent
    reads Sonnet facet fills, so the two share a source.

**What the data says about it** (details in the review's first analysis, 2026-11-19):
- grade then S beats grade then B3 by +0.6 points of pairwise accuracy (95% interval −5.3 to +5.9);
- among pairs that tie on grade, S puts Barbara's higher-graded pair first 68% of the time, B3 63% (94
  comparisons); inside the agent's 1s, median S is 50 for both her 0s and her 1s;
- swapping S for B3 changes the top 3 for 22 of 45 targets, but the number of peers in the top 3 for only 5
  (S better on 2, worse on 3);
- E alone ranks worse than B3 (78.7% vs 81.6% pairwise accuracy).

## Comp list length (batch size)

Share of B3 candidates Barbara grades 0, by rank in the target's list:

| Rank | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pairs | 43 | 42 | 39 | 37 | 30 | 31 | 23 | 16 | 17 | 15 |
| Barbara 0s | 9% | 14% | 28% | 32% | 27% | 48% | 30% | 56% | 53% | 67% |
| Agent keeps (≥ 1) | 37 | 32 | 31 | 21 | 18 | 16 | 10 | 7 | 7 | 4 |
| of which Barbara 0 | 1 | 0 | 7 | 0 | 1 | 3 | 0 | 1 | 2 | 0 |

- **Without a filter**, stopping at 7 drops 28 of the 91 zeros and 20 of the 202 peers.
- **With the agent filter**, the cap adds little: at ranks 8 to 10 the agent keeps 18 pairs, 15 of them
  Barbara's peers. A cap at 7 would mostly remove peers. It only saves calls (48 of 293 pairs).
- If cost is the reason for a cap, a B3 similarity floor loses fewer peers than a fixed count. RUBRIC_V2.md:
  pairs at similarity ≥ 0.43 are 4% zeros; below 0.35 they are 52% zeros.

## Rubric v2 and reviewer agreement

Matthew's four yes/no questions (`v1a/06_labels/RUBRIC_V2.md`) are the right base for measuring agreement:
each question can get its own kappa, which shows *which* judgment people (or the model) disagree on.

- **Not every question carries information on a B3 list.** Matthew answered yes to same product on 24% of
  pairs, same customers 70%, same revenue model 79%, same chain step 77%. Questions 3 and 4 are nearly always
  yes for candidates B3 already found.
- **Report kappa next to the yes rate.** When nearly everything is yes, kappa can be low even if raw agreement
  is high, so read both.
- **"Majority of yes answers" decides peers badly across questions, but works across reviewers.** Counting 2
  yes out of 4 questions would make 38 pairs peers with no product and no customer overlap (yes only to
  revenue model and chain step). Use majority *across reviewers* for each question (an odd number of reviewers,
  e.g. three), then the rubric's rule for the score (2 = all four yes; 1 = product or customers yes; 0 =
  neither).
- **Needed first:** a second reviewer on the same rubric v2 sheet. Barbara's v2 columns are empty, so no
  person-vs-person kappa on the same questions exists yet.
- **Proxy for the agent:** the agent was not asked the four questions, but its fit fields map to three of them
  (`questions.csv`). Kappa vs Matthew: same product 0.50 (agent "match" only), same customers 0.57 and revenue
  model 0.47 (agent "match" or "partial"). The agent says "match" on product much less often than Matthew says
  yes (25 vs 63 pairs).

## How the reviews can improve the models (no training needed)

1. **Choose settings on labels, check on other labels.** Which filter, grade 2 vs ≥ 1, the list length or
   similarity floor, the prompt version. Split the labelled targets into a tuning half and a checking half,
   so a change is not scored on the pairs it was fitted to (the C/S/E order missed this step).
2. **Per-question error analysis → prompt edits.** With rubric v2 answers, every model miss names a question
   (for example "says same product too rarely"). Fix the prompt's definition for that question, rerun on the
   tuning half, check on the other half. This is the main loop the reviews feed.
3. **Anchor examples.** Put a few labelled pairs (from tuning targets only) into the prompt as worked examples
   of each question's yes and no.
4. **Point the selector at what people use.** The X-learner (09) finds that people's peer grade follows primary
   services, end markets and customer segment, while the selector mostly uses sub-sector and offering. That is
   a prompt change, not a model change.
5. **List length is an input setting, not a model fix.** See above: it saves calls but does not make the
   filters better.

## Next steps

1. **Rework the ranking (C / S / E).** Score facets yes/no (rubric v2 questions plus any facets that earn their
   place), in a separate call from the grade so it is an independent signal. Decide what unknown means. Pick
   the order on tuning targets and test it on held-out targets. Until then, use grade then B3, or no order
   within a grade.
2. **A second reviewer on rubric v2** (Barbara or Riya on the round-3 v2 sheet), then per-question kappa.
3. **The agent grader asks the four questions** (RUBRIC_V2.md, "The agent grader"), so the model is compared
   to people question by question.
4. **Decide the v2 roles:** agent ≥ 1 as the any-peer filter, selector or agent 2 as the direct-peer filter.
