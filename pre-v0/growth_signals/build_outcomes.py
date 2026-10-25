"""Build leakage-safe future revenue-growth outcomes from annual revenue data."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

REQUIRED_COLUMNS = {"IQ_COMPANY_ID", "company_name", "fiscal_year", "revenue"}
HORIZONS = (1, 2, 3)
OUTCOME_NAMES = [
    "IQ_COMPANY_ID", "company_name", "cutoff_fiscal_year", "revenue_at_cutoff",
    *[f"revenue_growth_{years}y" for years in HORIZONS],
    *[f"revenue_cagr_{years}y" for years in HORIZONS],
    "outcome_years_available",
]


def _normalize_record(record: dict, row_label: str) -> dict:
    missing = REQUIRED_COLUMNS - set(record)
    if missing:
        raise ValueError(f"{row_label}: missing required columns: {sorted(missing)}")
    company_id = str(record["IQ_COMPANY_ID"]).strip()
    company_name = str(record["company_name"]).strip()
    if not company_id:
        raise ValueError(f"{row_label}: IQ_COMPANY_ID is required")
    if not company_name:
        raise ValueError(f"{row_label}: company_name is required")
    try:
        fiscal_year = int(record["fiscal_year"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{row_label}: fiscal_year must be an integer") from exc
    try:
        revenue = float(record["revenue"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{row_label}: revenue must be numeric") from exc
    if revenue < 0:
        raise ValueError(f"{row_label}: revenue must be nonnegative")
    return {
        "IQ_COMPANY_ID": company_id,
        "company_name": company_name,
        "fiscal_year": fiscal_year,
        "revenue": revenue,
    }


def read_annual_revenue_csv(path: Path) -> list[dict]:
    """Read a long-form annual revenue CSV with an explicit required schema."""
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing required columns: {sorted(missing)}")
        return [_normalize_record(record, f"{path}:{line_number}")
                for line_number, record in enumerate(reader, start=2)]


def build_revenue_outcomes(records: list[dict], cutoff_fiscal_year: int) -> list[dict]:
    """Return exact 1-3 year outcomes for companies with cutoff-year revenue."""
    by_company: dict[str, dict[int, float]] = defaultdict(dict)
    company_names: dict[str, str] = {}
    for index, raw_record in enumerate(records, start=1):
        record = _normalize_record(raw_record, f"record {index}")
        company_id = record["IQ_COMPANY_ID"]
        company_name = record["company_name"]
        fiscal_year = record["fiscal_year"]
        if company_id in company_names and company_names[company_id] != company_name:
            raise ValueError(f"conflicting company names for {company_id}")
        company_names[company_id] = company_name
        if fiscal_year in by_company[company_id]:
            raise ValueError(f"duplicate company-year for {company_id}, {fiscal_year}")
        by_company[company_id][fiscal_year] = record["revenue"]

    rows = []
    for company_id in sorted(by_company):
        revenues = by_company[company_id]
        if cutoff_fiscal_year not in revenues:
            continue
        baseline = revenues[cutoff_fiscal_year]
        if baseline <= 0:
            raise ValueError(f"cutoff revenue must be positive for {company_id}")
        row = {
            "IQ_COMPANY_ID": company_id,
            "company_name": company_names[company_id],
            "cutoff_fiscal_year": cutoff_fiscal_year,
            "revenue_at_cutoff": baseline,
        }
        available = 0
        for years in HORIZONS:
            future = revenues.get(cutoff_fiscal_year + years)
            if future is None:
                row[f"revenue_growth_{years}y"] = ""
                row[f"revenue_cagr_{years}y"] = ""
                continue
            row[f"revenue_growth_{years}y"] = future / baseline - 1
            row[f"revenue_cagr_{years}y"] = (future / baseline) ** (1 / years) - 1
            available += 1
        row["outcome_years_available"] = available
        rows.append(row)
    return rows


def write_outcome_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTCOME_NAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annual-revenue", type=Path, required=True)
    parser.add_argument("--cutoff-fiscal-year", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = build_revenue_outcomes(
        read_annual_revenue_csv(args.annual_revenue), args.cutoff_fiscal_year)
    write_outcome_csv(rows, args.output)


if __name__ == "__main__":
    main()
