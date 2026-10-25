"""Stage-level evaluation: missing labels are explicit, never fabricated."""

from pipeline.stages import MethodStage
from pipeline.evaluation import human_ranking_metrics
from valuation.measurement import accuracy_summary


def event_metrics(results, labels, records):
    truth, border, predicted = set(), set(), set()
    incomplete = 0
    for cid, label in labels.items():
        if cid.startswith("_"):
            continue
        truth |= {
            (cid, page, kind)
            for page, kinds in label["truth"].items()
            for kind in kinds
        }
        border |= {(cid, page, kind) for page, kind in label.get("borderline", [])}
        page_of = {p["source_url"]: p["page_id"] for p in records[cid]["pages"]}
        result = results.get(cid)
        if result is None or result["status"] == "incomplete_llm_run":
            incomplete += 1
        for event in (result or {}).get("events", []):
            predicted.add((cid, page_of[event["source_url"]], event["event_type"]))
    scored = predicted - border
    correct = len(truth & scored)
    return {
        "status": "incomplete_run_not_scored"
        if incomplete
        else "scored_development_only",
        "correct": correct,
        "predicted": len(scored),
        "true": len(truth),
        "precision": correct / len(scored) if scored and not incomplete else None,
        "recall": correct / len(truth) if truth and not incomplete else None,
        "f1": 2 * correct / (len(scored) + len(truth))
        if (scored or truth) and not incomplete
        else None,
        "incomplete_companies": incomplete,
        "label_status": "Single-annotator team labels; no independent second review",
        "false_positives": sorted(scored - truth),
        "false_negatives": sorted(truth - scored),
    }


class EvaluationStage(MethodStage):
    def __init__(self):
        super().__init__()
        self.register(
            "valuation_accuracy",
            lambda actual, predicted: accuracy_summary(actual, predicted),
            "Coverage, percentage/log errors and all-target success rates",
            "valuation/measurement.py",
        )
        self.register(
            "business_ranking",
            human_ranking_metrics,
            "Precision@k and nDCG on a fully judged candidate pool",
            "pipeline/evaluation.py",
        )
        self.register(
            "event_extraction",
            event_metrics,
            "Article/type precision, recall, F1 and error lists",
            "growth_signals/eval/score_rules.py",
        )
