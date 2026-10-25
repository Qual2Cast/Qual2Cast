"""Rank the available corpus and review candidates until the requested count."""

import pandas as pd


def ranked_pool(workflow, matching, company_id, method):
    limit = len(workflow.ids) - 1
    primary = matching.run(method, company_id=company_id, limit=limit).copy()
    primary["ranking_stage"] = "primary"
    # Membership selectors may return only a subset. Keep that preference, then
    # expand through the remaining corpus using an explicitly labeled RRF tail.
    if len(primary) < limit:
        tail = matching.run("rrf", company_id=company_id, limit=limit).copy()
        tail = tail[~tail.peer_id.isin(primary.peer_id)]
        tail["ranking_stage"] = "rrf_expansion"
        primary = pd.concat([primary, tail], ignore_index=True)
    primary = primary.rename(columns={"retrieval_rank": "method_rank"})
    primary["retrieval_rank"] = range(1, len(primary) + 1)
    return primary


def review_ranked_candidates(candidates, review, target_count=10, review_limit=None):
    """A review limit is a resumable budget, never a claim of corpus exhaustion.

    Re-running with a higher limit reuses exact-request cached judgments. A
    missing cached response stops replay; an unreviewed earlier rank cannot be
    silently skipped in favor of a later candidate.
    """
    if target_count < 1 or (review_limit is not None and review_limit < 1):
        raise ValueError("Target count and optional review limit must be positive")
    judgments, statuses = [], {}
    approved, last_rank = 0, 0
    stop = "candidate_pool_exhausted"
    completed = {
        "source_review_pass",
        "incompatible",
        "insufficient_evidence",
        "full_scope_review_not_passed",
    }
    for row in candidates.to_dict("records"):
        if review_limit is not None and len(judgments) >= review_limit:
            stop = "review_budget_reached"
            break
        result = review(row["peer_id"])
        judgments.append(result)
        statuses[row["peer_id"]] = result
        last_rank = row["retrieval_rank"]
        if result["status"] not in completed:
            stop = "review_incomplete"
            break
        approved += int(result["eligible"])
        if approved >= target_count:
            stop = "target_count_reached"
            break
    ranked = []
    for row in candidates.to_dict("records"):
        result = statuses.get(row["peer_id"])
        ranked.append(
            {
                **row,
                "review_status": result["status"] if result else "not_reviewed",
                "business_eligible": result["eligible"]
                if result and result["status"] in completed
                else None,
                "reason": ((result or {}).get("review") or {}).get("rationale", ""),
            }
        )
    return {
        "ranked_candidates": ranked,
        "reviews": judgments,
        "requested_peers": target_count,
        "business_approved": approved,
        "reviewed_candidates": sum(r["status"] in completed for r in judgments),
        "candidate_count": len(candidates),
        "last_attempted_rank": last_rank,
        "unreviewed_candidates": len(candidates)
        - sum(r["status"] in completed for r in judgments),
        "status": stop,
        "review_limit": review_limit,
    }
