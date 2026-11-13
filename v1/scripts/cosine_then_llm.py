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
(outputs-local/v1/candidates/<run>/candidates.csv), for the training
targets only (that file holds no others).

With --b3 the candidates are instead the v1 baseline's comp lists (B3 =
method 1: TF-IDF-blended facet scores, information weights, mutual top 10
topped up to 3), from the latest run of method1_candidates.py in
outputs-local/v1/candidates_method1/ (or --candidates <that run>). The LLM
then screens each target's baseline list, which is at most 10 comps.

Prompt versions (details and the checks: v1/PROMPT_VERSIONS.md):
  2026-10-25a  SAVED_PROMPT_VERSION. All twelve facets, company size (F9)
               included. Every saved verdict (outputs-local/v1/judge/, 373
               training targets, Haiku) and every saved holdout answer was
               made with it; the holdout replay scripts and the readers of
               saved verdicts pin it, so they keep matching what is saved.
  2026-11-04a  PROMPT_VERSION, the default for new runs. Company size is
               left out of the facet lines (team decision 2026-11-03: too
               generic, hurt the comps). Nothing else in the prompt changed.
Choose with --prompt-version. A new run writes, by default, to
outputs-local/v1/cosine_then_llm/<candidates run>_<prompt version>/, so it
never replaces the saved verdicts in outputs-local/v1/judge/.

Every call keeps its prompt, raw answer and logs under
<out>/runs/<IQ_ID>/<time>/. A target is judged once per prompt and model;
a rerun skips finished targets, and a replaced judgment or table moves to
a history folder. The run stops if the API credit runs out or the key is
refused; run it again after fixing that.

  python v1/scripts/cosine_then_llm.py --tickers PCTY BV     # a few targets
  python v1/scripts/cosine_then_llm.py --workers 4           # every training target
  python v1/scripts/cosine_then_llm.py --dry-run             # write the prompts only
  python v1/scripts/cosine_then_llm.py --tables-only --out outputs-local/v1/judge --prompt-version 2026-10-25a
                                                             # rebuild the saved judgments.csv
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
from fill_facets import DEFAULT_MODEL, call_claude, now_iso, output_paths as facet_paths, stamp  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

PROMPT_VERSION = "2026-11-04a"            # new runs: company size (F9) left out of the facet lines
SAVED_PROMPT_VERSION = "2026-10-25a"      # every saved verdict and holdout answer: all twelve facets
PROMPT_EXCLUDES = {                       # facets left out of the prompt, per version
    "2026-10-25a": (),
    "2026-11-04a": ("company_size",),
}
SAVED_OUT = OUTPUTS_LOCAL / "v1" / "judge"                # the saved 2026-10-25a verdicts (read-only in practice)
DEFAULT_OUT_ROOT = OUTPUTS_LOCAL / "v1" / "cosine_then_llm"   # new runs: <root>/<candidates run>_<prompt version>/
DEFAULT_OUT = SAVED_OUT                   # kept for older imports; new runs use DEFAULT_OUT_ROOT
CANDIDATES_ROOT = OUTPUTS_LOCAL / "v1" / "candidates"
METHOD1_ROOT = OUTPUTS_LOCAL / "v1" / "candidates_method1"   # the v1 baseline's lists (method1_candidates.py)
FACETS_OUT = OUTPUTS_LOCAL / "v1" / "facets"
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

