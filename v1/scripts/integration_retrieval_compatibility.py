"""Check which saved retrieval rules accept the sector-specific facet inputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration"
SOURCES = ("candidate_methods", "source_reviewed_default/retrieval",
           "candidate_methods_gpt", "candidate_methods_cited")


def main() -> None:
    methods = {}
    for source in SOURCES:
        run = json.loads((BASE / source / "run.json").read_text(encoding="utf-8"))
        table = pd.read_csv(BASE / source / "reviewed_metrics.csv")
        if run["method_count"] != 20 or len(table) != 20 or table["method"].duplicated().any():
            raise ValueError(f"Incomplete common-field retrieval: {source}")
        methods[source] = set(table["method"])
    if len(set.union(*methods.values())) != 20 or any(items != methods[SOURCES[0]] for items in methods.values()):
        raise ValueError("The three source runs have different methods")
    variants = sorted(path for path in (BASE / "gpt_candidates").iterdir()
                      if path.is_dir() and (path / "run.json").exists())
    if len(variants) != 12:
        raise ValueError("Incomplete specialized B3 conditions")
    names = [json.loads((path / "run.json").read_text(encoding="utf-8"))["method"]
             for path in variants]
    if len(set(names)) != 12 or "GPT general" not in names:
        raise ValueError("Specialized B3 variant identity changed")
    records = []
    for method in sorted(methods[SOURCES[0]]):
        specialized = method == "B3 embedding plus TF-IDF"
        records.append({"method": method, "common_field_source_runs": len(SOURCES),
                        "specialized_facet_conditions": 12 if specialized else 0,
                        "specialized_input_rule": ("facet-level additive B3 matrices"
                                                   if specialized else "not an original-method input"),
                        "status": "executed"})
    out = BASE / "retrieval_compatibility.csv"
    pd.DataFrame(records).to_csv(out, index=False)
    (BASE / "retrieval_compatibility.json").write_text(json.dumps({
        "common_field_methods": 20, "common_field_sources": len(SOURCES),
        "specialized_B3_conditions": 12,
        "boundary": "The other nineteen original implementations consume only the twelve common fields; adding sector text changes their representation and requires a separately named experiment.",
    }, indent=2), encoding="utf-8")
    print(f"{len(records)} common-field methods; {len(variants)} specialized B3 conditions")


if __name__ == "__main__":
    main()
