"""Run Kethan's source-cited peer judge directly on the 0-2 golden-set rubric.

This diagnostic compares 36 PCTY/WEN pairs without changing peer selection or
valuation. All judge calls use the rubric's 0-2 scores; no score remapping.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import peer_evaluation as pe
import reviewer_gold_eval as gold
from cli_models import call_cli
from project_data import OUTPUTS_LOCAL, REPO_ROOT, sha256


CANDIDATES = OUTPUTS_LOCAL / "comps_pilot_targets/candidates/20261027T204930Z"
LABELS = gold.LABELS
POOL = gold.POOL
DEFAULT_OUT = OUTPUTS_LOCAL / "comps_pilot_targets/golden_set/judge_comparison_0_2_exact"
PROMPT_VERSION = "golden-set-0-2-exact-2026-10-28"
VERDICTS = {0: "not_peer", 1: "adjacent_peer", 2: "direct_peer",
            None: "insufficient_evidence"}
RUBRIC = """Score | Meaning | Rule
2 | Direct competitor | Same product AND same customers.
1 | Adjacent | Overlapping product OR customers, but not both.
0 | Not a peer | No real overlap.

Reasons for a 0 | Use it when
Different industry | Unrelated industry, no overlap in product or customers (e.g. an apparel brand vs. a restaurant)
Different business model | Same or neighboring industry, but it makes money a different way (e.g. a food manufacturer vs. a restaurant)
Different customers | Similar kind of offering, but it sells to a different buyer.
Different scale | The business matches, but the size gap makes it useless.
Generic wording only | The only link is buzzwords like platform or solutions.
Wrong industry code | Same SIC code, but a different business."""


def answer_schema() -> dict:
    schema = pe.answer_schema()
    schema["properties"]["score"]["enum"] = [0, 1, 2, None]
    schema["properties"]["verdict"]["enum"] = list(VERDICTS.values())
    return schema


class GoldenSetJudge(pe.PeerEvaluation):
    """Reuse Kethan's evidence and prompt construction with the gold rubric."""

    def check_answer(self, raw: dict, packet: dict) -> dict:
        score = raw["score"]
        if score not in VERDICTS or (score is not None and type(score) is not int) \
                or raw["verdict"] != VERDICTS[score]:
            raise ValueError("Score and verdict must agree with the 0-2 rubric")
        normalized, citations = {}, []
        for side in ("target", "comp"):
            prefix = "T:" if side == "target" else "C:"
            labels = raw[f"{side}_citations"]
            if score is not None and not labels:
                raise ValueError(f"A graded answer requires {side} citations")
            normalized[f"{side}_citations"] = []
            for reference in labels:
                match = re.fullmatch(r"\[([TC]:P\d+\.\d+)\](?:\s+.*)?",
                                     reference.strip(), re.S)
                label = match.group(1) if match else reference.strip()
                if label not in packet["lines"] or not label.startswith(prefix):
                    raise ValueError(f"Citation is not a supplied {side} passage: {label}")
                normalized[f"{side}_citations"].append(label)
                citations.append({"label": label, **packet["lines"][label]})
        if not raw["reason"].strip() or (score is None and not raw["missing_evidence"].strip()):
            raise ValueError("A reason and an explanation of missing evidence are required")
        return {**raw, **normalized, "citations": citations}


def majority(scores: list[int]) -> int | None:
    counts = Counter(scores)
    value, count = counts.most_common(1)[0]
    return value if count >= 2 else None