def describe(row: pd.Series, exclude: tuple[str, ...] = PROMPT_EXCLUDES[PROMPT_VERSION]) -> str:
    """A company's facets as lines: "unknown" or "none" (not applicable) where
    so. Facets in `exclude` are left out; the default is the current prompt
    version's list (company size). Pass PROMPT_EXCLUDES[SAVED_PROMPT_VERSION]
    to rebuild the saved prompts exactly."""
    lines = []
    for f in fc.FACETS:
        if f.name in exclude:
            continue
        status = row.get(f"{f.name}_status", "unknown")
        value = {"unknown": "unknown", "not_applicable": "none"}.get(status) or row.get(f.name, "") or "unknown"
        lines.append(f"- {f.label}: {value}")
    sector_summary = row.get("sector_summary", "")
    if isinstance(sector_summary, str) and sector_summary:
        lines.append(f"- Sector-specific business characteristics: {sector_summary}")
    sub_sector = row.get("sub_sector", "")
    if isinstance(sub_sector, str) and sub_sector:
        lines.append(f"- Sub-sector: {sub_sector}")
    return "\n".join(lines)


def build_prompt(target: str, comps: list[str], info: pd.DataFrame, facet_rows: pd.DataFrame,
                 prompt_version: str = PROMPT_VERSION) -> tuple[str, dict[str, str]]:
    """The prompt for one target, and the label of each candidate (C1, ...).
    Candidates are listed alphabetically by name, so their order carries no
    similarity rank. `prompt_version` sets which facets are listed (see
    PROMPT_EXCLUDES); replays of saved answers pass SAVED_PROMPT_VERSION."""
    order = sorted(comps, key=lambda c: (info.loc[c, "target_company_name"].lower(), c))
    labels = {f"C{i}": c for i, c in enumerate(order, 1)}
    exclude = PROMPT_EXCLUDES[prompt_version]

    def block(iq_id: str) -> str:
        r = info.loc[iq_id]
        return f"{r['target_company_name']} ({r['target_ciq_website']})\n{describe(facet_rows.loc[iq_id], exclude)}"

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


def latest_method1() -> Path:
    runs = sorted(p for p in METHOD1_ROOT.iterdir() if (p / "candidates.csv").exists()) if METHOD1_ROOT.exists() else []
    if not runs:
        raise SystemExit("No v1 baseline lists yet: run  uv run python v1/scripts/method1_candidates.py")
    return runs[-1]


def pick_pairs(pairs: pd.DataFrame, z: float, rule: str = "z") -> pd.DataFrame:
    """The candidate rows to judge: z >= z (rule "z"), or the rows marked
    `selected` (rule "selected", a method1_candidates.py run)."""
    if rule == "selected":
        if "selected" not in pairs:
            raise SystemExit("These candidates have no `selected` column: --b3 needs a method1_candidates.py run")
        return pairs[pairs["selected"].astype(str).str.lower() == "true"]
    return pairs[pairs["z"] >= z]


def load_inputs(candidates_run: Path, z: float, rule: str = "z") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """The pairs to judge, company names and websites, and the current facets
    (first business). rule "z": the pairs at z >= z (v0's shortlist);
    rule "selected": the rows marked `selected` (a method1_candidates.py run:
    the v1 baseline's comp lists)."""
    pairs = pick_pairs(pd.read_csv(candidates_run / "candidates.csv", dtype={"target": str, "comp": str}), z, rule)
    run = json.loads((candidates_run / "run.json").read_text(encoding="utf-8"))
    universe_run = run["universe_run"]
    info = pd.read_csv(OUTPUTS_LOCAL / "v1" / "universe" / universe_run / "universe.csv",
                       dtype=str).set_index("IQ_COMPANY_ID")
    facet_override = run.get("facet_override")
    if facet_override:
        facet_path = Path(facet_override)
    else:
        facet_source = run.get("facet_source", "haiku")
        if facet_source not in {"haiku", "sonnet"}:
            raise ValueError(f"unsupported facet source: {facet_source}")
        source_dir = FACETS_OUT if facet_source == "haiku" else OUTPUTS_LOCAL / "v1" / "facets_sonnet"
        facet_path = facet_paths(source_dir).tables / "facets.csv"
    facets = pd.read_csv(facet_path, dtype=str).fillna("")
    facets = facets[(facets["prompt_version"] == fc.PROMPT_VERSION) & (facets["llm_status"] == "ok")
                    & (facets["business_id"] == "B1")].set_index("IQ_COMPANY_ID")
    if "Fiona sub-sector" in run.get("method", ""):
        sector = pd.read_csv(OUTPUTS_LOCAL / "v1" / "sector_facets_sonnet" / "tables" /
                             "sector_facets.csv", dtype=str).fillna("").set_index("IQ_COMPANY_ID")
        facets["sub_sector"] = sector["sub_sector"].where(sector["sub_sector_status"] == "stated").reindex(facets.index).fillna("")
    return pairs, info, facets


