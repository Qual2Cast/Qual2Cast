"""Trait X-learner: do economic-trait matches go with people's peer judgments? (v2, pre-registered 2026-11-24)

Implements v2/09_analysis/PREREG_TRAITS.md exactly; read that first. In short:

  cohort      matthew_v2_262 (one reviewer, rubric v2 wording)
  outcomes    direct (score == 2, primary) and peer (score >= 1, secondary)
  treatments  six traits (E1-E6): match = both companies give the same yes/no answer; unknown on either side ->
              the pair is left out of that trait only
  covariates  the 12 current B3 signals + the other traits' match indicators (missingness indicators included)
  estimator   facet_uplift.estimate_fold (v2/09_analysis, copied unchanged from v1a apart from paths), imported
  cells       one fit per trait and outcome, out-of-fold effects averaged in 5 cells: all pairs, target offers
              services yes/no, target sells to consumers yes/no
  p-values    shuffle test: the trait's answers shuffled across companies, full estimator rerun (default 1000)
  intervals   refit bootstrap over targets (default 200)
  multiple    Benjamini-Hochberg across all 60 tests (6 traits x 5 cells x 2 outcomes) at q = 0.10; unsupported = p 1

  uv run python v2/09_analysis/scripts/trait_uplift.py --traits outputs-local/v2/02_profiles/traits_new/tables/traits.csv

No LLM, search or financial inputs. Writes outputs-local/v2/09_analysis/trait_uplift/<stamp>/ (never overwrites).
"""
from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import v2paths as v2  # noqa: E402
v2.setup()

import argparse  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
import hashlib  # noqa: E402
from importlib.metadata import version  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import facet_uplift as fu  # noqa: E402  09_analysis: the estimator (v1a's, copied unchanged apart from paths)

ROOT = v2.ROOT
OUT = v2.out("09_analysis") / "trait_uplift"
TRAITS = ["recurring_revenue", "cyclical_demand", "big_ticket", "people_delivered", "large_customers", "asset_heavy"]
TAGS = {"offers_services": "services", "sells_to_consumers": "consumers"}      # target tags used for cells
OUTCOMES = {"direct": "direct", "peer": "peer"}        # outcome -> column in pairs; direct is primary
CELLS = ["all", "services_yes", "services_no", "consumers_yes", "consumers_no"]
Q = 0.10
PREREG = v2.V2 / "09_analysis" / "PREREG_TRAITS.md"
PROMPT_VERSION = "2026-11-24a"


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ inputs

def load_traits(path: Path) -> pd.DataFrame:
    """The trait table, one row per company, answers lower-cased yes/no/unknown ('' and NaN -> unknown)."""
    t = pd.read_csv(path, dtype=str).set_index("IQ_COMPANY_ID")
    if t.index.duplicated().any():
        raise ValueError("duplicate company in the trait table")
    need = TRAITS + list(TAGS)
    missing = [c for c in need if c not in t]
    if missing:
        raise ValueError(f"trait table lacks {missing}")
    if "llm_status" in t:
        t.loc[t["llm_status"] != "ok", need] = "unknown"
    t[need] = t[need].fillna("unknown").apply(lambda s: s.str.strip().str.lower())
    bad = ~t[need].isin(["yes", "no", "unknown"])
    if bad.any().any():
        raise ValueError(f"answers outside yes/no/unknown in {list(t[need].columns[bad.any()])}")
    return t


def match(target_answers: pd.Series, comp_answers: pd.Series) -> np.ndarray:
    """1 = same yes/no answer, 0 = one yes and one no, NaN = unknown (or missing) on either side."""
    a = target_answers.fillna("unknown").to_numpy()
    b = comp_answers.fillna("unknown").to_numpy()
    known = np.isin(a, ["yes", "no"]) & np.isin(b, ["yes", "no"])
    return np.where(known, (a == b).astype(float), np.nan)


def add_traits(pairs: pd.DataFrame, traits: pd.DataFrame) -> pd.DataFrame:
    """Adds match__<trait> for the six traits and tag__<tag> (the target's tag answer) to the pairs."""
    pairs = pairs.copy()
    for trait in TRAITS:
        pairs[f"match__{trait}"] = match(pairs.target.map(traits[trait]), pairs.comp.map(traits[trait]))
    for tag in TAGS:
        pairs[f"tag__{tag}"] = pairs.target.map(traits[tag]).fillna("unknown").to_numpy()
    return pairs