def prepare(out: Path, model: str, effort: str | None) -> tuple[GoldenSetJudge, pd.DataFrame]:
    labels, source = gold.load_snapshot(LABELS)
    pool = pd.read_csv(POOL, dtype={"target_id": str, "comp_id": str})
    gold.validate(labels, pool)
    joined = labels.merge(pool, on=gold.gs.KEY, how="left", validate="one_to_one")
    meta = json.loads((CANDIDATES / "run.json").read_text(encoding="utf-8"))
    universe = OUTPUTS_LOCAL / "comps/universe" / meta["universe_run"] / "universe.csv"

    config = pe.Config(candidates_run=str(CANDIDATES.relative_to(REPO_ROOT)),
                       backend="codex", model=model, effort=effort, rubric=RUBRIC,
                       passing_score=2)
    judge = GoldenSetJudge(config, run_dir=out)
    judge.info = pd.read_csv(universe, dtype=str).set_index("IQ_COMPANY_ID")
    ids = set(joined.target_id) | set(joined.comp_id)
    absent = ids - set(judge.info.index)
    if absent:
        raise ValueError(f"Reviewer pairs missing from the frozen universe: {sorted(absent)}")
    judge.evidence = {iq: judge.company_evidence(iq) for iq in sorted(ids)}
    judge.packets = {}
    for row in joined.itertuples(index=False):
        key = f"{row.target_id}__{row.comp_id}"
        prompt, lines = judge.prompt(row.target_id, row.comp_id)
        identity = json.dumps([config.backend, config.model, config.effort,
                               answer_schema(), prompt,
                               judge.evidence[row.target_id], judge.evidence[row.comp_id]],
                              sort_keys=True)
        judge.packets[key] = {"target": row.target_id, "comp": row.comp_id,
                              "prompt": prompt, "lines": lines,
                              "fingerprint": hashlib.sha256(identity.encode()).hexdigest()}
    inputs = out / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    provenance = {str(p.relative_to(REPO_ROOT)): sha256(p)
                  for p in (LABELS, POOL, CANDIDATES / "run.json", universe)}
    (inputs / "provenance.json").write_text(json.dumps({"source": source, "files": provenance,
        "judge_prompt_version": PROMPT_VERSION,
        "rubric_source": "https://docs.google.com/spreadsheets/d/1rp6H-IXhfZ09NbOObzPreLvGaXjOugEUblYcHo31IQg/edit#gid=1963357707",
        "rubric": RUBRIC}, indent=2), encoding="utf-8")
    (inputs / "rubric.txt").write_text(RUBRIC + "\n", encoding="utf-8")
    return judge, joined


def run_one(judge: GoldenSetJudge, key: str, packet: dict) -> tuple[str, str]:
    if judge.cached(key, packet):
        return key, "cached"
    run_dir = judge.run_dir / "runs" / key / pe.stamp()
    result = call_cli(packet["prompt"], run_dir, answer_schema(),
                      judge.config.backend, judge.config.model or None,
                      judge.config.effort)
    record = {"target": packet["target"], "comp": packet["comp"],
              "fingerprint": packet["fingerprint"], "backend": judge.config.backend,
              "model": judge.config.model, "prompt_version": PROMPT_VERSION,
              "run_dir": str(run_dir.relative_to(judge.run_dir)),
              "finished_at": pe.stamp(), "status": result["llm_status"]}
    if result["llm_status"] == "ok":
        try:
            record["answer"] = judge.check_answer(json.loads(result["text"]), packet)
        except (ValueError, KeyError, TypeError) as exc:
            record.update(status="invalid_answer", error=str(exc))
    else:
        record["error"] = result.get("error", result["llm_status"])
    judge.save(f"runs/{key}/{run_dir.name}/run.json",
               {name: value for name, value in result.items() if name != "text"})
    judge.save(f"judgments/{key}.json", record)
    return key, record["status"]


