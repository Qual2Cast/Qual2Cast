# Optional manual eval-agent review

No model calls were made. Read report.md and a cases/*.json packet. Use only the supplied references. Report observations separately from hypotheses. Cite the packet reference IDs and original file paths for every proposed failure. A valid passage ID is not proof of entailment. Old labels apply only to their exact text. Do not use model knowledge to assert current business facts. Do not invent counts, change facet values, run commands or tune a method against these labels. Identify the smallest controlled experiment or source check that could distinguish causes. When evidence is inadequate, say undetermined. Output one record per diagnosis:

```json
{
  "stage": "source_evidence | facet_fill | retrieval_scoring | selection | rubric_disagreement | undetermined",
  "affected_facets": [],
  "explanation": "",
  "evidence_refs": [],
  "proposed_change": "",
  "verification_needed": "",
  "status": "hypothesis"
}
```
