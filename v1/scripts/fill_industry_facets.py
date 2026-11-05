"""
Fill the industry-specific facets (industry_facets.py: Barbara's SIC2
dictionary) for every company in the universe, one call per company, and
write outputs-local/v1/industry_facets/tables/industry_facets_long.csv.

Each company gets the facets of its own two-digit SIC code, filled from its
saved website pages (the same evidence the sector facets use), cited line by
line; the model's own knowledge fills only gaps and is flagged from_memory.
No financials.

Backends (same as fill_facets.py): claude-cli (default here: Claude Code CLI
under the student's own subscription, Claude Sonnet 5.5), claude (Anthropic
API, needs ANTHROPIC_API_KEY) and codex. Every call keeps its prompt, raw
answer and run.json under <out>/runs/<IQ_ID>/<time>/; a company is filled
once per prompt and model, and replaced profiles move to profiles_history/.

  python v1/scripts/fill_industry_facets.py --tickers PCTY WEN       # a few
  python v1/scripts/fill_industry_facets.py --workers 4              # everyone
  python v1/scripts/fill_industry_facets.py --sic2 73 58             # two industries
  python v1/scripts/fill_industry_facets.py --dry-run                # prompts only
  python v1/scripts/fill_industry_facets.py --tables-only
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facets as fc  # noqa: E402,F401  (puts website_scrape/ and src/ on the path)
import industry_facets as inf  # noqa: E402
from fill_facets import DEFAULT_MODEL, call_claude, claude_api_key, now_iso, stamp  # noqa: E402
from fill_sector_facets import gather_evidence  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402
from universe import build_universe  # noqa: E402

DEFAULT_OUT = OUTPUTS_LOCAL / "v1" / "industry_facets"


def output_paths(out_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(runs=out_dir / "runs", profiles=out_dir / "profiles",
                           profiles_history=out_dir / "profiles_history",
                           prompts_dry_run=out_dir / "prompts_dry_run", tables=out_dir / "tables",
                           tables_history=out_dir / "tables_history", logs=out_dir / "logs")


def companies_to_fill() -> pd.DataFrame:
    companies, _ = build_universe()
    companies = companies[companies["in_universe"]].set_index("IQ_COMPANY_ID")
    out = companies[["target_company_name", "target_ciq_ticker", "target_ciq_website", "target_sic4_code"]].copy()
    out["sic2"] = companies["target_sic2_code"].astype(str).str.zfill(2)
    return out


def fill_one(iq_id: str, row: pd.Series, industry: dict, out: SimpleNamespace, args) -> dict:
    company = {"IQ_COMPANY_ID": iq_id, "company_name": row["target_company_name"], "website": row["target_ciq_website"]}
    evidence, lines, used = gather_evidence(iq_id, company["company_name"], company["website"], False)
    prompt = inf.build_prompt(company, industry, evidence)
    fp = inf.fingerprint(prompt, args.model)
    path = out.profiles / f"{iq_id}.json"
    if path.exists() and not args.refresh:
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") == fp and old.get("llm_status") == "ok":
            return {"IQ_COMPANY_ID": iq_id, "status": "current"}
    run_dir = out.runs / iq_id / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    schema = inf.answer_schema(industry)
    if args.backend == "claude":
        result = call_claude(prompt, run_dir, schema, args.model, args.effort, instructions_len=len(inf.INSTRUCTIONS))
    else:
        from cli_models import call_cli
        result = call_cli(prompt, run_dir, schema, args.backend, model=args.model, effort=args.effort,
                          instructions_len=len(inf.INSTRUCTIONS) if args.backend == "claude-cli" else 0)
    (run_dir / "run.json").write_text(json.dumps(
        {"backend": args.backend, "model": args.model, "prompt_version": inf.PROMPT_VERSION,
         "fingerprint": fp, "finished_at": now_iso(),
         **{k: v for k, v in result.items() if k != "text"}}, indent=1), encoding="utf-8")
    profile = {"IQ_COMPANY_ID": iq_id, "company_name": company["company_name"], "website": company["website"],
               "sic4": row["target_sic4_code"], "sic2": row["sic2"], "industry": industry["title"],
               "model": args.model, "prompt_version": inf.PROMPT_VERSION, "fingerprint": fp,
               "llm_status": result["llm_status"], "run_dir": str(run_dir.relative_to(out.runs.parent)),
               "created_at": now_iso(), "facets": {}, "issues": [], "notes": "", "evidence": used}
    if result["llm_status"] == "ok":
        try:
            raw = json.loads(result["text"])
            profile["facets"], profile["issues"] = inf.check_answer(raw, industry, lines)
            profile["knows_company"], profile["notes"] = bool(raw.get("knows_company")), raw.get("notes", "")
        except json.JSONDecodeError:
            profile["llm_status"] = "invalid_json"
    else:
        profile["error"] = result.get("error", "")
    if result.get("stop_run"):
        return {"IQ_COMPANY_ID": iq_id, "status": result["llm_status"], "error": result.get("error", ""),
                "stop_run": True}
    if path.exists():
        out.profiles_history.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), out.profiles_history / f"{iq_id}_{stamp()}.json")
    path.write_text(json.dumps(profile, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"IQ_COMPANY_ID": iq_id, "status": profile["llm_status"], "issues": profile["issues"],
            "error": profile.get("error", ""), "usage": result.get("usage", {})}


def write_tables(out: SimpleNamespace) -> Path:
    """industry_facets_long.csv: one row per company and facet."""
    rows = []
    for path in sorted(out.profiles.glob("*.json")):
        p = json.loads(path.read_text(encoding="utf-8"))
        if p.get("prompt_version") != inf.PROMPT_VERSION or p.get("llm_status") != "ok":
            continue
        for name, f in p.get("facets", {}).items():
            rows.append({"IQ_COMPANY_ID": p["IQ_COMPANY_ID"], "company": p["company_name"], "sic2": p["sic2"],
                         "industry": p["industry"], "facet": name, "facet_label": f["label"], "status": f["status"],
                         "value": f["value"], "source": f["source"], "cites": " ".join(f["cites"]),
                         "model": p["model"], "prompt_version": p["prompt_version"]})
    table = pd.DataFrame(rows, columns=["IQ_COMPANY_ID", "company", "sic2", "industry", "facet", "facet_label",
                                        "status", "value", "source", "cites", "model", "prompt_version"])
    out.tables.mkdir(parents=True, exist_ok=True)
    dest = out.tables / "industry_facets_long.csv"
    if dest.exists():
        hist = out.tables_history / stamp()
        hist.mkdir(parents=True, exist_ok=True)
        dest.replace(hist / dest.name)
    table.to_csv(dest, index=False)
    n = table["IQ_COMPANY_ID"].nunique() if len(table) else 0
    stated = (table["status"] == "stated").sum() if len(table) else 0
    print(f"industry facets: {n} companies, {len(table)} facet rows, {stated} stated -> {dest}", flush=True)
    return dest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--tickers", nargs="*")
    p.add_argument("--sic2", nargs="*", help="only these two-digit SIC codes")
    p.add_argument("--limit", type=int)
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--backend", choices=["claude-cli", "claude", "codex"], default="claude-cli")
    p.add_argument("--model", default=None)
    p.add_argument("--effort", choices=["low", "medium", "high"])
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--tables-only", action="store_true")
    args = p.parse_args()
    args.model = args.model or ("gpt-6.1-sol" if args.backend == "codex" else DEFAULT_MODEL[args.backend])
    out = output_paths(Path(args.out))
    for d in (out.runs, out.profiles, out.logs):
        d.mkdir(parents=True, exist_ok=True)
    if args.tables_only:
        write_tables(out)
        return

    dictionary = inf.load_dictionary()
    todo = companies_to_fill()
    missing = sorted(set(todo["sic2"]) - set(dictionary))
    if missing:
        raise SystemExit(f"No facets in the dictionary for SIC2 {missing}")
    if args.sic2:
        todo = todo[todo["sic2"].isin({s.zfill(2) for s in args.sic2})]
    if args.tickers:
        todo = todo[todo["target_ciq_ticker"].str.upper().isin({t.upper() for t in args.tickers})]
    if args.limit:
        todo = todo.head(args.limit)
    print(f"{len(todo)} companies in {todo['sic2'].nunique()} SIC2 groups; backend {args.backend}, model {args.model}",
          flush=True)

    if args.dry_run:
        out.prompts_dry_run.mkdir(parents=True, exist_ok=True)
        for iq_id, row in todo.iterrows():
            company = {"company_name": row["target_company_name"], "website": row["target_ciq_website"]}
            evidence = gather_evidence(iq_id, company["company_name"], company["website"], False)[0]
            (out.prompts_dry_run / f"{iq_id}.txt").write_text(
                inf.build_prompt(company, dictionary[row["sic2"]], evidence), encoding="utf-8")
        print(f"wrote {len(todo)} prompts to {out.prompts_dry_run}")
        return

    if args.backend == "claude":
        claude_api_key()
    log = out.logs / f"fill_{stamp()}.log"
    totals, started = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}, time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool, log.open("w", encoding="utf-8") as lf:
        futures = {pool.submit(fill_one, i, r, dictionary[r["sic2"]], out, args): i for i, r in todo.iterrows()}
        for n, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            for k in totals:
                totals[k] += r.get("usage", {}).get(k, 0) or 0
            line = f"[{n}/{len(todo)}] {todo.loc[r['IQ_COMPANY_ID'], 'target_ciq_ticker']:<8} {r['status']}" + \
                   (f" {r['error'][:160]}" if r.get("error") else "")
            print(line, flush=True)
            lf.write(line + "\n")
            if r.get("stop_run"):
                print("stopping: the CLI or API refused the call; finished companies are kept", flush=True)
                for f in futures:
                    f.cancel()
                break
    print(f"tokens: {totals}; {time.time() - started:.0f} s", flush=True)
    write_tables(out)


if __name__ == "__main__":
    main()
