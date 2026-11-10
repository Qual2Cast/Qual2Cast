"""Check whether fresh GPT fields repeat activities removed by Yiming's dated review."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

import pandas as pd

from holdout_llm_routes import checked_call


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
BASE = V1 / "integration"
OUT = BASE / "gpt_scope_alignment"
MODEL = "gpt-6.1-sol"
PROMPT = """Compare each fresh GPT company field with a dated correction to a different model's field.
The corrected text is the reference for which business activity remains current. Decide only whether
the fresh GPT field repeats a business activity removed or replaced by that correction. Different
wording, omissions, and harmless extra detail do not imply an outdated activity. If the change is
ambiguous, answer uncertain. Do not infer current activities from model memory. Return every row ID.

"""
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["rows"],
          "properties": {"rows": {"type": "array", "items": {
              "type": "object", "additionalProperties": False,
              "required": ["id", "status", "reason"],
              "properties": {"id": {"type": "string"},
                             "status": {"type": "string", "enum": ["aligned", "outdated", "uncertain"]},
                             "reason": {"type": "string"}}}}}}
STRICT_PROMPT = """Check whether each fresh field explicitly attributes a completed divested business to the current company.
The listed divestitures were confirmed by the team's dated source review. A broad sector, customer market,
or related product is insufficient to prove that the sold operation is still included. Treat distinct
retained operations separately. Classify each of the two fresh fields as specific_outdated,
not_specific, or unclear. Do not assume a broad term refers to the divested operation.
"""
STRICT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["rows"],
                 "properties": {"rows": {"type": "array", "items": {
                     "type": "object", "additionalProperties": False,
                     "required": ["id", "general", "cited", "reason"],
                     "properties": {"id": {"type": "string"},
                                    "general": {"type": "string", "enum": ["specific_outdated", "not_specific", "unclear"]},
                                    "cited": {"type": "string", "enum": ["specific_outdated", "not_specific", "unclear"]},
                                    "reason": {"type": "string"}}}}}}


def main() -> None:
    changes_path = BASE / "sources/yiming_corrections.csv"
    general_path = V1 / "facets_codex_gpt61sol/tables/facets.csv"
    cited_path = V1 / "facets_source_gpt61sol/tables/facets.csv"
    changes = pd.read_csv(changes_path, dtype=str).fillna("")
    changes = changes[changes["applied"].eq("True")].reset_index(drop=True)
    general = pd.read_csv(general_path, dtype=str).fillna("").set_index("IQ_COMPANY_ID")
    cited = pd.read_csv(cited_path, dtype=str).fillna("").set_index("IQ_COMPANY_ID")
    if len(changes) != 116 or changes["IQ_COMPANY_ID"].nunique() != 42:
        raise ValueError("The dated correction set changed")
    inputs = []
    for index, row in changes.iterrows():
        iq, field = row["IQ_COMPANY_ID"], row["facet"]
        inputs.append({"id": f"R{index:03d}", "ticker": row["ticker"],
                       "IQ_COMPANY_ID": iq, "facet": field, "old": row["old"],
                       "new": row["new"], "gpt_general": general.at[iq, field],
                       "gpt_cited": cited.at[iq, field]})
    batches = [inputs[start:start+10] for start in range(0, len(inputs), 10)]
    OUT.mkdir(parents=True, exist_ok=True)

    def one(batch_number: int, batch: list[dict]) -> list[dict]:
        prompt = PROMPT + "\n\n".join(
            f"{item['id']} {item['ticker']} {item['facet']}\n"
            f"Original: {item['old']}\nCorrected: {item['new']}\n"
            f"Fresh GPT: {item['gpt_general']}" for item in batch)
        raw = checked_call(prompt, SCHEMA, OUT / "calls" / f"{batch_number:02d}", MODEL)
        found = {item["id"]: item for item in raw["rows"]}
        expected = {item["id"] for item in batch}
        if len(found) != len(raw["rows"]) or set(found) != expected:
            raise ValueError(f"Incomplete scope audit batch {batch_number}")
        return [{**item, "status": found[item["id"]]["status"],
                 "reason": found[item["id"]]["reason"]} for item in batch]

    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, index, batch) for index, batch in enumerate(batches, 1)]
        for number, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.extend(result)
            print(f"scope batch {number}/{len(batches)}: {len(result)} fields", flush=True)
    table = pd.DataFrame(results).sort_values("id")
    table.to_csv(OUT / "alignment.csv", index=False)
    exits = pd.read_csv(BASE / "sources/yiming_exits.csv", dtype=str).fillna("")
    exits = exits[exits["confirmed"].eq("True")]
    flagged = table[table["status"].ne("aligned")].to_dict("records")
    strict_batches = [flagged[start:start+8] for start in range(0, len(flagged), 8)]

    def strict_one(batch_number: int, batch: list[dict]) -> list[dict]:
        blocks = []
        for item in batch:
            sold = exits[exits["ticker"].eq(item["ticker"])]
            businesses = "; ".join(f"{row.business} ({row.date})" for row in sold.itertuples())
            blocks.append(f"{item['id']} {item['ticker']} {item['facet']}\n"
                          f"Confirmed sales: {businesses}\nCorrected reference: {item['new']}\n"
                          f"Fresh general: {item['gpt_general']}\nFresh source-cited: {item['gpt_cited']}")
        raw = checked_call(STRICT_PROMPT + "\n\n".join(blocks), STRICT_SCHEMA,
                           OUT / "calls/strict" / f"{batch_number:02d}", MODEL)
        found = {row["id"]: row for row in raw["rows"]}
        if len(found) != len(raw["rows"]) or set(found) != {row["id"] for row in batch}:
            raise ValueError(f"Incomplete strict audit batch {batch_number}")
        return [{"id": row["id"], **found[row["id"]]} for row in batch]

    strict_rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(strict_one, number, batch)
                   for number, batch in enumerate(strict_batches, 1)]
        for future in as_completed(futures):
            strict_rows.extend(future.result())
    strict = table.merge(pd.DataFrame(strict_rows), on="id", how="left", validate="one_to_one")
    strict.to_csv(OUT / "specificity.csv", index=False)
    summary = {"model": MODEL, "companies": 42, "corrected_fields": len(table),
               "status_counts": table["status"].value_counts().to_dict(),
               "strict_general_counts": strict["general"].value_counts().to_dict(),
               "strict_cited_counts": strict["cited"].value_counts().to_dict(),
               "corrections_sha256": hashlib.sha256(changes_path.read_bytes()).hexdigest(),
               "general_sha256": hashlib.sha256(general_path.read_bytes()).hexdigest(),
               "cited_sha256": hashlib.sha256(cited_path.read_bytes()).hexdigest(),
               "interpretation": "Semantic comparison to teammate's dated edits; source evidence remains evaluated separately. Uncertain is not a corrected field."}
    (OUT / "run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(table[~table["status"].eq("aligned")][["ticker", "facet", "status", "reason"]].to_string(index=False))


if __name__ == "__main__":
    main()
