"""Align shared Orbis facet definitions and WRDS ratios to the frozen v1 pool."""

from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

import sectors


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
SOURCES = V1 / "integration/sources"
OUT = V1 / "integration/fields"


FACET_MAP = {
    "Primary offering": ("offering_description", "partial", "Yifan limits text to 15 words; v1 has a broader whole-company description"),
    "Offering type": ("", "separate", "Product/service/mixed is not a dedicated v1 field"),
    "Revenue model": ("revenue_model", "partial", "Yifan uses one categorical payer mechanism; v1 allows several and adds detail"),
    "Customer type": ("customer_segment", "partial", "Yifan asks who pays directly; v1 may describe users or buyers"),
    "End markets": ("end_markets", "partial", "Related concept with different extraction format"),
    "Value-chain role": ("value_chain_position", "partial", "Yifan's categories differ from v1's"),
    "Sales channel": ("distribution_channels", "partial", "Related route to customer; category set differs"),
    "Diversification": ("", "separate", "One versus multiple segments is not the same as v1 specialization"),
    "Geographic reach": ("geography_served", "partial", "Yifan has three coarse categories"),
    "Size": ("company_size", "separate", "Financial/employee bands; excluded from B3 business similarity"),
    "Capital intensity": ("sector asset_intensity", "partial", "Fiona covers selected sectors; no common v1 field"),
    "Regulation exposure": ("regulatory_exposure", "partial", "Related concept; category and evidence rules require alignment"),
    "Revenue growth": ("", "separate", "Needs dated target financial history, not website inference"),
    "EBITDA growth": ("", "separate", "Needs dated compatible EBITDA history"),
    "Headcount growth": ("", "separate", "Needs dated headcount history; no target record in the fixed pool"),
}


def clean_name(value: str) -> str:
    value = re.sub(r"[^a-z0-9 ]", " ", str(value).lower())
    words = [w for w in value.split() if w not in {"inc", "incorporated", "corp", "corporation",
             "company", "co", "ltd", "limited", "plc", "the"}]
    return " ".join(words)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    yifan = pd.read_excel(SOURCES / "yifan_orbis_facets.xlsx", sheet_name="Facet list v0.1", header=None)
    rows = []
    for _, row in yifan.iterrows():
        name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        if name not in FACET_MAP:
            continue
        field, relation, note = FACET_MAP[name]
        rows.append({"orbis_facet": name, "orbis_question": str(row.iloc[2]),
                     "orbis_allowed_values": str(row.iloc[3]), "orbis_filled_by": str(row.iloc[4]),
                     "v1_field": field, "relation": relation, "definition_note": note,
                     "private_target_source": "ordinary site or supplied profile" if name not in {
                         "Size", "Revenue growth", "EBITDA growth", "Headcount growth"}
                         else "sponsor-supplied dated accounts or HR records"})
    pd.DataFrame(rows).to_csv(OUT / "yifan_facet_crosswalk.csv", index=False)

    selected = ["Ticker", "CUSIP", "Company Name", "Global Company Key",
                "Fiscal year end", "Fiscal quarter end", "Date", "Enterprise Value Multiple",
                "Operating Profit Margin Before Depreciation", "Total Debt/EBITDA"]
    wrds = pd.read_excel(SOURCES / "wrds_560_ratios.xlsx", sheet_name="Latest Ratios",
                         usecols=lambda name: name in selected)
    wrds = wrds.rename(columns={"Ticker": "wrds_ticker", "Company Name": "wrds_company",
                                "Date": "wrds_date", "Enterprise Value Multiple": "wrds_evm"})
    if wrds["wrds_ticker"].duplicated().any():
        raise ValueError("The WRDS latest sheet has duplicate tickers")
    universe = pd.read_csv(V1 / "universe/20261025T060358Z/universe.csv", dtype=str)
    aligned = universe[["IQ_COMPANY_ID", "target_company_name", "target_ciq_ticker", "target_sic4_code"]].merge(
        wrds, left_on="target_ciq_ticker", right_on="wrds_ticker", how="left", validate="one_to_one")
    aligned["name_similarity"] = aligned.apply(
        lambda row: SequenceMatcher(None, clean_name(row.target_company_name),
                                    clean_name(row.wrds_company)).ratio()
        if pd.notna(row.wrds_company) else None, axis=1)
    aligned["id_status"] = "no_exact_ticker"
    same = aligned["wrds_ticker"].notna()
    aligned.loc[same, "id_status"] = "name_review"
    aligned.loc[same & aligned["name_similarity"].ge(.8), "id_status"] = "ticker_name_agree"
    aligned["wrds_year"] = pd.to_datetime(aligned["wrds_date"]).dt.year
    aligned["date_status"] = "missing"
    aligned.loc[same, "date_status"] = "stale_before_2025"
    aligned.loc[same & aligned["wrds_year"].eq(2025), "date_status"] = "2025_observation"
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str})[["IQ_COMPANY_ID", "target_ev_to_ebitda"]]
    aligned = aligned.merge(financials, on="IQ_COMPANY_ID", validate="one_to_one")
    aligned.to_csv(OUT / "wrds_exact_ticker_crosswalk.csv", index=False)
    valid = aligned[(aligned["id_status"] == "ticker_name_agree") &
                    (aligned["date_status"] == "2025_observation") &
                    aligned["wrds_evm"].notna()]
    sectors_table = sectors.sector_table(universe.set_index("IQ_COMPANY_ID"))
    ff49 = pd.read_excel(SOURCES / "wrds_ff49_ratios.xlsx",
                          usecols=["Date", "Fama and French 49 Industries - Description",
                                   "NFIRM", "Enterprise Value Multiple_Median"])
    ff49["Date"] = pd.to_datetime(ff49["Date"])
    ff49 = ff49[ff49["Date"].eq(pd.Timestamp("2025-12-31"))].copy()
    ff49["ff49"] = ff49["Fama and French 49 Industries - Description"].str.title()
    sector_counts = sectors_table["ff49"].value_counts()
    ff49["baseline_companies"] = ff49["ff49"].map(sector_counts).fillna(0).astype(int)
    ff49.to_csv(OUT / "ff49_2025_medians.csv", index=False)
    summary = {"eligible_companies": len(universe), "wrds_rows": len(wrds),
               "exact_ticker_overlap": int(same.sum()),
               "ticker_name_agreement": int((aligned["id_status"] == "ticker_name_agree").sum()),
               "ticker_name_review": int((aligned["id_status"] == "name_review").sum()),
               "matched_2025_nonmissing_evm": len(valid),
               "wrds_2025_ff49_groups": len(ff49),
               "wrds_evm_vs_capiq_multiple_median_absolute_difference": float(
                   (valid["wrds_evm"] - valid["target_ev_to_ebitda"]).abs().median()),
               "wrds_evm_vs_capiq_multiple_spearman": float(valid["wrds_evm"].corr(
                   valid["target_ev_to_ebitda"], method="spearman")),
               "interpretation": "Cross-source diagnostic only: CapIQ observation date and EV denominator definition are not confirmed equal",
               "sources_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in (SOURCES / "yifan_orbis_facets.xlsx",
                                               SOURCES / "wrds_560_ratios.xlsx",
                                               SOURCES / "wrds_ff49_ratios.xlsx")}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "sources_sha256"}, indent=2))


if __name__ == "__main__":
    main()
