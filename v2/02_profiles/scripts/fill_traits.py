"""Fill the tags and economic traits (traits.py) with Sonnet through the Claude Code CLI, one call per company.

Input per company: name, website and up to 1,500 words of its saved website text (financial figures already
removed by the scrape). The model may use what it knows about the company; a company it doesn't know is answered
from the page text only. Every call keeps its prompt, schema, raw answer and run.json under
<out>/runs/<IQ_ID>/<time>/; a company is filled once per prompt and model; replaced answers move to
profiles_history/; tables/traits.csv is rebuilt from the saved answers (an old table moves to tables_history/).

  uv run python v2/02_profiles/scripts/fill_traits.py --sample 30 --out outputs-local/v2/02_profiles/traits_test/run1
  uv run python v2/02_profiles/scripts/fill_traits.py --sample 30 --out outputs-local/v2/02_profiles/traits_test/run2
  uv run python v2/02_profiles/scripts/fill_traits.py --workers 4                    # all 533 companies
  uv run python v2/02_profiles/scripts/fill_traits.py --tickers PCTY WEN --dry-run    # prompts only
  uv run python v2/02_profiles/scripts/fill_traits.py --tables-only
  uv run python v2/02_profiles/scripts/fill_traits.py --round 2 --sample 30 --out outputs-local/v2/02_profiles/traits_r2_test/run1
  uv run python v2/02_profiles/scripts/fill_traits.py --round 2 --workers 4      # round 2, all 533 -> traits_r2/

--round 2 asks only the round-2 questions (traits.ROUND_2, prompt 2026-11-24b) and writes to traits_r2/ by default;
round 1 (the default) is unchanged.

Runs on the Claude subscription (claude-cli backend; API keys are removed from the CLI's environment).
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import v2paths as v2  # noqa: E402
v2.setup()

import argparse
import hashlib
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import facets as fc            # 02_profiles (page lines with figures removed)
import traits as tr            # v2 02_profiles
from cli_models import call_cli                          # common
from fill_facets import DEFAULT_MODEL, company_record, now_iso, stamp   # 02_profiles
from universe import build_universe                      # 01_universe

DEFAULT_OUT = {1: v2.out("02_profiles") / "traits_new", 2: v2.out("02_profiles") / "traits_r2"}
QUESTIONS, PROMPT_VERSION, INSTRUCTIONS, ROUND = tr.QUESTIONS, tr.PROMPT_VERSION, tr.INSTRUCTIONS, 1


def use_round(r: int) -> None:
    """Select the question set (1: tags and traits E1-E6; 2: traits E7-E10)."""
    global QUESTIONS, PROMPT_VERSION, INSTRUCTIONS, ROUND
    QUESTIONS, PROMPT_VERSION, INSTRUCTIONS = tr.ROUNDS[r]
    ROUND = r
SHOWCASE = ["PCTY", "BV", "ROAD", "LMB", "BRO", "ADUS", "DXPE", "SLGN", "BGS", "WEN"]   # v0 showcase targets
SAMPLE_SEED = 2026


def output_paths(out_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(root=out_dir, runs=out_dir / "runs", profiles=out_dir / "profiles",
                           profiles_history=out_dir / "profiles_history", prompts_dry_run=out_dir / "prompts_dry_run",
                           tables=out_dir / "tables", tables_history=out_dir / "tables_history", logs=out_dir / "logs")


def companies() -> pd.DataFrame:
    """The 533 universe companies with their split sample (training/holdout)."""
    u, _ = build_universe()
    u = u[u["in_universe"]].set_index("IQ_COMPANY_ID")[["target_company_name", "target_ciq_ticker",
                                                        "target_ciq_website"]]
    split = pd.read_csv(v2.path(v2.current()["universe"]["split"]), dtype=str).set_index("IQ_COMPANY_ID")
    u["sample"] = u.index.map(split["sample"])
    return u


def test_sample(all_companies: pd.DataFrame, n: int) -> pd.DataFrame:
    """The showcase targets plus random training companies (seed 2026) up to n."""
    training = all_companies[all_companies["sample"] == "training"]
    show = training[training["target_ciq_ticker"].isin(SHOWCASE)]
    rest = training.drop(show.index).sample(n=max(0, n - len(show)), random_state=SAMPLE_SEED)
    return pd.concat([show, rest])


def prompt_for(iq_id: str, row: pd.Series) -> tuple[str, bool]:
    record = company_record(iq_id, row["target_company_name"], row["target_ciq_website"], True)
    _, lines = fc.build_prompt(record, True)
    pages = tr.page_text(lines)
    return tr.build_prompt(row["target_company_name"], row["target_ciq_website"], pages, ROUND), bool(pages)


def fill_one(iq_id: str, row: pd.Series, out: SimpleNamespace, args) -> dict:
    prompt, had_pages = prompt_for(iq_id, row)
    fp = tr.fingerprint(prompt, args.model)
    path = out.profiles / f"{iq_id}.json"
    if path.exists() and not args.refresh:
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") == fp and old.get("llm_status") == "ok":
            return {"IQ_COMPANY_ID": iq_id, "status": "current"}
    run_dir = out.runs / iq_id / stamp()
    result = call_cli(prompt, run_dir, tr.answer_schema(QUESTIONS), "claude-cli", model=args.model, effort=args.effort,
                      instructions_len=len(INSTRUCTIONS))
    (run_dir / "run.json").write_text(json.dumps(
        {"backend": "claude-cli", "model": args.model, "prompt_version": PROMPT_VERSION, "fingerprint": fp,
         "had_pages": had_pages, "finished_at": now_iso(), **{k: v for k, v in result.items() if k != "text"}},
        indent=1), encoding="utf-8")
    if result.get("stop_run"):
        return {"IQ_COMPANY_ID": iq_id, "status": result["llm_status"], "stop_run": True,
                "error": result.get("error", "")}
    profile = {"IQ_COMPANY_ID": iq_id, "company_name": row["target_company_name"],
               "ticker": row["target_ciq_ticker"], "website": row["target_ciq_website"], "sample": row["sample"],
               "model": args.model, "prompt_version": PROMPT_VERSION, "fingerprint": fp, "had_pages": had_pages,
               "llm_status": result["llm_status"], "run_dir": str(run_dir.relative_to(out.root)),
               "created_at": now_iso(), "answers": {}, "issues": [], "knows_company": None, "notes": ""}
    if result["llm_status"] == "ok":
        try:
            raw = json.loads(result["text"])
            profile["answers"], profile["issues"] = tr.check_answer(raw, had_pages, QUESTIONS)
            profile["knows_company"], profile["notes"] = bool(raw.get("knows_company")), raw.get("notes", "")
        except (json.JSONDecodeError, ValueError, AttributeError) as exc:
            profile["llm_status"], profile["error"] = "invalid_answer", str(exc)
    else:
        profile["error"] = result.get("error", "")
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
        if p.get("prompt_version") != PROMPT_VERSION:
            continue
        rows.append({"IQ_COMPANY_ID": p["IQ_COMPANY_ID"], "ticker": p.get("ticker", ""),
                     "company_name": p["company_name"], "sample": p.get("sample", ""),
                     "llm_status": p["llm_status"], "knows_company": p.get("knows_company"),
                     "had_pages": p.get("had_pages"), "prompt_version": p["prompt_version"], "model": p["model"],
                     **tr.table_row(p.get("answers", {}), QUESTIONS), "issues": "; ".join(p.get("issues", [])),
                     "notes": p.get("notes", "")})
    table = pd.DataFrame(rows)
    if table.empty:
        raise SystemExit(f"no answers at prompt version {PROMPT_VERSION} in {out.profiles}; table not written")
    out.tables.mkdir(parents=True, exist_ok=True)
    dest = out.tables / "traits.csv"
    if dest.exists():
        hist = out.tables_history / stamp()
        hist.mkdir(parents=True, exist_ok=True)
        dest.replace(hist / dest.name)
    table.to_csv(dest, index=False)
    print(f"traits: {(table['llm_status'] == 'ok').sum()} of {len(table)} companies ok -> {dest}")
    return dest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--round", type=int, choices=[1, 2], default=1, help="question set (default 1)")
    p.add_argument("--out", help="output folder (default traits_new/ for round 1, traits_r2/ for round 2)")
    p.add_argument("--tickers", nargs="*")
    p.add_argument("--sample", type=int, help="test sample: the showcase targets plus random training companies")
    p.add_argument("--limit", type=int)
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL["claude-cli"])
    p.add_argument("--effort", choices=["low", "medium", "high"])
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--tables-only", action="store_true")
    args = p.parse_args()
    use_round(args.round)
    out = output_paths(Path(args.out or DEFAULT_OUT[args.round]).resolve())
    for d in (out.runs, out.profiles, out.logs):
        d.mkdir(parents=True, exist_ok=True)
    if args.tables_only:
        write_tables(out)
        return

    todo = companies()
    if args.sample:
        todo = test_sample(todo, args.sample)
        todo.to_csv(out.root / "sample.csv")
    if args.tickers:
        todo = todo[todo["target_ciq_ticker"].str.upper().isin({t.upper() for t in args.tickers})]
    if args.limit:
        todo = todo.head(args.limit)
    print(f"{len(todo)} companies, model {args.model}, round {ROUND}, prompt {PROMPT_VERSION}")

    if args.dry_run:
        out.prompts_dry_run.mkdir(parents=True, exist_ok=True)
        for iq_id, row in todo.iterrows():
            (out.prompts_dry_run / f"{iq_id}.txt").write_text(prompt_for(iq_id, row)[0], encoding="utf-8")
        print(f"wrote {len(todo)} prompts to {out.prompts_dry_run}")
        return

    # The system prompt (the instructions) is the same for every call; call_cli keeps it once as
    # runs/system_<hash>.txt and writes it when missing. Written here, before the workers start, so parallel calls
    # don't race on the same temporary file (Windows refused the second writer on 2026-11-24).
    digest = hashlib.sha256(INSTRUCTIONS.encode("utf-8")).hexdigest()[:8]
    system_file = out.runs / f"system_{digest}.txt"
    if not system_file.exists():
        system_file.write_text(INSTRUCTIONS, encoding="utf-8")
    log = out.logs / f"fill_{stamp()}.log"
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool, log.open("w", encoding="utf-8") as lf:
        futures = {pool.submit(fill_one, i, r, out, args): i for i, r in todo.iterrows()}
        for n, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            line = f"[{n}/{len(todo)}] {todo.loc[r['IQ_COMPANY_ID'], 'target_ciq_ticker']:<8} {r['status']}" + \
                   (f" issues: {'; '.join(r['issues'])}" if r.get("issues") else "")
            print(line, flush=True)
            lf.write(line + "\n")
            if r.get("stop_run"):
                print(f"stopping: {r.get('error', '')[:300]}; finished companies are kept")
                for f in futures:
                    f.cancel()
                break
    print(f"{time.time() - started:.0f} s")
    write_tables(out)


if __name__ == "__main__":
    main()
