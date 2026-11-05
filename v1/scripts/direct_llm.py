"""
Recipe step 4 without embeddings: an LLM suggests each target's comps
directly from the whole pool of training firms, instead of judging a
shortlist made by cosine similarity (cosine_then_llm.py).

One call per training target (Claude Haiku 5.5 by default, through
fill_facets.call_claude). The system prompt holds the instructions and the
full pool, every training firm labeled P001, P002, ... in alphabetical
order with its name, website and the facets that define its business
(core offering, products, services, customers, revenue model). It is the
same for every target, so it is cached. The user message is the target:
name, website and its facets. The model picks at most ten companies in
the same business, best first, each with a reason; code drops the target
itself, unknown labels and repeats.

The pool is the training firms of the split that the latest step 4 run
used (outputs-local/v1/candidates/<run>/run.json), so the same firms can be
comps here as there.

Prompt versions (details and the checks: v1/PROMPT_VERSIONS.md). Only the
target's facet lines differ; the pool lines never listed company size:
  2026-10-25a  SAVED_PROMPT_VERSION. The target with all twelve facets,
               company size (F9) included. The saved picks
               (outputs-local/v1/suggest/, 373 training targets, Haiku) and
               the saved holdout answers were made with it.
  2026-11-04a  PROMPT_VERSION, the default for new runs: company size left
               out (team decision 2026-11-03).
Choose with --prompt-version. A new run writes, by default, to
outputs-local/v1/direct_llm/<split run>_<prompt version>/, so it never
replaces the saved picks.

  python v1/scripts/direct_llm.py --tickers PCTY BV     # a few targets
  python v1/scripts/direct_llm.py --workers 4           # every training target
  python v1/scripts/direct_llm.py --dry-run             # write the prompts only
  python v1/scripts/direct_llm.py --tables-only --out outputs-local/v1/suggest --prompt-version 2026-10-25a
                                                        # rebuild the saved suggestions.csv
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facets as fc  # noqa: E402  (also puts website_scrape/ and src/ on the path)
from fill_facets import DEFAULT_MODEL, call_claude, now_iso, output_paths as facet_paths, stamp  # noqa: E402
from cosine_then_llm import describe, fingerprint, latest_candidates, move_to_history  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

PROMPT_VERSION = "2026-11-04a"            # new runs: company size (F9) left out of the target's facet lines
SAVED_PROMPT_VERSION = "2026-10-25a"      # the saved picks and holdout answers: all twelve facets
PROMPT_EXCLUDES = {                       # facets left out of the target's description, per version
    "2026-10-25a": (),
    "2026-11-04a": ("company_size",),
}
SAVED_OUT = OUTPUTS_LOCAL / "v1" / "suggest"              # the saved 2026-10-25a picks
DEFAULT_OUT_ROOT = OUTPUTS_LOCAL / "v1" / "direct_llm"    # new runs: <root>/<split run>_<prompt version>/
DEFAULT_OUT = SAVED_OUT                   # kept for older imports; new runs use DEFAULT_OUT_ROOT
FACETS_OUT = OUTPUTS_LOCAL / "v1" / "facets"
MAX_COMPS = 10
POOL_FACETS = ["offering_description", "primary_products", "primary_services", "customer_segment",
               "revenue_model"]   # the facets that say what business a company is in

INSTRUCTIONS = f"""You help a private-equity analyst choose comparable public companies (comps) for valuing a target company. A buyout investor values a target from the EV/EBITDA multiples of companies in the same business: the same main products or services, sold to the same kind of customers, earning money the same way. Scale matters less than being in the same business.

Below is a list of public companies, each with a label (P001, P002, ...), its name, website and a short description of its business. After the list comes the target, with a fuller description.

Choose the companies on the list that are good comps for the target: in the same business, so their multiples say something about the target's. A company that only shares an industry label, customers or a technology is not a good comp.

