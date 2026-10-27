# 2026-10-27: v0 LLM then cosine baseline

The fourth route reuses the direct LLM selections and existing full cosine
ranking. `v0/llm_then_cosine.py` reranks the selected peers; notebook Section 5
shows the peer results and Section 6 calls the unchanged `valuation.estimate`
and `valuation.summary` functions. Original Sections 1–4 and recipe Step 7
remain intact. The README records the added route.

Data: required `company_list_v3` snapshot; saved split, candidate, judgment,
and suggestion run `20261025T080854Z`; 373 training targets. No new model calls.
The route retains 1,194 peers for 341 targets. Median absolute percentage error
is 32.69% on those 341 and 30.57% on the 277 targets shared with the other
LLM route. All 14 pre-existing rows of both valuation summaries match the
team's saved results exactly (maximum numeric difference 0.0).

The changed notebook cells ran on the saved inputs. The local v0 suite has
98 passing tests and one unrelated unchanged assertion: with the installed
pandas version, an unknown facet returns `NaN` where the test expects `None`.
The holdout and human peer review remain untested. Next: review the fourth
route on independent targets before treating a small training-error difference
as evidence of superiority.
