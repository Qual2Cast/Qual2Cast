"""Check GPT whole-company scope on the fixed ten source-audited cases."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

import pandas as pd

import business_split_refinement as refinement
import facets as fc
import integration_web_evidence as we
from cli_models import call_cli
from source_split_benchmark import canonical


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/gpt_scope_eval"
MODEL = "gpt-6.1-sol"
INSTRUCTIONS = """Classify the listed activities of one company as current, exited, or unknown
at the evaluation date. Use the labeled website lines as evidence, not model memory.
An activity is exited only with evidence of a completed sale or closure; an announced
future sale remains current. Group current activities by economically distinct business,
not by product name or accounting segment. Keep one company identity. The supplied GPT
description is context only and cannot support a citation. Cite exact P labels for each
decided status and group. If the evidence does not settle a status, mark it unknown.
Return only the requested JSON."""


def schema(ids: list[str]) -> dict:
    activity = {"type": "object", "additionalProperties": False,
                "required": ["business_id", "status", "cites"],
                "properties": {"business_id": {"type": "string", "enum": ids},
                               "status": {"type": "string", "enum": ["current", "exited", "unknown"]},
                               "cites": {"type": "array", "items": {"type": "string"}}}}
    group = {"type": "object", "additionalProperties": False,
             "required": ["members", "cites"],
             "properties": {"members": {"type": "array", "items": {"type": "string", "enum": ids}},
                            "cites": {"type": "array", "items": {"type": "string"}}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["activities", "groups"],
            "properties": {"activities": {"type": "array", "items": activity},
                           "groups": {"type": "array", "items": group}}}


def main() -> None:
    reference = json.loads((V1 / "business_structure_refinement/primary_source_reference.json")
                           .read_text(encoding="utf-8"))["cases"]
    snapshot = json.loads(refinement.SNAPSHOT.read_text(encoding="utf-8"))["companies"]
    universe = pd.read_csv(V1 / "universe/20261025T060358Z/universe.csv", dtype=str)
    by_ticker = universe.set_index("target_ciq_ticker")
    profiles = V1 / "facets_codex_gpt61sol/profiles"
    if len(reference) != 10:
        raise ValueError("The source benchmark must contain ten cases")
    OUT.mkdir(parents=True, exist_ok=True)

    def one(ticker: str) -> dict:
        company = by_ticker.loc[ticker]
        iq = company["IQ_COMPANY_ID"]
        profile = json.loads((profiles / f"{iq}.json").read_text(encoding="utf-8"))
        decision = snapshot[ticker]["decision"]
        activities = decision["businesses"]
        ids = [row["business_id"] for row in activities]
        record = we.record_for(iq, company["target_company_name"], company["target_ciq_website"])
        _, lines = fc.build_prompt(record, True)
        urls = {page["page_id"]: page["url"] for page in record["pages"]}
        body = "\n".join(f"[{key}] {value}" for key, value in lines.items())
        context = profile["businesses"][0]["facets"]
        prompt = (INSTRUCTIONS + "\n\nCompany: " + company["target_company_name"]
                  + "\nEvaluation date: 2026-10-28\n\nActivities to classify:\n"
                  + "\n".join(f"{row['business_id']}: {row['business']}" for row in activities)
                  + "\n\nGPT whole-company profile (uncited context):\n"
                  + str(context["offering_description"]["value"]) + "\n"
                  + str(context["primary_products"]["value"])
                  + "\n\nOfficial website lines:\n" + (body or "(none)"))
        answer_schema = schema(ids)
        key = hashlib.sha256((MODEL + "\n" + prompt + "\n"
                              + json.dumps(answer_schema, sort_keys=True)).encode("utf-8")).hexdigest()
        directory = OUT / "calls" / ticker / key[:16]
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
                return {"ticker": ticker, "status": result["llm_status"], "activities": [],
                        "groups": [], "evidence_lines": len(lines)}
            raw = json.loads(result["text"])
        found = {row["business_id"]: row for row in raw["activities"]}
        if len(found) != len(raw["activities"]) or set(found) != set(ids):
            raise ValueError(f"Invalid activity coverage: {ticker}")
        checked = []
        for business_id in ids:
            item = found[business_id]
            cites = [str(x).strip("[] ") for x in item["cites"]]
            status = item["status"] if cites and all(x in lines for x in cites) else "unknown"
            checked.append({"ticker": ticker, "business_id": business_id,
                            "status": status, "model_status": item["status"],
                            "cites": "; ".join(cites),
                            "source_urls": " | ".join(dict.fromkeys(
                                urls[x.split(".")[0]] for x in cites if x in lines))})
        current = {x["business_id"] for x in checked if x["status"] == "current"}
        groups = []
        group_cited = True
        for group in raw["groups"]:
            members = group["members"]
            cites = [str(x).strip("[] ") for x in group["cites"]]
            if not cites or not all(x in lines for x in cites):
                group_cited = False
            groups.append(members)
        flat = [x for group in groups for x in group]
        valid_groups = group_cited and len(flat) == len(set(flat)) and set(flat) == current
        return {"ticker": ticker, "status": "ok", "activities": checked,
                "groups": groups if valid_groups else [], "evidence_lines": len(lines),
                "group_cited": valid_groups}

    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, ticker) for ticker in reference]
        for number, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            print(f"[{number}/10] {result['ticker']} {result['status']}", flush=True)
    actual = pd.DataFrame([row for result in results for row in result["activities"]])
    expected = pd.DataFrame([{"ticker": ticker, "business_id": id_, "reference": status}
                             for ticker, case in reference.items()
                             for status, ids in (("current", case["current"]),
                                                 ("exited", case["exited"])) for id_ in ids])
    joined = expected.merge(actual, on=["ticker", "business_id"], how="left", validate="one_to_one")
    joined["correct"] = joined["status"].eq(joined["reference"])
    joined.to_csv(OUT / "activity_status.csv", index=False)
    group_rows = []
    for item in results:
        case = reference[item["ticker"]]
        if "groups" not in case:
            continue
        covered = set(actual.loc[(actual["ticker"] == item["ticker"]) &
                                 actual["status"].eq("current"), "business_id"])
        known = covered == set(case["current"])
        group_rows.append({"ticker": item["ticker"], "reference_groups": json.dumps(case["groups"]),
                           "predicted_groups": json.dumps(item["groups"]),
                           "exact": bool(known and item["groups"] and
                                         canonical(item["groups"]) == canonical(case["groups"]))})
    groups = pd.DataFrame(group_rows)
    groups.to_csv(OUT / "group_partitions.csv", index=False)
    evidence_rows = []
    for ticker, case in reference.items():
        company = by_ticker.loc[ticker]
        record = we.record_for(company["IQ_COMPANY_ID"], company["target_company_name"],
                               company["target_ciq_website"])
        available = {page["url"].rstrip("/") for page in record["pages"]}
        expected_urls = {url.rstrip("/") for url in case["sources"]}
        evidence_rows.append({"ticker": ticker, "saved_site_lines": len(fc.build_prompt(record, True)[1]),
                              "reference_pages_available": len(available & expected_urls),
                              "reference_pages_total": len(expected_urls)})
    evidence = pd.DataFrame(evidence_rows)
    evidence.to_csv(OUT / "evidence_overlap.csv", index=False)
    summary = {"model": MODEL, "cases": len(results), "activity_labels": len(joined),
               "activity_decided": int(joined["status"].isin(["current", "exited"]).sum()),
               "activity_correct_strict": int(joined["correct"].sum()),
               "group_reference_cases": len(groups), "group_exact_strict": int(groups["exact"].sum()),
               "cases_with_reference_page_in_input": int(evidence["reference_pages_available"].gt(0).sum()),
               "interpretation": "targeted diagnostic; unknown and unsupported decisions count as failures"}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
