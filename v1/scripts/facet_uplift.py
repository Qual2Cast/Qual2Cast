"""Offline, exploratory X-learners for facet match signals versus human peer labels.

Run from the root: uv run python v1/scripts/facet_uplift.py
No LLM, search, financial inputs, or pipeline changes. See v1/FACET_UPLIFT.md.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, roc_auc_score, mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
LABELS = V1 / "integration/review/pairs.csv"
AGENT = V1 / "agent_loop/ranking_45targets_sonnet/verdicts.csv"
# Same profile condition as the saved agent run, rather than mixing corrections.
FACETS = V1 / "facets_sonnet/tables/facets.csv"
OUT = V1 / "facet_uplift"
MIN_ARM = 15
MIN_TARGETS = 5


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group_splits(groups: np.ndarray, folds: int = 5, seed: int = 42):
    """Same target never appears on both sides; deterministic across sources."""
    unique = np.array(sorted(set(groups)))
    np.random.default_rng(seed).shuffle(unique)
    for held in np.array_split(unique, min(folds, len(unique))):
        test = np.isin(groups, held)
        yield np.flatnonzero(~test), np.flatnonzero(test)


def weights(groups: np.ndarray) -> np.ndarray:
    _, inverse, count = np.unique(groups, return_inverse=True, return_counts=True)
    w = 1 / count[inverse]
    return w / w.mean()


def model(kind: str):
    estimator = (LogisticRegression(C=0.1, max_iter=2000) if kind == "binary"
                 else Ridge(alpha=10))
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True,
                                       keep_empty_features=True),
                         StandardScaler(), estimator)


def fit_predict(x, y, groups, test, kind="binary"):
    if not len(y):
        raise ValueError("empty training arm")
    # A constant response in a small inner arm is explicit, not a model failure.
    if len(np.unique(y)) == 1:
        return np.full(len(test), float(y[0]))
    fitted = model(kind)
    fitted.fit(x, y, **{f"{fitted.steps[-1][0]}__sample_weight": weights(groups)})
    if kind == "binary":
        return fitted.predict_proba(test)[:, 1]
    prediction = fitted.predict(test)
    # Rating response models estimate E[grade | X,T], bounded to the grade scale.
    # Effect regressions remain unbounded so unstable effects can be flagged.
    return np.clip(prediction, 0, 2) if kind == "rating" else prediction


def treatment(train: np.ndarray, values: np.ndarray, source: str, rule: str):
    """Thresholds use outer training scores only; unknown is never control."""
    observed = train[np.isfinite(train)]
    if not len(observed):
        return np.full(len(values), np.nan), np.nan, np.nan
    if source == "agent":
        low, high = (50., 75.) if rule == "primary" else (25., 75.)
    elif rule == "primary":
        low = high = float(np.median(observed))
    else:
        low, high = np.quantile(observed, [1/3, 2/3])
        if low >= high:
            return np.full(len(values), np.nan), float(low), float(high)
    result = np.full(len(values), np.nan)
    result[np.isfinite(values) & (values <= low)] = 0
    result[np.isfinite(values) & ((values > high) if low == high else (values >= high))] = 1
    return result, float(low), float(high)


def arm_support(t, groups):
    return all(int((t == a).sum()) >= MIN_ARM and len(set(groups[t == a])) >= MIN_TARGETS
               for a in (0, 1))


def estimate_fold(x, y, t, groups, xt, tt, outcome="peer"):
    """Inner group cross-fitting makes pseudo-effects without own-target outcomes."""
    if outcome not in ("peer", "rating"):
        raise ValueError("outcome must be peer or rating")
    response_kind = "binary" if outcome == "peer" else "rating"
    pseudo = np.full(len(y), np.nan)
    for train, valid in group_splits(groups, 3):
        for arm in (0, 1):
            own = valid[t[valid] == arm]
            opposite = train[t[train] == 1-arm]
            if not len(own) or not len(opposite):
                continue
            counter = fit_predict(x[opposite], y[opposite], groups[opposite], x[own], response_kind)
            pseudo[own] = y[own] - counter if arm == 1 else counter - y[own]
    mu, tau = {}, {}
    for arm in (0, 1):
        rows = np.flatnonzero(t == arm)
        usable = rows[np.isfinite(pseudo[rows])]
        if len(usable) < MIN_ARM or len(set(groups[usable])) < MIN_TARGETS:
            raise ValueError("insufficient inner cross-fit pseudo-effects")
        mu[arm] = fit_predict(x[rows], y[rows], groups[rows], xt, response_kind)
        tau[arm] = fit_predict(x[usable], pseudo[usable], groups[usable], xt, "effect")
    propensity = fit_predict(x, t.astype(int), groups, xt)
    uplift = propensity * tau[0] + (1-propensity) * tau[1]
    observed_probability = np.where(tt == 1, mu[1], mu[0])
    return uplift, propensity, mu[0], mu[1], observed_probability


def build_features(cache: Path):
    import facet_weighting as fw
    labels = pd.read_csv(LABELS, dtype={"target_id": str, "comp_id": str})
    pairs = labels.rename(columns={"target_id": "target", "comp_id": "comp"})[
        ["target", "comp", "target_ticker", "comp_ticker", "score_barbara"]].copy()
    if pairs.duplicated(["target", "comp"]).any() or not pairs.score_barbara.isin([0, 1, 2]).all():
        raise ValueError("Expected unique, completely reviewed 0–2 pairs")
    pairs["peer"] = (pairs.score_barbara >= 1).astype(int)
    agent = pd.read_csv(AGENT, dtype={"target": str, "comp": str})
    if agent.duplicated(["target", "comp"]).any():
        raise ValueError("Duplicate agent pair")
    columns = [c for c in agent if c.startswith("facet_") and c not in ("facet_scores", "facet_weights")]
    numeric = agent[["target", "comp", "status", *columns]].copy()
    numeric.loc[numeric.status != "ok", columns] = np.nan
    numeric = numeric.drop(columns="status").rename(columns={c: c.replace("facet_", "agent__", 1) for c in columns})
    pairs = pairs.merge(numeric, on=["target", "comp"], how="left", validate="one_to_one")
    for c in numeric.columns[2:]:
        if not pairs[c].dropna().isin([0, 25, 50, 75, 100]).all():
            raise ValueError(f"Invalid agent score: {c}")
    profiles = pd.read_csv(FACETS).fillna("")
    texts = fw.facet_texts(profiles)
    ids = list(texts.index)
    pos = {k: i for i, k in enumerate(ids)}
    if not (set(pairs.target) | set(pairs.comp)).issubset(pos):
        raise ValueError("Reviewed company missing from profiles")
    wanted = {s for col in texts for s in texts[col].dropna()}
    seed = fw.load_text_cache(V1 / "embeddings/texts_all-mpnet-base-v2.npz")
    def offline_embed(items):
        from sentence_transformers import SentenceTransformer
        encoder = SentenceTransformer("sentence-transformers/all-mpnet-base-v2", local_files_only=True)
        return encoder.encode(items, batch_size=64, normalize_embeddings=True, show_progress_bar=True)
    vectors = fw.embed_texts(wanted, cache, embed=offline_embed,
                            seed={s: seed[fw._key(s)] for s in wanted if fw._key(s) in seed})
    lexical, _, _ = fw.lexical(texts)
    components = fw.blend(fw.embedding_cosines(texts, vectors), lexical)
    a, b = pairs.target.map(pos).to_numpy(), pairs.comp.map(pos).to_numpy()
    for facet, matrix in components.items():
        pairs[f"b3__{facet}"] = matrix[a, b]
    return pairs


def analyze(pairs: pd.DataFrame, outcome="peer"):
    if outcome not in ("peer", "rating"):
        raise ValueError("outcome must be peer or rating")
    predictions, diagnostics = [], []
    groups = pairs.target.to_numpy()
    y = pairs["peer" if outcome == "peer" else "score_barbara"].to_numpy()
    if not np.isin(y, [0, 1] if outcome == "peer" else [0, 1, 2]).all():
        raise ValueError("Invalid human outcome values")
    for source in ("b3", "agent"):
        columns = [c for c in pairs if c.startswith(source + "__")]
        for column in columns:
            score = pairs[column].to_numpy(float)
            x = pairs[[c for c in columns if c != column]].to_numpy(float)
            for rule in ("primary", "extreme"):
                for fold, (train, valid) in enumerate(group_splits(groups)):
                    t, low, high = treatment(score[train], score, source, rule)
                    train = train[np.isfinite(t[train])]
                    test = valid[np.isfinite(t[valid])]
                    record = dict(source=source, facet=column.split("__", 1)[1], rule=rule,
                                  fold=fold, threshold_low=low, threshold_high=high,
                                  train_n=len(train), test_n=len(test),
                                  unknown_test=int(np.isnan(score[valid]).sum()),
                                  middle_test=int((np.isfinite(score[valid]) & np.isnan(t[valid])).sum()),
                                  controls=int((t[train] == 0).sum()), treated=int((t[train] == 1).sum()))
                    for arm in (0, 1):
                        record[f"targets_arm_{arm}"] = len(set(groups[train][t[train] == arm]))
                    if not len(test) or not arm_support(t[train], groups[train]):
                        diagnostics.append(record | {"status": "insufficient_support"})
                        continue
                    try:
                        tau, e, m0, m1, probability = estimate_fold(
                            x[train], y[train], t[train], groups[train], x[test], t[test], outcome)
                    except ValueError as error:
                        diagnostics.append(record | {"status": str(error)})
                        continue
                    diagnostics.append(record | {"status": "ok"})
                    clipped = np.clip(e, .05, .95)
                    dr = m1-m0 + t[test]*(y[test]-m1)/clipped - (1-t[test])*(y[test]-m0)/(1-clipped)
                    out = pairs.iloc[test][["target", "comp", "target_ticker", "comp_ticker", "peer", "score_barbara"]].copy()
                    for key in ("source", "facet", "rule", "fold"):
                        out[key] = record[key]
                    out["treatment"] = t[test]
                    out["facet_signal"] = score[test]
                    out["uplift"] = tau
                    out["propensity"] = e
                    out["overlap"] = (e >= .1) & (e <= .9)
                    out["dr_pseudo_effect"] = dr
                    out["outcome"] = outcome
                    out["outcome_value"] = y[test]
                    out["predicted_outcome"] = probability
                    out["baseline_outcome"] = np.average(y[train], weights=weights(groups[train]))
                    if outcome == "peer":
                        out["observed_probability"] = probability
                        out["baseline_probability"] = out["baseline_outcome"]
                    predictions.append(out)
    return (pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame(),
            pd.DataFrame(diagnostics))


def summarize(predictions, diagnostics, repetitions=1000, outcome="peer"):
    rows, calibration = [], []
    for key, folds in diagnostics.groupby(["source", "facet", "rule"]):
        row = dict(zip(["source", "facet", "rule"], key))
        row.update(folds_ok=int(folds.status.eq("ok").sum()), folds_total=len(folds))
        part = predictions
        for k, v in zip(["source", "facet", "rule"], key):
            if len(part):
                part = part[part[k] == v]
        row["predicted_pairs"] = len(part)
        row["status"] = "complete" if row["folds_ok"] == 5 else "partial_or_unsupported"
        if len(part):
            row["overlap_pairs"] = int(part.overlap.sum())
            row["outcome"] = outcome
            if outcome == "peer":
                row.update(brier=brier_score_loss(part.peer, part.observed_probability),
                           baseline_brier=brier_score_loss(part.peer, part.baseline_probability),
                           response_auc=roc_auc_score(part.peer, part.observed_probability) if part.peer.nunique() == 2 else np.nan,
                           outside_probability_range=int((part.uplift.abs() > 1).sum()))
            else:
                row.update(mae=mean_absolute_error(part.outcome_value, part.predicted_outcome),
                           rmse=float(np.sqrt(mean_squared_error(part.outcome_value, part.predicted_outcome))),
                           baseline_mae=mean_absolute_error(part.outcome_value, part.baseline_outcome),
                           baseline_rmse=float(np.sqrt(mean_squared_error(part.outcome_value, part.baseline_outcome))),
                           outside_rating_effect_range=int((part.uplift.abs() > 2).sum()))
            overlap = part[part.overlap].copy()
            if len(overlap):
                by_target = overlap.groupby("target")[["uplift", "dr_pseudo_effect"]].mean()
                row.update(overlap_targets=len(by_target),
                           mean_uplift=by_target.uplift.mean(),
                           dr_adjusted_difference=by_target.dr_pseudo_effect.mean())
                rng = np.random.default_rng(42)
                boot = rng.choice(by_target.uplift.to_numpy(), (repetitions, len(by_target)), replace=True).mean(axis=1)
                row["uplift_ci_low"], row["uplift_ci_high"] = np.quantile(boot, [.025, .975])
                # Descriptive diagnostic only: DR scores are not observed effect truth.
                if overlap.uplift.nunique() >= 3:
                    overlap["uplift_bin"] = pd.qcut(overlap.uplift, 3, labels=False, duplicates="drop")
                    for bucket, block in overlap.groupby("uplift_bin"):
                        target = block.groupby("target")[["uplift", "dr_pseudo_effect"]].mean()
                        calibration.append(dict(zip(["source", "facet", "rule"], key)) |
                                           dict(bin=int(bucket), pairs=len(block), targets=len(target),
                                                predicted_uplift=target.uplift.mean(),
                                                dr_adjusted_difference=target.dr_pseudo_effect.mean()))
        rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(calibration)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--outcome", choices=["peer", "rating"], default="peer",
                    help="peer: combined 1/2 vs 0; rating: expected original 0/1/2 grade")
    args = ap.parse_args()
    if args.bootstrap < 1:
        ap.error("--bootstrap must be positive")
    run = args.out / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run.mkdir(parents=True, exist_ok=False)
    pairs = build_features(args.out / "cache/sonnet_texts.npz")
    pairs.to_csv(run / "pair_features.csv", index=False)
    predictions, diagnostics = analyze(pairs, args.outcome)
    summary, calibration = summarize(predictions, diagnostics, args.bootstrap, args.outcome)
    for name, frame in (("oof_effects", predictions), ("fold_diagnostics", diagnostics),
                        ("facet_summary", summary), ("uplift_bins", calibration)):
        frame.to_csv(run / f"{name}.csv", index=False)
    manifest = {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "script_sha256": digest(Path(__file__)), "cohort": "Barbara only, selected reviewed pairs",
                "pairs": len(pairs), "targets": pairs.target.nunique(),
                "outcome": "human grade >= 1" if args.outcome == "peer" else "expected human grade on 0/1/2 scale",
                "outcome_mode": args.outcome,
                "effect_units": "probability difference" if args.outcome == "peer" else "rating points",
                "response_estimator": "logistic C=0.1" if args.outcome == "peer" else "ridge alpha=10; predictions clipped to [0,2]",
                "rating_assumption": "0→1 and 1→2 are equally spaced; not a multiclass probability model" if args.outcome == "rating" else None,
                "sources": {str(p.relative_to(ROOT)): digest(p) for p in [LABELS, AGENT, FACETS]},
                "settings": {"outer_folds": 5, "inner_folds": 3, "seed": 42,
                             "min_arm": MIN_ARM, "min_arm_targets": MIN_TARGETS,
                             "logistic_C": .1, "ridge_alpha": 10, "overlap": [.1, .9],
                             "dr_propensity_clip": [.05, .95], "bootstrap": args.bootstrap,
                             "primary": {"b3": "training median", "agent": "75/100 vs 0/25/50"},
                             "sensitivity": {"b3": "training upper vs lower thirds", "agent": "75/100 vs 0/25"},
                             "model_weighting": "equal total weight per training target"},
                "libraries": {name: version(name) for name in ["numpy", "pandas", "scikit-learn", "sentence-transformers", "torch"]},
                "embedding_cache_sha256": digest(args.out / "cache/sonnet_texts.npz"),
                "interpretation": "Exploratory adjusted associations, not identified causal CATE. Fixed unlabeled 533-company text representation; target-group outcome cross-fitting. Shared comp companies may cross folds.",
                "uncertainty": "Target bootstrap of fixed OOF predictions; excludes refitting, selection, reviewer and threshold uncertainty."}
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    primary = summary[summary.rule.eq("primary")]
    complete = primary[primary.status.eq("complete")].groupby("source").size().to_dict()
    (run / "report.md").write_text(
        f"# Exploratory facet lift\n\n{len(pairs)} reviewed pairs, {pairs.target.nunique()} targets, Barbara only.\n\n"
        f"Outcome: {manifest['outcome']}. Effect units: {manifest['effect_units']}.\n\n"
        f"Complete five-fold analyses: B3 {complete.get('b3', 0)}/11; agent {complete.get('agent', 0)}/11. "
        "Partial and unsupported facets remain in facet_summary.csv; missing effects are not zero.\n\n"
        "Use the companion notebook for estimates, missingness and fold support. Unsupported facets are retained in the summary. "
        "Brier/AUC (binary) or MAE/RMSE (rating) assess response predictions, not accuracy of treatment effects. "
        "Rating analysis assumes equal spacing between grades; it does not estimate separate category probabilities. "
        "DR bins are adjusted diagnostics, not effect ground truth. "
        "Do not use uplift to rank comp quality or add effects across correlated facets. "
        "No causal identification, unreviewed-universe generalization, or pipeline improvement is established.\n")
    print(summary[["source", "facet", "rule", "status", "predicted_pairs"]].to_string(index=False))
    print(f"Run: {run}")


if __name__ == "__main__":
    main()