Rules:
- Choose at most {MAX_COMPS}, the best comp first. Choose fewer, or none, if fewer are in the same business.
- Never choose the target itself, if it is on the list.
- Use the descriptions and what you know about the companies.
- For each, give its label and one short sentence, at most twenty words, on why it is in the same business.
- Judge the business only. Do not use or mention valuations, multiples, share prices or financial figures."""

ANSWER_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["comps"],
                 "properties": {"comps": {"type": "array", "items": {
                     "type": "object", "additionalProperties": False, "required": ["label", "reason"],
                     "properties": {"label": {"type": "string"}, "reason": {"type": "string"}}}}}}


def output_paths(out_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        runs=out_dir / "runs",                              # prompt, raw answer, logs per call
        suggestions=out_dir / "suggestions",                # one checked answer per target
        suggestions_history=out_dir / "suggestions_history",
        prompts_dry_run=out_dir / "prompts_dry_run",
        tables=out_dir / "tables",                          # suggestions.csv
        tables_history=out_dir / "tables_history",
        logs=out_dir / "logs",
    )


# ---------------------------------------------------------------- prompt

def pool_line(label: str, row: pd.Series, facet_row: pd.Series) -> str:
    """One pool company on one line: label, name, website and its business facets."""
    parts = []
    for f in fc.FACETS:
        if f.name in POOL_FACETS:
            status = facet_row.get(f"{f.name}_status", "unknown")
            value = {"unknown": "unknown", "not_applicable": "none"}.get(status) or facet_row.get(f.name, "")
            parts.append(f"{f.label.lower()}: {value or 'unknown'}")
    sector_summary = facet_row.get("sector_summary", "")
    if isinstance(sector_summary, str) and sector_summary:
        parts.append(f"sector-specific: {sector_summary}")
    return f"{label}: {row['target_company_name']} ({row['target_ciq_website']}) | " + " | ".join(parts)


def build_system(pool: list[str], info: pd.DataFrame, facet_rows: pd.DataFrame) -> tuple[str, dict[str, str]]:
    """The instructions and the pool list (the same for every target), and each pool company's label."""
    order = sorted(pool, key=lambda c: (info.loc[c, "target_company_name"].lower(), c))
    labels = {f"P{i:03d}": c for i, c in enumerate(order, 1)}
    lines = [pool_line(label, info.loc[c], facet_rows.loc[c]) for label, c in labels.items()]
    return INSTRUCTIONS + "\n\nCompanies:\n" + "\n".join(lines) + "\n\n", labels


def build_prompt(system: str, target: str, info: pd.DataFrame, facet_rows: pd.DataFrame,
                 prompt_version: str = PROMPT_VERSION) -> str:
    """The shared part plus the target. `prompt_version` sets which facets
    describe the target (PROMPT_EXCLUDES); replays pass SAVED_PROMPT_VERSION."""
    r = info.loc[target]
    description = describe(facet_rows.loc[target], PROMPT_EXCLUDES[prompt_version])
    return system + f"Target: {r['target_company_name']} ({r['target_ciq_website']})\n{description}"


# ---------------------------------------------------------------- answer

def check_answer(raw: dict, labels: dict[str, str], target: str, max_comps: int = MAX_COMPS
                 ) -> tuple[list[dict], list[str]]:
    """The chosen comps in the model's order (rank 1 = best), and the issues:
    the target itself, an unknown label or a repeat is dropped; past
    max_comps the rest are dropped."""
    rows, issues, seen = [], [], set()
    for item in raw.get("comps", []):
        label = (item.get("label") or "").strip()
        comp = labels.get(label)
        if comp is None:
            issues.append(f"unknown_label:{label}")
        elif comp == target:
            issues.append("chose_target")
        elif comp in seen:
            issues.append(f"duplicate_label:{label}")
        elif len(rows) >= max_comps:
            issues.append(f"over_{max_comps}:{label}")
        else:
            seen.add(comp)
            rows.append({"rank": len(rows) + 1, "label": label, "comp": comp,
                         "reason": (item.get("reason") or "").strip()})
    return rows, issues


# ---------------------------------------------------------------- run

def load_inputs(candidates_run: Path) -> tuple[list[str], pd.DataFrame, pd.DataFrame, str]:
    """The training firms (targets and pool), company names and websites, the
    current facets (first business), and the split run they come from."""
    run = json.loads((candidates_run / "run.json").read_text(encoding="utf-8"))
    # the split sits beside the candidates run's own folder (comps/ or another run root)
    split = pd.read_csv(candidates_run.parent.parent / "split" / run["split_run"] / "split.csv", dtype=str)
    training = split.loc[split["sample"] == "training", "IQ_COMPANY_ID"].tolist()
    info = pd.read_csv(OUTPUTS_LOCAL / "v1" / "universe" / run["universe_run"] / "universe.csv",
                       dtype=str).set_index("IQ_COMPANY_ID")
    facets = pd.read_csv(facet_paths(FACETS_OUT).tables / "facets.csv", dtype=str).fillna("")
    facets = facets[(facets["prompt_version"] == fc.PROMPT_VERSION) & (facets["llm_status"] == "ok")
                    & (facets["business_id"] == "B1")].set_index("IQ_COMPANY_ID")
    return training, info, facets, run["split_run"]


