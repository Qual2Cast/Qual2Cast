"""
Verify the filled facets (fill_facets.py) against each company's own saved
website pages. Task 1 of the evals: the fill takes most facets from the
model's memory, which can be wrong or out of date (Carlisle's facets listed
industrial finishing, a business it sold in 2023; its site describes only
building-envelope products). Nothing in the fill checks that; this does.

What is checked. Each facet is split into claims, one per item, so a
single outdated item is caught without judging the whole facet:
- text facets that are lists (products, services, end markets): one claim
  per item between semicolons;
- category facets: one claim per category with its detail;
- core offering: one claim, the whole description.
Company size (F9) is left out: it is judged from scale, which the pages
don't state. Unknown and not-applicable facets have nothing to check.

The call. One call per company (Claude Sonnet 5.5 by default, a different
and stronger model than the one that filled the facets, so it isn't
checking its own answers), through fill_facets.call_claude. It gets the
claims and the company's saved pages, every line labeled ([P1.3] = page
P1, line 3), the same page text the fill's second pass uses (no new
scraping, figure lines left out). It uses only the pages, not what it
knows. For each claim it answers:
- supported: a page line says this or clearly means it; cite the line;
- contradicted: a page line says otherwise (the company sold it, no
  longer does it, or the pages list its businesses or products in a way
  that leaves no room for it); cite the line and say what it says;
- not mentioned: the pages don't say either way.

Code decides, not the model (as in facets.apply_split_check):
- supported / contradicted count only if a cited label is a line that was
  in the prompt; otherwise the claim is not_on_pages, flagged
  citation_not_found;
- not mentioned is not evidence of an error when the pages are thin
  (fewer than MIN_PAGES pages or MIN_WORDS words sent: News Corp's scrape
  saved only its 59-word homepage): then the claim is not_checkable.
  On adequate pages it is not_on_pages, which is weak evidence: many true
  facts (regulators, channels) are rarely on a homepage. Whether it means
  anything is for the gold labels to show.
Facet verdict, from its claims: contradicted if any claim is; supported if
every claim is; partly_supported if some are and the rest are only not on
the pages; not_on_pages; not_checkable. MIN_PAGES and MIN_WORDS are first
guesses, to be set from the hand-labeled gold set, not from this output.

Every call keeps its prompt, raw answer and logs under
<out>/runs/<IQ_ID>/<time>/. A company is checked once per prompt and
model; a rerun skips it, and a replaced check or table moves to a
history folder. The run stops if the API credit runs out or the key is
refused; run it again after fixing that.

  python v0/verify_facets.py --facets outputs-local/comps/facets_riya --tickers CSL AFG
  python v0/verify_facets.py --facets outputs-local/comps/facets_riya     # every company there
  python v0/verify_facets.py --dry-run                                    # prompts only
  python v0/verify_facets.py --tables-only                                # rebuild the CSVs

Output (default <facets>/verify/): checks/<IQ_ID>.json (each claim with
the model's answer, the cited lines and the code's verdict),
tables/verify_claims.csv (one row per claim) and tables/verify_facets.csv
(one row per company and facet, with the facet's verdict).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facets as fc  # noqa: E402  (also puts website_scrape/ and src/ on the path)
from fill_facets import (DEFAULT_OUT as FACETS_OUT, call_claude, claude_api_key, company_record,  # noqa: E402
                         now_iso, output_paths as facet_paths, stamp)

PROMPT_VERSION = "2026-10-25a"
DEFAULT_MODEL = "claude-sonnet-5-5"
SKIP_FACETS = {"company_size"}          # judged from scale, which the pages don't state
LIST_FACETS = {"primary_products", "primary_services", "end_markets"}   # text, items split by ";"
MIN_PAGES = 2                           # thin-page guard: fewer pages with text, or
MIN_WORDS = 250                         # fewer words sent, and "not mentioned" says nothing
VERDICTS = ("supported", "contradicted", "not mentioned")

INSTRUCTIONS = """You check a description of a company against text from the company's current website. The description was written earlier, partly from memory, and may be wrong or out of date: it may list businesses the company has sold, spun off or closed, or products and customers it doesn't have.

Below is a list of claims from the description, each with an id (B1.F2.1), and the website text. Each line of website text starts with a label: [P1.3] is page P1, line 3.

