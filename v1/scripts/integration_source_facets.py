"""Fill one whole-company profile per firm using cited saved website evidence."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import threading

import pandas as pd

import b3_facet_add_drop as b3
import facets as fc
import fill_facets as ff
import integration_web_evidence as we


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "facets_source_gpt61sol"
MODEL = "gpt-6.1-sol"
PREFIX = """Source-constrained run: use only the labeled website lines below. Do not use model
memory, company-name inference or uncited facts. A filled facet must have a
supporting citation. Describe all material current operations as one company;
exclude a business only if its sale or closure is established in the evidence.
If the saved pages do not support a field, mark it unknown.\n\n"""
KNOWLEDGE = ('First, say whether you know this company: set "knows_company" to true only if you '
             'recognize this specific company from what you already know. Either way, describe it: '
             "if you don't know it, use only the website pages. Do not guess anything from the "
             "company's name, its web address, or what is typical for companies with similar "
             'names; a facet the pages don\'t support is "unknown".')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--tail-count", type=int)
    parser.add_argument("--profiles-only", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError("workers must be between 1 and 4")
    _, ids, _, _ = b3.read_inputs()
    if args.limit:
        ids = ids[:args.limit]
    if args.tail_count:
        if not args.profiles_only or not 1 <= args.tail_count < len(ids):
            raise ValueError("A tail partition requires --profiles-only")
        ids = ids[-args.tail_count:]
    source = pd.read_csv(V1 / "universe/20261025T060358Z/universe.csv",
                         dtype=str).set_index("IQ_COMPANY_ID")
    out = ff.output_paths(OUT)
    out.profiles.mkdir(parents=True, exist_ok=True)
    schema = fc.answer_schema(True)
    schema_path = OUT / "answer_schema_with_pages.json"
    schema_path.write_text(json.dumps(schema, indent=1), encoding="utf-8")
    stopped = threading.Event()

    def one(iq: str) -> dict:
        if stopped.is_set():
            return {"IQ_COMPANY_ID": iq, "status": "not_run"}
        r = source.loc[iq]
        record = we.record_for(iq, r["target_company_name"], r["target_ciq_website"])
        original, lines = fc.build_prompt(record, True)
        if not lines:
            return {"IQ_COMPANY_ID": iq, "status": "no_saved_evidence"}
        if KNOWLEDGE not in original:
            raise ValueError("The general-facet prompt changed; review its source-only rewrite")
        mode_note = ("Some labeled lines are official-site search snippets, not full pages. "
                     "Treat unmentioned fields as unknown.\n\n"
                     if "search_snippet" in record["status"] else "")
        prompt = PREFIX + mode_note + original.replace(
            KNOWLEDGE,
            'Set "knows_company" to false for this source-only run. Describe the company '
            'only from the labeled website lines; unsupported facts are unknown.').replace(
            "Use what you know about the company, and the website pages.",
            "Use only the labeled website-page lines.").replace(
            "For a company you know, fill every facet you can.",
            "Fill only facets supported by the labeled website-page lines.").replace(
            "A facet you fill from what you already know about the company gets no citation.",
            "Do not fill a facet from model knowledge; every filled facet needs a citation.").replace(
            "If you are not sure of a detail, give your best description of this company and say "
            'what is uncertain in "notes".',
            'If a detail is unsupported by the labeled lines, mark it unknown and note the gap.')
        fingerprint = hashlib.sha256((MODEL + "\n" + prompt + "\n"
                                      + json.dumps(schema, sort_keys=True)).encode("utf-8")).hexdigest()
        path = out.profiles / f"{iq}.json"
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("fingerprint") == fingerprint and saved.get("llm_status") == "ok":
                return {"IQ_COMPANY_ID": iq, "status": "current"}
        run_dir = out.codex_runs / iq / fingerprint[:16]
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        response_path = run_dir / "response.json"
        if response_path.exists():
            raw = json.loads(response_path.read_text(encoding="utf-8"))
            status = "ok"
        else:
            from cli_models import call_cli
            result = call_cli(prompt, run_dir, schema, "codex", model=MODEL,
                              timeout=600)
            status = result["llm_status"]
            (run_dir / "run.json").write_text(json.dumps({
                "model": MODEL, "backend": "codex", "status": status,
                "fingerprint": fingerprint, "prompt_version": fc.PROMPT_VERSION,
                "usage": result.get("usage", {}), "seconds": result.get("seconds"),
                "error": result.get("error", ""),
            }, indent=2), encoding="utf-8")
            if status != "ok":
                if result.get("stop_run"):
                    stopped.set()
                return {"IQ_COMPANY_ID": iq, "status": status,
                        "error": result.get("error", "")}
            raw = json.loads(result["text"])
        answer = fc.check_answer(raw, lines, {p["page_id"]: p["url"] for p in record["pages"]})
        unsupported = []
        for business in answer["businesses"]:
            for name, facet in business["facets"].items():
                if facet["status"] != "filled":
                    continue
                if not any(q["quote_found"] and q["url"] for q in facet["quotes"]):
                    unsupported.append(name)
                    facet.update(status="unknown", value="", category="", source=[], quotes=[],
                                 flags=[*facet["flags"], "no_cited_website_line"])
        profile = {
            "IQ_COMPANY_ID": iq, "company_name": r["target_company_name"],
            "website": r["target_ciq_website"], "with_pages": True,
            "evidence_mode": record["status"],
            "model": MODEL, "prompt_version": fc.PROMPT_VERSION,
            "fingerprint": fingerprint, "llm_status": status,
            "input_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "llm_run_dir": run_dir.relative_to(OUT).as_posix(),
            "created_at": ff.now_iso(),
            "businesses": answer["businesses"], "knows_company": answer["knows_company"],
            "issues": answer["issues"], "notes": answer["notes"],
            "unsupported_facets": unsupported,
            "divestiture_lines": fc.divestiture_lines(lines),
        }
        path.write_text(json.dumps(profile, indent=1, ensure_ascii=False), encoding="utf-8")
        return {"IQ_COMPANY_ID": iq, "status": status, "cited_facets":
                sum(f["status"] == "filled" for f in profile["businesses"][0]["facets"].values()),
                "unsupported_facets": len(unsupported)}

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(one, iq): iq for iq in ids}
        for number, future in enumerate(as_completed(futures), 1):
            row = future.result()
            rows.append(row)
            print(f"[{number}/{len(ids)}] {row['IQ_COMPANY_ID']} {row['status']}", flush=True)
    if args.profiles_only:
        return
    pd.DataFrame(rows).to_csv(OUT / "audit.csv", index=False)
    ff.write_tables(OUT)
    (OUT / "run.json").write_text(json.dumps({
        "model": MODEL, "prompt_version": fc.PROMPT_VERSION,
        "source_mode": "saved website lines only, cited fields retained",
        "workers": args.workers,
        "companies": len(ids), "status_counts": pd.DataFrame(rows)["status"].value_counts().to_dict(),
        "prompt_prefix_sha256": hashlib.sha256(PREFIX.encode("utf-8")).hexdigest(),
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
