"""Group every saved current activity under one company ID.

Source-cited company business groups take precedence over incomplete pairwise
model comparisons. Otherwise related or unresolved pairs stay together; only
fully separated components become distinct businesses.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "outputs-local/comps_pilot_targets/business_structure_refinement/split_pilot_snapshot.json"
OUTPUT = ROOT / "outputs-local/comps_pilot_targets/business_structure_refinement/split_classification"
CORRECTIONS = ROOT / "outputs-local/comps_pilot_targets/business_structure_refinement/source_corrections.json"


def apply_source_corrections(decision: dict, correction: dict | None) -> dict:
    """Apply dated primary-source facts without changing the original snapshot."""
    updated = deepcopy(decision)
    if not correction:
        return updated
    valid_ids = {line["business_id"] for line in updated["businesses"]}
    for business_id, item in correction.get("line_status", {}).items():
        if business_id not in valid_ids or item["status"] not in ("current", "exited"):
            raise ValueError(f"Invalid status correction: {decision['ticker']} {business_id}")
        if not item.get("url") or not item.get("as_of"):
            raise ValueError(f"Missing source for: {decision['ticker']} {business_id}")
        updated["line_status"][business_id] = item["status"]
    updated["current"] = [line["business_id"] for line in updated["businesses"]
                          if updated["line_status"][line["business_id"]] != "exited"]
    updated["exited"] = [line["business_id"] for line in updated["businesses"]
                         if updated["line_status"][line["business_id"]] == "exited"]
    updated["unresolved"] = [line for line in updated["current"]
                             if updated["line_status"][line] == "unresolved"]
    resolved = set(correction.get("line_status", {}))
    updated["evidence_gaps"] = [gap for gap in updated.get("evidence_gaps", [])
                                if gap not in resolved]
    prior_groups = updated.get("groups", [])
    prior_evidence = updated.get("group_evidence") or []
    kept = [(group, prior_evidence[i] if i < len(prior_evidence) else [])
            for i, group in enumerate(prior_groups) if any(x in updated["current"] for x in group)]
    updated["groups"] = [[x for x in group if x in updated["current"]] for group, _ in kept]
    if prior_evidence:
        updated["group_evidence"] = [evidence for _, evidence in kept]
    override = correction.get("groups")
    if override:
        if not correction.get("group_source_url"):
            raise ValueError(f"Missing group source: {decision['ticker']}")
        updated["source_group_override"] = override
        updated["source_group_url"] = correction["group_source_url"]
    return updated


def make_snapshot(source_root: Path, destination: Path) -> dict:
    """Freeze the same 40 saved decisions and source bundles used in the pilot."""
    final = source_root / "final-split-20261027"
    focused = source_root / "focused-split-20261027"
    web = source_root / "web-split-20261027"
    overrides = {"AZZ": web, "BBCP": web, "BUKS": web, "SNFC.A": web,
                 "AFG": focused, "NWSA": focused}
    tickers = pd.read_csv(final / "summary.csv")["ticker"].tolist()
    companies = {}
    for ticker in tickers:
        preferred = overrides.get(ticker, final)
        run = preferred if (preferred / "companies" / f"{ticker}.json").exists() else final
        decision = json.loads((run / "companies" / f"{ticker}.json").read_text(encoding="utf-8"))
        evidence_path = run / "calls" / ticker / "evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.exists() else {}
        companies[ticker] = {"decision": decision, "evidence": evidence,
                             "source_run": run.name}
    snapshot = {"description": "40-company source-bound split pilot; existing decisions, not new labels",
                "companies": companies}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return snapshot


def refine_decision(decision: dict) -> dict:
    """Return a complete, source-led partition of the company's current lines."""
    active = list(decision.get("current", []))
    proposed = [list(group) for group in decision.get("groups", [])]
    if not proposed and active:
        proposed = [active]
    if sorted(x for group in proposed for x in group) != sorted(active):
        raise ValueError(f"Groups do not cover current activities: {decision.get('ticker')}")
    pair_status = {frozenset(key.split("|")): value
                   for key, value in decision.get("pair_status", {}).items()}

    def relation(left: str, right: str) -> str:
        return pair_status.get(frozenset((left, right)), "unresolved")

    source_override = decision.get("source_group_override")
    citations = decision.get("group_evidence") or []
    if source_override:
        groups = [list(group) for group in source_override]
        if sorted(x for group in groups for x in group) != sorted(active):
            raise ValueError(f"Source groups do not cover current activities: {decision.get('ticker')}")
        basis = "dated_primary_source"
    elif len(citations) == len(proposed) and all(citations):
        # The prior grouping stage required real cited source lines for every
        # group. A missing pairwise comparison does not erase that evidence.
        groups = proposed
        basis = "source_cited_grouping"
    else:
        parent = {line: line for line in active}

        def root(line: str) -> str:
            while parent[line] != line:
                line = parent[line]
            return line

        for left, right in combinations(active, 2):
            if relation(left, right) == "distinct":
                continue
            left_group = [line for line in active if root(line) == root(left)]
            right_group = [line for line in active if root(line) == root(right)]
            if any(relation(a, b) == "distinct" for a in left_group for b in right_group):
                continue
            parent[root(right)] = root(left)
        buckets: dict[str, list[str]] = {}
        for line in active:
            buckets.setdefault(root(line), []).append(line)
        groups = list(buckets.values())
        basis = "pair_evidence" if len(groups) > 1 else "whole_company_scope"

    group_of = {line: index for index, group in enumerate(groups) for line in group}
    conflicts = [f"{left}|{right}" for left, right in combinations(active, 2)
                 if (relation(left, right) == "distinct" and group_of[left] == group_of[right])
                 or (relation(left, right) == "related" and group_of[left] != group_of[right])]
    return {"IQ_COMPANY_ID": decision.get("IQ_COMPANY_ID"),
            "ticker": decision.get("ticker"), "decision":
            "multiple_businesses" if len(groups) > 1 else "one_business",
            "groups": groups, "group_basis": basis,
            "proposed_groups": proposed, "exited": decision.get("exited", []),
            "conflicting_pair_evidence": conflicts,
            "source_gaps": decision.get("evidence_gaps", []),
            "review_flags": [*conflicts, *decision.get("evidence_gaps", [])]}


