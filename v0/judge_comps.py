"""
The model step: an LLM decides, for each target, which of its candidate
comps (step 4) are good comps and which are bad. Each comp gets a score of
1 (good) or 0 (bad), with a short reason.

One call per target (Claude Haiku 5.5 by default, through
fill_facets.call_claude): the target's name, website and facets, then each
candidate's name, website and facets, labeled C1, C2, ... in alphabetical
order, with no similarity, rank or multiple, so the order says nothing
about how close they are. The model answers good or bad for every label;
code checks that every candidate was answered once and maps the labels back
to companies.

Candidates: the pairs at z >= 2 (--z) in the latest step 4 run
(outputs-local/comps/candidates/<run>/candidates.csv), for the training
targets only (that file holds no others).

Every call keeps its prompt, raw answer and logs under
<out>/runs/<IQ_ID>/<time>/. A target is judged once per prompt and model;
a rerun skips finished targets, and a replaced judgment or table moves to
a history folder. The run stops if the API credit runs out or the key is
refused; run it again after fixing that.

  python v0/judge_comps.py --tickers PCTY BV     # a few targets
  python v0/judge_comps.py --workers 4           # every training target
  python v0/judge_comps.py --dry-run             # write the prompts only
  python v0/judge_comps.py --tables-only         # rebuild judgments.csv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facets as fc  # noqa: E402  (also puts website_scrape/ and src/ on the path)
from fill_facets import DEFAULT_MODEL, call_model, now_iso, output_paths as facet_paths, stamp  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

PROMPT_VERSION = "2026-10-25a"
DEFAULT_OUT = OUTPUTS_LOCAL / "comps" / "judge"
CANDIDATES_ROOT = OUTPUTS_LOCAL / "comps" / "candidates"
FACETS_OUT = OUTPUTS_LOCAL / "comps" / "facets"
DEFAULT_Z = 2.0

INSTRUCTIONS = """You help a private-equity analyst choose comparable public companies (comps) for valuing a target company. A buyout investor values a target from the EV/EBITDA multiples of companies in the same business: the same main products or services, sold to the same kind of customers, earning money the same way. Scale matters less than being in the same business.

Below are the target and a list of candidate comps, each with its name, website and a description of its business model. Use the descriptions and what you know about the companies.

For every candidate, decide whether it is a good comp for the target:
- good: in the same business as the target, so its multiple says something about the target's.
- bad: a different business, even if it shares an industry label, customers or a technology.

Rules:
- Answer for every candidate, once, by its label (C1, C2, ...).
- The reason is one short sentence, at most twenty words, naming what matches or differs.
- Judge the business only. Do not use or mention valuations, multiples, share prices or financial figures."""


def output_paths(out_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        runs=out_dir / "runs",                          # prompt, raw answer, logs per call
        judgments=out_dir / "judgments",                # one checked judgment per target
        judgments_history=out_dir / "judgments_history",
        prompts_dry_run=out_dir / "prompts_dry_run",
        tables=out_dir / "tables",                      # judgments.csv
        tables_history=out_dir / "tables_history",
        logs=out_dir / "logs",
    )


def answer_schema(labels: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["comps"],
            "properties": {"comps": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["label", "good", "reason"],
                "properties": {"label": {"type": "string", "enum": labels},
                               "good": {"type": "boolean"},
                               "reason": {"type": "string"}}}}}}


# ---------------------------------------------------------------- prompt

def describe(row: pd.Series) -> str:
    """A company's facets as lines: "unknown" or "none" (not applicable) where so."""
    lines = []
    for f in fc.FACETS:
        status = row.get(f"{f.name}_status", "unknown")
        value = {"unknown": "unknown", "not_applicable": "none"}.get(status) or row.get(f.name, "") or "unknown"
        lines.append(f"- {f.label}: {value}")
    return "\n".join(lines)


def build_prompt(target: str, comps: list[str], info: pd.DataFrame, facet_rows: pd.DataFrame
                 ) -> tuple[str, dict[str, str]]:
    """The prompt for one target, and the label of each candidate (C1, ...).
    Candidates are listed alphabetically by name, so their order carries no
    similarity rank."""
    order = sorted(comps, key=lambda c: (info.loc[c, "target_company_name"].lower(), c))
    labels = {f"C{i}": c for i, c in enumerate(order, 1)}

    def block(iq_id: str) -> str:
        r = info.loc[iq_id]
        return f"{r['target_company_name']} ({r['target_ciq_website']})\n{describe(facet_rows.loc[iq_id])}"

    parts = [INSTRUCTIONS, "", f"Target: {block(target)}", "", "Candidates:"]
    parts += [f"\n{label}: {block(c)}" for label, c in labels.items()]
    return "\n".join(parts), labels