For every claim, answer one of:
- "supported": a line of the website text says this, or clearly means it in other words. In "cite", give the labels of the 1 or 2 lines that show it.
- "contradicted": a line of the website text says otherwise: the company sold it or no longer does it, or the text lists the company's businesses, products or customers in a way that leaves no room for this claim. In "cite", give the labels of the 1 or 2 lines, and in "says" write in a few words what the text says instead.
- "not mentioned": the website text doesn't say either way. Being absent from the text is not a contradiction: most websites leave out many true facts.

Rules:
- Use only the website text, not what you already know about the company.
- Answer for every claim, once, by its id.
- Leave "cite" empty and "says" empty for "not mentioned".
- Everything you need is in this message. Do not run commands, open files or search the web. Write the JSON on one line."""


def output_paths(out_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        runs=out_dir / "runs",                          # prompt, raw answer, logs per call
        checks=out_dir / "checks",                      # one checked answer per company
        checks_history=out_dir / "checks_history",
        prompts_dry_run=out_dir / "prompts_dry_run",
        tables=out_dir / "tables",                      # verify_claims.csv, verify_facets.csv
        tables_history=out_dir / "tables_history",
        logs=out_dir / "logs",
    )


# ---------------------------------------------------------------- claims

def facet_claims(name: str, facet: dict) -> list[str]:
    """The claims in one filled facet: list items, category items, or the
    whole value. Nothing for skipped, unknown or not-applicable facets."""
    if name in SKIP_FACETS or facet["status"] != "filled" or not facet["value"].strip():
        return []
    if name in LIST_FACETS or fc.FACET_BY_NAME[name].kind != "text":
        # category items are "category: detail" joined by "; " (details never
        # hold ";", see facets.clean_detail)
        return [x.strip() for x in facet["value"].split(";") if x.strip()]
    return [facet["value"].strip()]


def profile_claims(profile: dict) -> list[dict]:
    """Every claim in a company's profile, with its id: business, facet ID and
    item number ("B1.F2.3")."""
    claims = []
    for b in profile["businesses"]:
        for name, facet in b["facets"].items():
            for n, text in enumerate(facet_claims(name, facet), start=1):
                claims.append({"id": f"{b['business_id']}.{fc.FACET_ID[name]}.{n}",
                               "business_id": b["business_id"], "facet": name, "claim": text})
    return claims


# ---------------------------------------------------------------- prompt

def page_coverage(lines: dict[str, str]) -> dict:
    """How much page text the prompt carries, and whether it is enough for
    "not mentioned" to mean anything (the thin-page guard)."""
    pages = sorted({label.split(".")[0] for label in lines})
    words = sum(len(text.split()) for text in lines.values())
    return {"pages": len(pages), "words": words,
            "adequate": len(pages) >= MIN_PAGES and words >= MIN_WORDS}


def build_prompt(record: dict, claims: list[dict]) -> tuple[str, dict[str, str]]:
    """The prompt for one company, and label -> page line. The page text is
    the fill's own (facets.build_prompt with pages): same labels, same
    filters, same word cap."""
    full, lines = fc.build_prompt(record, True)
    pages = full[full.index('<page id="'):] if lines else ""
    listed = "\n".join(f"{c['id']} ({fc.FACET_BY_NAME[c['facet']].label}): {c['claim']}" for c in claims)
    prompt = (f"{INSTRUCTIONS}\n\nCompany: {record['company_name']}\nWebsite: {record['website']}\n\n"
              f"Claims:\n{listed}\n\nWebsite text:\n\n{pages}")
    return prompt, lines


def answer_schema(ids: list[str]) -> dict:
    item = {"type": "object", "additionalProperties": False, "required": ["id", "verdict", "cite", "says"],
            "properties": {"id": {"type": "string", "enum": ids},
                           "verdict": {"type": "string", "enum": list(VERDICTS)},
                           "cite": {"type": "array", "items": {"type": "string"}},
                           "says": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": ["claims", "notes"],
            "properties": {"claims": {"type": "array", "items": item}, "notes": {"type": "string"}}}


def fingerprint(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- the code's verdicts

def apply_verdicts(claims: list[dict], raw: dict, lines: dict[str, str], page_urls: dict[str, str],
                   coverage: dict) -> tuple[list[dict], list[str]]:
    """Each claim with the model's answer, its cited lines, and the code's
    verdict (see the module docstring), and the issues found: a claim
    answered twice keeps its first answer; one never answered is
    not_on_pages or not_checkable like "not mentioned", flagged
    not_answered."""
    said, issues = {}, []
    for a in raw.get("claims", []):
        if a.get("id") not in {c["id"] for c in claims}:
            issues.append(f"unknown_id:{a.get('id')}")
        elif a["id"] in said:
            issues.append(f"duplicate_id:{a['id']}")
        else:
            said[a["id"]] = a
    absent = "not_on_pages" if coverage["adequate"] else "not_checkable"
    out = []
    for c in claims:
        a = said.get(c["id"])
        flags = [] if a else ["not_answered"]
        a = a or {"verdict": "not mentioned", "cite": [], "says": ""}
        labels = [x for cite in a["cite"] for x in re.findall(r"P\d+\.\d+", cite)]   # "[P1.6]" too
        quotes = [{"block": x, "url": page_urls.get(x.split(".")[0], ""), "quote": lines.get(x, ""),
                   "quote_found": x in lines} for x in dict.fromkeys(labels)]
        if a["verdict"] in ("supported", "contradicted"):
            if any(q["quote_found"] for q in quotes):
                verdict = a["verdict"]
            else:
                verdict = absent
                flags.append("citation_not_found")
        else:
            verdict = absent
        out.append({**c, "model_said": a["verdict"], "says": a.get("says", "").strip(),
                    "quotes": quotes, "verdict": verdict, "flags": flags})
    issues += [f"not_answered:{c['id']}" for c in out if "not_answered" in c["flags"]]
    return out, issues


def facet_verdict(verdicts: list[str]) -> str:
    """A facet's verdict from its claims' verdicts."""
    if not verdicts:
        return "not_checked"
    if "contradicted" in verdicts:
        return "contradicted"
    if all(v == "supported" for v in verdicts):
        return "supported"
    if "supported" in verdicts:
        return "partly_supported"
    if "not_on_pages" in verdicts:
        return "not_on_pages"
    return "not_checkable"


# ---------------------------------------------------------------- run

def move_to_history(path: Path, history: Path) -> None:
    if path.exists():
        history.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), history / f"{path.stem}_{stamp()}{path.suffix}")


def load_profiles(facets_dir: Path, tickers: list[str] | None) -> list[tuple[dict, str]]:
    """The current-version profiles in a fill output folder, with each
    company's ticker, optionally only some tickers."""
    from universe import build_universe
    companies, _ = build_universe()
    ticker = companies.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
    wanted = {t.upper() for t in tickers} if tickers else None
    out = []
    for path in sorted(facet_paths(facets_dir).profiles.glob("*.json")):
        prof = json.loads(path.read_text(encoding="utf-8"))
        t = str(ticker.get(prof["IQ_COMPANY_ID"], ""))
        if prof.get("prompt_version") != fc.PROMPT_VERSION or prof.get("llm_status") != "ok":
            continue
        if wanted is None or t.upper() in wanted:
            out.append((prof, t))
    return out


