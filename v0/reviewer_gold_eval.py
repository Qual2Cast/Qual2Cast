"""Score the four saved comp routes against each reviewer's blind labels.

The source Sheet is snapshotted as JSON. No label is changed or combined into
consensus; this module reuses the route metrics in ``golden_set.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import golden_set as gs


ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "outputs-local/comps_pilot_targets/golden_set/labels/reviewer_labels_20261028.json"
POOL = ROOT / "outputs-local/comps_pilot_targets/golden_set/labels/pool_with_routes.csv"
OUTPUT = ROOT / "outputs-local/comps_pilot_targets/golden_set/reviewer_evaluation"
REVIEWERS = ("riya", "barbara", "matthew")


def load_snapshot(path: Path) -> tuple[pd.DataFrame, dict]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    labels = pd.DataFrame(snapshot["labels"]).fillna("")
    if labels.duplicated(gs.KEY).any():
        raise ValueError("The review snapshot has duplicate company pairs")
    return labels, {key: snapshot[key] for key in ("source", "sheet", "range", "fetched_at_utc")}


def routes_from_pool(pool: pd.DataFrame) -> dict[str, pd.DataFrame]:
    routes = {}
    for column in pool.columns:
        if not column.startswith("rank: "):
            continue
        name = column.removeprefix("rank: ")
        selected = pool.loc[pool[column].notna(), ["target_id", "comp_id", column]].copy()
        selected.columns = ["target", "comp", "rank"]
        selected["rank"] = pd.to_numeric(selected["rank"], errors="raise").astype(int)
        if selected.duplicated(["target", "comp"]).any():
            raise ValueError(f"Duplicate pair in route: {name}")
        routes[name] = selected.sort_values(["target", "rank"]).reset_index(drop=True)
    if len(routes) != 4:
        raise ValueError(f"Expected the four saved routes; found {list(routes)}")
    return routes


def validate(labels: pd.DataFrame, pool: pd.DataFrame) -> None:
    keys = lambda frame: set(map(tuple, frame[gs.KEY].to_numpy()))
    if keys(labels) != keys(pool) or len(labels) != len(pool):
        raise ValueError("Review labels and the frozen route pool have different pairs")
    for reviewer in REVIEWERS:
        score = labels[f"score_{reviewer}"].astype(str).str.strip()
        reason = labels[f"reason_if_0_{reviewer}"].astype(str).str.strip()
        if not score.isin(["0", "1", "2"]).all():
            raise ValueError(f"{reviewer} has an unscored pair or a score outside 0–2")
        if ((score == "0") & (reason == "")).any():
            raise ValueError(f"{reviewer} has a 0 without a reason")
        if ((score != "0") & (reason != "")).any():
            raise ValueError(f"{reviewer} has a positive score with a zero-only reason")


def evaluate_reviewers(labels: pd.DataFrame, routes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    targets = labels["target_id"].drop_duplicates().tolist()
    results = []
    for reviewer in REVIEWERS:
        final = labels[gs.KEY].assign(score=labels[f"score_{reviewer}"].astype(int))
        result = gs.evaluate(routes, final, targets, k=10)
        result.insert(0, "reviewer", reviewer)
        results.append(result)
    return pd.concat(results, ignore_index=True)


def agreement(labels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scores = labels[[f"score_{reviewer}" for reviewer in REVIEWERS]].astype(int)
    review = labels[["pair", "target_id", "comp_id", *scores.columns]].copy()
    review["unanimous"] = scores.nunique(axis=1) == 1
    review["score_range"] = scores.max(axis=1) - scores.min(axis=1)
    pairs = []
    for left, right in (("riya", "barbara"), ("riya", "matthew"), ("barbara", "matthew")):
        equal = scores[f"score_{left}"] == scores[f"score_{right}"]
        pairs.append({"reviewer_a": left, "reviewer_b": right,
                      "exact_agreement": int(equal.sum()), "pairs": len(equal),
                      "agreement_rate": float(equal.mean())})
    return review, pd.DataFrame(pairs)


def export_facet_labels(labels: pd.DataFrame, output: Path) -> dict[str, int]:
    """Export independently scored pairs for the existing facet evaluator.

    A majority label requires at least two identical scores. Three distinct
    scores remain unresolved rather than being silently averaged.
    """
    columns = {"target_id": "target_iq_id", "comp_id": "comp_iq_id"}
    counts = {}
    for reviewer in REVIEWERS:
        table = labels[[*gs.KEY, f"score_{reviewer}"]].rename(
            columns={**columns, f"score_{reviewer}": "score"})
        table.to_csv(output / f"facet_labels_{reviewer}.csv", index=False)
        counts[reviewer] = len(table)
    scores = labels[[f"score_{reviewer}" for reviewer in REVIEWERS]].astype(int)
    majority = scores.apply(lambda row: row.value_counts().index[0]
                            if row.value_counts().iloc[0] >= 2 else None, axis=1)
    agreed = labels.loc[majority.notna(), gs.KEY].rename(columns=columns).copy()
    agreed["score"] = majority.loc[majority.notna()].astype(int).to_numpy()
    agreed.to_csv(output / "facet_labels_majority.csv", index=False)
    unresolved = labels.loc[majority.isna(), ["pair", *gs.KEY, *scores.columns]]
    unresolved.to_csv(output / "facet_labels_no_majority.csv", index=False)
    counts["majority"] = len(agreed)
    counts["no_majority"] = len(unresolved)
    return counts


def run(labels_path: Path = LABELS, pool_path: Path = POOL, output: Path = OUTPUT) -> dict:
    labels, source = load_snapshot(labels_path)
    pool = pd.read_csv(pool_path, dtype={"target_id": str, "comp_id": str})
    validate(labels, pool)
    routes = routes_from_pool(pool)
    metrics = evaluate_reviewers(labels, routes)
    review, pairwise = agreement(labels)
    output.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output / "route_metrics.csv", index=False)
    review.to_csv(output / "pair_agreement.csv", index=False)
    review.loc[~review["unanimous"]].to_csv(output / "disagreements.csv", index=False)
    pairwise.to_csv(output / "reviewer_agreement.csv", index=False)
    facet_label_counts = export_facet_labels(labels, output)
    summary = {"source": source, "labels_snapshot": str(labels_path.relative_to(ROOT)),
               "route_pool": str(pool_path.relative_to(ROOT)), "targets": labels["target_id"].nunique(),
               "pairs": len(labels), "routes": list(routes), "reviewers": list(REVIEWERS),
               "unanimous_pairs": int(review["unanimous"].sum()),
               "disputed_pairs": int((~review["unanimous"]).sum()),
               "facet_label_counts": facet_label_counts,
               "note": "Reviewer-specific development results; no adjudicated gold or holdout claim."}
    (output / "run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--pool", type=Path, default=POOL)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.labels, args.pool, args.out), indent=2))
