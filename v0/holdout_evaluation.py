"""Evaluate the frozen v0 routes on all 160 SIC2 holdout companies.

Peer selection uses saved facets and the 373 training companies. This module
reads EV/EBITDA only after the peer lists are fixed. The F3 ablation was
selected from the independent 36-pair reviewer labels, not holdout multiples.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import valuation as vl
from llm_then_cosine import rank_selected
from project_data import OUTPUTS_LOCAL


CANDIDATES = (OUTPUTS_LOCAL / "comps_pilot_targets/business_structure_refinement/"
              "holdout_all_candidates")
LLM = OUTPUTS_LOCAL / "comps_pilot_targets/holdout_completion"
OUTPUT = OUTPUTS_LOCAL / "comps_pilot_targets/holdout_completion/evaluation"


def summary_without_scipy(results: dict[str, pd.DataFrame], actual: pd.Series,
                          baseline: str) -> pd.DataFrame:
    """Use the v0 summary definitions; rank correlation needs no SciPy."""
    base = vl.errors(results[baseline], actual)
    rows = []
    for name, result in results.items():
        errors = vl.errors(result, actual)
        ape = errors["error %"].abs()
        both = errors.index.intersection(base.index)
        closer = (abs(errors.loc[both, "estimate"] - errors.loc[both, "actual"])
                  < abs(base.loc[both, "estimate"] - base.loc[both, "actual"]))
        observed = errors[["estimate", "actual"]].dropna()
        rho = (observed["estimate"].rank().corr(observed["actual"].rank())
               if name != baseline and len(observed) >= 2 else np.nan)
        rows.append({"comp rule": name, "targets": len(errors),
                     "comps per target (median)": errors["comps"].median(),
                     "median abs % error": ape.median(),
                     "% within 25%": 100 * (ape <= 25).mean(),
                     "Spearman(estimate, actual)": rho,
                     "% closer than no matching": (100 * closer.mean()
                                                    if name != baseline else np.nan)})
    return pd.DataFrame(rows).set_index("comp rule")


def rerank_without_primary_services(ranking: pd.DataFrame) -> pd.DataFrame:
    """Reapply the saved cosine recipe after removing one prespecified facet."""
    columns = [c for c in ranking if c.startswith("sim_") and c != "sim_primary_services"]
    if len(columns) != 10:
        raise ValueError(f"Expected ten retained facet similarities, found {len(columns)}")
    pieces = []
    for _, group in ranking.groupby("target", sort=False):
        group = group.copy()
        group["similarity"] = group[columns].mean(axis=1, skipna=True)
        group = group.sort_values("similarity", ascending=False, kind="stable")
        group["rank"] = np.arange(1, len(group) + 1)
        scores = group["similarity"]
        group["z"] = (scores - scores.mean()) / scores.std(ddof=0)
        group["in_top_k"] = group["rank"] <= 10
        group["z_ge_2"] = group["z"] >= 2
        group["z_ge_2.5"] = group["z"] >= 2.5
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def paired_differences(results: dict[str, pd.DataFrame], actual: pd.Series) -> pd.DataFrame:
    """Compare the reviewer-selected F3 ablation on identical holdout firms."""
    rows = []
    rng = np.random.default_rng(2026)
    for selection in ("top 10", "z >= 2", "z >= 2.5"):
        for estimator in ("weighted mean", "median"):
            old = f"cosine {selection}, {estimator}"
            new = f"cosine minus F3 {selection}, {estimator}"
            a = vl.errors(results[old], actual)["error %"].abs()
            b = vl.errors(results[new], actual)["error %"].abs()
            aligned = pd.concat([a.rename("old"), b.rename("new")], axis=1).dropna()
            delta = (aligned["new"] - aligned["old"]).to_numpy()
            boot = np.median(rng.choice(delta, size=(2000, len(delta)), replace=True), axis=1)
            rows.append({"selection": selection, "estimator": estimator,
                         "common targets": len(delta), "old median APE": aligned["old"].median(),
                         "minus F3 median APE": aligned["new"].median(),
                         "median paired change": float(np.median(delta)),
                         "paired change 95% low": float(np.quantile(boot, .025)),
                         "paired change 95% high": float(np.quantile(boot, .975)),
                         "targets improved": int((delta < 0).sum()),
                         "targets worsened": int((delta > 0).sum())})
    return pd.DataFrame(rows)


def run(candidates_dir: Path = CANDIDATES, llm_dir: Path = LLM,
        output: Path = OUTPUT, require_llm: bool = False) -> dict:
    config = json.loads((candidates_dir / "run.json").read_text(encoding="utf-8"))
    split = pd.read_csv(OUTPUTS_LOCAL / "comps_pilot_targets/split" /
                        config["split_run"] / "split.csv", dtype={"IQ_COMPANY_ID": str})
    targets = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    training = split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"].tolist()
    if len(targets) != 160 or len(training) != 373:
        raise ValueError("The frozen SIC2 split changed")
    financials = pd.read_csv(OUTPUTS_LOCAL / "comps/universe" /
                             config["universe_run"] / "financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    actual = multiples.reindex(targets)
    ranking = pd.read_csv(candidates_dir / "ranking.csv.gz",
                          dtype={"target": str, "comp": str})
    if (len(ranking) != len(targets) * len(training)
            or ranking.duplicated(["target", "comp"]).any()
            or set(ranking["target"]) != set(targets)
            or set(ranking["comp"]) != set(training)):
        raise ValueError("Holdout rankings must cover every training candidate exactly once")
    output.mkdir(parents=True, exist_ok=True)

    results = {"no matching, training-pool median": vl.no_matching(targets, training, multiples)}
    for tag, peers in [("cosine", ranking),
                       ("cosine minus F3", rerank_without_primary_services(ranking))]:
        for rule, mask in [("top 10", peers["in_top_k"]),
                           ("z >= 2", peers["z_ge_2"]),
                           ("z >= 2.5", peers["z_ge_2.5"])]:
            selected = peers[mask]
            results[f"{tag} {rule}, weighted mean"] = vl.estimate(
                selected, multiples, weight="similarity")
            results[f"{tag} {rule}, median"] = vl.estimate(
                selected, multiples, how="median")
    universe = pd.read_csv(OUTPUTS_LOCAL / "comps/universe" /
                           config["universe_run"] / "universe.csv",
                           dtype=str).set_index("IQ_COMPANY_ID")
    for level in (2, 3, 4):
        sic = universe[f"target_sic{level}_code"]
        sector_pairs = pd.DataFrame(
            [(target, comp) for target in targets for comp in training
             if pd.notna(sic[target]) and sic[target] == sic[comp]],
            columns=["target", "comp"])
        results[f"same SIC{level}, mean"] = vl.estimate(sector_pairs, multiples)

    llm_run = llm_dir / "llm_run.json"
    llm_meta = json.loads(llm_run.read_text(encoding="utf-8")) if llm_run.exists() else {}
    llm_complete = (llm_meta.get("complete") is True
                    and llm_meta.get("targets_done") == len(targets)
                    and llm_meta.get("split_run") == config["split_run"])
    if require_llm and not llm_complete:
        raise ValueError("All holdout LLM routes must finish before final evaluation")
    if llm_complete:
        judge = pd.read_csv(llm_dir / "judge.csv", dtype={"target": str, "comp": str})
        direct = pd.read_csv(llm_dir / "direct.csv", dtype={"target": str, "comp": str})
        if not set(judge["target"]) <= set(targets) or not set(direct["target"]) <= set(targets):
            raise ValueError("LLM outputs contain non-holdout targets")
        if not set(judge["comp"]) <= set(training) or not set(direct["comp"]) <= set(training):
            raise ValueError("LLM outputs contain peers outside the training pool")
        if (judge.duplicated(["target", "comp"]).any()
                or direct.duplicated(["target", "comp"]).any()
                or direct.groupby("target").size().max() > 10):
            raise ValueError("LLM peer lists have duplicate pairs or more than ten direct peers")
        z2 = ranking.loc[ranking["z_ge_2"], ["target", "comp"]]
        if len(judge.merge(z2, on=["target", "comp"], how="left", indicator=True)
               .query("_merge != 'both'")):
            raise ValueError("The LLM judge scored a peer outside the z >= 2 shortlist")
        good = judge[judge["score"].eq(1)].merge(
            ranking[["target", "comp", "similarity"]], on=["target", "comp"],
            how="left", validate="one_to_one")
        results["cosine then LLM, weighted mean"] = vl.estimate(
            good, multiples, weight="similarity")
        results["cosine then LLM, median"] = vl.estimate(good, multiples, how="median")
        results["LLM direct, mean"] = vl.estimate(direct, multiples)
        results["LLM direct, median"] = vl.estimate(direct, multiples, how="median")
        reranked_direct = rank_selected(direct, ranking)
        results["LLM then cosine, weighted mean"] = vl.estimate(
            reranked_direct, multiples, weight="similarity")
        reranked_direct.to_csv(output / "llm_then_cosine_peers.csv", index=False)

    summary = summary_without_scipy(results, actual,
                                    baseline="no matching, training-pool median")
    summary.insert(0, "holdout targets", len(targets))
    summary.to_csv(output / "summary.csv")
    per_target = pd.concat({name: vl.errors(value, actual).reindex(targets)
                            for name, value in results.items()}, names=["method", "target"])
    per_target.to_csv(output / "target_errors.csv")
    paired_differences(results, actual).to_csv(output / "paired_f3.csv", index=False)
    if llm_complete:
        names = ["cosine z >= 2, weighted mean", "cosine then LLM, weighted mean",
                 "LLM direct, mean", "LLM then cosine, weighted mean"]
        support = pd.concat({name: vl.errors(results[name], actual)["error %"].abs()
                             for name in names}, axis=1).dropna()
        if support.empty:
            raise ValueError("The four routes have no common holdout targets")
        rng = np.random.default_rng(2027)
        common_rows = []
        for name in names:
            delta = (support[name] - support[names[0]]).to_numpy()
            boot = np.median(rng.choice(delta, size=(2000, len(delta)), replace=True), axis=1)
            common_rows.append({"method": name, "common targets": len(support),
                                "median APE on common targets": support[name].median(),
                                "median paired change vs cosine": np.median(delta),
                                "paired change 95% low": np.quantile(boot, .025),
                                "paired change 95% high": np.quantile(boot, .975),
                                "targets improved vs cosine": int((delta < 0).sum())})
        pd.DataFrame(common_rows).to_csv(output / "route_common_support.csv", index=False)
        direct_error = vl.errors(results["LLM direct, mean"], actual)["error %"].abs()
        reverse_error = vl.errors(results["LLM then cosine, weighted mean"], actual)["error %"].abs()
        direct_pair = pd.concat([direct_error.rename("direct"),
                                 reverse_error.rename("reverse")], axis=1).dropna()
        change = (direct_pair["reverse"] - direct_pair["direct"]).to_numpy()
        boot = np.median(rng.choice(change, size=(2000, len(change)), replace=True), axis=1)
        pd.DataFrame([{"common targets": len(change),
                       "direct median APE": direct_pair["direct"].median(),
                       "LLM then cosine median APE": direct_pair["reverse"].median(),
                       "median paired change": np.median(change),
                       "paired change 95% low": np.quantile(boot, .025),
                       "paired change 95% high": np.quantile(boot, .975),
                       "targets improved": int((change < 0).sum()),
                       "targets worsened": int((change > 0).sum())}]).to_csv(
            output / "reverse_hybrid_paired.csv", index=False)
    meta = {"split_run": config["split_run"], "targets": len(targets),
            "training_pool": len(training), "llm_complete": bool(llm_complete),
            "llm_model": llm_meta.get("model") if llm_complete else None,
            "factor_ablation": "primary_services (F3), selected from reviewer labels",
            "methods": list(results)}
    (output / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--require-llm", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(require_llm=args.require_llm), indent=2))
