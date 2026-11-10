"""Compare saved peer lists on one fixed reviewer cohort at a time."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import b3_facet_add_drop as b3


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration"
V1 = ROOT / "outputs-local/v1"


def ndcg_at_3(grades: np.ndarray) -> float:
    gains = np.power(2.0, grades) - 1.0
    discounts = np.log2(np.arange(2, 5))
    observed = float(np.sum(gains[:3] / discounts))
    ideal = float(np.sum(np.sort(gains)[::-1][:3] / discounts))
    return observed / ideal if ideal else np.nan


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_sources() -> dict[str, str]:
    manifest = json.loads((ROOT / "data_manifest.json").read_text(encoding="utf-8"))
    universe = json.loads((V1 / "universe/20261025T060358Z/run.json").read_text(encoding="utf-8"))
    split = json.loads((V1 / "split/20261027T204930Z/run.json").read_text(encoding="utf-8"))
    assert universe["snapshot"] == manifest["required_snapshot"] == "company_list_v3"
    assert split["universe_run"] == universe["run"]
    snapshot = ROOT / manifest["snapshots"]["company_list_v3"]["file"]
    assert sha(snapshot) == universe["snapshot_sha256"] == manifest["snapshots"]["company_list_v3"]["sha256"]
    sources = {"snapshot": sha(snapshot), "split": sha(V1 / "split/20261027T204930Z/split.csv")}
    for condition in ("candidate_methods", "candidate_methods_gpt", "candidate_methods_cited"):
        run = json.loads((BASE / condition / "run.json").read_text(encoding="utf-8"))
        path = Path(run["facet_path"])
        if not path.is_absolute():
            path = ROOT / path
        assert sha(path) == run["facet_sha256"], f"Changed facet source: {condition}"
        assert (run["company_count"], run["pool"], run["method_count"]) == (533, 373, 20)
        sources[condition] = sha(path)
    gpt = {
        "facet_sha256": V1 / "facets_codex_gpt61sol/tables/facets.csv",
        "sector_sha256": V1 / "sector_facets_codex_gpt61sol/tables/sector_facets.csv",
        "industry_sha256": V1 / "industry_facets_codex_gpt61sol/tables/industry_facets_long.csv",
    }
    for route in (BASE / "gpt_candidates").iterdir():
        if not route.is_dir():
            continue
        run = json.loads((route / "run.json").read_text(encoding="utf-8"))
        assert run["split_run"] == split["run"] and run["universe_run"] == universe["run"]
        for field, path in gpt.items():
            assert sha(path) == run[field], f"Changed {field}: {route.name}"
    sources.update({field: sha(path) for field, path in gpt.items()})
    return sources


def mutual_from_top10(ranking: pd.DataFrame, targets: set[str]) -> pd.DataFrame:
    """Reconstruct the fixed mutual-top-10 and three-peer top-up for reviewed targets."""
    top = {target: group.sort_values("rank", kind="stable") for target, group in ranking.groupby("target")}
    choices = []
    for target in sorted(targets):
        peers = top[target].copy()
        peers["mutual"] = peers["comp"].map(
            lambda comp: target in set(top[comp]["comp"]) if comp in top else False)
        keep = peers["mutual"].to_numpy(copy=True)
        if keep.sum() < 3:
            keep[np.flatnonzero(~keep)[:3 - keep.sum()]] = True
        choices.append(peers.loc[keep, ["target", "comp"]])
    return pd.concat(choices, ignore_index=True)


def score_cohort(source: str, method: str, ranking: pd.DataFrame,
                 selected: pd.DataFrame, label_name: str,
                 labels: pd.DataFrame) -> tuple[dict, list[dict]]:
    paired = labels.merge(ranking[["target", "comp", "rank"]], on=["target", "comp"], how="left",
                          validate="one_to_one")
    paired["rank"] = paired["rank"].fillna(11).astype(int)
    paired = paired.merge(selected.assign(selected=True), on=["target", "comp"], how="left",
                          validate="one_to_one")
    paired["selected"] = paired["selected"].fillna(False).astype(bool)
    compared = correct = 0
    target_rows = []
    for target, group in paired.groupby("target"):
        grades = group["grade"].to_numpy(dtype=int)
        ranks = group["rank"].to_numpy(dtype=int)
        better = grades[:, None] > grades[None, :]
        compared += int(better.sum())
        correct += int((better & (ranks[:, None] < ranks[None, :])).sum())
        target_rows.append({"facet_source": source, "method": method,
                            "label_source": label_name, "target": target,
                            "labeled_pairs": len(group),
                            "good_total": int((group["grade"] >= 1).sum()),
                            "good_selected": int(((group["grade"] >= 1) & group["selected"]).sum()),
                            "bad_selected": int(((group["grade"] == 0) & group["selected"]).sum())})
    good = paired["grade"] >= 1
    return ({"facet_source": source, "method": method, "label_source": label_name,
             "labeled_targets": paired["target"].nunique(), "labeled_pairs": len(paired),
             "pairwise_top10_accuracy": correct / compared if compared else np.nan,
             "pairwise_comparisons": compared,
             "good_selected": int((good & paired["selected"]).sum()),
             "good_total": int(good.sum()),
             "good_recall": float((good & paired["selected"]).sum() / good.sum()) if good.any() else np.nan,
             "bad_selected": int(((paired["grade"] == 0) & paired["selected"]).sum()),
             "bad_total": int((paired["grade"] == 0).sum()),
             "good_in_top10": int((good & paired["rank"].le(10)).sum()),
             "selected_on_labeled_targets": int(selected["target"].isin(labels["target"]).sum())}, target_rows)


def main() -> None:
    sources = checked_sources()
    _, ids, training, _ = b3.read_inputs()
    labels = pd.read_csv(BASE / "review/pairs.csv", dtype={"target_id": str, "comp_id": str})
    labels = labels.rename(columns={"target_id": "target", "comp_id": "comp",
                                    "score_barbara": "grade"})[["target", "comp", "grade"]]
    if len(labels) != 293 or labels[["target", "comp"]].duplicated().any():
        raise ValueError("The reviewer cohort changed")
    cohorts = {name: frame for name, frame in b3.load_labels(training).items()
               if name.startswith("human_")}
    cohorts["barbara_293"] = labels
    targets = set().union(*(set(frame["target"]) for frame in cohorts.values()))
    if not targets.issubset(set(ids)):
        raise ValueError("Reviewer targets outside the fixed universe")
    rows = []
    golden_rows, target_rows = [], []
    general_top = general_selected = None
    for condition in ("candidate_methods", "candidate_methods_gpt", "candidate_methods_cited"):
        path = BASE / condition
        ranks = pd.read_csv(path / "rankings.csv.gz",
                            dtype={"target": str, "comp": str, "method": str})
        observed = ranks.merge(labels, on=["target", "comp"], validate="many_to_one")
        if observed[["method", "target", "comp"]].duplicated().any():
            raise ValueError(f"Duplicate ranked peer in {condition}")
        for method, subset in observed.groupby("method", sort=True):
            precision, ndcg = [], []
            for _, target in subset.groupby("target"):
                target = target.sort_values("rank", kind="stable")
                if len(target) < 3:
                    continue
                grades = target["grade"].to_numpy(dtype=float)
                precision.append(float(np.mean(grades[:3] >= 1)))
                ndcg.append(ndcg_at_3(grades))
            rows.append({
                "facet_source": condition,
                "method": method,
                "reviewed_pairs_ranked": len(subset),
                "reviewed_targets_ranked": subset["target"].nunique(),
                "targets_with_three_reviewed_peers": len(precision),
                "labeled_precision_at_3": float(np.mean(precision)) if precision else np.nan,
                "labeled_ndcg_at_3": float(np.nanmean(ndcg)) if np.isfinite(ndcg).any() else np.nan,
                "reviewed_pairs_in_actual_top_10": int((subset["rank"] <= 10).sum()),
            })
        top = ranks.loc[ranks["target"].isin(targets) & ranks["rank"].le(10),
                        ["method", "target", "comp", "rank"]].copy()
        peers = pd.read_csv(path / "selected_peers.csv",
                            usecols=["method", "target", "comp"], dtype=str)
        peers = peers[peers["target"].isin(targets)]
        for method in sorted(ranks["method"].unique()):
            method_top = top[top["method"].eq(method)].drop(columns="method")
            method_peers = peers[peers["method"].eq(method)].drop(columns="method")
            for label_name, cohort in cohorts.items():
                result, per_target = score_cohort(condition, method, method_top,
                                                   method_peers, label_name, cohort)
                golden_rows.append(result)
                target_rows.extend(per_target)
            if condition == "candidate_methods_gpt" and method == "B3 embedding plus TF-IDF":
                general_top, general_selected = method_top, method_peers
    rank_result = pd.DataFrame(rows)
    if rank_result.groupby("facet_source")["method"].nunique().to_dict() != {
        name: 20 for name in ("candidate_methods", "candidate_methods_gpt", "candidate_methods_cited")
    }:
        raise ValueError("Expected 20 methods for each facet source")
    rank_result.to_csv(BASE / "reviewed_rank_metrics.csv", index=False)
    variants = BASE / "gpt_candidates"
    for route in sorted(path for path in variants.iterdir() if path.is_dir()):
        run = json.loads((route / "run.json").read_text(encoding="utf-8"))
        method = run["method"]
        full_top = pd.read_csv(route / "all_targets_top10.csv",
                               dtype={"target": str, "comp": str})
        if (full_top["target"].nunique() != len(ids)
                or not full_top.groupby("target").size().eq(10).all()
                or full_top.duplicated(["target", "comp"]).any()
                or not full_top["rank"].between(1, 10).all()):
            raise ValueError(f"Incomplete saved top-ten rankings: {method}")
        selected = mutual_from_top10(full_top, targets)
        top = full_top[full_top["target"].isin(targets)][["target", "comp", "rank"]]
        if method == "GPT general":
            left = set(map(tuple, top[["target", "comp", "rank"]].itertuples(index=False, name=None)))
            right = set(map(tuple, general_top[["target", "comp", "rank"]].itertuples(index=False, name=None)))
            if left != right or set(map(tuple, selected.itertuples(index=False, name=None))) != set(
                    map(tuple, general_selected.itertuples(index=False, name=None))):
                raise ValueError("Saved GPT B3 rankings do not reproduce the retrieval run")
        for label_name, cohort in cohorts.items():
            result, per_target = score_cohort("gpt_facet_variants", method, top,
                                               selected, label_name, cohort)
            golden_rows.append(result)
            target_rows.extend(per_target)
    golden = pd.DataFrame(golden_rows)
    if (len(golden) != 72 * len(cohorts)
            or golden.duplicated(["facet_source", "method", "label_source"]).any()
            or not golden["pairwise_top10_accuracy"].dropna().between(0, 1).all()):
        raise ValueError("The golden-set comparison is incomplete")
    golden.to_csv(BASE / "golden_method_metrics.csv", index=False)
    pd.DataFrame(target_rows).to_csv(BASE / "golden_target_metrics.csv", index=False)
    (BASE / "golden_method_run.json").write_text(json.dumps({
        "snapshot": "company_list_v3", "universe_run": "20261025T060358Z",
        "split_run": "20261027T204930Z", "company_count": len(ids),
        "training_count": len(training), "methods": 72,
        "label_counts": {name: len(cohort) for name, cohort in cohorts.items()},
        "label_sha256": sha(b3.LABELS), "barbara_label_sha256": sha(BASE / "review/pairs.csv"),
        "source_sha256": sources,
        "ranking_rule": "Saved top-ten peers; missing reviewed peers tie at rank 11",
        "selection_rule": "Saved selected lists, or mutual top ten with a three-peer top-up",
        "caveat": "The historical majority set has only two targets; Barbara's 293 pairs are a separate single-reviewer cohort."
    }, indent=2), encoding="utf-8")
    print(rank_result.groupby("facet_source")["method"].nunique().to_string())
    print(golden["label_source"].value_counts().to_string())


if __name__ == "__main__":
    main()
