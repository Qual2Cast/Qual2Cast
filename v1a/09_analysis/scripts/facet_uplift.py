"""Offline X-learners: which facet matches go with good comps (people's grades) and with the LLM selector's keeps.

v1: v1/scripts/facet_uplift.py (Kethan, 11-13). The estimator (outer/inner target folds, logistic or ridge response
models, ridge effect models, propensity-weighted combination, overlap filter, target bootstrap) is unchanged; see
FACET_UPLIFT.md. v1a adds:

  --cohort    the reviewed pairs, by cohort name (06_labels/scripts/cohorts.py): dev_293 (default), round1_36,
              matthew_v2_262; or b3_current, every pair in the current B3 comp lists (03). The locked
              final_holdout_24 cohort is refused.
  --outcome   peer (grade >= 1), rating (grade 0/1/2), or selector (the current LLM selector kept the comp,
              04_selection judgments in current.toml; works on any cohort, including b3_current).
  --features  current (default): B3 per-facet signals of the current variant ("Sonnet + Fiona sub-sector", so a
              12th signal, sub_sector); record: v1's 11 general-facet signals, which reproduces the pinned v1 runs.

Treatment sources, each analysed separately with its own other signals as covariates:
  b3        each facet's 0.5 embedding + 0.5 TF-IDF similarity (above vs at/below the training median)
  agent     the agent loop's facet scores, where the agent graded the pair (75/100 vs 0/25/50; null = unknown)
  selector  only with a human outcome: the selector's keep vs drop, adjusted for the B3 signals. This is the
            selector's lift over what the B3 facets already tell (stage ablation of 04).
  agent_grade  only with a human outcome: the agent's overall grade (05) peer (1/2) vs non-peer (0), adjusted for
            the B3 signals; pairs the agent did not grade are left out. Stage ablation of 05 (added 2026-11-18).

  uv run python v1a/09_analysis/scripts/facet_uplift.py --cohort b3_current --outcome selector
No LLM, search or financial inputs. Writes outputs-local/v1a/09_analysis/facet_uplift/<stamp>/ (never overwrites).
"""
from __future__ import annotations

import sys as _sys  # v1a: shared paths (common/paths.py) put every component's scripts on the path
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v1a  # noqa: E402
v1a.setup()

import argparse  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
import hashlib  # noqa: E402
from importlib.metadata import version  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
import subprocess  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LogisticRegression, Ridge  # noqa: E402
from sklearn.metrics import brier_score_loss, roc_auc_score, mean_absolute_error, mean_squared_error  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

ROOT = v1a.ROOT
OUT = v1a.out("09_analysis") / "facet_uplift"
COHORTS = ("dev_293", "round1_36", "matthew_v2_262", "b3_current")
OUTCOMES = {"peer": "peer", "rating": "grade", "selector": "selector_keep"}   # outcome -> column
BINARY = {"peer", "selector"}
STAGES = {"selector": ("selector_keep", "keep"), "agent_grade": ("agent_peer", "peer")}   # source -> column, facet
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
    if source in STAGES:
        low, high = 0., 1.                     # selector keep vs drop; agent peer vs non-peer
    elif source == "agent":
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
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {list(OUTCOMES)}")
    response_kind = "binary" if outcome in BINARY else "rating"
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


# ------------------------------------------------------------------ inputs

def current_pairs() -> pd.DataFrame:
    """Every pair in the current B3 comp lists (training targets), no human grade."""
    top = pd.read_csv(v1a.path(v1a.current()["retrieval"]["candidates"]) / "candidates.csv",
                      dtype={"target": str, "comp": str})
    top = top[top["selected"]]
    return top[["target", "comp", "target_ticker", "comp_ticker"]].assign(grade=np.nan).reset_index(drop=True)


def load_pairs(cohort: str) -> pd.DataFrame:
    """target, comp, tickers and the human grade (NaN for b3_current)."""
    if cohort == "b3_current":
        return current_pairs()
    import cohorts
    if cohort in cohorts.LOCKED:
        raise cohorts.LockedCohort(f"{cohort} is the locked final check; not used for analysis")
    pairs = cohorts.load(cohort).rename(columns={"target_id": "target", "comp_id": "comp"})
    pairs = pairs[["target", "comp", "target_ticker", "comp_ticker", "grade"]].copy()
    if pairs.duplicated(["target", "comp"]).any() or not pairs.grade.isin([0, 1, 2]).all():
        raise ValueError("Expected unique, completely reviewed 0-2 pairs")
    return pairs


