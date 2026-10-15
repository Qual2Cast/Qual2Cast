# Qual2Cast

**Forecasting private-company revenue growth from qualitative signals.**

Qual2Cast estimates the 3-year cumulative revenue growth of private companies by turning qualitative information (news, hiring activity, contracts, credit stress) into quantitative features that a forecasting model can use. Large language models extract the features, and the extraction is evaluated as a measurable system, not trusted as an oracle.

---

## Why

Private companies don't publish audited financials, so investors often have little hard data to forecast their growth. They do leave a trail of qualitative evidence:

- New contracts, product launches, and aggressive hiring → likely **positive** momentum
- Difficulty servicing debt, layoffs, and customer churn → likely **negative** momentum

Qual2Cast tries to systematically identify which of these signals actually predict growth and how strongly.

## Approach

```
Qualitative sources ──► LLM feature extraction ──► Company profile ──► Growth model ──► 3-yr revenue growth
 (news, alt data,        (structured signals,       (numeric feature    (benchmarked vs.     + uncertainty
  reviews, filings)       confidence, abstention)    vector)             public comps)
```

1. **Signal collection.** Gather qualitative data on each company from news, alternative data, and consumer-facing sources.
2. **Feature extraction.** LLMs convert unstructured text into structured, scored growth signals. Low-confidence cases are routed to abstention or human review.
3. **Company profiling.** Map features onto a common numeric scale so companies can be compared by similarity.
4. **Forecasting and valuation proxy.** Train on public companies, where revenue outcomes are observable, and use comparable companies to anchor growth and EV/EBITDA estimates.

## Evaluation

The LLM components are treated as a system under test:

- Held-out companies and time-based splits to prevent look-ahead bias
- Error categories for extraction failures
- Abstention rules for low-evidence cases
- Human review of a sampled audit set

## Status

🚧 Early development. Structure, data sources, and methodology are being defined.

## Deliverables

- Reproducible data pipeline and analysis
- Concise technical report
- Presentation of methods, findings, and limitations

## Acknowledgments

Developed under the guidance of Aziz Lookman, founder of Rational AI.
