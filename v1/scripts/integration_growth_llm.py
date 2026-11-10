"""Evaluate the existing growth LLM and hybrid stages on saved event labels."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pre-v0"))
sys.path.insert(0, str(ROOT / "v1/scripts"))
from growth_signals.stage import GrowthStage  # noqa: E402
from growth_signals.eval.score_rules import DEFAULT_DIR, SETS  # noqa: E402
from growth_signals.build_features import FEATURE_NAMES, build_company_features  # noqa: E402
from growth_signals.schema import Event  # noqa: E402
from cli_models import call_cli  # noqa: E402

OUT = ROOT / "outputs-local/v1/integration/growth_llm"


class CodexGrowthModel:
    def __init__(self, model: str):
        self.model = model

    def complete(self, stage: str, payload: dict, schema: dict, instructions: str) -> dict:
        if not payload.get("sentences"):
            return {"status": "ok", "data": {"events": []}, "request_id": "empty_page"}
        prompt = instructions + "\n\nInput:\n" + json.dumps(payload, ensure_ascii=False)
        key = hashlib.sha256(json.dumps({"model": self.model, "stage": stage,
            "prompt": prompt, "schema": schema}, sort_keys=True).encode("utf-8")).hexdigest()
        directory = OUT / "calls" / key
        saved = directory / "response.json"
        if saved.exists():
            return {"status": "ok", "data": json.loads(saved.read_text(encoding="utf-8")),
                    "request_id": key}
        result = call_cli(prompt, directory, schema, backend="codex", model=self.model,
                          timeout=600)
        if result["llm_status"] != "ok":
            return {"status": result["llm_status"], "data": None, "request_id": key}
        return {"status": "ok", "data": json.loads(result["text"]), "request_id": key}


def score(events: list[dict], labels: dict, records: dict) -> list[dict]:
    truth, border, predicted = set(), set(), set()
    for company_id, label in labels.items():
        if company_id.startswith("_"):
            continue
        truth |= {(company_id, page, kind) for page, kinds in label["truth"].items() for kind in kinds}
        border |= {(company_id, page, kind) for page, kind in label.get("borderline", [])}
    for event in events:
        company_id = event["IQ_COMPANY_ID"]
        page_of = {p["source_url"]: p["page_id"] for p in records[company_id]["pages"]}
        if event["source_url"] in page_of:
            predicted.add((company_id, page_of[event["source_url"]], event["event_type"]))
    predicted -= border
    rows = []
    for kind in sorted({x[2] for x in truth | predicted}) + ["ALL"]:
        found = {x for x in predicted if kind in ("ALL", x[2])}
        actual = {x for x in truth if kind in ("ALL", x[2])}
        correct = len(found & actual)
        rows.append({"event_type": kind, "predicted": len(found), "true": len(actual),
                     "correct": correct, "precision": correct / len(found) if found else None,
                     "recall": correct / len(actual) if actual else None})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=SETS, default="holdout_c")
    parser.add_argument("--model", default="gpt-6.1-sol")
    args = parser.parse_args()
    labels = json.loads((DEFAULT_DIR / f"labels_{args.set}.json").read_text(encoding="utf-8"))
    folder = DEFAULT_DIR / "records" / args.set
    records = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in folder.glob("*.json")}
    stage = GrowthStage(llm=CodexGrowthModel(args.model))
    rows, all_events, audits = [], {}, {}
    rule_events = []
    for company_id, record in records.items():
        result = GrowthStage().run(record, method="rules", cutoff="2026-10-19",
                                   target_mode="public_benchmark",
                                   require_capture_by_cutoff=True)
        rule_events.extend(result["events"])
    all_events["rules"] = rule_events
    for method in ("llm", "hybrid"):
        events = []
        for company_id, record in records.items():
            result = stage.run(record, method=method, cutoff="2026-10-19",
                               target_mode="public_benchmark", require_capture_by_cutoff=True)
            events.extend(result["events"])
            audits[f"{method}:{company_id}"] = {"status": result["status"],
                "eligible_pages": result.get("eligible_pages", 0)}
            print(f"{method} {company_id} {result['status']}", flush=True)
        all_events[method] = events
        rows.extend({"cohort": args.set, "method": method, **item}
                    for item in score(events, labels, records))
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / f"{args.set}_metrics.csv", index=False)
    (OUT / f"{args.set}_events.json").write_text(json.dumps(all_events, indent=2), encoding="utf-8")
    (OUT / f"{args.set}_audit.json").write_text(json.dumps(audits, indent=2), encoding="utf-8")
    features = []
    for method, events in all_events.items():
        captured = [Event.from_dict(event) for event in events
                    if event["retrieved_at"][:10] <= "2026-10-19"]
        by_id = {row["IQ_COMPANY_ID"]: row for row in
                 build_company_features(captured, date(2026, 10, 19))}
        for company_id, record in records.items():
            row = by_id.get(company_id)
            if row is None:
                row = {name: ("" if name.startswith("mean_confidence_") else 0)
                       for name in FEATURE_NAMES}
                row.update(IQ_COMPANY_ID=company_id, company_name=record["company_name"],
                           cutoff_date="2026-10-19")
            features.append({"method": method, **row})
    pd.DataFrame(features).to_csv(OUT / f"{args.set}_features.csv", index=False)
    print(pd.DataFrame(rows).query("event_type == 'ALL'").to_string(index=False))


if __name__ == "__main__":
    main()