def build_pairs(traits: pd.DataFrame, cohort: str = "matthew_v2_262") -> pd.DataFrame:
    pairs = fu.load_pairs(cohort)
    pairs["direct"] = (pairs.grade == 2).astype(float)
    pairs["peer"] = (pairs.grade >= 1).astype(float)
    ids = pd.read_csv(v2.path(v2.current()["universe"]["universe"]), dtype=str)["IQ_COMPANY_ID"].tolist()
    pos = {k: i for i, k in enumerate(ids)}
    if not (set(pairs.target) | set(pairs.comp)).issubset(pos):
        raise ValueError("pair company missing from the universe")
    a, b = pairs.target.map(pos).to_numpy(), pairs.comp.map(pos).to_numpy()
    for facet, matrix in fu.b3_signals(ids, "current").items():
        pairs[f"b3__{facet}"] = matrix[a, b]
    return add_traits(pairs, traits)


def covariates(pairs: pd.DataFrame, trait: str) -> list[str]:
    return [c for c in pairs if c.startswith("b3__")] + [f"match__{t}" for t in TRAITS if t != trait]


# ------------------------------------------------------------------ one analysis

def oof(pairs: pd.DataFrame, trait: str, outcome: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Out-of-fold effects for one trait and outcome, and the fold diagnostics. Folds hold out whole targets
    (pairs.target); bootstrap copies of a target share its id and so always fall in the same fold."""
    groups = pairs.target.to_numpy()
    y = pairs[OUTCOMES[outcome]].to_numpy(float)
    t = pairs[f"match__{trait}"].to_numpy(float)
    x = pairs[covariates(pairs, trait)].to_numpy(float)
    unit = pairs["unit"].to_numpy() if "unit" in pairs else groups
    rows, diags = [], []
    for fold, (train, valid) in enumerate(fu.group_splits(groups)):
        train = train[np.isfinite(t[train])]
        test = valid[np.isfinite(t[valid])]
        record = dict(trait=trait, outcome=outcome, fold=fold, train_n=len(train), test_n=len(test),
                      unknown_test=int(np.isnan(t[valid]).sum()),
                      mismatch_train=int((t[train] == 0).sum()), match_train=int((t[train] == 1).sum()),
                      targets_arm_0=len(set(groups[train][t[train] == 0])),
                      targets_arm_1=len(set(groups[train][t[train] == 1])))
        if not len(test) or not fu.arm_support(t[train], groups[train]):
            diags.append(record | {"status": "insufficient_support"})
            continue
        try:
            tau, e, m0, m1, _ = fu.estimate_fold(x[train], y[train], t[train], groups[train], x[test], t[test], "peer")
        except ValueError as error:
            diags.append(record | {"status": str(error)})
            continue
        diags.append(record | {"status": "ok"})
        clipped = np.clip(e, .05, .95)
        dr = m1 - m0 + t[test] * (y[test] - m1) / clipped - (1 - t[test]) * (y[test] - m0) / (1 - clipped)
        rows.append(pd.DataFrame({
            "target": groups[test], "unit": unit[test], "comp": pairs.comp.to_numpy()[test],
            **{f"tag__{g}": pairs[f"tag__{g}"].to_numpy()[test] for g in TAGS},
            "trait": trait, "outcome": outcome, "fold": fold, "treatment": t[test], "outcome_value": y[test],
            "uplift": tau, "propensity": e, "overlap": (e >= .1) & (e <= .9), "dr_pseudo_effect": dr}))
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()), pd.DataFrame(diags)


def cell_mask(frame: pd.DataFrame, cell: str) -> pd.Series:
    if cell == "all":
        return pd.Series(True, index=frame.index)
    name, answer = cell.rsplit("_", 1)
    tag = {v: k for k, v in TAGS.items()}[name]
    return frame[f"tag__{tag}"] == answer


def cells(effects: pd.DataFrame, folds_ok: int) -> dict[str, dict]:
    """Lift per cell: mean over units (targets, or bootstrap draws of a target) of each unit's mean OOF effect,
    overlap pairs only. A cell is supported when the analysis is complete (5 folds) and it has >= MIN_TARGETS
    distinct targets with overlap pairs."""
    out = {}
    overlap = effects[effects.overlap] if len(effects) else effects
    for cell in CELLS:
        part = overlap[cell_mask(overlap, cell)] if len(overlap) else overlap
        targets = part.target.nunique() if len(part) else 0
        supported = folds_ok == 5 and targets >= fu.MIN_TARGETS
        if len(part):
            by = part.groupby("unit")[["uplift", "dr_pseudo_effect"]].mean()
            lift, dr = float(by.uplift.mean()), float(by.dr_pseudo_effect.mean())
        else:
            lift = dr = np.nan
        out[cell] = dict(pairs=len(part), targets=targets, supported=supported,
                         lift=lift if supported else np.nan, dr_adjusted_difference=dr if supported else np.nan,
                         lift_descriptive=lift)
    return out


def analyze(pairs: pd.DataFrame, trait: str, outcome: str):
    effects, diags = oof(pairs, trait, outcome)
    folds_ok = int(diags.status.eq("ok").sum()) if len(diags) else 0
    return effects, diags, cells(effects, folds_ok), folds_ok


# ------------------------------------------------------------------ shuffle test and refit bootstrap

def _shuffle_job(pairs, answers: pd.Series, trait, outcome, seeds):
    """Lift per cell after shuffling one trait's answers across companies, once per seed."""
    results = []
    for seed in seeds:
        shuffled = pd.Series(np.random.default_rng(seed).permutation(answers.to_numpy()), index=answers.index)
        p = pairs.copy()
        p[f"match__{trait}"] = match(p.target.map(shuffled), p.comp.map(shuffled))
        _, _, c, _ = analyze(p, trait, outcome)
        results += [dict(trait=trait, outcome=outcome, seed=seed, cell=k, lift=v["lift"], supported=v["supported"])
                    for k, v in c.items()]
    return results


def _bootstrap_job(pairs, trait, outcome, seeds):
    """Lift per cell after resampling targets with replacement and refitting, once per seed."""
    targets = np.array(sorted(pairs.target.unique()))
    by_target = {k: g for k, g in pairs.groupby("target")}
    results = []
    for seed in seeds:
        drawn = np.random.default_rng(seed).choice(targets, len(targets), replace=True)
        p = pd.concat([by_target[k].assign(unit=f"{k}#{i}") for i, k in enumerate(drawn)], ignore_index=True)
        _, _, c, _ = analyze(p, trait, outcome)
        results += [dict(trait=trait, outcome=outcome, seed=seed, cell=k, lift=v["lift"], supported=v["supported"])
                    for k, v in c.items()]
    return results


def _chunks(seq, n):
    seq = list(seq)
    size = max(1, -(-len(seq) // max(1, n)))
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def resample(pairs, traits, outcomes, permutations, bootstrap, workers, seed=2026):
    """Runs every shuffle and bootstrap draw (in parallel when workers > 1); returns two long tables."""
    jobs = []
    per_job = max(1, workers) * 2
    for o_i, outcome in enumerate(outcomes):
        for t_i, trait in enumerate(TRAITS):
            base = seed + 100_000 * o_i + 10_000 * t_i
            for chunk in _chunks(range(base, base + permutations), per_job):
                jobs.append(("shuffle", (pairs, traits[trait], trait, outcome, chunk)))
            for chunk in _chunks(range(base + 5_000, base + 5_000 + bootstrap), per_job):
                jobs.append(("bootstrap", (pairs, trait, outcome, chunk)))
    jobs = [(k, a) for k, a in jobs if a[-1]]
    run = {"shuffle": _shuffle_job, "bootstrap": _bootstrap_job}
    if workers > 1:
        from joblib import Parallel, delayed
        out = Parallel(n_jobs=workers, backend="loky")(delayed(run[k])(*a) for k, a in jobs)
    else:
        out = [run[k](*a) for k, a in jobs]
    shuffles = pd.DataFrame([r for (k, _), res in zip(jobs, out) if k == "shuffle" for r in res])
    boots = pd.DataFrame([r for (k, _), res in zip(jobs, out) if k == "bootstrap" for r in res])
    return shuffles, boots


def permutation_p(observed: float, nulls: np.ndarray) -> float:
    """Two-sided: (1 + #|null| >= |observed|) / (1 + #nulls). NaN when the observed lift is NaN or no null exists."""
    nulls = np.asarray(nulls, float)
    nulls = nulls[np.isfinite(nulls)]
    if not np.isfinite(observed) or not len(nulls):
        return np.nan
    return float((1 + np.sum(np.abs(nulls) >= abs(observed) - 1e-12)) / (1 + len(nulls)))


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    """BH-adjusted p-values; NaN (unsupported) counts as 1, so the family size never shrinks."""
    p = np.where(np.isfinite(np.asarray(p, float)), np.asarray(p, float), 1.0)
    m = len(p)
    if not m:
        return p
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(adjusted, 1.0)
    return out


def summarize(observed: dict, shuffles: pd.DataFrame, boots: pd.DataFrame, q: float = Q) -> pd.DataFrame:
    """One row per outcome x trait x cell, BH across all rows."""
    rows = []
    for (outcome, trait), (c, folds_ok) in observed.items():
        for cell, v in c.items():
            row = dict(outcome=outcome, primary=outcome == "direct", trait=trait, cell=cell, folds_ok=folds_ok,
                       status="supported" if v["supported"] else ("partial" if folds_ok else "unsupported"),
                       pairs=v["pairs"], targets=v["targets"], lift=v["lift"],
                       dr_adjusted_difference=v["dr_adjusted_difference"], lift_descriptive=v["lift_descriptive"])
            sel = lambda f: f[(f.outcome == outcome) & (f.trait == trait) & (f.cell == cell) & f.supported] \
                if len(f) else f  # noqa: E731
            s, b = sel(shuffles), sel(boots)
            row["shuffles_usable"] = len(s)
            row["perm_p"] = permutation_p(v["lift"], s.lift.to_numpy() if len(s) else [])
            row["boot_usable"] = len(b)
            if len(b) and np.isfinite(v["lift"]):
                row["ci_low"], row["ci_high"] = np.quantile(b.lift.to_numpy(float), [.025, .975])
            else:
                row["ci_low"] = row["ci_high"] = np.nan
            rows.append(row)
    s = pd.DataFrame(rows)
    if len(s):
        s["bh_q"] = benjamini_hochberg(s.perm_p.to_numpy())
        s["finding"] = s.bh_q <= q
    return s


# ------------------------------------------------------------------ run

def run_all(pairs, traits, outcomes, permutations, bootstrap, workers, seed=2026):
    observed, effects, diags = {}, [], []
    for outcome in outcomes:
        for trait in TRAITS:
            e, d, c, folds_ok = analyze(pairs, trait, outcome)
            observed[(outcome, trait)] = (c, folds_ok)
            effects.append(e)
            diags.append(d)
    shuffles, boots = resample(pairs, traits, outcomes, permutations, bootstrap, workers, seed)
    summary = summarize(observed, shuffles, boots)
    effects = pd.concat([e for e in effects if len(e)], ignore_index=True) if any(len(e) for e in effects) \
        else pd.DataFrame()
    tag_rows = []
    for (outcome, trait), (c, folds_ok) in observed.items():
        tag_rows += [dict(outcome=outcome, trait=trait, cell=k, folds_ok=folds_ok, **v) for k, v in c.items()]
    return summary, effects, pd.concat(diags, ignore_index=True), pd.DataFrame(tag_rows), shuffles, boots


def report(summary: pd.DataFrame, meta: dict) -> str:
    lines = [f"# Trait X-learner ({meta['stamp']})", "",
             f"Pre-registered in `v2/09_analysis/PREREG_TRAITS.md`. Cohort `{meta['cohort']}`: {meta['pairs']} pairs, "
             f"{meta['targets']} targets. Traits table `{meta['traits']}` (prompt {meta['trait_prompt_versions']}).",
             f"Shuffles {meta['permutations']} and refit bootstrap draws {meta['bootstrap']} per trait and outcome. "
             f"Benjamini-Hochberg across {len(summary)} tests at q = {Q}; unsupported tests count as p = 1.", "",
             "Lift = percentage-point difference in the probability of the outcome between pairs that match and "
             "pairs that differ on the trait, adjusted for the 12 B3 signals and the other traits. An adjusted "
             "association within B3's lists, not a cause and not a pipeline improvement.", ""]
    for outcome in summary.outcome.unique():
        part = summary[summary.outcome == outcome]
        lines += [f"## {'Primary' if outcome == 'direct' else 'Secondary'}: {outcome}", "",
                  "| trait | cell | status | pairs | targets | lift (pp) | 95% interval | shuffle p | BH q | finding |",
                  "|---|---|---|---:|---:|---:|---|---:|---:|---|"]
        for r in part.itertuples():
            pp = lambda v: "" if not np.isfinite(v) else f"{100 * v:+.1f}"  # noqa: E731
            ci = "" if not np.isfinite(r.ci_low) else f"{100 * r.ci_low:+.1f} to {100 * r.ci_high:+.1f}"
            pv = "" if not np.isfinite(r.perm_p) else f"{r.perm_p:.3f}"
            lines.append(f"| {r.trait} | {r.cell} | {r.status} | {r.pairs} | {r.targets} | {pp(r.lift)} | {ci} | "
                         f"{pv} | {r.bh_q:.3f} | {'yes' if r.finding else 'no'} |")
        lines.append("")
    lines += ["Every test is listed, including nulls and unsupported cells. Missing effects are not zero."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--traits", type=Path, required=True, help="trait table (fill_traits.py tables/traits.csv)")
    ap.add_argument("--cohort", default="matthew_v2_262", choices=[c for c in fu.COHORTS if c != "b3_current"])
    ap.add_argument("--outcome", choices=["both", "direct", "peer"], default="both")
    ap.add_argument("--permutations", type=int, default=1000)
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--smoke", action="store_true", help="plumbing check (e.g. on a test table); label the run so")
    args = ap.parse_args(argv)
    started = time.time()
    traits = load_traits(args.traits)
    versions = sorted(traits["prompt_version"].dropna().unique()) if "prompt_version" in traits else []
    if not args.smoke and versions != [PROMPT_VERSION]:
        ap.error(f"trait table prompt versions {versions}; the pre-registration fixes {PROMPT_VERSION}")
    pairs = build_pairs(traits, args.cohort)
    outcomes = ["direct", "peer"] if args.outcome == "both" else [args.outcome]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run = args.out / (stamp + ("_smoke" if args.smoke else ""))
    run.mkdir(parents=True, exist_ok=False)
    pairs.to_csv(run / "pair_features.csv", index=False)
    summary, effects, diags, tags, shuffles, boots = run_all(
        pairs, traits, outcomes, args.permutations, args.bootstrap, args.workers, args.seed)
    for name, frame in (("summary", summary), ("oof_effects", effects), ("fold_diagnostics", diags),
                        ("tag_effects", tags), ("permutations", shuffles), ("bootstrap", boots)):
        frame.to_csv(run / f"{name}.csv", index=False)
    cur = v2.current()
    rel = lambda p: str(Path(p).resolve().relative_to(ROOT).as_posix()) if Path(p).resolve().is_relative_to(ROOT) \
        else str(p)  # noqa: E731
    inputs = [args.traits, v2.src("06_labels", "round3", "round3_scores_v2.csv"),
              v2.path(cur["profiles"]["general"]), v2.path(cur["profiles"]["sector"]),
              v2.path(cur["universe"]["universe"]), PREREG]
    meta = {"stamp": stamp, "smoke": args.smoke, "cohort": args.cohort, "pairs": len(pairs),
            "targets": int(pairs.target.nunique()), "traits": rel(args.traits), "trait_prompt_versions": versions,
            "permutations": args.permutations, "bootstrap": args.bootstrap}
    manifest = {**meta,
                "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "script_sha256": digest(Path(__file__)), "estimator_sha256": digest(Path(fu.__file__)),
                "sources": {rel(p): digest(p) for p in inputs if Path(p).exists()},
                "outcomes": {"direct": "Matthew derived score == 2 (primary)", "peer": "score >= 1 (secondary)"},
                "settings": {"outer_folds": 5, "inner_folds": 3, "fold_seed": 42, "resample_seed": args.seed,
                             "min_arm": fu.MIN_ARM, "min_arm_targets": fu.MIN_TARGETS, "logistic_C": .1,
                             "ridge_alpha": 10, "overlap": [.1, .9], "dr_propensity_clip": [.05, .95],
                             "match": "same yes/no answer; unknown on either side excluded for that trait",
                             "covariates": "12 B3 signals (current variant) + other traits' match indicators, "
                                           "median-imputed with missingness indicators",
                             "cells": CELLS, "bh_q": Q, "bh_family": len(summary),
                             "workers": args.workers},
                "libraries": {n: version(n) for n in ["numpy", "pandas", "scikit-learn", "joblib"]},
                "runtime_seconds": round(time.time() - started, 1),
                "interpretation": "Adjusted associations within B3's lists, one reviewer; not causal, not a "
                                  "pipeline improvement."}
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    (run / "report.md").write_text(report(summary, meta), encoding="utf-8")
    cols = ["outcome", "trait", "cell", "status", "pairs", "targets", "lift", "perm_p", "bh_q", "finding"]
    print(summary[cols].to_string(index=False))
    print(f"Run: {run} ({manifest['runtime_seconds']} s)")
    return run


if __name__ == "__main__":
    main()