def fingerprint(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- answer

def check_answer(raw: dict, labels: dict[str, str]) -> tuple[list[dict], list[str]]:
    """One row per candidate (comp, score 1/0, reason) and the issues found:
    a candidate answered twice keeps its first answer; one never answered
    gets no score."""
    rows, issues, seen = {}, [], set()
    for item in raw.get("comps", []):
        label = item.get("label")
        if label not in labels:
            issues.append(f"unknown_label:{label}")
        elif label in seen:
            issues.append(f"duplicate_label:{label}")
        else:
            seen.add(label)
            rows[label] = {"label": label, "comp": labels[label], "score": int(bool(item.get("good"))),
                           "reason": (item.get("reason") or "").strip()}
    for label, comp in labels.items():
        if label not in rows:
            issues.append(f"not_answered:{label}")
            rows[label] = {"label": label, "comp": comp, "score": None, "reason": ""}
    return [rows[label] for label in labels], issues


# ---------------------------------------------------------------- run

def latest_candidates() -> Path:
    runs = sorted(p for p in CANDIDATES_ROOT.iterdir() if (p / "candidates.csv").exists())
    if not runs:
        raise SystemExit("No step 4 candidates yet: run v0/notebooks/comps_and_valuation.ipynb section 2.")
    return runs[-1]


def load_inputs(candidates_run: Path, z: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """The pairs at z >= z, company names and websites, and the current facets (first business)."""
    pairs = pd.read_csv(candidates_run / "candidates.csv", dtype={"target": str, "comp": str})
    pairs = pairs[pairs["z"] >= z]
    universe_run = json.loads((candidates_run / "run.json").read_text(encoding="utf-8"))["universe_run"]
    info = pd.read_csv(OUTPUTS_LOCAL / "comps" / "universe" / universe_run / "universe.csv",
                       dtype=str).set_index("IQ_COMPANY_ID")
    facets = pd.read_csv(facet_paths(FACETS_OUT).tables / "facets.csv", dtype=str).fillna("")
    facets = facets[(facets["prompt_version"] == fc.PROMPT_VERSION) & (facets["llm_status"] == "ok")
                    & (facets["business_id"] == "B1")].set_index("IQ_COMPANY_ID")
    return pairs, info, facets


def move_to_history(path: Path, history: Path) -> None:
    if path.exists():
        history.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), history / f"{path.stem}_{stamp()}{path.suffix}")


