"""Evaluation-only outcomes are read after peer selection."""

import numpy as np


def human_ranking_metrics(ranked_ids, pooled_grades, k=5):
    """Compute nDCG against the whole judged pool, not the returned ranking.

    Require complete labels for every returned ID. The caller must use a pooled
    candidate set assembled independently of one method's output.
    """
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k must be a positive integer")
    if not pooled_grades:
        return {
            "status": "not_computed_no_independent_labels",
            "ndcg": None,
            "precision": None,
        }
    ranked_ids = list(ranked_ids)[:k]
    if len(set(ranked_ids)) != len(ranked_ids):
        raise ValueError("Duplicate ranked IDs")
    if any(x not in pooled_grades for x in ranked_ids):
        return {"status": "incomplete_judgments", "ndcg": None, "precision": None}
    grades = np.asarray(list(pooled_grades.values()), float)
    if not np.isfinite(grades).all() or not np.isin(grades, [0, 1, 2, 3]).all():
        raise ValueError("Human grades must be integers from zero to three")
    observed = np.asarray([pooled_grades[x] for x in ranked_ids], float)

    def dcg(g):
        return np.sum((2**g - 1) / np.log2(np.arange(len(g)) + 2))

    ideal = dcg(np.sort(grades)[::-1][:k])
    return {
        "status": "scored",
        "ndcg": float(dcg(observed) / ideal) if ideal > 0 else None,
        "precision": float((observed >= 2).sum() / k),
        "returned": len(observed),
        "judged_pool": len(grades),
        "denominator_k": k,
    }


def flatten_result(report, outcome=None):
    v = report["valuation"]
    estimate = v["multiple"]
    valid = (
        estimate is not None
        and outcome is not None
        and np.isfinite(outcome)
        and outcome > 0
    )
    return {
        "target": report["target"],
        "configuration_id": report["configuration_id"],
        **report["configuration"],
        "peers": len(report["peers"]),
        "estimate": estimate,
        "actual": outcome,
        "ev_source_units": v["ev_source_units"],
        "ape": 100 * abs(estimate / outcome - 1) if valid else np.nan,
        "absolute_log_error": abs(np.log(estimate / outcome)) if valid else np.nan,
        "peer_iqr": v["q75"] - v["q25"] if v["q25"] is not None else np.nan,
        "status": v["status"],
    }
