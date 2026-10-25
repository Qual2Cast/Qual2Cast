"""Pure evaluation and peer-policy functions for the frozen modular pilot.

No outcomes, source files or historic labels are loaded here. Caller-provided
human grades, historic development labels and diagnostic proxies stay separate.
Unknown labels are explicit; similarity, SIC agreement and source coverage are
not human business accuracy. All outputs are JSON-safe and no function writes.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from scipy.stats import spearmanr

from .numeric import aggregate_multiples


def verify_experiment_seal(previous, current):
    """Refuse altered ranking, design, parameters or executable evaluators.

    Timestamp differences are not substantive. Missing legacy proof fields are
    not presumed to match; a separate explicitly versioned experiment is needed.
    """
    fields = ("ranking_inputs", "design_sha256", "parameter_sha256",
              "evaluation_script_sha256", "direct_valuation_script_sha256", "module_sha256")
    changed = [key for key in fields if key not in previous or key not in current
               or previous[key] != current[key]]
    if changed:
        raise RuntimeError("Experiment changed after outcome seal (" + ", ".join(changed)
                           + "); a separate explicit experiment version is required")
    return {"verified": True, "verified_fields": list(fields)}


def _unique_ids(values, label="ranking"):
    result = list(map(str, values))
    if len(result) != len(set(result)):
        raise ValueError(f"{label} contains duplicate IDs")
    return result


def _mapping(values: Mapping):
    result = {str(key): value for key, value in values.items()}
    if len(result) != len(values):
        raise ValueError("mapping keys collide after canonical string conversion")
    return result


def _finite(value):
    try:
        return value is not None and bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _grade(value, max_grade):
    if value is None or (isinstance(value, str) and value.upper() in ("U", "UNKNOWN", "UNJUDGED")):
        return None
    if not _finite(value):
        return None
    value = float(value)
    if value < 0 or value > max_grade:
        raise ValueError("grade outside the declared scale")
    return value


def _dcg(known_grades):
    values = np.asarray(known_grades, dtype=float)
    return float(np.sum(np.expm1(values * np.log(2)) / np.log2(np.arange(len(values)) + 2)))


def common_pool_metrics(ranking_ids, judgments: Mapping, *, pool_ids=None, k=10,
                        relevance_threshold=2, max_grade=3):
    """Fixed-k precision bounds and DCG against a shared, explicitly finite pool.

    Use identical pool_ids for every method on a target. Point nDCG is emitted
    only if the pool and returned top-k grades are known and ideal DCG is positive.
    It is pooled nDCG, never exhaustive-universe recall. Unknown grades are not
    assumed irrelevant. Unreturned slots contribute zero to a fixed-k output.
    Conservative nDCG bounds use worst/best independent assignments to unknowns;
    they need not be tight. A point precision is withheld for unknown top-k grades.
    """
    if not isinstance(k, (int, np.integer)) or k < 1:
        raise ValueError("k must be a positive integer")
    if not np.isfinite(max_grade) or not 0 < relevance_threshold <= max_grade:
        raise ValueError("require 0 < relevance_threshold <= finite max_grade")
    ranking = _unique_ids(ranking_ids)
    labels = _mapping(judgments)
    pool = _unique_ids(list(labels) if pool_ids is None else pool_ids, "pool")
    pool_set = set(pool)
    top = ranking[:k]
    if any(peer not in pool_set for peer in top):
        raise ValueError("returned top-k IDs must belong to the common pool, with unknown grades if necessary")
    pool_grades = [_grade(labels.get(peer), max_grade) for peer in pool]
    top_grades = [_grade(labels.get(peer), max_grade) for peer in top]
    unknown = sum(value is None for value in top_grades)
    known = len(top_grades) - unknown
    relevant = sum(value is not None and value >= relevance_threshold for value in top_grades)
    lower_grades = [0.0 if value is None else value for value in top_grades]
    upper_grades = [float(max_grade) if value is None else value for value in top_grades]
    lower_dcg, upper_dcg = _dcg(lower_grades), _dcg(upper_grades)
    ideal_low = _dcg(sorted([0.0 if value is None else value for value in pool_grades], reverse=True)[:k])
    ideal_high = _dcg(sorted([float(max_grade) if value is None else value for value in pool_grades], reverse=True)[:k])
    pool_unknown = sum(value is None for value in pool_grades)
    exact_ndcg = lower_dcg / ideal_low if not unknown and not pool_unknown and ideal_low > 0 else None
    return {"k": int(k), "selected_ids": top, "selected_count": len(top),
            "missing_output_slots": int(k - len(top)), "judged_top_count": known,
            "unknown_top_count": unknown, "judgment_coverage_at_k": known / k,
            "judgment_coverage_returned": known / len(top) if top else None,
            "precision_at_k": relevant / k if unknown == 0 else None,
            "judgment_based_precision_at_k": relevant / k if unknown == 0 and known > 0 else None,
            "output_status": "no_candidates_returned" if not top else "partial_output" if len(top) < k else "complete_output",
            "precision_interpretation": "fixed_k_output_utility; zero for no output is not human validation",
            "precision_lower": relevant / k, "precision_upper": (relevant + unknown) / k,
            "dcg": lower_dcg if unknown == 0 else None,
            "dcg_lower": lower_dcg, "dcg_upper": upper_dcg,
            "ideal_dcg": ideal_low if pool_unknown == 0 else None,
            "ideal_dcg_lower": ideal_low, "ideal_dcg_upper": ideal_high,
            "pooled_ndcg": exact_ndcg,
            "pooled_ndcg_lower": lower_dcg / ideal_high if ideal_high > 0 else None,
            "pooled_ndcg_upper": min(1., upper_dcg / ideal_low) if ideal_low > 0
            else 1. if ideal_high > 0 else None,
            "pool_size": len(pool), "pool_unknown_count": pool_unknown,
            "metric_scope": "conditional_on_common_pool_not_exhaustive_gold",
            "status": "fully_judged" if not unknown and not pool_unknown else "incomplete_judgments",
            "ndcg_reason": "no_positive_ideal" if ideal_high == 0 else
            "unknown_grades" if exact_ndcg is None else None}


def _spearman(a, b):
    if len(a) < 2 or len(set(a)) < 2 or len(set(b)) < 2:
        return None
    value = float(spearmanr(a, b).statistic)
    return value if np.isfinite(value) else None


def ranking_agreement(ranking_a, ranking_b, *, k=5):
    """Method agreement diagnostics, not relevance accuracy or independent truth."""
    if not isinstance(k, (int, np.integer)) or k < 1:
        raise ValueError("k must be positive")
    a, b = _unique_ids(ranking_a), _unique_ids(ranking_b)
    aset, bset = set(a[:k]), set(b[:k])
    common, union = aset & bset, aset | bset
    rank_a, rank_b = {v: i + 1 for i, v in enumerate(a)}, {v: i + 1 for i, v in enumerate(b)}
    full_common = sorted(set(a) & set(b))
    return {"k": int(k), "overlap_count": len(common), "overlap_fraction_of_k": len(common) / k,
            "topk_jaccard": len(common) / len(union) if union else None,
            "topk_common_ids": sorted(common), "a_returned": min(k, len(a)),
            "b_returned": min(k, len(b)), "full_common_count": len(full_common),
            "spearman_common_rank": _spearman([rank_a[v] for v in full_common], [rank_b[v] for v in full_common]),
            "metric_scope": "agreement_only_not_accuracy"}


def ranking_coverage(ranking_ids, candidate_ids):
    """Availability accounting for a frozen eligible universe; no relevance claim."""
    ranking, candidates = _unique_ids(ranking_ids), _unique_ids(candidate_ids, "candidates")
    universe = set(candidates)
    outside = [value for value in ranking if value not in universe]
    if outside:
        raise ValueError("ranking contains IDs outside the frozen candidate universe")
    returned = set(ranking)
    return {"ranked_count": len(ranking), "candidate_count": len(candidates),
            "coverage": len(ranking) / len(candidates) if candidates else None,
            "unranked_ids": [value for value in candidates if value not in returned]}


def ranking_proxy_diagnostics(ranking_ids, *, text_lengths: Mapping,
                              candidate_sic: Mapping, target_sic=None,
                              scores: Mapping | None = None, k=5):
    """Text-length associations and SIC overlap, explicitly diagnostic proxies.

    SIC equality uses caller-canonicalized strings (no guessed code padding).
    Length/rank Spearman uses positions where 1 is best; score correlation uses
    the caller's score direction and is labeled accordingly. Neither is accuracy.
    """
    if not isinstance(k, (int, np.integer)) or k < 1:
        raise ValueError("k must be positive")
    ranking = _unique_ids(ranking_ids)
    lengths, sic = _mapping(text_lengths), _mapping(candidate_sic)
    score_map = _mapping(scores) if scores is not None else {}
    valid_lengths = [(i + 1, float(lengths[value])) for i, value in enumerate(ranking)
                     if _finite(lengths.get(value)) and float(lengths[value]) >= 0]
    score_pairs = [(float(score_map[value]), float(lengths[value])) for value in ranking
                   if _finite(score_map.get(value)) and _finite(lengths.get(value)) and float(lengths[value]) >= 0]
    top = ranking[:k]
    known_sic = [value for value in top if sic.get(value) is not None and str(sic[value]).strip()]
    target_known = target_sic is not None and bool(str(target_sic).strip())
    same = sum(str(sic[value]) == str(target_sic) for value in known_sic) if target_known else None
    return {"metric_scope": "SIC_and_length_proxies_not_business_relevance",
            "k": int(k), "selected_count": len(top), "known_sic_count": len(known_sic),
            "sic_coverage_at_k": len(known_sic) / k,
            "same_sic_count": same,
            "same_sic_fraction_known": same / len(known_sic) if same is not None and known_sic else None,
            "same_sic_fraction_requested_k": same / k if same is not None else None,
            "rank_length_spearman": _spearman([x[0] for x in valid_lengths], [x[1] for x in valid_lengths]),
            "rank_length_n": len(valid_lengths), "rank_direction": "1_is_best",
            "score_length_spearman": _spearman([x[0] for x in score_pairs], [x[1] for x in score_pairs]),
            "score_length_n": len(score_pairs), "score_direction": "caller_supplied"}


def fixed_peer_sets(ranking_ids, *, ks=(3, 5, 10)):
    """Preserve supplied ranking order; no refill, reranking or hidden tie-break."""
    ranking = _unique_ids(ranking_ids)
    if len(set(ks)) != len(ks) or any(not isinstance(k, (int, np.integer)) or k < 1 for k in ks):
        raise ValueError("ks must contain distinct positive integers")
    return {str(k): {"policy": f"fixed_top{k}", "requested_k": int(k),
                    "selected_ids": ranking[:k], "selected_count": min(k, len(ranking)),
                    "complete": len(ranking) >= k, "refill": False} for k in ks}


def evidence_coverage_abstention(ranking_ids, evidence_supported: Mapping, *,
                                 target_supported, k=5):
    """Require supported activity evidence in target and every original top-k peer.

    Values must be True/False/None. This frozen policy is a source-coverage guard,
    NOT a calibrated relevance threshold. No final human relevance grades enter.
    If it rejects, selected_ids still shows the original proposed set; accepted_ids
    is empty. Missing evidence and explicit unsupported status remain distinct.
    """
    peers = fixed_peer_sets(ranking_ids, ks=(k,))[str(k)]
    evidence = _mapping(evidence_supported)
    values = [target_supported] + [evidence.get(value) for value in peers["selected_ids"]]
    if any(value is not None and not isinstance(value, (bool, np.bool_)) for value in values):
        raise ValueError("evidence support must be boolean or None, not similarity scores")
    reasons = []
    if target_supported is None:
        reasons.append({"entity": "target", "reason": "unknown_activity_support"})
    elif not target_supported:
        reasons.append({"entity": "target", "reason": "no_supported_activity"})
    for value in peers["selected_ids"]:
        support = evidence.get(value)
        if support is None or not support:
            reasons.append({"entity": value, "reason": "unknown_activity_support" if support is None else "no_supported_activity"})
    if not peers["complete"]:
        reasons.append({"entity": "peer_set", "reason": "fewer_than_required_peers"})
    accepted = not reasons
    return {**peers, "policy": "evidence_coverage_abstention", "accepted": accepted,
            "accepted_ids": peers["selected_ids"] if accepted else [], "reasons": reasons,
            "claim": "evidence_coverage_guard_not_relevance_calibration"}


def fixed_peer_aggregations(peer_ids, multiples_by_id: Mapping, *, minimum_valid_peers=3):
    """Median/harmonic/reciprocal-original-rank means on identical positive rows.

    Uses the supplied selected peer IDs, never fills gaps from lower ranks. Rank
    weights remain 1/original_position after exclusions. A minimum-count failure
    suppresses estimates for every method; the eligible/excluded audit is retained.
    This function neither reads target valuations nor computes target accuracy.
    """
    if not isinstance(minimum_valid_peers, (int, np.integer)) or minimum_valid_peers < 1:
        raise ValueError("minimum_valid_peers must be a positive integer")
    ids, multiples = _unique_ids(peer_ids), _mapping(multiples_by_id)
    values = [float(multiples[value]) if _finite(multiples.get(value)) else np.nan for value in ids]
    results = {"median": aggregate_multiples(ids, values, method="median"),
               "positive_harmonic": aggregate_multiples(ids, values, method="harmonic"),
               "reciprocal_rank_weighted_mean": aggregate_multiples(ids, values, method="weighted",
                                               weights=[1 / (index + 1) for index in range(len(ids))])}
    valid_ids = results["median"]["valid_ids"]
    if any(result["valid_ids"] != valid_ids for result in results.values()):
        raise AssertionError("aggregation eligibility diverged")
    eligible = len(valid_ids) >= minimum_valid_peers
    if not eligible:
        for result in results.values():
            result["estimate"] = None
            result["status"] = "insufficient_valid_peers"
    return {"selected_ids": ids, "selected_count": len(ids), "valid_ids": valid_ids,
            "valid_count": len(valid_ids), "excluded": results["median"]["excluded"],
            "minimum_valid_peers": int(minimum_valid_peers), "eligible": eligible,
            "aggregations": results, "financial_refill": False,
            "rank_weight_definition": "1/original_selected_rank", "target_outcomes_accessed": False}


def strict_valuation_indication(evidence_guard, *, estimate_multiple, target_ebitda,
                                valid_peer_count, dates_and_definitions_confirmed=False,
                                minimum_valid_peers=3):
    """Keep an exploratory calculation separate from an eligible indication.

    No outcomes are read. The original target/peer evidence guard must pass;
    financial-date/definition alignment is never inferred from a snapshot. Even
    an eligible indication is unreviewed and is not investment-committee approval.
    """
    reasons = []
    if evidence_guard.get("accepted") is not True:
        reasons.append("target_or_original_peer_evidence_guard_failed")
    if valid_peer_count < minimum_valid_peers:
        reasons.append("fewer_than_required_valid_selected_peers")
    if not _finite(estimate_multiple) or float(estimate_multiple) <= 0:
        reasons.append("nonpositive_or_missing_estimate_multiple")
    if not _finite(target_ebitda) or float(target_ebitda) <= 0:
        reasons.append("nonpositive_or_missing_target_ebitda")
    if dates_and_definitions_confirmed is not True:
        reasons.append("financial_dates_and_definitions_unconfirmed")
    accepted = not reasons
    return {"strict_indication_status": "eligible_unreviewed" if accepted else "withheld",
            "strict_indication_reasons": reasons,
            "strict_estimate_multiple": float(estimate_multiple) if accepted else None,
            "strict_estimated_ev_supplied_millions": float(estimate_multiple * target_ebitda) if accepted else None,
            "strict_indication_scope": "evidence_and_financial_alignment_only_not_IC_approval"}


def historical_development_metrics(ranking_ids, judgments: Mapping, *, target_id,
                                    label_source, target_is_development,
                                    pool_ids=None, k=10, relevance_threshold=1,
                                    max_grade=3):
    """Historic PCTY-style labels are development evidence, never fresh validation.

    Label scale, provenance and common pool are supplied by the caller. Missing
    labels remain unknown. This wrapper refuses an evaluation-role target, and
    makes no claim that labels are complete, human-authored or independent.
    """
    if target_is_development is not True:
        raise ValueError("historic tuned labels must remain in the development split")
    if not str(label_source).strip():
        raise ValueError("label_source is required")
    metrics = common_pool_metrics(ranking_ids, judgments, pool_ids=pool_ids, k=k,
                                 relevance_threshold=relevance_threshold, max_grade=max_grade)
    return {**metrics, "target_id": str(target_id), "label_source": str(label_source),
            "evaluation_role": "historical_development_only", "fresh_validation": False,
            "independent_human_truth_claimed": False}