def judge_one(target: str, comps: list[str], info, facets, out: SimpleNamespace, args) -> dict:
    prompt, labels = build_prompt(target, comps, info, facets)
    fp = fingerprint(prompt, f"{getattr(args, 'backend', 'claude')}:{args.model}:{args.effort}")
    path = out.judgments / f"{target}.json"
    if path.exists() and not args.refresh:
        old = json.loads(path.read_text(encoding="utf-8"))
        if (old.get("fingerprint") == fp and old.get("llm_status") == "ok"
                and len(old.get("comps", [])) == len(labels)
                and all(c.get("score") is not None for c in old["comps"])):
            return {"target": target, "status": "current"}
    run_dir = out.runs / target / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    result = call_model(prompt, run_dir, answer_schema(list(labels)), args.model, args.effort,
                        backend=getattr(args, "backend", "claude"), instructions_len=len(INSTRUCTIONS))
    run_info = {"backend": getattr(args, "backend", "claude"), "model": args.model, "effort": args.effort or "", "prompt_version": PROMPT_VERSION,
                "fingerprint": fp, "finished_at": now_iso(),
                **{k: v for k, v in result.items() if k != "text"}}
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=1), encoding="utf-8")
    judgment = {"target": target, "candidates_run": args.candidates.name, "z_min": args.z,
                "prompt_version": PROMPT_VERSION, "model": args.model, "fingerprint": fp,
                "run_dir": str(run_dir.relative_to(out.runs.parent)), "llm_status": result["llm_status"],
                "judged_at": now_iso(), "labels": labels, "comps": [], "issues": []}
    if result["llm_status"] == "ok":
        try:
            judgment["comps"], judgment["issues"] = check_answer(json.loads(result["text"]), labels)
        except json.JSONDecodeError:
            judgment["llm_status"] = "invalid_json"
    else:
        judgment["error"] = result.get("error", "")
    move_to_history(path, out.judgments_history)
    path.write_text(json.dumps(judgment, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"target": target, "status": judgment["llm_status"], "issues": judgment["issues"],
            "stop_run": result.get("stop_run", False), "usage": result.get("usage", {}),
            "seconds": result.get("seconds")}


def write_tables(out: SimpleNamespace, pairs: pd.DataFrame, info: pd.DataFrame) -> Path:
    """judgments.csv: one row per judged target-comp pair, with its step 4
    rank, similarity and z, the score (1 good, 0 bad) and the reason."""
    rows = []
    for path in sorted(out.judgments.glob("*.json")):
        j = json.loads(path.read_text(encoding="utf-8"))
        if j.get("llm_status") != "ok" or j.get("prompt_version") != PROMPT_VERSION:
            continue
        for c in j["comps"]:
            rows.append({"target": j["target"], "comp": c["comp"], "label": c["label"], "score": c["score"],
                         "reason": c["reason"], "model": j["model"], "prompt_version": j["prompt_version"],
                         "candidates_run": j["candidates_run"], "judged_at": j["judged_at"],
                         "issues": "; ".join(j["issues"])})
    table = pd.DataFrame(rows, columns=["target", "comp", "label", "score", "reason", "model", "prompt_version",
                                        "candidates_run", "judged_at", "issues"])
    # Only current candidate pairs belong to this run's table; old judgments
    # remain on disk for history but cannot re-enter a changed candidate set.
    table = table.merge(pairs[["target", "comp", "rank", "similarity", "z"]], on=["target", "comp"], how="inner")
    for col, src in [("target_ticker", "target"), ("comp_ticker", "comp")]:
        table.insert(table.columns.get_loc(src) + 1, col, table[src].map(info["target_ciq_ticker"]))
    table.insert(table.columns.get_loc("comp_ticker") + 1, "comp_company", table["comp"].map(info["target_company_name"]))
    out.tables.mkdir(parents=True, exist_ok=True)
    dest = out.tables / "judgments.csv"
    move_to_history(dest, out.tables_history)
    table.sort_values(["target", "rank"]).to_csv(dest, index=False)
    return dest


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--candidates", help="step 4 run folder (default: the latest)")
    p.add_argument("--z", type=float, default=DEFAULT_Z, help="candidates at z >= this (default 2)")
    p.add_argument("--tickers", nargs="*", help="only these targets")
    p.add_argument("--limit", type=int, help="stop after N targets")
    p.add_argument("--refresh", action="store_true", help="judge current targets again")
    p.add_argument("--backend", choices=["claude", "codex", "claude-cli"], default="claude")
    p.add_argument("--model")
    p.add_argument("--effort", choices=["low", "medium", "high"], help="default: the model's own")
    p.add_argument("--workers", type=int, default=2, help="targets in parallel")
    p.add_argument("--dry-run", action="store_true", help="write the prompts only")
    p.add_argument("--tables-only", action="store_true", help="only rebuild judgments.csv")
    args = p.parse_args(argv)
    args.model = args.model or DEFAULT_MODEL[args.backend]
    args.candidates = Path(args.candidates) if args.candidates else latest_candidates()
    out = output_paths(Path(args.out))
    for d in (out.runs, out.judgments, out.logs):
        d.mkdir(parents=True, exist_ok=True)

    pairs, info, facets = load_inputs(args.candidates, args.z)
    groups = pairs.groupby("target")["comp"].apply(list)
    if args.tickers:
        wanted = set(args.tickers)
        groups = groups[groups.index.map(info["target_ciq_ticker"]).isin(wanted)]
    if args.limit:
        groups = groups.iloc[:args.limit]
    missing = sorted((set(pairs["target"]) | set(pairs["comp"])) - set(facets.index))
    if missing:
        raise SystemExit(f"{len(missing)} companies have no current facets, e.g. {missing[:3]}")

    if args.dry_run:
        out.prompts_dry_run.mkdir(parents=True, exist_ok=True)
        for target, comps in groups.items():
            (out.prompts_dry_run / f"{target}.txt").write_text(build_prompt(target, comps, info, facets)[0],
                                                               encoding="utf-8")
        print(f"wrote {len(groups)} prompts to {out.prompts_dry_run}")
        return

    if not args.tables_only:
        log = out.logs / f"judge_{stamp()}.log"
        print(f"candidates {args.candidates.name}, z >= {args.z:g}: {len(groups)} targets, "
              f"{groups.str.len().sum()} pairs; model {args.model}; log {log.name}")
        totals, started = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}, time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as pool, log.open("w", encoding="utf-8") as lf:
            futures = {pool.submit(judge_one, t, c, info, facets, out, args): t for t, c in groups.items()}
            for n, fut in enumerate(as_completed(futures), 1):
                r = fut.result()
                for k in totals:
                    totals[k] += r.get("usage", {}).get(k, 0) or 0
                line = (f"[{n}/{len(groups)}] {info.loc[r['target'], 'target_ciq_ticker']:<8} {r['status']:<12}"
                        + (f" issues: {'; '.join(r['issues'])}" if r.get("issues") else ""))
                print(line)
                lf.write(line + "\n")
                if r.get("stop_run"):
                    print("stopping: the model call failed or its usage allowance was exhausted; finished targets are kept")
                    for f in futures:
                        f.cancel()
                    break
        print(f"tokens: {totals}; {time.time() - started:.0f} s")
    dest = write_tables(out, pairs, info)
    print("wrote", dest)


if __name__ == "__main__":
    main()
