"""
Experiment: fill the facets the way they would be filled for a private
company the model has never heard of, from the saved website pages alone.

The test companies are public, and Haiku knows 19 of the 20 checked on
2026-10-25, so the normal fill describes them from memory. A real
PE-backed target falls through to the pages pass instead, and the one
company described that way in the check (Resolute Holdings) had none of its
12 facets supported. This rerun measures that case directly:

- same prompt, schema and checks as the fill's pages pass (facets.py,
  version as in fc.PROMPT_VERSION), except that the model is told to use the
  pages only and is not asked whether it knows the company;
- the company's name and web address are replaced by "the Company" in the
  prompt and in the page text, so the model can't fall back on memory (as
  the website-only prompt versions a-d did); brand names in the page text
  can still give it away, so knows_company is recorded but not relied on;
- a company with no saved pages gets every facet unknown: that is what
  would happen to a private company whose site can't be scraped.

  python v0/verification/pages_only_fill.py --tickers PCTY ROAD ...
  python v0/verification/pages_only_fill.py --compare outputs-local/comps/facets_verify20 \
      --gold outputs-local/comps/facets_verify20/verification/facet_verification_20.csv

Writes outputs-local/comps/facets_verify20_pages_only/ in the fill's layout
(codex_runs/, profiles/, tables/facets.csv), so verify_with_evidence.py can
judge it like any fill; --compare writes compare_with_memory.csv there.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import facets as fc  # noqa: E402
import fill_facets as ff  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402
from universe import build_universe  # noqa: E402

OUT = OUTPUTS_LOCAL / "comps" / "facets_verify20_pages_only"
EXPERIMENT = "pages_only_masked"
MASK = "the Company"
SUFFIX = re.compile(r",?\s+(?:inc\.?|incorporated|corp\.?|corporation|co\.?|company|holdings?|group"
                    r"|ltd\.?|limited|llc|plc|lp|l\.p\.)$", re.I)

PAGES_ONLY = """Use only the website pages below, not anything you already know. The \
company's name and web address are withheld and written as "the Company". \
Set "knows_company" to false. Do not guess anything that the pages don't \
support; a facet the pages don't support is "unknown"."""


def name_variants(company_name: str, website: str) -> list[str]:
    """Strings to mask, longest first: the full name, the name without legal
    suffixes and a leading "The", and the website's domain words."""
    full = company_name.strip()
    short = re.sub(r"^the\s+", "", full, flags=re.I)
    for _ in range(3):
        s = SUFFIX.sub("", short).strip(" ,")
        if s == short:
            break
        short = s
    domain = re.sub(r"^(?:https?://)?(?:www\.)?", "", website.strip(), flags=re.I).split("/")[0]
    variants = {full, short, domain, domain.split(".")[0]}
    # a distinctive first word ("Addus" of "Addus HomeCare"), not a common one
    first = short.split()[0] if short.split() else ""
    if len(first) >= 4 and first.lower() not in {"american", "national", "united", "general", "first",
                                                 "international", "global", "the"}:
        variants.add(first)
    return sorted((v for v in variants if len(v) >= 3), key=len, reverse=True)


def mask_text(text: str, variants: list[str]) -> str:
    for v in variants:
        text = re.sub(rf"(?<![\w]){re.escape(v)}(?:'s|’s)?(?![\w])", MASK, text, flags=re.I)
    return text


def masked_record(record: dict) -> dict:
    variants = name_variants(record["company_name"], record["website"])
    pages = [{**p, "title": mask_text(p.get("title", ""), variants),
              "meta": mask_text(p.get("meta", ""), variants),
              "blocks": [mask_text(b, variants) for b in p.get("blocks", [])]}
             for p in record["pages"]]
    return {**record, "company_name": MASK, "website": "(withheld)", "pages": pages}


def pages_only_instructions() -> str:
    instr = fc.instructions(True)
    known = re.search(r"First, say whether you know this company.*?is \"unknown\"\.", instr, re.S)
    if not known:
        raise RuntimeError("facets.instructions(True) changed; update PAGES_ONLY")
    instr = instr.replace(known.group(0), PAGES_ONLY)
    swaps = [
        ("Use what you know about the company, and the website pages.", "Use only the website pages."),
        ("For a company you know, fill every facet you can. If you are not sure of a detail, give "
         "your best description of this company and say what is uncertain in \"notes\".",
         "Fill every facet the pages support, and say what is uncertain in \"notes\"."),
        (" A facet you fill from what you already know about the company gets no citation.",
         " Every facet you fill needs a citation."),
    ]
    for old, new in swaps:
        if old not in instr:
            raise RuntimeError(f"facets.instructions(True) changed; update the swap for: {old[:40]}...")
        instr = instr.replace(old, new)
    return instr


def build(record: dict) -> tuple[str, dict[str, str]]:
    """The pages-only prompt and its labelled lines."""
    prompt, lines = fc.build_prompt(masked_record(record), True)
    instr = fc.instructions(True)
    if not lines:
        return "", {}
    return pages_only_instructions() + prompt[len(instr):], lines