def move_to_history(path: Path, history: Path) -> None:
    if path.exists():
        history.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), history / f"{path.stem}_{stamp()}{path.suffix}")


def judge_one(target: str, comps: list[str], info, facets, out: SimpleNamespace, args) -> dict:
    prompt, labels = build_prompt(target, comps, info, facets, args.prompt_version)
    fp = fingerprint(prompt, json.dumps([args.backend, args.model, args.effort]))
    path = out.judgments / f"{target}.json"
    if path.exists() and not args.refresh:
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") == fp and old.get("llm_status") == "ok":
            return {"target": target, "status": "current"}
    run_dir = out.runs / target / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    if args.backend in ("claude-cli", "codex"):
        from cli_models import call_cli
        result = call_cli(prompt, run_dir, answer_schema(list(labels)), args.backend, model=args.model,
                          effort=args.effort, instructions_len=len(INSTRUCTIONS))
    else:
        result = call_claude(prompt, run_dir, answer_schema(list(labels)), args.model, args.effort,
                             instructions_len=len(INSTRUCTIONS))
    run_info = {"backend": args.backend, "model": args.model, "effort": args.effort or "", "prompt_version": args.prompt_version,
                "fingerprint": fp, "finished_at": now_iso(),
                **{k: v for k, v in result.items() if k != "text"}}
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=1), encoding="utf-8")
    judgment = {"target": target, "candidates_run": args.candidates.name,
                "z_min": None if args.b3 else args.z, "list_rule": "b3_selected" if args.b3 else "z",
                "prompt_version": args.prompt_version, "model": args.model, "fingerprint": fp,
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


def write_tables(out: SimpleNamespace, pairs: pd.DataFrame, info: pd.DataFrame,
                 prompt_version: str = PROMPT_VERSION) -> Path:
    """judgments.csv: one row per judged target-comp pair made with
    `prompt_version`, with its step 4 rank, similarity and z, the score (1
    good, 0 bad) and the reason. Refuses to write an empty table over saved
    judgments made with another version (pass that version instead)."""
    rows, other_versions = [], set()
    for path in sorted(out.judgments.glob("*.json")):
        j = json.loads(path.read_text(encoding="utf-8"))
        if j.get("llm_status") == "ok" and j.get("prompt_version") != prompt_version:
            other_versions.add(j.get("prompt_version"))
        if j.get("llm_status") != "ok" or j.get("prompt_version") != prompt_version:
            continue
        for c in j["comps"]:
            rows.append({"target": j["target"], "comp": c["comp"], "label": c["label"], "score": c["score"],
                         "reason": c["reason"], "model": j["model"], "prompt_version": j["prompt_version"],
                         "candidates_run": j["candidates_run"], "judged_at": j["judged_at"],
                         "issues": "; ".join(j["issues"])})
    if not rows and other_versions:
        raise SystemExit(f"No judgments made with prompt {prompt_version} in {out.judgments}; the ones there use "
                         f"{sorted(other_versions)}. Pass --prompt-version with that version to rebuild their table.")
    table = pd.DataFrame(rows, columns=["target", "comp", "label", "score", "reason", "model", "prompt_version",
                                        "candidates_run", "judged_at", "issues"])
    table = table.merge(pairs[["target", "comp", "rank", "similarity", "z"]], on=["target", "comp"], how="left")
    for col, src in [("target_ticker", "target"), ("comp_ticker", "comp")]:
        table.insert(table.columns.get_loc(src) + 1, col, table[src].map(info["target_ciq_ticker"]))
    table.insert(table.columns.get_loc("comp_ticker") + 1, "comp_company", table["comp"].map(info["target_company_name"]))
    out.tables.mkdir(parents=True, exist_ok=True)
    dest = out.tables / "judgments.csv"
    move_to_history(dest, out.tables_history)
    table.sort_values(["target", "rank"]).to_csv(dest, index=False)
    return dest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", help="output folder (default: outputs-local/v1/cosine_then_llm/<candidates run>_<prompt "
                                 "version>/; the saved verdicts are in outputs-local/v1/judge/)")
    p.add_argument("--candidates", help="step 4 run folder (default: the latest)")
    p.add_argument("--prompt-version", choices=sorted(PROMPT_EXCLUDES), default=PROMPT_VERSION,
                   help=f"default {PROMPT_VERSION} (no company size); {SAVED_PROMPT_VERSION} rebuilds the saved prompts")
    p.add_argument("--z", type=float, default=DEFAULT_Z, help="candidates at z >= this (default 2)")
    p.add_argument("--b3", action="store_true",
                   help="screen the v1 baseline's lists (B3, mutual top 10) from the latest method1_candidates.py run "
                        "instead of v0's z >= 2 shortlist")
    p.add_argument("--tickers", nargs="*", help="only these targets")
    p.add_argument("--limit", type=int, help="stop after N targets")
    p.add_argument("--refresh", action="store_true", help="judge current targets again")
    p.add_argument("--backend", choices=["claude", "claude-cli", "codex"], default="claude",
                   help="claude: Anthropic API; claude-cli: Claude Code CLI; codex: Codex CLI")
    p.add_argument("--model", help="default: claude-haiku-5-5 for claude, claude-sonnet-5-5 for claude-cli, gpt-6.1-sol for codex")
    p.add_argument("--effort", choices=["low", "medium", "high"], help="default: the model's own")
    p.add_argument("--workers", type=int, default=2, help="targets in parallel")
    p.add_argument("--dry-run", action="store_true", help="write the prompts only")
    p.add_argument("--tables-only", action="store_true", help="only rebuild judgments.csv")
    args = p.parse_args()
    args.model = args.model or ("gpt-6.1-sol" if args.backend == "codex" else DEFAULT_MODEL[args.backend])
    args.candidates = (Path(args.candidates) if args.candidates
                       else latest_method1() if args.b3 else latest_candidates())
    out = output_paths(Path(args.out) if args.out else DEFAULT_OUT_ROOT /
                       f"{'b3_' if args.b3 else ''}{args.candidates.name}_{args.prompt_version}_{args.backend}_{args.model}")
    for d in (out.runs, out.judgments, out.logs):
        d.mkdir(parents=True, exist_ok=True)

    pairs, info, facets = load_inputs(args.candidates, args.z, "selected" if args.b3 else "z")
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
            (out.prompts_dry_run / f"{target}.txt").write_text(
                build_prompt(target, comps, info, facets, args.prompt_version)[0], encoding="utf-8")
        print(f"wrote {len(groups)} prompts to {out.prompts_dry_run}")
        return

    if not args.tables_only:
        log = out.logs / f"judge_{stamp()}.log"
        rule = "v1 baseline lists (B3)" if args.b3 else f"z >= {args.z:g}"
        print(f"candidates {args.candidates.name}, {rule}: {len(groups)} targets, "
              f"{groups.str.len().sum()} pairs; model {args.model}; prompt {args.prompt_version}; log {log.name}")
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
                    print("stopping: the API refused the key or the credit ran out; finished targets are kept")
                    for f in futures:
                        f.cancel()
                    break
        print(f"tokens: {totals}; {time.time() - started:.0f} s")
    dest = write_tables(out, pairs, info, args.prompt_version)
    print("wrote", dest)


if __name__ == "__main__":
    main()
