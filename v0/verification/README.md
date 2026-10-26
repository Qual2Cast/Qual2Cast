# v0/verification/

Checking the LLM-filled facets against evidence outside the fill. This
complements the website verifier (Riya): her verifier checks each facet
against the company's own site; this folder collects the evidence beyond
it, meaning more of the same site and the open web, and measures what that
evidence adds. Started 2026-10-26 (Yiming).

Background: the hand check of 20 companies (`outputs-local/comps/facets_verify20/verification/`).
Of the 208 facets that could be checked, 90 were settled from the saved pages, and 118 needed
press releases, news, the live site or profiles. 24.5% of checkable fills had a
problem. Resolute Holdings, the one company described from its pages alone,
had 0 of 12 facets supported.

| file | what it does |
|---|---|
| `evidence.py` | Collects evidence for a company and labels each line: `P1.3` saved scrape page, `W2.4` another page of its own site (deeper crawl, robots.txt honoured), `S3.1` a web search result. It drops investor-relations, SEC and market-data sources, and results pages a private company wouldn't have. It ranks sources (company site > press release > news > reference > database), drops lines with financial or headcount figures, and logs every query and page. It doesn't judge anything. |
| `verify_with_evidence.py` | Stand-in verifier for measuring the evidence: one Haiku call per company and evidence tier (`P`, `PW`, `PWS`). It gives each facet supported / partly / contradicted / missed / not_found, with cited labels. Code rules: an uncited verdict becomes not_found, and a contradiction resting only on database sources becomes not_found. It scores against gold labels. |
| `pages_only_fill.py` | Experiment: refill companies from the saved pages only, with the company's name and website masked, to see how fills look for a private company the model doesn't know. `--compare` puts the result next to the memory fill and the gold verdicts. |
| `tests/` | Offline tests (no network, no API): `python -m pytest v0/verification/tests -q` |

## Plugging into Riya's verifier

`evidence.gather(iq_id, name, website)` returns an `Evidence` with
`lines` (label to text, the same format as `facets.build_prompt`'s page lines)
and `sources` (`P1`/`W2`/`S3` to url, type, title, date). `ev.text("PWS")` is
the block to put in a prompt. When her verifier finds that the site doesn't
settle a facet, pass it these lines and have it cite the labels.

## Running (from the repo root)

Search needs one API key in the environment or `.env`: `SERPER_API_KEY`
(Google results, serper.dev), `BRAVE_API_KEY` or `TAVILY_API_KEY`. Five
queries per company. Without a key, the crawl still runs and search is
recorded as `no_search_api_key`.

```
# 1. pages-only refill of the 20 checked companies, then compare
python v0/verification/pages_only_fill.py --tickers PCTY ROAD BRO DXPE BV WEN ADUS LMB APG IPI KINS LFVN NWSA DORM SSD WMK GDRX VYX RHLD ASIC
python v0/verification/pages_only_fill.py --compare outputs-local/comps/facets_verify20 --gold outputs-local/comps/facets_verify20/verification/facet_verification_20.csv

# 2. collect evidence, then judge the memory fill with P, PW and PWS and score it
python v0/verification/evidence.py --tickers PCTY ROAD BRO DXPE BV WEN ADUS LMB APG IPI KINS LFVN NWSA DORM SSD WMK GDRX VYX RHLD ASIC
python v0/verification/verify_with_evidence.py --facets outputs-local/comps/facets_verify20 --tickers PCTY ROAD BRO DXPE BV WEN ADUS LMB APG IPI KINS LFVN NWSA DORM SSD WMK GDRX VYX RHLD ASIC --gold outputs-local/comps/facets_verify20/verification/facet_verification_20.csv
```

`score.csv` per tier gives:
- **decided**: facets the verifier could rule on.
- **agree_on_decided_%**: it agrees with the gold label on problem / no problem.
- **problems_caught**: gold problems it found.
- **false_alarms**: gold-supported facets it flagged.

The gain from `P` to `PWS` is what evidence beyond the website adds.

## Known limits

- The crawl uses plain HTTP; pages built by JavaScript come back thin. The scrape's renderer could be added.
- Search snippets are short. Fetching the top result pages would give more but costs time.
- The gold labels cover 20 companies labelled by one person. Merge them with Riya's 40 and agree on the labels before trusting the scores.
- Masking in `pages_only_fill.py` hides the company's name, but brand names in the page text can still give it away.
