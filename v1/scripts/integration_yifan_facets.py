"""Fill Yifan's Orbis-aligned qualitative schema from saved company websites."""

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
import integration_web_evidence as we


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/yifan_facets"
CROSSWALK = V1 / "integration/fields/yifan_facet_crosswalk.csv"
MODEL = "gpt-6.1-sol"
VERSION = "yifan-orbis-qualitative-2026-11-09a"


def definitions() -> list[dict]:
    rows = pd.read_csv(CROSSWALK, dtype=str).fillna("")
    fields = rows[rows["orbis_filled_by"].eq("LLM")]
    if len(fields) != 11:
        raise ValueError("Yifan's qualitative field list changed")
    return [{"name": row.orbis_facet.lower().replace("-", "_").replace(" ", "_"),
             "label": row.orbis_facet, "question": row.orbis_question,
             "allowed": row.orbis_allowed_values}
            for row in fields.itertuples(index=False)]


def answer_schema(fields: list[dict]) -> dict:
    item = {"type": "object", "additionalProperties": False,
            "required": ["status", "value", "cites"],
            "properties": {"status": {"type": "string", "enum": ["stated", "unknown", "not_applicable"]},
                           "value": {"type": "string"},
                           "cites": {"type": "array", "items": {"type": "string"}}}}
    return {"type": "object", "additionalProperties": False,
            "required": [f["name"] for f in fields],
            "properties": {f["name"]: item for f in fields}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError("workers must be between 1 and 4")
    _, ids, _, _ = b3.read_inputs()
    if args.limit:
        ids = ids[:args.limit]
    universe = pd.read_csv(V1 / "universe/20261025T060358Z/universe.csv",
                           dtype=str).set_index("IQ_COMPANY_ID")
    fields = definitions()
    schema = answer_schema(fields)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    instructions = "\n".join(
        ["Describe the current company as a whole using only the labeled lines from its own website.",
         "List all material operations; a product range serving the same general business is not a separate company.",
         "Use 'customer type' for the direct payer, not the ultimate user.",
         "For each stated field give one or two exact P labels that support it. If the lines do not",
         "support a field, return unknown and an empty value and citation list. Do not infer from",
         "the company name or outside knowledge. No financial figures or listed-company inputs.",
         "Fields:"] + [f"- {f['name']}: {f['question']} Allowed: {f['allowed']}"
                        for f in fields])
    stopped = threading.Event()

    def one(iq: str) -> dict:
        if stopped.is_set():
            return {"IQ_COMPANY_ID": iq, "status": "not_run", "values": {}}
        r = universe.loc[iq]
        record = we.record_for(iq, r["target_company_name"], r["target_ciq_website"])
        _, lines = fc.build_prompt(record, True)
        if not lines:
            return {"IQ_COMPANY_ID": iq, "status": "no_saved_evidence", "values": {}}
        note = ("\nSome lines are official-site search snippets, not full pages; leave unsupported fields unknown."
                if "search_snippet" in record["status"] else "")
        prompt = (instructions + note + f"\n\nCompany: {r['target_company_name']}\n"
                  + f"Website: {r['target_ciq_website']}\n\n"
                  + "\n".join(f"[{key}] {value}" for key, value in lines.items()))
        fingerprint = hashlib.sha256((MODEL + "\n" + VERSION + "\n" + prompt + "\n"
                                      + json.dumps(schema, sort_keys=True)).encode("utf-8")).hexdigest()
        run_dir = OUT / "runs" / iq / fingerprint[:16]
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        saved = run_dir / "response.json"
        if saved.exists():
            raw = json.loads(saved.read_text(encoding="utf-8"))
        else:
            from cli_models import call_cli
            result = call_cli(prompt, run_dir, schema, "codex", model=MODEL, timeout=600)
            (run_dir / "run.json").write_text(json.dumps({
                "model": MODEL, "version": VERSION, "fingerprint": fingerprint,
                "status": result["llm_status"], "usage": result.get("usage", {}),
                "seconds": result.get("seconds"), "error": result.get("error", ""),
            }, indent=2), encoding="utf-8")
            if result["llm_status"] != "ok":
                if result.get("stop_run"):
                    stopped.set()
                return {"IQ_COMPANY_ID": iq, "status": result["llm_status"], "values": {}}
            raw = json.loads(result["text"])
        values = {}
        for f in fields:
            item = raw[f["name"]]
            cited = [str(x).strip("[] ") for x in item["cites"]]
            supported = bool(cited) and all(x in lines for x in cited)
            status = item["status"]
            value = item["value"].strip()
            if status == "stated" and not supported:
                status, value = "unknown", ""
            if status == "stated" and f["allowed"] not in ("Free text list", "Free text, 15 words or fewer"):
                choices = [x.strip() for x in f["allowed"].split(" / ")]
                if value not in choices:
                    status, value = "unknown", ""
            values[f["name"]] = {"status": status, "value": value,
                                  "cites": cited if status == "stated" else []}
        return {"IQ_COMPANY_ID": iq, "status": "ok", "values": values,
                "fingerprint": fingerprint}

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(one, iq): iq for iq in ids}
        for number, future in enumerate(as_completed(futures), 1):
            row = future.result()
            results.append(row)
            print(f"[{number}/{len(ids)}] {row['IQ_COMPANY_ID']} {row['status']}", flush=True)
    rows = []
    for item in results:
        row = {"IQ_COMPANY_ID": item["IQ_COMPANY_ID"], "llm_status": item["status"],
               "prompt_version": VERSION, "business_id": "B1"}
        for f in fields:
            value = item["values"].get(f["name"], {"status": "unknown", "value": "", "cites": []})
            row[f["name"]] = value["value"]
            row[f"{f['name']}_status"] = value["status"]
            row[f"{f['name']}_cites"] = "; ".join(value["cites"])
        rows.append(row)
    table = pd.DataFrame(rows).set_index("IQ_COMPANY_ID").reindex(ids).reset_index()
    table.to_csv(OUT / "facets.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "model": MODEL, "version": VERSION, "companies": len(ids),
        "workers": args.workers,
        "status_counts": table["llm_status"].value_counts().to_dict(),
        "source": str(CROSSWALK), "source_sha256": hashlib.sha256(CROSSWALK.read_bytes()).hexdigest(),
        "field_count": len(fields), "input": "saved public website lines, no financials",
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
