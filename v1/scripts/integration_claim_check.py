"""Check new general facet claims against retrieved company-site passages."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

import facets as fc
import integration_web_evidence as we
from cli_models import call_cli


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/claim_check"
FACETS = V1 / "facets_codex_gpt61sol/tables/facets.csv"
LABELS = V1 / "gold_labels/source/facet_gold_labels - Labels.csv"
MODEL = "gpt-6.1-sol"
sys.path.insert(0, str(ROOT / "v1/scripts/verification"))
import evidence as evm  # noqa: E402
import verify_with_evidence as verify  # noqa: E402


def site_evidence(iq: str, name: str, website: str) -> evm.Evidence:
    record = we.record_for(iq, name, website)
    _, lines = fc.build_prompt(record, True)
    sources = {page["page_id"]: {"url": page["url"], "type": "company_site",
                                  "title": page["title"], "date": ""}
               for page in record["pages"]}
    return evm.Evidence(iq, name, website, lines=lines, sources=sources)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--facets", type=Path, default=FACETS)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    output = args.out
    filled = pd.read_csv(args.facets, dtype=str).fillna("")
    filled = filled[(filled["business_id"] == "B1") & (filled["llm_status"] == "ok")]
    if filled["IQ_COMPANY_ID"].duplicated().any() or filled["IQ_COMPANY_ID"].nunique() != 533:
        raise ValueError("The GPT general run must contain all 533 companies")
    universe = pd.read_csv(V1 / "universe/20261025T060358Z/universe.csv", dtype=str)
    companies = universe.merge(filled, on="IQ_COMPANY_ID", validate="one_to_one",
                               suffixes=("", "_facet"))
    if not companies["target_company_name"].eq(companies["target_company_name_facet"]).all():
        raise ValueError("Universe and facet company names disagree")
    tickers = set(pd.read_csv(LABELS, dtype=str)["ticker"])
    cohort = companies[companies["target_ciq_ticker"].isin(tickers)].copy()
    if cohort["target_ciq_ticker"].nunique() != 40:
        raise ValueError("The historical 40-company review cohort has changed")
    if args.limit:
        cohort = cohort.head(args.limit)
    output.mkdir(parents=True, exist_ok=True)

    def one(row: pd.Series) -> dict:
        iq = row["IQ_COMPANY_ID"]
        ev = site_evidence(iq, row["target_company_name"], row["target_ciq_website"])
        prompt, lines = verify.build_prompt(row, ev, "R", retriever="bm25")
        answer_schema = verify.schema()
        key = hashlib.sha256((MODEL + "\n" + verify.PROMPT_VERSION + "\n" + prompt + "\n"
                              + json.dumps(answer_schema, sort_keys=True)).encode()).hexdigest()
        directory = output / "calls" / iq / key[:16]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
        saved = directory / "response.json"
        if saved.exists():
            raw = json.loads(saved.read_text(encoding="utf-8"))
        else:
            result = call_cli(prompt, directory, answer_schema, "codex", model=MODEL, timeout=600)
            (directory / "run.json").write_text(json.dumps({
                "model": MODEL, "fingerprint": key, "status": result["llm_status"],
                "usage": result.get("usage", {}), "seconds": result.get("seconds"),
                "error": result.get("error", ""),
            }, indent=2), encoding="utf-8")
            if result["llm_status"] != "ok":
                return {"IQ_COMPANY_ID": iq, "ticker": row["target_ciq_ticker"],
                        "status": result["llm_status"], "checks": []}
            raw = json.loads(result["text"])
        checked = verify.apply_rules(raw, lines, ev)
        return {"IQ_COMPANY_ID": iq, "ticker": row["target_ciq_ticker"],
                "status": "ok", "checks": checked, "evidence_lines": len(lines),
                "fingerprint": key}

    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, row) for _, row in cohort.iterrows()]
        for number, future in enumerate(as_completed(futures), 1):
            item = future.result()
            results.append(item)
            print(f"[{number}/{len(cohort)}] {item['ticker']} {item['status']}", flush=True)
    checks = pd.DataFrame([{k: v for k, v in item.items() if k != "checks"} | check
                           for item in results for check in item["checks"]])
    checks.to_csv(output / "verdicts.csv", index=False)
    audit = pd.DataFrame([{k: v for k, v in item.items() if k != "checks"} for item in results])
    audit.to_csv(output / "audit.csv", index=False)
    (output / "run.json").write_text(json.dumps({
        "model": MODEL, "companies": len(cohort), "facets_expected": 12 * len(cohort),
        "facets_checked": len(checks), "status_counts": audit["status"].value_counts().to_dict(),
        "facet_source": str(args.facets),
        "evidence": "saved company-site lines; tier-R BM25 retrieval; no reviewer grades in prompts",
        "interpretation": "verifier verdicts are diagnostic, not independent human truth",
    }, indent=2), encoding="utf-8")
    if not checks.empty:
        print(checks["verdict"].value_counts().to_string())


if __name__ == "__main__":
    main()
