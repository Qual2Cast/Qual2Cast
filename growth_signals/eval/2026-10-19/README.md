# Growth-signal extraction evaluation, 2026-10-19

Hand labels and the saved pages they describe, so anyone can re-score the
rule extractor without `outputs-local/` or a new crawl.

```bash
cd growth_signals
python eval/score_rules.py                     # all four sets
python eval/score_rules.py --set holdout_c --errors
```

| set | companies | role | rules, precision / recall (2026-10-19) |
|---|---:|---|---|
| `pilot` | 5 (PCTY, WING, HRI, PRGS, BV) | in-sample: rules were written against it | 100% / 100% |
| `holdout_b` | 2 (older BV, WING sitemap articles) | in-sample since round 3 | 95% / 100% |
| `holdout_a` | 10 | in-sample since round 3 | 88% / 97% |
| `holdout_c` | 10 | **held-out**: labeled before scoring, never used for tuning | 58% / 43% (61% if TGS P12 is counted; see misses) |

Only `holdout_c` estimates performance on unseen companies.

How the labels were made:
- Scores count (company, page, event type) pairs. Pages not listed under
  `truth` have no true event. `borderline` pairs are neither rewarded nor
  penalized.
- An event reported inside the period an earnings release covers is true; a
  mention of an event from an earlier period is borderline.
- Single annotator, no second review: treat differences of a few points as
  noise.

Files:
- `labels_<set>.json`: labels.
- `records/<set>/<IQ_COMPANY_ID>.json`: the collector's page records (page
  text as the extractor reads it, URLs, dates). Raw HTML paths inside them
  point to local files that are not shared; scoring does not need them. No
  financial fields.
- `holdout_*_misses.md`: false positives and negatives written up after each
  held-out run, used as the next round's fix list.