def fill(tickers: list[str], model: str, effort: str | None) -> None:
    paths = ff.output_paths(OUT)
    paths.profiles.mkdir(parents=True, exist_ok=True)
    companies, _ = build_universe()
    rows = companies[companies["in_universe"] & companies["target_ciq_ticker"].str.upper()
                     .isin({t.upper() for t in tickers})]
    ff.claude_api_key()
    instr = pages_only_instructions()
    for c in rows.itertuples():
        record = ff.company_record(c.IQ_COMPANY_ID, c.target_company_name, c.target_ciq_website, True)
        prompt, lines = build(record)
        run_dir = paths.codex_runs / c.IQ_COMPANY_ID / ff.stamp()
        run_dir.mkdir(parents=True, exist_ok=True)
        if not lines:
            answer, status = fc.unknown_facets("no saved page text"), "ok"
            answer["knows_company"] = False
            answer["issues"] = ["no_pages"]
            meta = {}
        else:
            (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
            res = ff.call_claude(prompt, run_dir, fc.answer_schema(True), model, effort,
                                 instructions_len=len(instr))
            status, meta = res["llm_status"], {k: v for k, v in res.items() if k != "text"}
            answer = None
            if status == "ok":
                page_urls = {p["page_id"]: p["url"] for p in record["pages"]}
                try:
                    answer = fc.check_answer(json.loads(res["text"]), lines, page_urls)
                except Exception as exc:              # noqa: BLE001  (recorded)
                    status, meta["error"] = "invalid_answer", str(exc)[:300]
            if res.get("stop_run"):
                raise SystemExit(f"Stopped: {res.get('error')}")
            answer = answer or fc.unknown_facets(f"no answer ({status})")
        (run_dir / "run.json").write_text(json.dumps({"experiment": EXPERIMENT, "model": model,
                                                      "prompt_version": fc.PROMPT_VERSION, **meta},
                                                     indent=1, default=str), encoding="utf-8")
        profile = {"IQ_COMPANY_ID": c.IQ_COMPANY_ID, "company_name": c.target_company_name,
                   "website": c.target_ciq_website, "with_pages": True, "model": model,
                   "experiment": EXPERIMENT, "prompt_version": fc.PROMPT_VERSION,
                   "llm_status": "ok" if status == "ok" else status,
                   "llm_run_dir": run_dir.relative_to(OUT).as_posix(), "created_at": ff.now_iso(),
                   **answer}
        out = paths.profiles / f"{c.IQ_COMPANY_ID}.json"
        if out.exists():
            paths.profiles_history.mkdir(exist_ok=True)
            out.replace(paths.profiles_history / f"{out.stem}_{ff.stamp()}.json")
        out.write_text(json.dumps(profile, indent=1, ensure_ascii=False), encoding="utf-8")
        facets = [f for b in answer["businesses"] for f in b["facets"].values()]
        filled = sum(f["status"] != "unknown" for f in facets)
        print(f"{c.target_ciq_ticker:<6} {status:<14} {filled}/{len(facets)} facets  pages lines {len(lines)}",
              flush=True)
    ff.write_tables(OUT)


def _cats(s: str) -> set[str]:
    return {x.strip() for x in str(s).split(";") if x.strip()}


def compare(memory_dir: str, gold_path: str | None) -> pd.DataFrame:
    """Pages-only fill next to the memory fill, per company and facet: both
    values, whether the categories agree (category facets), and the gold
    verdict on the memory fill. Category agreement with a memory fill the
    gold check found 'supported' is the automatic accuracy proxy; text
    facets are listed for review."""
    mem = pd.read_csv(Path(memory_dir) / "tables" / "facets.csv", dtype=str).fillna("")
    po = pd.read_csv(OUT / "tables" / "facets.csv", dtype=str).fillna("")
    po = po[po.llm_status.eq("ok")]
    companies, _ = build_universe()
    tick = companies.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
    gold = pd.read_csv(gold_path, dtype=str).fillna("") if gold_path else pd.DataFrame(
        columns=["ticker", "facet", "verdict"])
    gold = gold.set_index(["ticker", "facet"])["verdict"].to_dict()
    rows = []
    for _, p in po.iterrows():
        m = mem[mem.IQ_COMPANY_ID == p.IQ_COMPANY_ID]
        if m.empty:
            continue
        m = m.iloc[0]
        t = tick.get(p.IQ_COMPANY_ID, "")
        for f in fc.FACETS:
            r = {"ticker": t, "facet": f.name, "facet_id": fc.FACET_ID[f.name],
                 "pages_only_status": p[f"{f.name}_status"], "pages_only_value": p[f.name],
                 "memory_status": m[f"{f.name}_status"], "memory_value": m[f.name],
                 "gold_on_memory": gold.get((t, f.name), "")}
            if f.kind != "text":
                a, b = _cats(p[f"{f.name}_category"]), _cats(m[f"{f.name}_category"])
                r["category_agree"] = (a == b) if a and b else ""
                r["category_overlap"] = (len(a & b) / len(a | b)) if a and b else ""
            rows.append(r)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "compare_with_memory.csv", index=False)
    cov = out.assign(filled=out.pages_only_status.ne("unknown")).groupby("ticker").filled.sum()
    print("Facets filled from pages only (of 12):")
    print(cov.sort_values().to_string())
    ok = out[(out.gold_on_memory == "supported") & out.category_agree.isin([True, False])]
    if len(ok):
        print(f"\nCategory facets where the memory fill was verified supported: {len(ok)}; "
              f"pages-only gives the same categories in {int(ok.category_agree.sum())} "
              f"({100 * ok.category_agree.mean():.0f}%), unknown in "
              f"{int((out.loc[ok.index, 'pages_only_status'] == 'unknown').sum())}")
    print(f"\nSide by side -> {OUT / 'compare_with_memory.csv'}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--tickers", nargs="+")
    p.add_argument("--compare", metavar="MEMORY_FILL_DIR")
    p.add_argument("--gold")
    p.add_argument("--model", default=ff.DEFAULT_MODEL["claude"])
    p.add_argument("--effort", choices=["low", "medium", "high"])
    args = p.parse_args()
    if args.tickers:
        fill(args.tickers, args.model, args.effort)
    if args.compare:
        compare(args.compare, args.gold)
    if not args.tickers and not args.compare:
        p.error("give --tickers, --compare or both")


if __name__ == "__main__":
    main()
