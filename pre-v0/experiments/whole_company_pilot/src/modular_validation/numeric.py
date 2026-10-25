"""Pure numeric hypotheses for modular company comparison, not validated models.

No function reads files, websites, company data, labels or credentials. Callers
own input eligibility, evidence provenance, frozen parameters and evaluation.
Results use JSON-safe lists/None; missing evidence never becomes zero similarity.
Invalid schemas/configurations raise ValueError. Missing observations or solver
failures return explicit statuses. Distances/objectives are lower-is-better and
are not calibrated relevance probabilities. No implicit mass normalization occurs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import warnings

import numpy as np
from scipy.special import xlogy
from scipy.stats import rankdata


POT_VERSION = "0.9.7.post1"
UOT_REG_TYPE = "kl"


def _ids(values, count: int, label: str) -> list[str]:
    result = [str(i) for i in range(count)] if values is None else list(map(str, values))
    if len(result) != count or len(set(result)) != count:
        raise ValueError(f"{label} must contain exactly {count} unique IDs")
    return result


def _safe(values):
    """Convert numeric arrays to JSON-safe values, representing nonfinite as None."""
    array = np.asarray(values, dtype=float)
    if array.ndim == 0:
        return float(array) if np.isfinite(array) else None
    return [_safe(value) for value in array]


def _vector(value, label: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{label} must be one-dimensional")
    return array


def _matrix(value, width: int, label: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.size == 0 and array.ndim == 1:
        array = array.reshape(0, width)
    if array.ndim != 2 or array.shape[1] != width:
        raise ValueError(f"{label} must have shape (n, {width})")
    return array


def _unit_rows(rows: np.ndarray):
    # Scaling before norm avoids overflow for large but finite embeddings.
    valid = np.isfinite(rows).all(axis=1)
    scale = np.max(np.abs(rows), axis=1) if rows.shape[1] else np.zeros(len(rows))
    valid &= scale > 0
    normalized = np.full(rows.shape, np.nan)
    if valid.any():
        scaled = rows[valid] / scale[valid, None]
        normalized[valid] = scaled / np.linalg.norm(scaled, axis=1, keepdims=True)
    return normalized, valid


def cosine_scores(query_embedding, candidate_embeddings, *, candidate_ids=None):
    """Cosine from one query row and candidate rows; invalid/zero rows -> None.

    Returns scores, per-row availability and IDs. Inputs are not modified. The
    caller must ensure a common encoder, dimensionality and representation policy.
    """
    query = _vector(query_embedding, "query_embedding")
    if not query.size:
        raise ValueError("embedding dimension must be positive")
    candidates = _matrix(candidate_embeddings, query.size, "candidate_embeddings")
    ids = _ids(candidate_ids, len(candidates), "candidate_ids")
    q, q_valid = _unit_rows(query[None, :])
    c, c_valid = _unit_rows(candidates)
    available = c_valid & bool(q_valid[0])
    scores = np.full(len(candidates), np.nan)
    scores[available] = np.clip(c[available] @ q[0], -1.0, 1.0)
    reasons = [None if ok else ("invalid_query_embedding" if not q_valid[0]
               else "nonfinite_or_zero_candidate_embedding") for ok in available]
    return {"method": "cosine", "direction": "higher", "candidate_ids": ids,
            "scores": _safe(scores), "available": available.tolist(),
            "reasons": reasons, "status": "ok" if available.all() and len(ids)
            else "partial" if available.any() else "unavailable"}


def cosine_cost_matrix(source_embeddings, target_embeddings):
    """Return 1-cosine costs for activity rows, with unknown cells as None.

    The range is [0, 2] for valid rows. This choice of ground cost is an explicit
    hypothesis; no company/business-materiality interpretation is supplied.
    """
    source = np.asarray(source_embeddings, dtype=float)
    if source.ndim != 2 or source.shape[1] == 0:
        raise ValueError("source_embeddings must be (n, positive_dimension)")
    target = _matrix(target_embeddings, source.shape[1], "target_embeddings")
    s, sv = _unit_rows(source)
    t, tv = _unit_rows(target)
    costs = 1.0 - np.clip(s @ t.T, -1.0, 1.0)
    available = sv[:, None] & tv[None, :]
    return {"cost_matrix": _safe(costs), "source_available": sv.tolist(),
            "target_available": tv.tolist(), "available": available.tolist(),
            "status": "ok" if available.size and available.all() else "partial"
            if available.any() else "unavailable", "cost_definition": "1-cosine"}


def _transport_inputs(cost_matrix, source_mass, target_mass, source_ids, target_ids):
    a = _vector(source_mass, "source_mass")
    b = _vector(target_mass, "target_mass")
    costs = np.asarray(cost_matrix, dtype=float)
    if costs.shape != (len(a), len(b)):
        raise ValueError("cost_matrix shape must match the two mass vectors")
    meta = {"source_ids": _ids(source_ids, len(a), "source_ids"),
            "target_ids": _ids(target_ids, len(b), "target_ids"),
            "source_mass": _safe(a), "target_mass": _safe(b),
            "mass_normalization": "none", "cost_matrix": _safe(costs)}
    if (a < 0).any() or (b < 0).any() or (costs < 0).any():
        raise ValueError("mass and ground costs must be nonnegative")
    if not len(a) or not len(b) or not all(np.isfinite(x).all() for x in (a, b, costs)):
        return a, b, costs, {**meta, "status": "unavailable", "reason": "empty_or_nonfinite_input"}
    if not np.isfinite(a.sum()) or not np.isfinite(b.sum()):
        raise ValueError("total mass must be finite")
    if a.sum() <= 0 or b.sum() <= 0:
        return a, b, costs, {**meta, "status": "unavailable", "reason": "zero_total_mass"}
    return a, b, costs, {**meta, "status": "ready"}


def _pot(expected_version: str):
    try:
        import ot
    except ImportError:
        return None, {"status": "unavailable", "reason": "POT_not_installed"}
    info = {"pot_version": ot.__version__, "expected_pot_version": expected_version}
    if ot.__version__ != expected_version:
        return None, {**info, "status": "unavailable", "reason": "POT_version_mismatch"}
    return ot, info


def _plan_diagnostics(plan, a, b, costs):
    rows, columns = plan.sum(axis=1), plan.sum(axis=0)
    return {"plan": _safe(plan), "source_marginal": _safe(rows),
            "target_marginal": _safe(columns), "transported_mass": float(plan.sum()),
            "source_deficit": _safe(np.maximum(a - rows, 0)),
            "source_surplus": _safe(np.maximum(rows - a, 0)),
            "target_deficit": _safe(np.maximum(b - columns, 0)),
            "target_surplus": _safe(np.maximum(columns - b, 0)),
            "source_l1_deviation": float(np.abs(rows - a).sum()),
            "target_l1_deviation": float(np.abs(columns - b).sum()),
            "linear_cost": float(np.sum(plan * costs))}


def generalized_kl(measure, reference) -> float:
    """sum(p log(p/q) - p + q), including mass correction and zero conventions.

    KL(0,q)=q; KL(p,0)=infinity for p>0. Invalid/nonfinite measures raise.
    """
    p, q = np.asarray(measure, dtype=float), np.asarray(reference, dtype=float)
    if p.shape != q.shape or not np.isfinite(p).all() or not np.isfinite(q).all():
        raise ValueError("KL inputs must have matching shape and finite values")
    if (p < 0).any() or (q < 0).any():
        raise ValueError("KL inputs must be nonnegative")
    if ((p > 0) & (q == 0)).any():
        return float("inf")
    mask = p > 0
    value = np.sum(xlogy(p[mask], p[mask]) - xlogy(p[mask], q[mask])) - p.sum() + q.sum()
    return float(max(value, 0.0))  # protect against small cancellation below zero


def balanced_ot(cost_matrix, source_mass, target_mass, *, source_ids=None,
                target_ids=None, expected_pot_version=POT_VERSION,
                max_iterations=100000, marginal_tolerance=1e-8):
    """Exact unregularized balanced OT via POT's network-simplex emd solver.

    Equal positive total mass is required; no automatic renormalization. Report
    linear/full objective, plan and both marginal deviations. A solver warning or
    nonconserved marginal makes the result solver_failed with distance=None.
    """
    if max_iterations <= 0 or not np.isfinite(marginal_tolerance) or marginal_tolerance <= 0:
        raise ValueError("iteration limit and marginal tolerance must be positive")
    a, b, costs, result = _transport_inputs(cost_matrix, source_mass, target_mass, source_ids, target_ids)
    result.update(method="balanced_ot", direction="lower", distance=None)
    if result["status"] != "ready":
        return result
    if not np.isclose(a.sum(), b.sum(), rtol=1e-12, atol=1e-12):
        return {**result, "status": "unavailable", "reason": "unequal_total_mass"}
    ot, info = _pot(expected_pot_version)
    result.update(info)
    if ot is None:
        return result
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plan, log = ot.emd(a, b, costs, numItermax=max_iterations, log=True,
                           numThreads=1, check_marginals=True)
    notices = [str(item.message) for item in caught]
    if not np.isfinite(plan).all() or (plan < -marginal_tolerance).any():
        return {**result, "status": "solver_failed", "reason": "invalid_plan", "warnings": notices}
    diagnostics = _plan_diagnostics(plan, a, b, costs)
    good = (log.get("result_code") == 1 and not log.get("warning") and
            max(diagnostics["source_l1_deviation"], diagnostics["target_l1_deviation"]) <= marginal_tolerance)
    return {**result, **diagnostics, "status": "ok" if good else "solver_failed",
            "distance": diagnostics["linear_cost"] if good else None,
            "full_objective": diagnostics["linear_cost"],
            "objective_definition": "sum(plan * ground_cost), exact balanced marginals",
            "solver_result_code": log.get("result_code"),
            "solver_warning": log.get("warning"), "warnings": notices,
            "max_iterations": max_iterations, "marginal_tolerance": marginal_tolerance}


def unbalanced_ot(cost_matrix, source_mass, target_mass, *, reg, reg_m,
                  source_ids=None, target_ids=None, expected_pot_version=POT_VERSION,
                  max_iterations=10000, tolerance=1e-9):
    """Entropic UOT; explicit KL regularization and independently audited objective.

    Uses reg_type='kl', reference outer(a,b), and finite positive reg_m (scalar
    or source/target pair). Full objective is linear cost + reg*KL(plan,a*b)
    + rho_source*KL(row_sum,a) + rho_target*KL(col_sum,b), with generalized KL.
    POT's library_reported_total_cost is retained separately: its KL convention
    may omit mass correction. Scores across different regularizers/mass policies
    are not automatically comparable. Nonconvergence -> distance=None.
    """
    rho = np.asarray(reg_m, dtype=float).reshape(-1)
    if rho.size == 1:
        rho = np.repeat(rho, 2)
    if rho.size != 2 or not np.isfinite(rho).all() or (rho <= 0).any():
        raise ValueError("reg_m must be one or two finite positive penalties")
    if not np.isfinite(reg) or reg <= 0 or max_iterations <= 0 or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("reg, iteration limit and tolerance must be positive")
    a, b, costs, result = _transport_inputs(cost_matrix, source_mass, target_mass, source_ids, target_ids)
    result.update(method="unbalanced_ot", direction="lower", distance=None,
                  reg=float(reg), reg_m=rho.tolist(), reg_type=UOT_REG_TYPE,
                  reference_measure="outer(source_mass, target_mass)",
                  kl_convention="sum(p*log(p/q)-p+q)")
    if result["status"] != "ready":
        return result
    ot, info = _pot(expected_pot_version)
    result.update(info)
    if ot is None:
        return result
    # Zero-mass support is impossible under finite KL; solve only positive cells.
    ai, bi = a > 0, b > 0
    active_a, active_b = a[ai], b[bi]
    reference = np.outer(active_a, active_b)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        active_plan, log = ot.unbalanced.sinkhorn_unbalanced(
            active_a, active_b, costs[np.ix_(ai, bi)], reg=float(reg),
            reg_m=tuple(rho), method="sinkhorn", reg_type=UOT_REG_TYPE,
            c=reference, numItermax=max_iterations, stopThr=tolerance, log=True)
    notices = [str(item.message) for item in caught]
    if not np.isfinite(active_plan).all() or (active_plan < 0).any():
        return {**result, "status": "solver_failed", "reason": "invalid_plan", "warnings": notices}
    plan = np.zeros_like(costs)
    plan[np.ix_(ai, bi)] = active_plan
    diagnostics = _plan_diagnostics(plan, a, b, costs)
    terms = {"linear_cost": diagnostics["linear_cost"],
             "plan_kl_penalty": float(reg * generalized_kl(plan, np.outer(a, b))),
             "source_kl_penalty": float(rho[0] * generalized_kl(plan.sum(axis=1), a)),
             "target_kl_penalty": float(rho[1] * generalized_kl(plan.sum(axis=0), b))}
    objective = sum(terms.values())
    errors = log.get("err", [])
    converged = bool(errors and np.isfinite(errors[-1]) and errors[-1] < tolerance and not notices)
    return {**result, **diagnostics, "status": "ok" if converged else "solver_failed",
            "distance": float(objective) if converged else None,
            "full_objective": float(objective), "objective_terms": terms,
            "library_reported_total_cost": _safe(log.get("total_cost", np.nan)),
            "solver_method": "sinkhorn", "converged": converged,
            "final_solver_error": _safe(errors[-1]) if errors else None,
            "error_history_length": len(errors), "warnings": notices,
            "max_iterations": max_iterations, "tolerance": tolerance}


def sard_rank_distances(query_features, candidate_features, *, feature_names,
                        candidate_ids=None, weights=None, min_features=None,
                        rank_scale="raw", aggregation="sum"):
    """SARD-inspired weighted absolute average-rank differences; not original SARD.

    Rank each feature over finite query+candidate values, using average tie ranks.
    rank_scale='percentile' divides ranks by each feature's finite reference count.
    aggregation='mean' divides the weighted sum by declared positive weight sum.
    Default complete-case comparisons require every positive-weight feature.
    Explicit min_features permits partial comparisons; sums are rescaled by total
    declared weight/available weight, an unvalidated missingness assumption.
    Weights default to explicitly reported equal weights, not a claimed optimum.
    Returns distances plus negative-distance scores and feature/missingness data.
    """
    query = _vector(query_features, "query_features")
    if rank_scale not in ("raw", "percentile") or aggregation not in ("sum", "mean"):
        raise ValueError("rank_scale must be raw/percentile and aggregation sum/mean")
    candidates = _matrix(candidate_features, len(query), "candidate_features")
    names = _ids(feature_names, len(query), "feature_names")
    ids = _ids(candidate_ids, len(candidates), "candidate_ids")
    w = np.ones(len(query)) if weights is None else _vector(weights, "weights")
    if len(w) != len(query) or not np.isfinite(w).all() or (w < 0).any() or not (w > 0).any():
        raise ValueError("weights must match features, be finite/nonnegative, and have positive sum")
    active = w > 0
    required = int(active.sum()) if min_features is None else min_features
    if not isinstance(required, (int, np.integer)) or not 1 <= required <= active.sum():
        raise ValueError("min_features must be an integer within positive-weight feature count")
    values = np.vstack([query, candidates])
    ranks = np.full_like(values, np.nan)
    feature_metadata = []
    for j, name in enumerate(names):
        finite = np.isfinite(values[:, j])
        ranks[finite, j] = rankdata(values[finite, j], method="average")
        if rank_scale == "percentile" and finite.any():
            ranks[finite, j] /= finite.sum()
        feature_metadata.append({"feature": name, "weight": float(w[j]),
            "finite_reference_count": int(finite.sum()), "query_available": bool(finite[0]),
            "candidate_missing_count": int((~finite[1:]).sum()),
            "constant_observed_feature": bool(finite.any() and np.ptp(values[finite, j]) == 0)})
    distances = np.full(len(candidates), np.nan)
    row_meta = []
    for i, candidate_id in enumerate(ids):
        usable = active & np.isfinite(ranks[0]) & np.isfinite(ranks[i + 1])
        count = int(usable.sum())
        if count >= required:
            raw = np.sum(w[usable] * np.abs(ranks[i + 1, usable] - ranks[0, usable]))
            distances[i] = raw * w[active].sum() / w[usable].sum()
            if aggregation == "mean":
                distances[i] /= w[active].sum()
        row_meta.append({"candidate_id": candidate_id, "used_features": [names[j] for j in np.flatnonzero(usable)],
            "missing_features": [names[j] for j in np.flatnonzero(active & ~usable)],
            "used_count": count, "required_count": int(required),
            "available_weight": float(w[usable].sum()),
            "reason": None if count >= required else "insufficient_shared_finite_features"})
    available = np.isfinite(distances)
    return {"method": "sard_inspired_rank_distance", "candidate_ids": ids,
            "distances": _safe(distances), "scores": _safe(-distances),
            "distance_direction": "lower", "score_direction": "higher",
            "status": "ok" if available.size and available.all() else "partial"
            if available.any() else "unavailable", "feature_metadata": feature_metadata,
            "candidate_metadata": row_meta, "weights": w.tolist(),
            "rank_scale": rank_scale, "aggregation": aggregation,
            "percentile_definition": "average_rank / finite_reference_count" if rank_scale == "percentile" else None,
            "rank_reference": "finite query plus candidate universe, average ties",
            "missingness_policy": "complete_case" if required == active.sum()
            else "partial_weight_rescaled_explicit_adaptation"}


def reciprocal_rank_fusion(rankings: Mapping[str, Sequence], *, weights: Mapping,
                           constant=60.0, candidate_ids=None):
    """Predeclared weighted reciprocal-rank fusion of aligned complete rankings.

    Ranks start at one. Score=sum(w_j/(constant+rank_j))/sum(w_j). A candidate
    absent from any positive-weight component is unavailable, not implicitly
    assigned zero relevance. Callers must distinguish full ranks from shortlists.
    """
    if not rankings or set(rankings) != set(weights):
        raise ValueError("rankings and weights must have matching nonempty keys")
    if not np.isfinite(constant) or constant <= 0:
        raise ValueError("constant must be finite and positive")
    names = list(rankings)
    w = np.asarray([weights[name] for name in names], dtype=float)
    if not np.isfinite(w).all() or (w < 0).any() or not (w > 0).any():
        raise ValueError("weights must be finite, nonnegative, and not all zero")
    rank_maps = {}
    union = set()
    for name in names:
        values = _ids(rankings[name], len(rankings[name]), f"{name} ranking")
        rank_maps[name] = {value: index + 1 for index, value in enumerate(values)}
        union.update(values)
    ids = sorted(union) if candidate_ids is None else _ids(candidate_ids, len(candidate_ids), "candidate_ids")
    scores, missing = [], []
    for value in ids:
        absent = [name for name, weight in zip(names, w) if weight > 0 and value not in rank_maps[name]]
        missing.append(absent)
        scores.append(None if absent else float(sum(weight / (constant + rank_maps[name][value])
                      for name, weight in zip(names, w) if weight > 0) / w.sum()))
    available = [value is not None for value in scores]
    return {"method": "reciprocal_rank_fusion", "direction": "higher",
            "candidate_ids": ids, "scores": scores, "available": available,
            "missing_components": missing, "weights": dict(zip(names, w.tolist())),
            "constant": float(constant), "status": "ok" if ids and all(available)
            else "partial" if any(available) else "unavailable",
            "missingness_policy": "require_all_positive_weight_components"}


def hybrid_zscore(component_scores: Mapping[str, Sequence], *, weights: Mapping,
                  directions: Mapping, candidate_ids=None):
    """Combine oriented candidate-wise z-scores with declared nonnegative weights.

    directions maps each component to 'higher' or 'lower'. Population std (ddof=0)
    uses its finite candidate scores; means/std/counts are returned. Positive-weight
    missing components make a candidate unavailable, with no implicit reweighting.
    Constant finite components contribute zero centered information, not evidence
    of similarity; if every active component is constant, no ranking is available.
    """
    if not component_scores or set(component_scores) != set(weights) or set(weights) != set(directions):
        raise ValueError("components, weights and directions must have identical nonempty keys")
    names = list(component_scores)
    arrays = [_vector(component_scores[name], name) for name in names]
    n = len(arrays[0])
    if any(len(array) != n for array in arrays):
        raise ValueError("component candidate order and lengths must match")
    ids = _ids(candidate_ids, n, "candidate_ids")
    w = np.asarray([weights[name] for name in names], dtype=float)
    if not np.isfinite(w).all() or (w < 0).any() or not (w > 0).any():
        raise ValueError("weights must be finite, nonnegative, with positive sum")
    z = np.full((n, len(names)), np.nan)
    metadata = {}
    informative = False
    for j, (name, values) in enumerate(zip(names, arrays)):
        if directions[name] not in ("higher", "lower"):
            raise ValueError("directions must be 'higher' or 'lower'")
        finite = np.isfinite(values)
        oriented = values[finite] * (1 if directions[name] == "higher" else -1)
        mean = float(oriented.mean()) if finite.any() else np.nan
        std = float(oriented.std(ddof=0)) if finite.any() else np.nan
        state = "unavailable"
        if finite.any() and np.isfinite(mean) and np.isfinite(std):
            if std > 0:
                z[finite, j] = (oriented - mean) / std
                informative |= bool(w[j] > 0)
                state = "informative"
            else:
                z[finite, j] = 0
                state = "constant"
        metadata[name] = {"weight": float(w[j]), "direction": directions[name],
            "mean_oriented": _safe(mean), "population_std": _safe(std),
            "finite_count": int(finite.sum()), "status": state}
    active = w > 0
    complete = np.isfinite(z[:, active]).all(axis=1)
    scores = np.full(n, np.nan)
    if informative:
        scores[complete] = z[complete][:, active] @ w[active] / w[active].sum()
    available = np.isfinite(scores)
    return {"method": "predeclared_zscore_hybrid", "direction": "higher",
            "candidate_ids": ids, "scores": _safe(scores), "available": available.tolist(),
            "status": "ok" if available.size and available.all() else "partial"
            if available.any() else "unavailable", "components": metadata,
            "z_scores": {name: _safe(z[:, j]) for j, name in enumerate(names)},
            "missingness_policy": "complete_positive_weight_components_no_reweighting",
            "reason": None if informative else "no_informative_positive_weight_component"}


def aggregate_multiples(peer_ids, multiples, *, method="median", weights=None,
                       positive_only=True):
    """Aggregate precomputed multiples with explicit contributing/excluded IDs.

    methods: 'median', 'harmonic', 'weighted'. Harmonic always requires positive
    values. Default positive_only applies the same positive eligibility to all
    methods. weighted means a nonnegative weighted ARITHMETIC mean of multiples;
    weights must be supplied, not inferred from labels or similarity. Zero weights
    are explicit noncontributors. Caller must freeze rows for a fair comparison.
    """
    values = _vector(multiples, "multiples")
    ids = _ids(peer_ids, len(values), "peer_ids")
    if method not in ("median", "harmonic", "weighted"):
        raise ValueError("method must be median, harmonic, or weighted")
    if method != "weighted" and weights is not None:
        raise ValueError("weights are accepted only for the explicit weighted method")
    if method == "weighted" and weights is None:
        raise ValueError("weighted method requires predeclared weights")
    w = np.ones(len(values)) if weights is None else _vector(weights, "weights")
    if len(w) != len(values) or (w < 0).any():
        raise ValueError("weights must match multiples and cannot be negative")
    positive_required = bool(positive_only or method == "harmonic")
    valid, excluded = [], []
    for i, peer_id in enumerate(ids):
        reason = ("nonfinite_multiple" if not np.isfinite(values[i]) else
                  "nonpositive_multiple" if positive_required and values[i] <= 0 else
                  "nonfinite_weight" if not np.isfinite(w[i]) else
                  "zero_weight" if w[i] == 0 else None)
        if reason:
            excluded.append({"peer_id": peer_id, "reason": reason,
                             "multiple": _safe(values[i]), "weight": _safe(w[i])})
        else:
            valid.append(i)
    result = {"method": method, "positive_only": positive_required,
              "selected_count": len(ids), "valid_count": len(valid),
              "valid_ids": [ids[i] for i in valid], "excluded": excluded,
              "valid_multiples": _safe(values[valid]), "valid_weights": _safe(w[valid]),
              "estimate": None, "status": "unavailable", "effective_peer_count": None}
    if not valid:
        return {**result, "reason": "no_eligible_contributing_peers"}
    v, vw = values[valid], w[valid]
    # Stable scaling avoids reciprocal/weighted-sum overflow for finite inputs.
    if method == "median":
        ordered = np.sort(v)
        middle = len(ordered) // 2
        estimate = ordered[middle] if len(ordered) % 2 else (
            0.5 * ordered[middle - 1] + 0.5 * ordered[middle])
    elif method == "harmonic":
        scale = v.min()
        estimate = scale * (len(v) / np.sum(scale / v))
    else:
        normalized_weights = vw / vw.max()
        normalized_weights /= normalized_weights.sum()
        scale = np.max(np.abs(v))
        estimate = 0.0 if scale == 0 else scale * np.sum(normalized_weights * (v / scale))
    normalized_weights = vw / vw.max()
    normalized_weights /= normalized_weights.sum()
    result.update(estimate=_safe(estimate),
                  status="ok" if np.isfinite(estimate) else "numerical_failure",
                  effective_peer_count=float(1 / np.sum(normalized_weights ** 2)),
                  max_normalized_weight=float(normalized_weights.max()))
    return result
