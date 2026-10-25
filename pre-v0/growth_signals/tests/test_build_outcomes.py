import csv

from build_outcomes import build_revenue_outcomes, read_annual_revenue_csv


def revenue(company_id, company_name, fiscal_year, value):
    return {
        "IQ_COMPANY_ID": company_id,
        "company_name": company_name,
        "fiscal_year": fiscal_year,
        "revenue": value,
    }


def test_builds_one_to_three_year_growth_from_exact_fiscal_years():
    rows = build_revenue_outcomes([
        revenue("IQ1", "Example Co.", 2021, 90),
        revenue("IQ1", "Example Co.", 2022, 100),
        revenue("IQ1", "Example Co.", 2023, 110),
        revenue("IQ1", "Example Co.", 2024, 121),
        revenue("IQ1", "Example Co.", 2025, 133.1),
    ], cutoff_fiscal_year=2022)

    assert len(rows) == 1
    row = rows[0]
    assert row["cutoff_fiscal_year"] == 2022
    assert row["revenue_at_cutoff"] == 100.0
    assert round(row["revenue_growth_1y"], 8) == 0.1
    assert round(row["revenue_growth_2y"], 8) == 0.21
    assert round(row["revenue_growth_3y"], 8) == 0.331
    assert round(row["revenue_cagr_3y"], 8) == 0.1
    assert row["outcome_years_available"] == 3


def test_missing_year_is_not_filled_from_a_later_year():
    rows = build_revenue_outcomes([
        revenue("IQ1", "Example Co.", 2022, 100),
        revenue("IQ1", "Example Co.", 2024, 121),
    ], cutoff_fiscal_year=2022)

    row = rows[0]
    assert row["revenue_growth_1y"] == ""
    assert round(row["revenue_growth_2y"], 8) == 0.21
    assert row["revenue_growth_3y"] == ""
    assert row["outcome_years_available"] == 1


def test_company_without_cutoff_revenue_is_excluded():
    rows = build_revenue_outcomes([
        revenue("IQ1", "Example Co.", 2023, 110),
        revenue("IQ2", "Other Co.", 2022, 200),
        revenue("IQ2", "Other Co.", 2023, 220),
    ], cutoff_fiscal_year=2022)

    assert [row["IQ_COMPANY_ID"] for row in rows] == ["IQ2"]


def test_rejects_duplicate_company_year_and_conflicting_names():
    duplicate = [
        revenue("IQ1", "Example Co.", 2022, 100),
        revenue("IQ1", "Example Co.", 2022, 101),
    ]
    try:
        build_revenue_outcomes(duplicate, cutoff_fiscal_year=2022)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("expected duplicate company-year to fail")

    conflicting = [
        revenue("IQ1", "Example Co.", 2022, 100),
        revenue("IQ1", "Different Co.", 2023, 110),
    ]
    try:
        build_revenue_outcomes(conflicting, cutoff_fiscal_year=2022)
    except ValueError as exc:
        assert "conflicting company names" in str(exc)
    else:
        raise AssertionError("expected conflicting names to fail")


def test_rejects_nonpositive_cutoff_and_negative_future_revenue():
    for records, expected in [
        ([revenue("IQ1", "Example Co.", 2022, 0)], "cutoff revenue"),
        ([revenue("IQ1", "Example Co.", 2022, 100),
          revenue("IQ1", "Example Co.", 2023, -1)], "revenue must be nonnegative"),
    ]:
        try:
            build_revenue_outcomes(records, cutoff_fiscal_year=2022)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("expected invalid revenue to fail")


def test_csv_reader_requires_explicit_schema(tmp_path):
    valid = tmp_path / "annual_revenue.csv"
    with valid.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "IQ_COMPANY_ID", "company_name", "fiscal_year", "revenue"])
        writer.writeheader()
        writer.writerow(revenue("IQ1", "Example Co.", 2022, "100.5"))

    assert read_annual_revenue_csv(valid) == [
        revenue("IQ1", "Example Co.", 2022, 100.5)]

    invalid = tmp_path / "invalid.csv"
    invalid.write_text("IQ_COMPANY_ID,revenue\nIQ1,100\n", encoding="utf-8")
    try:
        read_annual_revenue_csv(invalid)
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("expected missing columns to fail")
