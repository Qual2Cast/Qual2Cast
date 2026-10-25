"""Continue past rejected candidates without treating unknown rows as rejected."""

import pandas as pd
from pipeline.peer_search import review_ranked_candidates


def candidates(n=30):
    return pd.DataFrame(
        {
            "peer_id": [str(i) for i in range(1, n + 1)],
            "retrieval_rank": range(1, n + 1),
        }
    )


def test_search_continues_past_first_five_until_ten_qualify():
    def review(peer):
        passed = 6 <= int(peer) <= 15
        return {
            "peer_id": peer,
            "eligible": passed,
            "status": "source_review_pass" if passed else "incompatible",
        }

    result = review_ranked_candidates(candidates(), review, target_count=10)
    assert result["status"] == "target_count_reached"
    assert result["last_attempted_rank"] == 15 and result["business_approved"] == 10
    assert result["ranked_candidates"][15]["business_eligible"] is None


def test_budget_and_exhaustion_are_distinct():
    reject = lambda peer: {"peer_id": peer, "eligible": False, "status": "incompatible"}
    limited = review_ranked_candidates(candidates(), reject, review_limit=12)
    exhausted = review_ranked_candidates(candidates(), reject)
    assert (
        limited["status"] == "review_budget_reached"
        and limited["unreviewed_candidates"] == 18
    )
    assert (
        exhausted["status"] == "candidate_pool_exhausted"
        and exhausted["unreviewed_candidates"] == 0
    )


def test_missing_replay_does_not_skip_an_unknown_higher_rank():
    calls = []

    def missing(peer):
        calls.append(peer)
        return {
            "peer_id": peer,
            "eligible": False,
            "status": "not_run_cache_missing",
            "review": None,
        }

    result = review_ranked_candidates(candidates(), missing)
    assert result["status"] == "review_incomplete" and calls == ["1"]
    assert result["reviewed_candidates"] == 0 and result["unreviewed_candidates"] == 30