def compare(judge: GoldenSetJudge, joined: pd.DataFrame) -> dict:
    rows = []
    for row in joined.to_dict("records"):
        key = f"{row['target_id']}__{row['comp_id']}"
        packet = judge.packets[key]
        path = judge.run_dir / "judgments" / f"{key}.json"
        record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if record.get("fingerprint") != packet["fingerprint"]:
            record = {}
        answer = record.get("answer", {})
        raw = answer.get("score")
        values = [int(row[f"score_{name}"]) for name in gold.REVIEWERS]
        rows.append({**row, "human_average": sum(values) / len(values),
                     "human_score_range": max(values) - min(values),
                     "human_majority": majority(values),
                     "judge_status": record.get("status", "not_run"),
                     "judge_score_0_2": raw,
                     "judge_verdict": answer.get("verdict"),
                     "judge_reason": answer.get("reason"),
                     "judge_missing_evidence": answer.get("missing_evidence"),
                     "judge_citations": json.dumps(answer.get("citations", []), ensure_ascii=False),
                     "judge_error": record.get("error", "")})
    table = pd.DataFrame(rows).sort_values("pair")
    out = judge.run_dir / "tables"
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "pair_comparison.csv", index=False)
    table.to_json(out / "pair_comparison.json", orient="records", indent=2,
                  force_ascii=False)
    brief = ["pair", "target", "comp", "score_riya", "score_matthew", "score_barbara",
             "human_average", "human_score_range", "human_majority", "judge_score_0_2",
             "judge_status", "judge_verdict", "judge_reason"]
    table[brief].to_csv(out / "labels_side_by_side.csv", index=False)
    graded = table[table.judge_score_0_2.notna()].copy()
    refs = [(name, f"score_{name}") for name in gold.REVIEWERS]
    refs.append(("majority", "human_majority"))
    metric_rows, confusion = [], []
    for name, column in refs:
        subset = graded[graded[column].notna()].copy()
        reference = subset[column].astype(int)
        prediction = subset.judge_score_0_2.astype(int)
        metric_rows.append({"reference": name, "labeled_pairs": int(table[column].notna().sum()),
                            "graded_pairs": len(subset),
                            "matching_pairs": int((reference == prediction).sum()),
                            "exact_agreement": float((reference == prediction).mean()) if len(subset) else None,
                            "mean_absolute_grade_error": float((reference - prediction).abs().mean()) if len(subset) else None})
        counts = Counter(zip(reference, prediction))
        confusion.extend({"reference": name, "human_score": human, "judge_score": predicted,
                          "pairs": counts[(human, predicted)]}
                         for human in range(3) for predicted in range(3))
    pd.DataFrame(metric_rows).to_csv(out / "agreement.csv", index=False)
    pd.DataFrame(confusion).to_csv(out / "confusion.csv", index=False)
    average_error = (graded.judge_score_0_2 - graded.human_average).abs()
    pd.DataFrame([{"reference": "three-reviewer average", "labeled_pairs": len(table),
                   "graded_pairs": len(graded),
                   "mean_absolute_grade_error": float(average_error.mean()) if len(graded) else None}]) \
        .to_csv(out / "average_comparison.csv", index=False)
    disagreement = table[(table.human_majority.isna()) |
                         (table.judge_score_0_2.notna() &
                          table.human_majority.notna() &
                          table.judge_score_0_2.ne(table.human_majority))]
    disagreement.to_csv(out / "review_queue.csv", index=False)
    summary = {"pairs": len(table), "graded": len(graded),
               "insufficient_evidence": int(table.judge_verdict.eq("insufficient_evidence").sum()),
               "failed": int((~table.judge_status.isin(["ok", "not_run"])).sum()),
               "human_unanimous": int(table.human_score_range.eq(0).sum()),
               "human_disputed": int(table.human_score_range.gt(0).sum()),
               "no_human_majority": int(table.human_majority.isna().sum()),
               "metrics": metric_rows,
               "interpretation": "Diagnostic agreement on two development targets; no model was tuned or reranked."}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--effort", default="low")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 4:
        raise ValueError("workers must be between 1 and 4")
    judge, joined = prepare(args.out, args.model, args.effort)
    print(f"Prepared {len(joined)} pairs; {sum(bool(judge.evidence[i]['lines']) for i in judge.evidence)} "
          f"of {len(judge.evidence)} companies have usable saved-page evidence.", flush=True)
    if args.execute:
        pending = [(key, packet) for key, packet in judge.packets.items()
                   if judge.cached(key, packet) is None]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run_one, judge, key, packet): key for key, packet in pending}
            for done in as_completed(futures):
                key, status = done.result()
                print(f"{key}: {status}", flush=True)
    print(json.dumps(compare(judge, joined), indent=2), flush=True)


if __name__ == "__main__":
    main()
