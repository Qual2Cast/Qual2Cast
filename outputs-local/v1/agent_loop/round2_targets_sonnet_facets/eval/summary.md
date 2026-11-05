# Agent loop evaluation: round2_targets_sonnet_facets

35 pairs, 5 targets. Status: {'ok': 35}. Lookups: {'mean lookups per pair': np.float64(0.11), 'pairs with a web search %': np.float64(5.7), 'pairs with no lookup %': np.float64(94.3)}.

## 1. Agreement with the reviewers (majority grade)

| grader                    |   pairs |   graded |   insufficient |   exact |   exact % |   within 1 % |   peer vs not-peer % |   mean (grader - human) |
|:--------------------------|--------:|---------:|---------------:|--------:|----------:|-------------:|---------------------:|------------------------:|
| agent loop                |       0 |        0 |              0 |       0 |       nan |          nan |                  nan |                     nan |
| one-shot Sol (same pairs) |       0 |        0 |              0 |       0 |       nan |          nan |                  nan |                     nan |

Agent loop, human (rows) vs agent (columns):

| human   |
|---------|

One-shot Sol, same pairs:

| human   |
|---------|

## 2. Agreement with Sol's holdout grades (alternative check)

| grader                      |   pairs |   graded |   insufficient |   exact |   exact % |   within 1 % |   peer vs not-peer % |   mean (grader - human) |
|:----------------------------|--------:|---------:|---------------:|--------:|----------:|-------------:|---------------------:|------------------------:|
| agent vs Sol holdout grades |       0 |        0 |              0 |       0 |       nan |          nan |                  nan |                     nan |

## 3. The filter on B3's lists, against the reviewers

| list             |   pairs |   labelled |   direct (2) kept |   adjacent (1) kept |   non-peer (0) kept |   precision (1 or 2) % |
|:-----------------|--------:|-----------:|------------------:|--------------------:|--------------------:|-----------------------:|
| B3 as is         |      35 |          0 |                 0 |                   0 |                   0 |                    nan |
| B3, agent 1 or 2 |      21 |          0 |                 0 |                   0 |                   0 |                    nan |
| B3, agent 2 only |       2 |          0 |                 0 |                   0 |                   0 |                    nan |

## 4. Valuation

Skipped: 5 targets (needs 20+).
