"""
Fill the sector-specific facets (sector_facets.py) with Claude Haiku, one
call per company, and write outputs-local/comps/sector_facets/tables/
sector_facets.csv.

Each company gets its sector from its SIC code (sectors.py), then the
sub-sector facet and its sector's facets from evidence (Aziz: no LLM memory
alone): its saved website pages by default, and with --evidence also a
deeper crawl of its site and web search (verification/evidence.py). Each
facet cites its evidence lines; memory fills only gaps and is flagged
from_memory. No financials. Training companies only by
default, so nothing about the holdout is looked at while the facets are
being designed; --include-holdout fills the holdout once the facet list is
frozen.

Like fill_facets.py: every call keeps its prompt, raw answer and run.json
under <out>/runs/<IQ_ID>/<time>/, a company is filled once per prompt and
model, and replaced profiles move to profiles_history/.

  python v0/fill_sector_facets.py --tickers AAON PCTY ROAD   # a few
  python v0/fill_sector_facets.py --workers 4                # training firms
  python v0/fill_sector_facets.py --dry-run                  # prompts only
  python v0/fill_sector_facets.py --tables-only
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
import sector_facets as sf  # noqa: E402
import sectors as sc  # noqa: E402
from fill_facets import DEFAULT_MODEL, call_claude, claude_api_key, company_record, now_iso, stamp  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402
from universe import build_universe  # noqa: E402

DEFAULT_OUT = OUTPUTS_LOCAL / "comps" / "sector_facets"
SPLIT_ROOT = OUTPUTS_LOCAL / "comps" / "split"


def output_paths(out_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(runs=out_dir / "runs", profiles=out_dir / "profiles",
                           profiles_history=out_dir / "profiles_history",
                           prompts_dry_run=out_dir / "prompts_dry_run", tables=out_dir / "tables",
                           tables_history=out_dir / "tables_history", logs=out_dir / "logs")


def latest_split() -> pd.DataFrame | None:
    runs = sorted(p for p in SPLIT_ROOT.iterdir() if (p / "split.csv").exists()) if SPLIT_ROOT.exists() else []
    return pd.read_csv(runs[-1] / "split.csv", dtype=str) if runs else None


def companies_to_fill(include_holdout: bool) -> pd.DataFrame:
    companies, _ = build_universe()
    companies = companies[companies["in_universe"]].set_index("IQ_COMPANY_ID")
    sectors = sc.sector_table(companies)
    out = companies[["target_company_name", "target_ciq_ticker", "target_ciq_website"]].join(sectors)
    split = latest_split()
    if split is None:
        if not include_holdout:
            raise SystemExit("No split yet (outputs-local/comps/split/): run the split first, "
                             "or pass --include-holdout to fill every company.")
        out["sample"] = ""
    else:
        out["sample"] = out.index.map(split.set_index("IQ_COMPANY_ID")["sample"])
        if not include_holdout:
            out = out[out["sample"] == "training"]
    return out


def gather_evidence(iq_id: str, name: str, website: str, deep: bool) -> tuple[str, dict[str, str], dict]:
    """The evidence for one company: its saved website pages (P lines,
    labeled as the facet fill labels them); with deep, also a further crawl
    of its own site (W) and web search (S, if a search key is set) through
    v0/verification/evidence.py. Returns the prompt text, label -> line,
    and a short record of what was used."""
    if deep:
        from verification.evidence import gather
        ev = gather(iq_id, name, website)
        kinds = sorted({k[0] for k in ev.lines})
        return ev.text("PWS"), dict(ev.lines), {"kinds": kinds, "log_dir": ev.log_dir,
                                                "sources": {k: v.get("url", "") for k, v in ev.sources.items()}}
    record = company_record(iq_id, name, website, True)
    _, lines = fc.build_prompt(record, True)
    return sf.evidence_text(lines), lines, {"kinds": ["P"] if lines else [], "scrape_status": record["status"],
                                            "sources": {p["page_id"]: p["url"] for p in record["pages"]}}


def fill_one(iq_id: str, row: pd.Series, out: SimpleNamespace, args) -> dict:
    company = {"IQ_COMPANY_ID": iq_id, "company_name": row["target_company_name"],
               "website": row["target_ciq_website"], "sector": row["sector"]}
    evidence, lines, used = gather_evidence(iq_id, company["company_name"], company["website"], args.evidence)
    prompt = sf.build_prompt(company, evidence)
    fp = sf.fingerprint(prompt, args.model)
    path = out.profiles / f"{iq_id}.json"
    if path.exists() and not args.refresh:
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") == fp and old.get("llm_status") == "ok":
            return {"IQ_COMPANY_ID": iq_id, "status": "current"}
    run_dir = out.runs / iq_id / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    result = call_claude(prompt, run_dir, sf.answer_schema(row["sector"]), args.model, args.effort,
                         instructions_len=len(sf.INSTRUCTIONS))
    (run_dir / "run.json").write_text(json.dumps(
        {"model": args.model, "prompt_version": sf.PROMPT_VERSION, "fingerprint": fp, "finished_at": now_iso(),
         **{k: v for k, v in result.items() if k != "text"}}, indent=1), encoding="utf-8")
    profile = {"IQ_COMPANY_ID": iq_id, "company_name": company["company_name"], "website": company["website"],
               "sic4": row["sic4"], "ff49": row["ff49"], "sector": row["sector"], "model": args.model,
               "prompt_version": sf.PROMPT_VERSION, "fingerprint": fp, "llm_status": result["llm_status"],
               "run_dir": str(run_dir.relative_to(out.runs.parent)), "created_at": now_iso(),
               "facets": {}, "issues": [], "notes": "", "evidence": used}
    if result["llm_status"] == "ok":
        try:
            raw = json.loads(result["text"])
            profile["facets"], profile["issues"] = sf.check_answer(raw, row["sector"], lines)
            profile["knows_company"], profile["notes"] = bool(raw.get("knows_company")), raw.get("notes", "")
        except json.JSONDecodeError:
            profile["llm_status"] = "invalid_json"
    else:
        profile["error"] = result.get("error", "")
    if result.get("stop_run"):
        return {"IQ_COMPANY_ID": iq_id, "status": result["llm_status"], "stop_run": True}
    if path.exists():
        out.profiles_history.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), out.profiles_history / f"{iq_id}_{stamp()}.json")
    path.write_text(json.dumps(profile, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"IQ_COMPANY_ID": iq_id, "status": profile["llm_status"], "issues": profile["issues"],
            "usage": result.get("usage", {})}


def write_tables(out: SimpleNamespace) -> Path:
    rows = []
    for path in sorted(out.profiles.glob("*.json")):
        p = json.loads(path.read_text(encoding="utf-8"))
        if p.get("prompt_version") != sf.PROMPT_VERSION:
            continue
        rows.append({"IQ_COMPANY_ID": p["IQ_COMPANY_ID"], "sic4": p["sic4"], "ff49": p["ff49"],
                     "sector": p["sector"], "llm_status": p["llm_status"], "knows_company": p.get("knows_company"),
                     "prompt_version": p["prompt_version"], "model": p["model"],
                     **sf.table_row(p.get("facets", {})), "issues": "; ".join(p.get("issues", [])),
                     "notes": p.get("notes", "")})
    table = pd.DataFrame(rows)
    out.tables.mkdir(parents=True, exist_ok=True)
    dest = out.tables / "sector_facets.csv"
    if dest.exists():
        hist = out.tables_history / stamp()
        hist.mkdir(parents=True, exist_ok=True)
        dest.replace(hist / dest.name)
    table.to_csv(dest, index=False)
    ok = (table["llm_status"] == "ok").sum() if len(table) else 0
    print(f"sector facets: {ok} of {len(table)} companies ok -> {dest}")
    return dest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--tickers", nargs="*")
    p.add_argument("--limit", type=int)
    p.add_argument("--include-holdout", action="store_true",
                   help="also fill holdout companies (only once the facet list is frozen)")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL["claude"])
    p.add_argument("--effort", choices=["low", "medium", "high"])
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--evidence", action="store_true",
                   help="also crawl more of each company's site and search the web (verification/evidence.py; "
                        "search needs SERPER_API_KEY, BRAVE_API_KEY or TAVILY_API_KEY); default: saved pages only")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--tables-only", action="store_true")
    args = p.parse_args()
    out = output_paths(Path(args.out))
    for d in (out.runs, out.profiles, out.logs):
        d.mkdir(parents=True, exist_ok=True)
    if args.tables_only:
        write_tables(out)
        return

    todo = companies_to_fill(args.include_holdout)
    if args.tickers:
        todo = todo[todo["target_ciq_ticker"].str.upper().isin({t.upper() for t in args.tickers})]
    if args.limit:
        todo = todo.head(args.limit)
    print(f"{len(todo)} companies; sectors: " + ", ".join(f"{k} {v}" for k, v in todo["sector"].value_counts().items()))

    if args.dry_run:
        out.prompts_dry_run.mkdir(parents=True, exist_ok=True)
        for iq_id, row in todo.iterrows():
            company = {"company_name": row["target_company_name"], "website": row["target_ciq_website"],
                       "sector": row["sector"]}
            (out.prompts_dry_run / f"{iq_id}.txt").write_text(sf.build_prompt(company, gather_evidence(iq_id, company["company_name"], company["website"], args.evidence)[0]), encoding="utf-8")
        print(f"wrote {len(todo)} prompts to {out.prompts_dry_run}")
        return

    claude_api_key()
    log = out.logs / f"fill_{stamp()}.log"
    totals, started = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}, time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool, log.open("w", encoding="utf-8") as lf:
        futures = {pool.submit(fill_one, i, r, out, args): i for i, r in todo.iterrows()}
        for n, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            for k in totals:
                totals[k] += r.get("usage", {}).get(k, 0) or 0
            line = f"[{n}/{len(todo)}] {todo.loc[r['IQ_COMPANY_ID'], 'target_ciq_ticker']:<8} {r['status']}" + \
                   (f" issues: {'; '.join(r['issues'])}" if r.get("issues") else "")
            print(line)
            lf.write(line + "\n")
            if r.get("stop_run"):
                print("stopping: the API refused the key or the credit ran out; finished companies are kept")
                for f in futures:
                    f.cancel()
                break
    print(f"tokens: {totals}; {time.time() - started:.0f} s")
    write_tables(out)


if __name__ == "__main__":
    main()