def selector_keeps(pairs: pd.DataFrame, judgments: Path) -> pd.Series:
    j = pd.read_csv(judgments, dtype={"target": str, "comp": str})
    if j.duplicated(["target", "comp"]).any():
        raise ValueError("Duplicate selector judgment")
    keep = pairs.merge(j[["target", "comp", "score"]], on=["target", "comp"], how="left", validate="one_to_one")["score"]
    if keep.isna().any():
        raise ValueError(f"{int(keep.isna().sum())} pairs have no selector judgment in {judgments.name}")
    return keep.astype(int).to_numpy()


def b3_signals(ids: list[str], features: str) -> dict[str, np.ndarray]:
    """Per-facet B3 similarities of the current variant (03_retrieval), as in the comp lists."""
    import method1_candidates as m1
    per, _, _ = m1.per_facet(ids, v1a.current())
    if features == "record":          # v1's pinned runs: the 11 general facets only
        per = {k: v for k, v in per.items() if k != "Fiona sub-sector"}
    return {("sub_sector" if k == "Fiona sub-sector" else k): v for k, v in per.items()}


def build_features(cohort: str = "dev_293", outcome: str = "peer", features: str = "current",
                   agent_path: Path | None = None, judgments: Path | None = None) -> pd.DataFrame:
    cur = v1a.current()
    agent_path = agent_path or v1a.path(cur["agent_grading"]["run"]) / "verdicts.csv"
    judgments = judgments or v1a.path(cur["selection"]["judgments"])
    pairs = load_pairs(cohort)
    if outcome != "selector" and pairs.grade.isna().any():
        raise ValueError(f"{cohort} has no human grades; use --outcome selector")
    pairs["peer"] = np.where(pairs.grade.isna(), np.nan, (pairs.grade >= 1).astype(float))
    if outcome == "selector" or cohort != "b3_current":
        pairs["selector_keep"] = selector_keeps(pairs, judgments)
    agent = pd.read_csv(agent_path, dtype={"target": str, "comp": str})
    if agent.duplicated(["target", "comp"]).any():
        raise ValueError("Duplicate agent pair")
    columns = [c for c in agent if c.startswith("facet_") and c not in ("facet_scores", "facet_weights")]
    if "score" in agent:   # the agent's overall 0/1/2 grade, used only as the 05 stage treatment
        grade = agent[["target", "comp"]].assign(agent_peer=np.where(agent.status.eq("ok") & agent.score.notna(),
                                                                     (agent.score >= 1).astype(float), np.nan))
        pairs = pairs.merge(grade, on=["target", "comp"], how="left", validate="one_to_one")
    numeric = agent[["target", "comp", "status", *columns]].copy()
    numeric.loc[numeric.status != "ok", columns] = np.nan
    numeric = numeric.drop(columns="status").rename(columns={c: c.replace("facet_", "agent__", 1) for c in columns})
    pairs = pairs.merge(numeric, on=["target", "comp"], how="left", validate="one_to_one")
    for c in numeric.columns[2:]:
        if not pairs[c].dropna().isin([0, 25, 50, 75, 100]).all():
            raise ValueError(f"Invalid agent score: {c}")
    ids = pd.read_csv(v1a.path(cur["universe"]["universe"]), dtype=str)["IQ_COMPANY_ID"].tolist()
    pos = {k: i for i, k in enumerate(ids)}
    if not (set(pairs.target) | set(pairs.comp)).issubset(pos):
        raise ValueError("Pair company missing from the universe")
    a, b = pairs.target.map(pos).to_numpy(), pairs.comp.map(pos).to_numpy()
    for facet, matrix in b3_signals(ids, features).items():
        pairs[f"b3__{facet}"] = matrix[a, b]
    return pairs


# ------------------------------------------------------------------ analysis

