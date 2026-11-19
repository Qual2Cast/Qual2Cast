# Pair ledger (2026-11-18)

Every target-comp pair a person or a model judged, from saved files. Unique pairs are (target, comp) once, whatever the number of judgments. A blank grade is not judged, never 0.

Left out: 66 pairs whose comp is outside the universe (Barbara's direct-peer list).

## By stage

| stage | sources | judgments | unique_pairs | targets |
|---|---|---|---|---|
| agent_loop | 18 | 1153 | 365 | 47 |
| human_review | 7 | 687 | 353 | 47 |
| llm_judge | 2 | 2275 | 2275 | 201 |
| llm_screen | 3 | 9788 | 5291 | 373 |

## Human review

353 unique pairs have at least one human judgment (47 targets); 298 have two or more (round 1 three reviewers; round 3 Barbara old form + Matthew v2). 352 have both a human judgment and an agent-loop grade.

## Rubric and prompt spans

| stage | rubric | sources | who | first | last | judgments | unique_pairs_judged | targets | sent_not_judged |
|---|---|---|---|---|---|---|---|---|---|
| llm_screen | binary screen prompt 2026-10-25a | screen:v0_haiku | claude-haiku-5-5 | 2026-10-27 | 2026-10-27 | 4996 | 4996 | 373 |  |
| human_review | round 1: 0/1/2, blank = 0 with one of five reasons | human:round1:riya;human:round1:barbara;human:round1:matthew | Barbara;Matthew;Riya | 2026-10-28 | 2026-10-28 | 108 | 36 | 2 |  |
| llm_judge | cited grades, 0/1/2 (v0 holdout) | judge:sol_holdout_grades | GPT-6.1 Sol | 2026-10-28 | 2026-10-28 | 1982 | 1982 | 156 |  |
| agent_loop | agent prompt 2026-11-05a | agent:gold;agent:gold_sonnet;agent:gold_sonnet_facets;agent:round2_targets;agent:round2_targets_sonnet;agent:round2_targets_sonnet_b3;agent:round2_targets_sonnet_facets;agent:round3_sonnet | sonnet agent | 2026-11-05 | 2026-11-06 | 505 | 341 | 47 |  |
| agent_loop | agent prompt 2026-11-05b | agent:gold_05b_web;agent:round2_05b_haiku_noweb;agent:round2_05b_haiku_web;agent:round2_05b_haiku_web_rep2;agent:round2_05b_web | sonnet agent | 2026-11-05 | 2026-11-05 | 146 | 71 | 7 |  |
| llm_screen | binary screen prompt 2026-11-04a | screen:20261104T074915Z_2026-11-04a_haiku;screen:20261104T074915Z_2026-11-04a_sonnet | claude-haiku-5-5;claude-sonnet-5-5 | 2026-11-05 | 2026-11-05 | 4792 | 2396 | 373 |  |
| human_review | rounds 2-3 old form: 0/1/2, six reasons, multi-business rule | human:round2_sonnet:barbara;human:round3:barbara | Barbara | 2026-11-10 | 2026-11-10 | 293 | 293 | 45 | human:round2_sheet:reviewer_a (67);human:round2_sheet:reviewer_b (67);human:round2_sheet:reviewer_c (67) |
| llm_judge | source-cited one-shot judge, 0/1/2 | judge:gpt61sol_293 | GPT-6.1 Sol | 2026-11-10 | 2026-11-10 | 293 | 293 | 45 |  |
| agent_loop | agent prompt 2026-11-05b + facet scores | agent:ranking_20targets_sonnet;agent:ranking_45targets_sonnet;agent:ranking_test_industry_sonnet;agent:ranking_test_sonnet;agent:direct_peers | sonnet agent | 2026-11-12 | 2026-11-18 | 502 | 313 | 45 |  |
| human_review | rubric v2: four yes/no questions, score derived | human:round3_v2:matthew | Matthew | 2026-11-13 | 2026-11-13 | 262 | 262 | 40 |  |
| human_review | direct-peer Yes/No (Yes = 2; No is not a 0) | human:direct_peers:barbara | Barbara | 2026-11-18 | 2026-11-18 | 24 | 24 | 20 |  |

## Sources

| source | who | rubric | pairs | targets | judged | answered_no_grade | grade_2 | grade_1 | grade_0 | peer_yes | peer_no | sent | judged_first | date_source | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| human:round1:riya | Riya | round 1: 0/1/2, blank = 0 with one of five reasons | 36 | 2 | 36 | 0 | 16 | 13 | 7 | 29 | 7 | 2026-10-27 | 2026-10-28 | time stamps in file | PCTY and WEN, pooled from the four v0 routes |
| human:round1:barbara | Barbara | round 1: 0/1/2, blank = 0 with one of five reasons | 36 | 2 | 36 | 0 | 3 | 12 | 21 | 15 | 21 | 2026-10-27 | 2026-10-28 | time stamps in file | PCTY and WEN, pooled from the four v0 routes |
| human:round1:matthew | Matthew | round 1: 0/1/2, blank = 0 with one of five reasons | 36 | 2 | 36 | 0 | 5 | 6 | 25 | 11 | 25 | 2026-10-27 | 2026-10-28 | time stamps in file | PCTY and WEN, pooled from the four v0 routes |
| human:round2_sheet:reviewer_a | slot A | rounds 2-3 old form: 0/1/2, six reasons, multi-business rule | 67 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2026-11-04 | 2026-11-04 | first git commit | CSL, AFG, AZZ, BBCP, BUKS + 2 WEN; sheet not filled in the repo |
| human:round2_sheet:reviewer_b | slot B | rounds 2-3 old form: 0/1/2, six reasons, multi-business rule | 67 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2026-11-04 | 2026-11-04 | first git commit | CSL, AFG, AZZ, BBCP, BUKS + 2 WEN; sheet not filled in the repo |
| human:round2_sheet:reviewer_c | slot C | rounds 2-3 old form: 0/1/2, six reasons, multi-business rule | 67 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2026-11-04 | 2026-11-04 | first git commit | CSL, AFG, AZZ, BBCP, BUKS + 2 WEN; sheet not filled in the repo |
| human:round2_sonnet:barbara | Barbara | rounds 2-3 old form: 0/1/2, six reasons, multi-business rule | 31 | 5 | 31 | 0 | 3 | 22 | 6 | 25 | 6 | 2026-11-05 | 2026-11-10 | first git commit | round-2 targets, comps from Sonnet-facet B3 |
| human:round3:barbara | Barbara | rounds 2-3 old form: 0/1/2, six reasons, multi-business rule | 262 | 40 | 262 | 0 | 21 | 156 | 85 | 177 | 85 | 2026-11-06 | 2026-11-10 | first git commit | one target per SIC2, comps from Sonnet-facet B3 |
| human:round3_v2:matthew | Matthew | rubric v2: four yes/no questions, score derived | 262 | 40 | 262 | 0 | 60 | 124 | 78 | 184 | 78 | 2026-11-06 | 2026-11-13 | first git commit | same 262 pairs as round 3 |
| human:direct_peers:barbara | Barbara | direct-peer Yes/No (Yes = 2; No is not a 0) | 24 | 20 | 24 | 5 | 19 | 0 | 0 | 19 | 0 | 2026-11-18 | 2026-11-18 | first git commit | pairs Barbara picked herself; in-universe comps only (all holdout companies) |
| agent:gold | sonnet agent | agent prompt 2026-11-05a | 36 | 2 | 36 | 0 | 3 | 11 | 22 | 14 | 22 | 2026-11-05 | 2026-11-05 | first git commit | sonnet facets |
| agent:gold_05b_web | sonnet agent | agent prompt 2026-11-05b | 36 | 2 | 36 | 0 | 3 | 8 | 25 | 11 | 25 | 2026-11-05 | 2026-11-05 | first git commit | sonnet facets |
| agent:gold_sonnet | sonnet agent | agent prompt 2026-11-05a | 36 | 2 | 36 | 0 | 3 | 8 | 25 | 11 | 25 | 2026-11-05 | 2026-11-05 | first git commit | haiku facets |
| agent:gold_sonnet_facets | sonnet agent | agent prompt 2026-11-05a | 36 | 2 | 36 | 0 | 3 | 10 | 23 | 13 | 23 | 2026-11-05 | 2026-11-05 | first git commit | sonnet facets |
| agent:ranking_20targets_sonnet | sonnet agent | agent prompt 2026-11-05b + facet scores | 140 | 20 | 137 | 0 | 11 | 81 | 45 | 92 | 45 | 2026-11-13 | 2026-11-13 | first git commit | sonnet facets, facet scores |
| agent:ranking_45targets_sonnet | sonnet agent | agent prompt 2026-11-05b + facet scores | 293 | 45 | 290 | 0 | 26 | 157 | 107 | 183 | 107 | 2026-11-06 | 2026-11-13 | first git commit | sonnet facets, facet scores |
| agent:ranking_test_industry_sonnet | sonnet agent | agent prompt 2026-11-05b + facet scores | 26 | 3 | 26 | 0 | 0 | 18 | 8 | 18 | 8 | 2026-11-12 | 2026-11-12 | first git commit | sonnet facets, facet scores, industry facets |
| agent:ranking_test_sonnet | sonnet agent | agent prompt 2026-11-05b + facet scores | 26 | 3 | 26 | 0 | 0 | 14 | 12 | 14 | 12 | 2026-11-12 | 2026-11-12 | first git commit | sonnet facets, facet scores |
| agent:round2_05b_haiku_noweb | sonnet agent | agent prompt 2026-11-05b | 35 | 5 | 33 | 0 | 4 | 16 | 13 | 20 | 13 | 2026-11-05 | 2026-11-05 | first git commit | haiku facets, no web search |
| agent:round2_05b_haiku_web | sonnet agent | agent prompt 2026-11-05b | 35 | 5 | 35 | 0 | 3 | 16 | 16 | 19 | 16 | 2026-11-05 | 2026-11-05 | first git commit | haiku facets |
| agent:round2_05b_haiku_web_rep2 | sonnet agent | agent prompt 2026-11-05b | 7 | 2 | 7 | 0 | 0 | 1 | 6 | 1 | 6 | 2026-11-05 | 2026-11-05 | first git commit | haiku facets |
| agent:round2_05b_web | sonnet agent | agent prompt 2026-11-05b | 35 | 5 | 35 | 0 | 4 | 18 | 13 | 22 | 13 | 2026-11-05 | 2026-11-05 | first git commit | sonnet facets |
| agent:round2_targets | sonnet agent | agent prompt 2026-11-05a | 35 | 5 | 35 | 0 | 3 | 21 | 11 | 24 | 11 | 2026-11-05 | 2026-11-05 | first git commit | sonnet facets |
| agent:round2_targets_sonnet | sonnet agent | agent prompt 2026-11-05a | 35 | 5 | 35 | 0 | 1 | 24 | 10 | 25 | 10 | 2026-11-05 | 2026-11-05 | first git commit | haiku facets |
| agent:round2_targets_sonnet_b3 | sonnet agent | agent prompt 2026-11-05a | 31 | 5 | 31 | 0 | 3 | 18 | 10 | 21 | 10 | 2026-11-05 | 2026-11-05 | first git commit | sonnet facets |
| agent:round2_targets_sonnet_facets | sonnet agent | agent prompt 2026-11-05a | 35 | 5 | 35 | 0 | 2 | 19 | 14 | 21 | 14 | 2026-11-05 | 2026-11-05 | first git commit | sonnet facets |
| agent:round3_sonnet | sonnet agent | agent prompt 2026-11-05a | 262 | 40 | 261 | 0 | 25 | 148 | 88 | 173 | 88 | 2026-11-06 | 2026-11-06 | first git commit | sonnet facets |
| agent:direct_peers | sonnet agent | agent prompt 2026-11-05b + facet scores | 24 | 20 | 23 | 0 | 13 | 10 | 0 | 23 | 0 | 2026-11-18 | 2026-11-18 | first git commit | sonnet facets, facet scores |
| judge:gpt61sol_293 | GPT-6.1 Sol | source-cited one-shot judge, 0/1/2 | 293 | 45 | 293 | 0 | 17 | 199 | 77 | 216 | 77 |  | 2026-11-10 | first git commit | label-blind, same 293 pairs as Barbara |
| judge:sol_holdout_grades | GPT-6.1 Sol | cited grades, 0/1/2 (v0 holdout) | 2138 | 160 | 1982 | 0 | 327 | 831 | 824 | 1158 | 824 |  | 2026-10-28 | first git commit | 160 holdout targets, comps from the training pool |
| screen:v0_haiku | claude-haiku-5-5 | binary screen prompt 2026-10-25a | 4996 | 373 | 4996 | 0 | 0 | 0 | 0 | 592 | 4404 |  | 2026-10-27 | time stamps in file | cosine -> LLM good/bad on a candidate list |
| screen:20261104T074915Z_2026-11-04a_haiku | claude-haiku-5-5 | binary screen prompt 2026-11-04a | 2396 | 373 | 2396 | 0 | 0 | 0 | 0 | 406 | 1990 |  | 2026-11-05 | time stamps in file | cosine -> LLM good/bad on a candidate list |
| screen:20261104T074915Z_2026-11-04a_sonnet | claude-sonnet-5-5 | binary screen prompt 2026-11-04a | 2396 | 373 | 2396 | 0 | 0 | 0 | 0 | 509 | 1887 |  | 2026-11-05 | time stamps in file | cosine -> LLM good/bad on a candidate list |

Not in this checkout: Kethan's focused pipeline (`kethan/wip`, `outputs-local/pipeline/`), Sol filter + Luna 0-3 judge on 2,438 B3 pairs, kept on his machine.