def suggest_one(target: str, system: str, labels: dict[str, str], info, facets, out: SimpleNamespace,
                args) -> dict:
    prompt = build_prompt(system, target, info, facets, args.prompt_version)
    fp = fingerprint(prompt, args.model)
    path = out.suggestions / f"{target}.json"
    if path.exists() and not args.refresh:
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") == fp and old.get("llm_status") == "ok":
            return {"target": target, "status": "current"}
    run_dir = out.runs / target / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt_target.txt").write_text(prompt[len(system):], encoding="utf-8")   # the pool is in system.txt
    if args.backend == "claude-cli":
        from cli_models import call_cli
        result = call_cli(prompt, run_dir, ANSWER_SCHEMA, "claude-cli", model=args.model, effort=args.effort,
                          instructions_len=len(system))
    else:
        result = call_claude(prompt, run_dir, ANSWER_SCHEMA, args.model, args.effort, instructions_len=len(system))
    run_info = {"backend": args.backend, "model": args.model, "effort": args.effort or "", "prompt_version": args.prompt_version,
                "fingerprint": fp, "finished_at": now_iso(),
                **{k: v for k, v in result.items() if k != "text"}}
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=1), encoding="utf-8")
    answer = {"target": target, "split_run": args.split_run, "prompt_version": args.prompt_version,
              "model": args.model, "fingerprint": fp, "run_dir": str(run_dir.relative_to(out.runs.parent)),
              "llm_status": result["llm_status"], "suggested_at": now_iso(), "comps": [], "issues": []}
    if result["llm_status"] == "ok":
        try:
            answer["comps"], answer["issues"] = check_answer(json.loads(result["text"]), labels, target)
        except json.JSONDecodeError:
            answer["llm_status"] = "invalid_json"
    else:
        answer["error"] = result.get("error", "")
    move_to_history(path, out.suggestions_history)
    path.write_text(json.dumps(answer, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"target": target, "status": answer["llm_status"], "issues": answer["issues"],
            "stop_run": result.get("stop_run", False), "usage": result.get("usage", {})}


def write_tables(out: SimpleNamespace, info: pd.DataFrame, prompt_version: str = PROMPT_VERSION) -> Path:
    """suggestions.csv: one row per suggested target-comp pair made with
    `prompt_version` (rank 1 = the model's best), and one row with no comp
    for a target it gave none. Refuses to write an empty table over saved
    picks made with another version (pass that version instead)."""
    rows, other_versions = [], set()
    for path in sorted(out.suggestions.glob("*.json")):
        s = json.loads(path.read_text(encoding="utf-8"))
        if s.get("llm_status") == "ok" and s.get("prompt_version") != prompt_version:
            other_versions.add(s.get("prompt_version"))
        if s.get("llm_status") != "ok" or s.get("prompt_version") != prompt_version:
            continue
        base = {"target": s["target"], "model": s["model"], "prompt_version": s["prompt_version"],
                "split_run": s["split_run"], "suggested_at": s["suggested_at"], "issues": "; ".join(s["issues"])}
        rows += [{**base, **c} for c in s["comps"]] or [{**base, "rank": None, "label": "", "comp": "", "reason": ""}]
    if not rows and other_versions:
        raise SystemExit(f"No picks made with prompt {prompt_version} in {out.suggestions}; the ones there use "
                         f"{sorted(other_versions)}. Pass --prompt-version with that version to rebuild their table.")
    table = pd.DataFrame(rows, columns=["target", "rank", "comp", "label", "reason", "model", "prompt_version",
                                        "split_run", "suggested_at", "issues"])
    for col, src in [("target_ticker", "target"), ("comp_ticker", "comp")]:
        table.insert(table.columns.get_loc(src) + 1, col, table[src].map(info["target_ciq_ticker"]))
    table.insert(table.columns.get_loc("comp_ticker") + 1, "comp_company", table["comp"].map(info["target_company_name"]))
    out.tables.mkdir(parents=True, exist_ok=True)
    dest = out.tables / "suggestions.csv"
    move_to_history(dest, out.tables_history)
    table.sort_values(["target", "rank"]).to_csv(dest, index=False)
    return dest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", help="output folder (default: outputs-local/v1/direct_llm/<split run>_<prompt version>/; "
                                 "the saved picks are in outputs-local/v1/suggest/)")
    p.add_argument("--candidates", help="step 4 run folder whose split is used (default: the latest)")
    p.add_argument("--prompt-version", choices=sorted(PROMPT_EXCLUDES), default=PROMPT_VERSION,
                   help=f"default {PROMPT_VERSION} (no company size); {SAVED_PROMPT_VERSION} rebuilds the saved prompts")
    p.add_argument("--tickers", nargs="*", help="only these targets")
    p.add_argument("--limit", type=int, help="stop after N targets")
    p.add_argument("--refresh", action="store_true", help="ask again for current targets")
    p.add_argument("--backend", choices=["claude", "claude-cli"], default="claude",
                   help="claude: Anthropic API (default); claude-cli: Claude Code CLI under your own login")
    p.add_argument("--model", help="default: claude-haiku-5-5 for claude, claude-sonnet-5-5 for claude-cli")
    p.add_argument("--effort", choices=["low", "medium", "high"], help="default: the model's own")
    p.add_argument("--workers", type=int, default=2, help="targets in parallel")
    p.add_argument("--dry-run", action="store_true", help="write the prompts only")
    p.add_argument("--tables-only", action="store_true", help="only rebuild suggestions.csv")
    args = p.parse_args()
    args.model = args.model or DEFAULT_MODEL[args.backend]
    candidates_run = Path(args.candidates) if args.candidates else latest_candidates()
    training, info, facets, args.split_run = load_inputs(candidates_run)
    out = output_paths(Path(args.out) if args.out
                       else DEFAULT_OUT_ROOT / f"{args.split_run}_{args.prompt_version}")
    for d in (out.runs, out.suggestions, out.logs):
        d.mkdir(parents=True, exist_ok=True)

    if missing := sorted(set(training) - set(facets.index)):
        raise SystemExit(f"{len(missing)} training firms have no current facets, e.g. {missing[:3]}")
    system, labels = build_system(training, info, facets)
    (out.runs / f"system_{args.prompt_version}_{args.split_run}.txt").write_text(system, encoding="utf-8")
    targets = training
    if args.tickers:
        targets = [t for t in training if info.loc[t, "target_ciq_ticker"] in set(args.tickers)]
    if args.limit:
        targets = targets[:args.limit]

    if args.dry_run:
        out.prompts_dry_run.mkdir(parents=True, exist_ok=True)
        for t in targets:
            (out.prompts_dry_run / f"{t}.txt").write_text(build_prompt(system, t, info, facets, args.prompt_version),
                                                           encoding="utf-8")
        print(f"wrote {len(targets)} prompts to {out.prompts_dry_run} (pool of {len(labels)}, "
              f"{len(system.split())} words in the shared part)")
        return

    if not args.tables_only:
        log = out.logs / f"suggest_{stamp()}.log"
        print(f"split {args.split_run}: {len(targets)} targets, pool of {len(labels)}; model {args.model}; "
              f"prompt {args.prompt_version}; log {log.name}")
        totals, started = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}, time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as pool, log.open("w", encoding="utf-8") as lf:
            futures = {pool.submit(suggest_one, t, system, labels, info, facets, out, args): t for t in targets}
            for n, fut in enumerate(as_completed(futures), 1):
                r = fut.result()
                for k in totals:
                    totals[k] += r.get("usage", {}).get(k, 0) or 0
                line = (f"[{n}/{len(targets)}] {info.loc[r['target'], 'target_ciq_ticker']:<8} {r['status']:<12}"
                        + (f" issues: {'; '.join(r['issues'])}" if r.get("issues") else ""))
                print(line)
                lf.write(line + "\n")
                if r.get("stop_run"):
                    print("stopping: the API refused the key or the credit ran out; finished targets are kept")
                    for f in futures:
                        f.cancel()
                    break
        print(f"tokens: {totals}; {time.time() - started:.0f} s")
    print("wrote", write_tables(out, info, args.prompt_version))


if __name__ == "__main__":
    main()
