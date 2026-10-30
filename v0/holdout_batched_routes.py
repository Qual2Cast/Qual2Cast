"""Finish the four-route holdout using batched, independent LLM decisions.

Each target retains the original v0 candidate pool and selection rules.
Batching shares the 373-firm direct-LLM prompt across eight targets and
reduces repeated long input. The changed inference protocol is recorded.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import holdout_llm_routes as common
import judge_comps as judge
import suggest_comps as suggest
from project_data import OUTPUTS_LOCAL


DIRECT_BATCH = 8
JUDGE_BATCH = 4


def chunks(items: list[str], size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def schema(items: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["targets"],
            "properties": {"targets": {"type": "array", "minItems": len(items),
                                      "maxItems": len(items), "items": {
                "type": "object", "additionalProperties": False,
                "required": ["target_id", "comps"],
                "properties": {"target_id": {"type": "string", "enum": list(items)},
                               "comps": {"type": "array", "items": items[next(iter(items))]}}}}}}


def answers_by_target(raw: dict, expected: list[str]) -> dict[str, dict]:
    rows = raw.get("targets", [])
    ids = [item.get("target_id") for item in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError(f"Batch returned targets {ids}; expected {expected}")
    return {item["target_id"]: item for item in rows}


def direct_schema(targets: list[str]) -> dict:
    item = suggest.ANSWER_SCHEMA["properties"]["comps"]["items"]
    return schema({target: item for target in targets})


def judge_schema(targets: list[str]) -> dict:
    # Per-target labels are verified after the model answers.
    item = {"type": "object", "additionalProperties": False,
            "required": ["label", "good", "reason"],
            "properties": {"label": {"type": "string"}, "good": {"type": "boolean"},
                           "reason": {"type": "string"}}}
    return schema({target: item for target in targets})


def run(candidates_run: Path = common.CANDIDATES, output: Path = common.OUTPUT,
        model: str = common.MODEL, limit: int | None = None,
        workers: int = 3, sector_facets: Path | None = None) -> dict:
    # Large shared-pool prompts sometimes exceed the facet fill's 10-minute
    # default. Resume cached batches and allow 20 minutes for the few long calls.
    common.ff.CODEX_TIMEOUT_SECONDS = 1200
    config = json.loads((candidates_run / "run.json").read_text(encoding="utf-8"))
    base = json.loads((common.BASE_RUN / "run.json").read_text(encoding="utf-8"))
    if config["split_run"] != base["split_run"]:
        raise ValueError("The holdout and baseline splits differ")
    split = pd.read_csv(OUTPUTS_LOCAL / "comps_pilot_targets/split" /
                        config["split_run"] / "split.csv", dtype={"IQ_COMPANY_ID": str})
    targets = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    training = split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"].tolist()
    if limit is not None:
        targets = targets[:limit]
    pairs, info, facets = judge.load_inputs(candidates_run, judge.DEFAULT_Z)
    pool, direct_info, direct_facets, _ = suggest.load_inputs(common.BASE_RUN)
    if training != pool or not info.index.equals(direct_info.index):
        raise ValueError("The LLM routes do not share one fixed training pool")
    if not set(pairs["target"]) <= set(split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"]):
        raise ValueError("Candidates include a training target")
    if not set(pairs["comp"]) <= set(training):
        raise ValueError("Candidates include a holdout peer")
    if sector_facets is not None:
        from sector_facet_candidates import attach_sector_summary, load_sector_facets
        sector = load_sector_facets(sector_facets, list(info.index))
        facets = attach_sector_summary(facets, sector)
        direct_facets = attach_sector_summary(direct_facets, sector)
    system, labels = suggest.build_system(training, direct_info, direct_facets)
    output.mkdir(parents=True, exist_ok=True)
    (output / "direct_system.txt").write_text(system, encoding="utf-8")
    direct_rows, judge_rows, issue_rows = [], [], []

    def direct_one(batch_no: int, group: list[str]):
        blocks = [f"Target ID {target}: " + suggest.build_prompt(
            system, target, direct_info, direct_facets)[len(system):].removeprefix("Target: ")
                  for target in group]
        prompt = (system + "\nEvaluate each target below independently. Return one "
                  "answer for each target ID; use the same pool labels for all.\n\n"
                  + "\n\n".join(blocks))
        raw = common.checked_call(prompt, direct_schema(group),
                                  output / "calls/batch_direct" /
                                  f"{batch_no:03d}_{len(group)}_{group[0]}_{group[-1]}",
                                  model, system)
        batch = answers_by_target(raw, group)
        rows, issues = [], []
        for target in group:
            selected, problems = suggest.check_answer(batch[target], labels, target)
            rows.extend({"target": target, "comp": item["comp"],
                         "rank": item["rank"], "reason": item["reason"]}
                        for item in selected)
            issues.extend({"target": target, "route": "direct", "issue": problem}
                          for problem in problems)
        return rows, issues, batch_no, len(group)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(direct_one, number, group)
                   for number, group in enumerate(chunks(targets, DIRECT_BATCH), 1)]
        for future in as_completed(futures):
            rows, issues, number, count = future.result()
            direct_rows.extend(rows)
            issue_rows.extend(issues)
            print(f"direct batch {number}: {count} targets", flush=True)

    judge_groups = [target for target in targets if pairs["target"].eq(target).any()]
    def judge_one(batch_no: int, group: list[str]):
        mappings = {}
        blocks = []
        for target in group:
            comps = pairs.loc[pairs["target"].eq(target), "comp"].tolist()
            target_prompt, mappings[target] = judge.build_prompt(target, comps, info, facets)
            blocks.append(f"Target ID {target}:\n" + target_prompt[len(judge.INSTRUCTIONS):].strip())
        prompt = (judge.INSTRUCTIONS + "\n\nEvaluate each target independently. "
                  "C labels restart for each target. Return one answer for each target ID.\n\n"
                  + "\n\n".join(blocks))
        raw = common.checked_call(prompt, judge_schema(group),
                                  output / "calls/batch_judge" /
                                  f"{batch_no:03d}_{len(group)}_{group[0]}_{group[-1]}", model)
        batch = answers_by_target(raw, group)
        rows, issues = [], []
        for target in group:
            judged, problems = judge.check_answer(batch[target], mappings[target])
            rows.extend({"target": target, "comp": item["comp"],
                         "score": item["score"], "reason": item["reason"]}
                        for item in judged if item["score"] is not None)
            issues.extend({"target": target, "route": "judge", "issue": problem}
                          for problem in problems)
        return rows, issues, batch_no, len(group)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(judge_one, number, group)
                   for number, group in enumerate(chunks(judge_groups, JUDGE_BATCH), 1)]
        for future in as_completed(futures):
            rows, issues, number, count = future.result()
            judge_rows.extend(rows)
            issue_rows.extend(issues)
            print(f"judge batch {number}: {count} targets", flush=True)

    judgment = pd.DataFrame(judge_rows, columns=["target", "comp", "score", "reason"])
    direct = pd.DataFrame(direct_rows, columns=["target", "comp", "rank", "reason"])
    order = {target: index for index, target in enumerate(targets)}
    judgment = judgment.sort_values(["target", "comp"], key=lambda col:
                                    col.map(order) if col.name == "target" else col)
    direct = direct.sort_values(["target", "rank"], key=lambda col:
                                col.map(order) if col.name == "target" else col)
    judgment.to_csv(output / "judge.csv", index=False)
    direct.to_csv(output / "direct.csv", index=False)
    pd.DataFrame(issue_rows, columns=["target", "route", "issue"]).to_csv(
        output / "answer_issues.csv", index=False)
    summary = {"model": model, "inference_protocol": "batched independent targets",
               "sector_facets": str(sector_facets) if sector_facets else None,
               "direct_batch_size": DIRECT_BATCH, "judge_batch_size": JUDGE_BATCH,
               "workers": workers, "call_timeout_seconds": common.ff.CODEX_TIMEOUT_SECONDS,
               "split_run": config["split_run"], "candidate_run": str(candidates_run),
               "targets_done": len(targets),
               "holdout_total": int(split["sample"].eq("holdout").sum()),
               "training_pool": len(training), "judged_pairs": len(judgment),
               "accepted_judge_pairs": int(judgment["score"].eq(1).sum()),
               "direct_pairs": len(direct), "answer_issues": len(issue_rows),
               "complete": len(targets) == int(split["sample"].eq("holdout").sum())}
    (output / "llm_run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default=common.MODEL)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--candidates-run", type=Path, default=common.CANDIDATES)
    parser.add_argument("--out", type=Path, default=common.OUTPUT)
    parser.add_argument("--sector-facets", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(candidates_run=args.candidates_run, output=args.out,
                         model=args.model, limit=args.limit, workers=args.workers,
                         sector_facets=args.sector_facets), indent=2))
