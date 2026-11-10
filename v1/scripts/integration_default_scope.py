"""Promote the source-reviewed Sonnet scope to the integration default."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from integration_scope_exception_sensitivity import INPUTS, OVERRIDES


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration"
OUT = BASE / "source_reviewed_default"
FACETS = OUT / "facets.csv"
DATED_REMOVALS = (
    ("ENSG", "revenue_model", "assisted living, home health and hospice",
     "assisted living",
     "https://investor.ensigngroup.net/news/news-details/2019/The-Ensign-Group-Inc.-Announces-Record-and-Distribution-Dates-for-Pennant-Spin-Off-08-28-2019/default.aspx"),
    ("ENSG", "value_chain_position", "rehabilitation, home health and hospice services",
     "rehabilitation services",
     "https://investor.ensigngroup.net/news/news-details/2019/The-Ensign-Group-Inc.-Announces-Record-and-Distribution-Dates-for-Pennant-Spin-Off-08-28-2019/default.aspx"),
    ("SKIL", "revenue_model", "service fees: instructor-led training, coaching and professional services",
     "service fees: coaching and professional services; reseller revenue sharing with Global Knowledge",
     "https://investor.skillsoft.com/sec-filings/all-sec-filings/content/0001437749-26-017991/ex_965969.htm"),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    original = pd.read_csv(INPUTS["Sonnet dated"], dtype=str).fillna("")
    cited = pd.read_csv(INPUTS["GPT cited"], dtype=str).fillna("")
    evidence = pd.read_csv(BASE / "gpt_scope_alignment/source_exceptions.csv", dtype=str)
    if len(original) != 533 or len(cited) != 533:
        raise ValueError("Expected one complete, fixed 533-company universe")
    if original["IQ_COMPANY_ID"].duplicated().any() or cited["IQ_COMPANY_ID"].duplicated().any():
        raise ValueError("Duplicate company identifiers")
    if set(original["IQ_COMPANY_ID"]) != set(cited["IQ_COMPANY_ID"]):
        raise ValueError("Facet universes differ")
    reviewed = original.set_index("IQ_COMPANY_ID")
    cited = cited.set_index("IQ_COMPANY_ID")
    changes = []
    for ticker, fields in OVERRIDES["Sonnet source exceptions"].items():
        row = evidence.loc[evidence["ticker"].eq(ticker)].squeeze()
        if row["decision"] != "retain_current_business":
            raise ValueError(f"Unsupported default correction: {ticker}")
        company = row["company_id"]
        for field in fields:
            replacement = cited.at[company, field]
            if cited.at[company, f"{field}_status"] != "filled" or not replacement:
                raise ValueError(f"Missing cited field: {ticker} {field}")
            changes.append({"ticker": ticker, "IQ_COMPANY_ID": company, "facet": field,
                            "before": reviewed.at[company, field], "after": replacement,
                            "primary_source": row["url"]})
            reviewed.at[company, field] = replacement
            reviewed.at[company, f"{field}_status"] = "filled"
            reviewed.at[company, f"{field}_source"] = cited.at[company, f"{field}_source"]
    for ticker, field, old, new, url in DATED_REMOVALS:
        row = evidence.loc[evidence["ticker"].eq(ticker)].squeeze()
        company = row["company_id"]
        before = reviewed.at[company, field]
        if before.count(old) != 1:
            raise ValueError(f"Expected one dated phrase for {ticker} {field}")
        after = before.replace(old, new)
        reviewed.at[company, field] = after
        reviewed.at[company, f"{field}_source"] = url
        changes.append({"ticker": ticker, "IQ_COMPANY_ID": company, "facet": field,
                        "before": before, "after": after, "primary_source": url})
    if len(changes) != 10:
        raise ValueError("Unexpected number of source-reviewed changes")
    if any(row["before"] == row["after"] for row in changes):
        raise ValueError("A recorded correction did not change the field")
    if "outpatient medical" not in reviewed.at["IQ223781219", "offering_description"].lower():
        raise ValueError("The remaining outpatient business was lost")
    ensign = reviewed.loc["IQ4295645"]
    if "assisted living" not in ensign["primary_services"].lower():
        raise ValueError("The retained senior-living business was lost")
    if "real estate" not in ensign["revenue_model"].lower():
        raise ValueError("Ensign's property business was lost")
    if any("home health" in value.lower() or "hospice" in value.lower()
           for value in ensign.values if isinstance(value, str)):
        raise ValueError("Ensign's divested activities reappeared")
    timken = reviewed.loc["IQ308582"]
    if any("belt" in timken[field].lower() for field in
           ("offering_description", "primary_products", "specialization")):
        raise ValueError("The divested belts business reappeared")
    skillsoft = reviewed.loc["IQ620407835"]
    if "reseller revenue sharing" not in skillsoft["revenue_model"].lower() or any(
            "instructor-led" in skillsoft[field].lower() for field in
            ("offering_description", "primary_services", "specialization")):
        raise ValueError("Skillsoft ownership and partner access were conflated")
    original_indexed = original.set_index("IQ_COMPANY_ID")
    regression_fields = ("customer_segment", "revenue_model", "value_chain_position",
                         "geography_served", "distribution_channels")
    if any(not reviewed[f"{field}_{suffix}"].equals(
            original_indexed[f"{field}_{suffix}"])
            for field in regression_fields for suffix in ("category", "status")):
        raise ValueError("Regression categories changed and require a model refit")
    OUT.mkdir(parents=True, exist_ok=True)
    reviewed.reset_index().to_csv(FACETS, index=False)
    pd.DataFrame(changes).to_csv(OUT / "changes.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "status": "default for the integrated v1 experiment",
        "company_count": len(reviewed), "reviewed_companies": ["HLTC", "ENSG", "SKIL"],
        "reviewed_fields": len(changes),
        "already_current_in_sonnet": ["TKR"],
        "base_sha256": digest(INPUTS["Sonnet dated"]),
        "cited_sha256": digest(INPUTS["GPT cited"]),
        "facets_sha256": digest(FACETS),
        "regression_categories_unchanged": True,
        "scope": "Only four dated source exceptions were reviewed; this is not a 533-company factual audit.",
    }, indent=2), encoding="utf-8")
    print(f"Default scope: {len(reviewed)} firms, {len(changes)} reviewed fields")


if __name__ == "__main__":
    main()
