from edgar_revenue import annual_revenue, ticker_map


def fact(val, start, end, filed, form="10-K", accn=None):
    return {"val": val, "start": start, "end": end, "filed": filed, "form": form,
            "accn": accn or f"0000-{filed}"}


def facts(**concepts):
    return {"facts": {"us-gaap": {name: {"units": {"USD": values}}
                                  for name, values in concepts.items()}}}


def test_total_revenue_wins_over_contract_revenue_subset():
    rows = annual_revenue(facts(
        RevenueFromContractWithCustomerExcludingAssessedTax=[
            fact(600, "2023-01-01", "2023-12-31", "2024-02-10")],
        Revenues=[fact(3282, "2023-01-01", "2023-12-31", "2024-02-10")],
    ), cik=1)
    assert [(r["fiscal_year"], r["revenue"], r["concept"]) for r in rows] == [(2023, 3282, "Revenues")]


def test_quarterly_and_non_10k_facts_are_ignored():
    rows = annual_revenue(facts(Revenues=[
        fact(80, "2023-10-01", "2023-12-31", "2024-02-10"),             # a quarter
        fact(300, "2023-01-01", "2023-12-31", "2024-02-10", form="8-K"),
        fact(320, "2023-01-01", "2023-12-31", "2024-02-10"),
    ]), cik=1)
    assert [r["revenue"] for r in rows] == [320]


def test_first_filed_value_is_used_and_restatement_kept():
    rows = annual_revenue(facts(Revenues=[
        fact(105, "2022-01-01", "2022-12-31", "2024-02-10"),            # restated later
        fact(100, "2022-01-01", "2022-12-31", "2023-02-10"),
    ]), cik=1)
    assert (rows[0]["revenue"], rows[0]["revenue_latest"]) == (100, 105)
    assert rows[0]["source_url"].startswith("https://www.sec.gov/Archives/edgar/data/1/")


def test_large_year_over_year_change_is_flagged_not_changed():
    rows = annual_revenue(facts(Revenues=[
        fact(1000, "2015-01-01", "2015-12-31", "2016-02-10"),
        fact(150, "2016-01-01", "2016-12-31", "2017-02-10"),
    ]), cik=1)
    assert rows[1]["revenue"] == 150 and "yoy change -85%" in rows[1]["review_flag"]


def test_changed_fiscal_year_end_keeps_later_period():
    rows = annual_revenue(facts(Revenues=[
        fact(100, "2020-02-01", "2021-01-31", "2021-03-10"),
        fact(110, "2021-01-01", "2021-12-31", "2022-03-10"),
    ]), cik=1)
    assert [(r["fiscal_year"], r["period_end"]) for r in rows] == [(2021, "2021-12-31")]


def test_ticker_map_uppercases():
    assert ticker_map({"0": {"ticker": "pcty", "cik_str": 1591698}}) == {"PCTY": 1591698}
