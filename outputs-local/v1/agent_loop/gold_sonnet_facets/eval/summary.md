# Agent loop evaluation: gold_sonnet_facets

36 pairs, 2 targets. Status: {'ok': 36}. Lookups: {'mean lookups per pair': np.float64(0.03), 'pairs with a web search %': np.float64(0.0), 'pairs with no lookup %': np.float64(97.2)}.

## 1. Agreement with the reviewers (majority grade)

| grader                    |   pairs |   graded |   insufficient |   exact |   exact % |   within 1 % |   peer vs not-peer % |   mean (grader - human) |
|:--------------------------|--------:|---------:|---------------:|--------:|----------:|-------------:|---------------------:|------------------------:|
| agent loop                |      32 |       32 |              0 |      31 |      96.9 |          100 |                100   |                    -0   |
| one-shot Sol (same pairs) |      32 |       32 |              0 |      26 |      81.2 |          100 |                 90.6 |                     0.2 |

Agent loop, human (rows) vs agent (columns):

|   human |   0 |   1 |   2 |
|--------:|----:|----:|----:|
|       0 |  21 |   0 |   0 |
|       1 |   0 |   7 |   0 |
|       2 |   0 |   1 |   3 |

One-shot Sol, same pairs:

|   human |   0 |   1 |   2 |
|--------:|----:|----:|----:|
|       0 |  18 |   3 |   0 |
|       1 |   0 |   4 |   3 |
|       2 |   0 |   0 |   4 |

## 2. Agreement with Sol's holdout grades (alternative check)

| grader                      |   pairs |   graded |   insufficient |   exact |   exact % |   within 1 % |   peer vs not-peer % |   mean (grader - human) |
|:----------------------------|--------:|---------:|---------------:|--------:|----------:|-------------:|---------------------:|------------------------:|
| agent vs Sol holdout grades |       0 |        0 |              0 |       0 |       nan |          nan |                  nan |                     nan |

## 3. The filter on B3's lists, against the reviewers

| list             |   pairs |   labelled |   direct (2) kept |   adjacent (1) kept |   non-peer (0) kept |   precision (1 or 2) % |
|:-----------------|--------:|-----------:|------------------:|--------------------:|--------------------:|-----------------------:|
| B3 as is         |      14 |         11 |                 4 |                   7 |                   0 |                    100 |
| B3, agent 1 or 2 |      11 |         11 |                 4 |                   7 |                   0 |                    100 |
| B3, agent 2 only |       3 |          3 |                 3 |                   0 |                   0 |                    100 |

## 4. Valuation

Skipped: 2 targets (needs 20+).
