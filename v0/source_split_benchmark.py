"""Compare saved and refined business structures with a primary-source check."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import business_split_refinement as refinement


REFERENCE = refinement.SNAPSHOT.parent / "primary_source_reference.json"
OUTPUT = refinement.SNAPSHOT.parent / "source_benchmark"


def canonical(groups: list[list[str]]) -> tuple[tuple[str, ...], ...]:
    return tuple(sorted(tuple(sorted(group)) for group in groups))


def run(reference_path: Path = REFERENCE, output: Path = OUTPUT) -> dict:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))["cases"]
    snapshot = json.loads(refinement.SNAPSHOT.read_text(encoding="utf-8"))["companies"]
    corrections = json.loads(refinement.CORRECTIONS.read_text(encoding="utf-8"))
    activity_rows, group_rows = [], []
    for ticker, labels in reference.items():
        original = snapshot[ticker]["decision"]
        corrected = refinement.apply_source_corrections(original, corrections.get(ticker))
        refined = refinement.refine_decision(corrected)
        expected = {**dict.fromkeys(labels["current"], "current"),
                    **dict.fromkeys(labels["exited"], "exited")}
        if set(expected) != {line["business_id"] for line in original["businesses"]}:
            raise ValueError(f"Reference omits an activity: {ticker}")
        for business_id, actual in expected.items():
            activity_rows.append({"ticker": ticker, "business_id": business_id,
                                  "reference": actual,
                                  "saved": original["line_status"][business_id],
                                  "refined": corrected["line_status"][business_id],
                                  "saved_correct": original["line_status"][business_id] == actual,
                                  "refined_correct": corrected["line_status"][business_id] == actual,
                                  "source": " | ".join(labels["sources"])})
        if "groups" in labels:
            truth = canonical(labels["groups"])
            group_rows.append({"ticker": ticker,
                               "reference_groups": json.dumps(labels["groups"]),
                               "saved_groups": json.dumps(original["groups"]),
                               "refined_groups": json.dumps(refined["groups"]),
                               "saved_exact": canonical(original["groups"]) == truth,
                               "refined_exact": canonical(refined["groups"]) == truth,
                               "source": " | ".join(labels["sources"]),
                               "basis": labels["basis"]})
    activities = pd.DataFrame(activity_rows)
    groups = pd.DataFrame(group_rows)
    output.mkdir(parents=True, exist_ok=True)
    activities.to_csv(output / "activity_status.csv", index=False)
    groups.to_csv(output / "group_partitions.csv", index=False)
    summary = {"cases": len(reference), "activity_labels": len(activities),
               "activity_correct_saved": int(activities["saved_correct"].sum()),
               "activity_correct_refined": int(activities["refined_correct"].sum()),
               "group_reference_cases": len(groups),
               "group_exact_saved": int(groups["saved_exact"].sum()),
               "group_exact_refined": int(groups["refined_exact"].sum()),
               "scope": "Targeted source-audited cases, not a random or blinded population accuracy estimate."}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