def scope_note(decision: dict, refined: dict) -> str:
    """Short source-derived correction for the existing peer judge prompt."""
    names = {item["business_id"]: item["business"] for item in decision["businesses"]}
    groups = [" + ".join(names[x] for x in group) for group in refined["groups"]]
    lines = ["Current company scope: " + "; ".join(groups) + "."] if groups else []
    if refined["exited"]:
        lines.append("Completed exits, excluded from current scope: " +
                     "; ".join(names[x] for x in refined["exited"]) + ".")
    return " ".join(lines)


def run(snapshot_path: Path = SNAPSHOT, output: Path = OUTPUT,
        corrections_path: Path = CORRECTIONS) -> dict:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    corrections = json.loads(corrections_path.read_text(encoding="utf-8")) if corrections_path.exists() else {}
    rows = []
    details = {}
    for ticker, record in snapshot["companies"].items():
        original = record["decision"]
        updated = apply_source_corrections(original, corrections.get(ticker))
        refined = refine_decision(updated)
        details[ticker] = {**refined, "scope_note": scope_note(updated, refined)}
        rows.append({"ticker": ticker, "company_id": refined["IQ_COMPANY_ID"],
                     "old_decision": original["company_decision"],
                     "refined_decision": refined["decision"],
                     "old_groups": len(original.get("groups", [])),
                     "refined_groups": len(refined["groups"]),
                     "group_basis": refined["group_basis"],
                     "pair_conflicts": len(refined["conflicting_pair_evidence"]),
                     "exited": len(refined["exited"]),
                     "source_gaps": len(refined["source_gaps"]),
                     "source_corrections": len(corrections.get(ticker, {}).get("line_status", {}))
                     + int(bool(corrections.get(ticker, {}).get("groups")))})
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "company_comparison.csv", index=False)
    (output / "refined_scopes.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
    return {"companies": len(rows), "old_multi": sum(r["old_decision"] == "multiple_businesses" for r in rows),
            "refined_multi": sum(r["refined_decision"] == "multiple_businesses" for r in rows),
            "pair_conflict_companies": sum(r["pair_conflicts"] > 0 for r in rows)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", type=Path, help="Freeze the prior pilot run locally")
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--corrections", type=Path, default=CORRECTIONS)
    args = parser.parse_args()
    if args.source_root:
        make_snapshot(args.source_root, args.snapshot)
    print(json.dumps(run(args.snapshot, args.out, args.corrections), indent=2))