def verify_one(profile: dict, ticker: str, out: SimpleNamespace, args) -> dict:
    record = company_record(profile["IQ_COMPANY_ID"], profile["company_name"], profile["website"], True)
    claims = profile_claims(profile)
    prompt, lines = build_prompt(record, claims)
    coverage = page_coverage(lines)
    fp = fingerprint(prompt, args.model)
    path = out.checks / f"{profile['IQ_COMPANY_ID']}.json"
    if path.exists() and not args.refresh:
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") == fp and old.get("llm_status") in ("ok", "no_pages"):
            return {"iq": profile["IQ_COMPANY_ID"], "ticker": ticker, "status": "current"}
    check = {"IQ_COMPANY_ID": profile["IQ_COMPANY_ID"], "ticker": ticker,
             "company_name": profile["company_name"], "prompt_version": PROMPT_VERSION,
             "facets_prompt_version": profile["prompt_version"], "facets_created_at": profile["created_at"],
             "model": args.model, "fingerprint": fp, "coverage": coverage, "checked_at": now_iso(),
             "claims": [], "issues": [], "notes": ""}
    result = {}
    if not lines:                             # nothing saved to check against
        check["llm_status"] = "no_pages"
        check["claims"], _ = apply_verdicts(claims, {"claims": []}, {}, {}, coverage)
        for c in check["claims"]:
            c["flags"] = []                   # not answered because never asked
    else:
        run_dir = out.runs / profile["IQ_COMPANY_ID"] / stamp()
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        result = call_claude(prompt, run_dir, answer_schema([c["id"] for c in claims]), args.model,
                             args.effort, instructions_len=len(INSTRUCTIONS))
        run_info = {"model": args.model, "effort": args.effort or "", "prompt_version": PROMPT_VERSION,
                    "fingerprint": fp, "finished_at": now_iso(),
                    **{k: v for k, v in result.items() if k != "text"}}
        (run_dir / "run.json").write_text(json.dumps(run_info, indent=1), encoding="utf-8")
        check["run_dir"] = run_dir.relative_to(out.runs.parent).as_posix()
        check["llm_status"] = result["llm_status"]
        if result["llm_status"] == "ok":
            try:
                raw = json.loads(result["text"])
                page_urls = {p["page_id"]: p["url"] for p in record["pages"]}
                check["claims"], check["issues"] = apply_verdicts(claims, raw, lines, page_urls, coverage)
                check["notes"] = raw.get("notes", "")
            except json.JSONDecodeError:
                check["llm_status"] = "invalid_json"
        else:
            check["error"] = result.get("error", "")
    if result.get("stop_run"):                # key refused or out of credit: save nothing
        return {"iq": profile["IQ_COMPANY_ID"], "ticker": ticker, "status": "not_run",
                "error": result.get("error", ""), "stop_run": True}
    move_to_history(path, out.checks_history)
    path.write_text(json.dumps(check, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = pd.Series([c["verdict"] for c in check["claims"]]).value_counts().to_dict()
    return {"iq": profile["IQ_COMPANY_ID"], "ticker": ticker, "status": check["llm_status"],
            "counts": counts, "coverage": coverage, "issues": check["issues"],
            "usage": result.get("usage", {}), "error": check.get("error", "")}


def write_tables(out: SimpleNamespace, profiles: list[tuple[dict, str]]) -> Path:
    """verify_claims.csv (one row per claim) and verify_facets.csv (one row
    per company and facet: the facet's value as filled and its verdict, so a
    reviewer can go down the list), from the checks of the current prompt
    version."""
    values = {(p["IQ_COMPANY_ID"], b["business_id"], name): f["value"]
              for p, _ in profiles for b in p["businesses"] for name, f in b["facets"].items()}
    claim_rows, facet_rows = [], []
    for path in sorted(out.checks.glob("*.json")):
        ch = json.loads(path.read_text(encoding="utf-8"))
        if ch.get("prompt_version") != PROMPT_VERSION or ch.get("llm_status") not in ("ok", "no_pages"):
            continue
        base = {"IQ_COMPANY_ID": ch["IQ_COMPANY_ID"], "ticker": ch["ticker"], "company": ch["company_name"]}
        cov = ch["coverage"]
        for c in ch["claims"]:
            claim_rows.append({**base, "claim_id": c["id"], "facet": c["facet"], "claim": c["claim"],
                               "verdict": c["verdict"], "model_said": c["model_said"], "says": c["says"],
                               "cited": " | ".join(f"{q['block']}: {q['quote']}" for q in c["quotes"]),
                               "cited_urls": "; ".join(dict.fromkeys(q["url"] for q in c["quotes"] if q["url"])),
                               "flags": "; ".join(c["flags"]), "pages": cov["pages"], "page_words": cov["words"],
                               "pages_adequate": cov["adequate"], "model": ch["model"]})
        by_facet: dict[tuple[str, str], list[dict]] = {}
        for c in ch["claims"]:
            by_facet.setdefault((c["business_id"], c["facet"]), []).append(c)
        bids = sorted({k[1] for k in values if k[0] == ch["IQ_COMPANY_ID"]}) or ["B1"]
        for bid in bids:
            for f in fc.FACETS:
                cs = by_facet.get((bid, f.name), [])
                facet_rows.append({**base, "business_id": bid, "facet_id": fc.FACET_ID[f.name], "facet": f.name,
                                   "value": values.get((ch["IQ_COMPANY_ID"], bid, f.name), ""),
                                   "verdict": facet_verdict([c["verdict"] for c in cs]),
                                   "claims": len(cs),
                                   "contradicted": " | ".join(f"{c['claim']} -> {c['says']}" for c in cs
                                                              if c["verdict"] == "contradicted"),
                                   "pages_adequate": cov["adequate"]})
    out.tables.mkdir(parents=True, exist_ok=True)
    for name, rows in [("verify_claims.csv", claim_rows), ("verify_facets.csv", facet_rows)]:
        dest = out.tables / name
        move_to_history(dest, out.tables_history)
        pd.DataFrame(rows).to_csv(dest, index=False)
    return out.tables


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--facets", default=str(FACETS_OUT), help="fill_facets.py output folder (its --out)")
    p.add_argument("--out", help="default: <facets>/verify")
    p.add_argument("--tickers", nargs="*", help="only these companies")
    p.add_argument("--limit", type=int, help="stop after N companies")
    p.add_argument("--refresh", action="store_true", help="check current companies again")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--effort", choices=["low", "medium", "high"], help="default: the model's own")
    p.add_argument("--workers", type=int, default=2, help="companies in parallel")
    p.add_argument("--dry-run", action="store_true", help="write the prompts only")
    p.add_argument("--tables-only", action="store_true", help="only rebuild the CSVs")
    args = p.parse_args()
    facets_dir = Path(args.facets).resolve()
    out = output_paths(Path(args.out).resolve() if args.out else facets_dir / "verify")

    profiles = load_profiles(facets_dir, args.tickers)
    if args.limit:
        profiles = profiles[:args.limit]
    if not profiles:
        raise SystemExit(f"No current profiles (facets version {fc.PROMPT_VERSION}) in {facets_dir}"
                         + (f" for {' '.join(args.tickers)}" if args.tickers else "")
                         + ": run fill_facets.py first, or pass --facets.")

    if args.dry_run:
        out.prompts_dry_run.mkdir(parents=True, exist_ok=True)
        for prof, t in profiles:
            record = company_record(prof["IQ_COMPANY_ID"], prof["company_name"], prof["website"], True)
            prompt, lines = build_prompt(record, profile_claims(prof))
            cov = page_coverage(lines)
            (out.prompts_dry_run / f"{prof['IQ_COMPANY_ID']}.txt").write_text(prompt, encoding="utf-8")
            print(f"{t:<6} {len(profile_claims(prof)):>3} claims, {cov['pages']} pages, {cov['words']:>5} words"
                  + ("" if cov["adequate"] else "  (thin: not mentioned -> not_checkable)"))
        print(f"wrote {len(profiles)} prompts to {out.prompts_dry_run}")
        return

    if not args.tables_only:
        claude_api_key()                      # fail early with setup instructions
        for d in (out.runs, out.checks, out.logs):
            d.mkdir(parents=True, exist_ok=True)
        log = out.logs / f"verify_{stamp()}.log"
        print(f"verifying {len(profiles)} companies from {facets_dir.name} with {args.model}; log {log.name}")
        totals, started = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}, time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as pool, log.open("w", encoding="utf-8") as lf:
            futures = {pool.submit(verify_one, prof, t, out, args): t for prof, t in profiles}
            for n, fut in enumerate(as_completed(futures), 1):
                r = fut.result()
                for k in totals:
                    totals[k] += r.get("usage", {}).get(k, 0) or 0
                c = r.get("counts", {})
                what = ", ".join(f"{c[v]} {v}" for v in ("supported", "contradicted", "not_on_pages",
                                                         "not_checkable") if c.get(v))
                line = (f"[{n}/{len(profiles)}] {r['ticker']:<6} {r['status']:<12} {what}"
                        + (f"  {r['error']}" if r.get("error") else "")
                        + (f"  issues: {'; '.join(r['issues'])}" if r.get("issues") else ""))
                print(line, flush=True)
                lf.write(line + "\n")
                if r.get("stop_run"):
                    print("stopping: the API refused the key or the credit ran out; finished companies are kept")
                    for f in futures:
                        f.cancel()
                    break
        print(f"tokens: {totals}; {time.time() - started:.0f} s")
    dest = write_tables(out, profiles)
    print("wrote", dest / "verify_claims.csv", "and verify_facets.csv")


if __name__ == "__main__":
    main()
