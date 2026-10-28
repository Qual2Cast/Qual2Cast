"""Run the two existing LLM peer-selection routes on the fixed SIC2 holdout.

The model sees business facets, names, and websites; it never sees multiples,
similarity scores, or human labels. Results resume by exact prompt hash.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fill_facets as ff
import judge_comps as judge
import suggest_comps as suggest
from project_data import OUTPUTS_LOCAL


BASE_RUN = OUTPUTS_LOCAL / "comps_pilot_targets/candidates/20261027T204930Z"
CANDIDATES = OUTPUTS_LOCAL / "comps_pilot_targets/business_structure_refinement/holdout_all_candidates"
OUTPUT = OUTPUTS_LOCAL / "comps_pilot_targets/holdout_completion"
MODEL = "gpt-6.1-sol"


def checked_call(prompt: str, schema: dict, folder: Path, model: str,
                 shared_prefix: str = "") -> dict:
    """Cache a valid structured answer for an exact prompt and model."""
    folder.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256((model + "\n" + prompt).encode("utf-8")).hexdigest()
    metadata = folder / "run.json"
    response = folder / "response.json"
    if response.exists():
        if not metadata.exists():
            raise ValueError(f"Response has no prompt/model record: {folder}")
        old = json.loads(metadata.read_text(encoding="utf-8"))
        if (old["fingerprint"] != fingerprint or old["model"] != model
                or old["status"] != "ok"):
            raise ValueError(f"Cached prompt changed: {folder}")
    else:
        (folder / "prompt.txt").write_text(prompt[len(shared_prefix):], encoding="utf-8")
        schema_path = folder / "schema.json"
        schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="holdout-peer-") as workdir:
            result = ff.call_codex(prompt, folder, schema_path, workdir, model, "low")
        metadata.write_text(json.dumps({"model": model, "fingerprint": fingerprint,
                                        "status": result["llm_status"],
                                        "usage": result.get("usage", {}),
                                        "seconds": result.get("seconds")}, indent=2), encoding="utf-8")
        if result["llm_status"] != "ok":
            raise RuntimeError(f"{folder}: {result.get('error', result['llm_status'])}")
    return json.loads(response.read_text(encoding="utf-8"))


def run(candidates_run: Path = CANDIDATES, output: Path = OUTPUT,
        model: str = MODEL, limit: int | None = None, workers: int = 2) -> dict:
    run = json.loads((candidates_run / "run.json").read_text(encoding="utf-8"))
    if run["split_run"] != json.loads((BASE_RUN / "run.json").read_text(encoding="utf-8"))["split_run"]:
        raise ValueError("Holdout candidates do not use the baseline split")
    split = pd.read_csv(OUTPUTS_LOCAL / "comps_pilot_targets/split" / run["split_run"] / "split.csv",
                        dtype={"IQ_COMPANY_ID": str})
    training = split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"].tolist()
    targets = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    if limit is not None:
        targets = targets[:limit]
    pairs, info, facets = judge.load_inputs(candidates_run, judge.DEFAULT_Z)
    all_training, direct_info, direct_facets, _ = suggest.load_inputs(BASE_RUN)
    if training != all_training or not info.index.equals(direct_info.index):
        raise ValueError("Judge and direct routes do not share the fixed training pool")
    if set(pairs["target"]) - set(targets):
        pairs = pairs[pairs["target"].isin(targets)]
    if not set(pairs["comp"]) <= set(training):
        raise ValueError("A holdout candidate is outside the training pool")
    system, labels = suggest.build_system(training, direct_info, direct_facets)
    output.mkdir(parents=True, exist_ok=True)
    (output / "direct_system.txt").write_text(system, encoding="utf-8")
    def one(target: str) -> tuple[list[dict], list[dict], list[dict], str, int]:
        ticker = info.loc[target, "target_ciq_ticker"]
        choices = pairs.loc[pairs["target"].eq(target), "comp"].tolist()
        judge_rows, direct_rows, issue_rows = [], [], []
        if choices:
            prompt, candidate_labels = judge.build_prompt(target, choices, info, facets)
            raw = checked_call(prompt, judge.answer_schema(list(candidate_labels)),
                               output / "calls/judge" / target, model)
            answers, problems = judge.check_answer(raw, candidate_labels)
            issue_rows.extend({"target": target, "ticker": ticker, "route": "judge", "issue": problem}
                              for problem in problems)
            judge_rows.extend({"target": target, "comp": item["comp"],
                               "score": item["score"], "reason": item["reason"]}
                              for item in answers if item["score"] is not None)
        direct_prompt = suggest.build_prompt(system, target, direct_info, direct_facets)
        raw = checked_call(direct_prompt, suggest.ANSWER_SCHEMA,
                           output / "calls/direct" / target, model, system)
        direct, problems = suggest.check_answer(raw, labels, target)
        issue_rows.extend({"target": target, "ticker": ticker, "route": "direct", "issue": problem}
                          for problem in problems)
        direct_rows.extend({"target": target, "comp": item["comp"],
                            "rank": item["rank"], "reason": item["reason"]}
                           for item in direct)
        return judge_rows, direct_rows, issue_rows, ticker, len(choices)

    judge_rows, direct_rows, issue_rows = [], [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, target): target for target in targets}
        for number, future in enumerate(as_completed(futures), 1):
            judged, direct, issues, ticker, count = future.result()
            judge_rows.extend(judged)
            direct_rows.extend(direct)
            issue_rows.extend(issues)
            print(f"{number}/{len(targets)} {ticker}: {count} judged, {len(direct)} direct peers",
                  flush=True)
    judgments = pd.DataFrame(judge_rows, columns=["target", "comp", "score", "reason"])
    suggestions = pd.DataFrame(direct_rows, columns=["target", "comp", "rank", "reason"])
    judgments.to_csv(output / "judge.csv", index=False)
    suggestions.to_csv(output / "direct.csv", index=False)
    pd.DataFrame(issue_rows, columns=["target", "ticker", "route", "issue"]).to_csv(
        output / "answer_issues.csv", index=False)
    summary = {"model": model, "split_run": run["split_run"], "candidate_run": str(candidates_run),
               "targets_done": len(targets), "holdout_total": int(split["sample"].eq("holdout").sum()),
               "training_pool": len(training), "judged_pairs": len(judgments),
               "accepted_judge_pairs": int(judgments["score"].eq(1).sum()),
               "direct_pairs": len(suggestions),
               "answer_issues": len(issue_rows),
               "complete": len(targets) == int(split["sample"].eq("holdout").sum())}
    (output / "llm_run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(run(args.candidates, args.out, args.model, args.limit, args.workers), indent=2))