def sources(pairs: pd.DataFrame, outcome: str) -> list[tuple[str, str, list[str]]]:
    """(source, treatment column, covariate columns) for every analysis."""
    out = []
    for source in ("b3", "agent"):
        columns = [c for c in pairs if c.startswith(source + "__")]
        if source == "agent" and pairs[columns].notna().sum().sum() == 0:
            continue
        out += [(source, c, [o for o in columns if o != c]) for c in columns]
    if outcome != "selector":
        b3 = [c for c in pairs if c.startswith("b3__")]
        out += [(source, column, b3) for source, (column, _) in STAGES.items()
                if column in pairs and pairs[column].notna().any()]
    return out


def analyze(pairs: pd.DataFrame, outcome="peer"):
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {list(OUTCOMES)}")
    predictions, diagnostics = [], []
    groups = pairs.target.to_numpy()
    y = pairs[OUTCOMES[outcome]].to_numpy(float)
    if not np.isin(y, [0, 1] if outcome in BINARY else [0, 1, 2]).all():
        raise ValueError("Invalid outcome values")
    keep = [c for c in ("target", "comp", "target_ticker", "comp_ticker", "peer", "grade", "selector_keep", "agent_peer")
            if c in pairs]
    for source, column, covariates in sources(pairs, outcome):
        score = pairs[column].to_numpy(float)
        x = pairs[covariates].to_numpy(float)
        for rule in (("primary",) if source in STAGES else ("primary", "extreme")):
            for fold, (train, valid) in enumerate(group_splits(groups)):
                t, low, high = treatment(score[train], score, source, rule)
                train = train[np.isfinite(t[train])]
                test = valid[np.isfinite(t[valid])]
                record = dict(source=source, facet=STAGES[source][1] if source in STAGES else column.split("__", 1)[1],
                              rule=rule, fold=fold, threshold_low=low, threshold_high=high,
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
                out = pairs.iloc[test][keep].copy()
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
                if outcome in BINARY:
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
            if outcome in BINARY:
                y = part.outcome_value
                row.update(brier=brier_score_loss(y, part.observed_probability),
                           baseline_brier=brier_score_loss(y, part.baseline_probability),
                           response_auc=roc_auc_score(y, part.observed_probability) if y.nunique() == 2 else np.nan,
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


def lift_table(runs: dict[str, Path], rule: str = "primary") -> pd.DataFrame:
    """Mean lift with its 95% interval per facet, one column group per named run (complete analyses only)."""
    parts = []
    for name, run in runs.items():
        s = pd.read_csv(run / "facet_summary.csv")
        s = s[(s.rule == rule) & (s.status == "complete")].set_index(["source", "facet"])
        parts.append(s[["mean_uplift", "uplift_ci_low", "uplift_ci_high"]].rename(
            columns={"mean_uplift": "lift", "uplift_ci_low": "low", "uplift_ci_high": "high"}))
    return pd.concat(parts, axis=1, keys=list(runs))


# ------------------------------------------------------------------ run

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cohort", choices=COHORTS, default="dev_293")
    ap.add_argument("--outcome", choices=list(OUTCOMES), default="peer",
                    help="peer: grade 1/2 vs 0; rating: expected 0/1/2 grade; selector: the LLM selector kept the comp")
    ap.add_argument("--features", choices=["current", "record"], default="current",
                    help="current: B3 signals of the current variant (with sub_sector); record: v1's 11 signals")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--bootstrap", type=int, default=1000)
    args = ap.parse_args(argv)
    if args.bootstrap < 1:
        ap.error("--bootstrap must be positive")
    cur = v1a.current()
    agent_path = v1a.path(cur["agent_grading"]["run"]) / "verdicts.csv"
    judgments = v1a.path(cur["selection"]["judgments"])
    pairs = build_features(args.cohort, args.outcome, args.features, agent_path, judgments)
    run = args.out / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run.mkdir(parents=True, exist_ok=False)
    pairs.to_csv(run / "pair_features.csv", index=False)
    predictions, diagnostics = analyze(pairs, args.outcome)
    summary, calibration = summarize(predictions, diagnostics, args.bootstrap, args.outcome)
    for name, frame in (("oof_effects", predictions), ("fold_diagnostics", diagnostics),
                        ("facet_summary", summary), ("uplift_bins", calibration)):
        frame.to_csv(run / f"{name}.csv", index=False)
    rel = lambda p: str(p.relative_to(ROOT).as_posix()) if p.is_relative_to(ROOT) else str(p)  # noqa: E731
    inputs = [agent_path, v1a.path(cur["profiles"]["general"]), v1a.path(cur["retrieval"]["candidates"]) / "candidates.csv"]
    if args.features == "current":
        inputs.append(v1a.path(cur["profiles"]["sector"]))
    if "selector_keep" in pairs:
        inputs.append(judgments)
    outcome_text = {"peer": "human grade >= 1", "rating": "expected human grade on 0/1/2 scale",
                    "selector": f"the LLM selector kept the comp ({cur['selection']['model']}, "
                                f"prompt {cur['selection']['prompt_version']})"}[args.outcome]
    manifest = {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "script_sha256": digest(Path(__file__)), "cohort": args.cohort, "features": args.features,
                "b3_variant": cur["retrieval"]["variant"] if args.features == "current" else "v1 record: 11 general facets",
                "pairs": len(pairs), "targets": pairs.target.nunique(),
                "outcome": outcome_text, "outcome_mode": args.outcome,
                "effect_units": "rating points" if args.outcome == "rating" else "probability difference",
                "response_estimator": "ridge alpha=10; predictions clipped to [0,2]" if args.outcome == "rating" else "logistic C=0.1",
                "rating_assumption": "0->1 and 1->2 are equally spaced; not a multiclass probability model" if args.outcome == "rating" else None,
                "sources": {rel(p): digest(p) for p in inputs},
                "settings": {"outer_folds": 5, "inner_folds": 3, "seed": 42,
                             "min_arm": MIN_ARM, "min_arm_targets": MIN_TARGETS,
                             "logistic_C": .1, "ridge_alpha": 10, "overlap": [.1, .9],
                             "dr_propensity_clip": [.05, .95], "bootstrap": args.bootstrap,
                             "primary": {"b3": "training median", "agent": "75/100 vs 0/25/50", "selector": "keep vs drop",
                                         "agent_grade": "agent grade 1/2 vs 0 (ungraded omitted)"},
                             "sensitivity": {"b3": "training upper vs lower thirds", "agent": "75/100 vs 0/25"},
                             "model_weighting": "equal total weight per training target"},
                "libraries": {name: version(name) for name in ["numpy", "pandas", "scikit-learn", "sentence-transformers", "torch"]},
                "interpretation": "Exploratory adjusted associations, not identified causal CATE. Fixed unlabeled 533-company "
                                  "text representation; target-group outcome cross-fitting. Shared comp companies may cross folds."
                                  + (" Selector outcome: lift on the LLM's decisions, not on comp quality." if args.outcome == "selector" else ""),
                "uncertainty": "Target bootstrap of fixed OOF predictions; excludes refitting, selection, reviewer and threshold uncertainty."}
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    primary = summary[summary.rule.eq("primary")]
    complete = primary[primary.status.eq("complete")].groupby("source").size().to_dict()
    totals = primary.groupby("source").size().to_dict()
    (run / "report.md").write_text(
        f"# Exploratory facet lift\n\n{len(pairs)} pairs, {pairs.target.nunique()} targets, cohort {args.cohort}, "
        f"features {args.features}.\n\nOutcome: {outcome_text}. Effect units: {manifest['effect_units']}.\n\n"
        "Complete five-fold analyses: " + "; ".join(f"{s} {complete.get(s, 0)}/{n}" for s, n in totals.items()) + ". "
        "Partial and unsupported facets remain in facet_summary.csv; missing effects are not zero.\n\n"
        "Brier/AUC (binary) or MAE/RMSE (rating) assess response predictions, not accuracy of treatment effects. "
        "DR bins are adjusted diagnostics, not effect ground truth. "
        "Do not use uplift to rank comp quality or add effects across correlated facets. "
        "No causal identification, unreviewed-universe generalization, or pipeline improvement is established.\n")
    print(summary[["source", "facet", "rule", "status", "predicted_pairs", "mean_uplift"]].to_string(index=False))
    print(f"Run: {run}")
    return run


if __name__ == "__main__":
    main()
