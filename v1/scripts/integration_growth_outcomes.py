"""Build Xiaozhe's dated revenue-growth labels from the saved EDGAR table."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pre-v0"))
from growth_signals.build_outcomes import (  # noqa: E402
    OUTCOME_NAMES, build_revenue_outcomes, read_annual_revenue_csv, write_outcome_csv,
)


OUT = ROOT / "outputs-local/v1/integration/growth_outcomes"
ANNUAL = OUT / "annual_revenue.csv"
COVERAGE = OUT / "coverage.csv"
CUTOFF_YEAR = 2022


def main() -> None:
    annual = pd.read_csv(ANNUAL, dtype={"IQ_COMPANY_ID": str})
    coverage = pd.read_csv(COVERAGE, dtype={"IQ_COMPANY_ID": str})
    company_ids = set(pd.read_csv(
        ROOT / "data-local/snapshots/company_list_v3_websites_fixed.csv",
        usecols=["IQ_COMPANY_ID"], dtype=str)["IQ_COMPANY_ID"])
    if not set(annual["IQ_COMPANY_ID"]).issubset(company_ids):
        raise ValueError("Revenue table contains an ID outside the company snapshot")
    if len(coverage) != len(company_ids) or set(coverage["IQ_COMPANY_ID"]) != company_ids:
        raise ValueError("EDGAR coverage must account for all snapshot companies")
    rows = build_revenue_outcomes(read_annual_revenue_csv(ANNUAL), CUTOFF_YEAR)
    write_outcome_csv(rows, OUT / "outcomes_2022.csv")
    result = pd.DataFrame(rows)
    split = pd.read_csv(ROOT / "outputs-local/v1/split/20261027T204930Z/split.csv",
                        usecols=["IQ_COMPANY_ID", "sample"], dtype=str)
    eligible = result.merge(split, on="IQ_COMPANY_ID", how="inner", validate="one_to_one")
    write_outcome_csv(eligible[OUTCOME_NAMES].to_dict("records"),
                      OUT / "eligible_outcomes_2022.csv")
    summary = {
        "source": str(ANNUAL.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(ANNUAL.read_bytes()).hexdigest(),
        "coverage_sha256": hashlib.sha256(COVERAGE.read_bytes()).hexdigest(),
        "cutoff_fiscal_year": CUTOFF_YEAR,
        "snapshot_companies": len(coverage),
        "companies_with_annual_revenue": int(annual["IQ_COMPANY_ID"].nunique()),
        "companies_with_cutoff_revenue": len(result),
        "eligible_companies_with_cutoff_revenue": len(eligible),
        "eligible_training": int(eligible["sample"].eq("training").sum()),
        "eligible_holdout": int(eligible["sample"].eq("holdout").sum()),
        "outcome_counts": {f"{years}y": int(result[f"revenue_growth_{years}y"].ne("").sum())
                           for years in (1, 2, 3)},
        "eligible_outcome_counts": {f"{years}y": int(eligible[f"revenue_growth_{years}y"].ne("").sum())
                                    for years in (1, 2, 3)},
        "rows_flagged_for_revenue_review": int(annual["review_flag"].notna().sum()),
        "companies_flagged_in_2022_2025": int(annual.loc[
            annual["fiscal_year"].between(2022, 2025) & annual["review_flag"].notna(),
            "IQ_COMPANY_ID"].nunique()),
        "status": "observed outcome labels; no historical event-feature panel or fitted forecast",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
