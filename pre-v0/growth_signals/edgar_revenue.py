"""Multi-year annual revenue from SEC EDGAR, for growth-outcome labels only.

10-K filings may be used. This script reads revenue from public companies'
10-K filings (SEC XBRL "company facts") to build the *answer* the growth
model is scored against
(build_outcomes.py). The revenue it writes is a financial field: it is kept
in its own table and is never a feature or an input describing a target.

Steps, each saved without overwriting earlier runs:
  1. ticker -> CIK from SEC's company_tickers.json;
  2. one companyfacts JSON per company (raw, gzipped);
  3. annual revenue per fiscal year from 10-K facts covering about 12 months,
     taking the largest of the REVENUE_CONCEPTS (the total); every value keeps
     its accession number, filing date, concept and a link to the filing.

A fiscal year is the calendar year in which the period ends. When a later
10-K restates a year, the first-filed value is used (as originally reported)
and the latest value is kept alongside it. Companies that cannot be matched
or have no 10-K revenue are listed in the coverage file as unknown, never
guessed.

SEC fair-access policy: requests carry a contact in the User-Agent and stay
under 10 per second. The contact is passed at run time (--contact or the
SEC_CONTACT environment variable) and is not stored in the repository.

python edgar_revenue.py --contact "Qual2Cast research name@example.edu" --limit 10
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]   # growth_signals/ is in pre-v0/
WEBSITE_SCRAPE_DIR = REPO_ROOT / "website_scrape"
if str(WEBSITE_SCRAPE_DIR) not in sys.path:
    sys.path.insert(0, str(WEBSITE_SCRAPE_DIR))

from fetch_and_clean import find_input, load_companies  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "outputs-local" / "growth_signals" / "edgar"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/"
REQUEST_PAUSE_SECONDS = 0.15          # under SEC's 10 requests per second
ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A"}
MIN_DAYS, MAX_DAYS = 330, 400         # "about 12 months"
JUMP_FLAG = 0.5                       # flag year-over-year changes beyond +/-50%
# Candidate total-revenue concepts; the largest annual value per fiscal year
# is used (see annual_revenue). No segment or product-line concepts.
REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "RevenuesNetOfInterestExpense",
)
CSV_COLUMNS = [
    "IQ_COMPANY_ID", "company_name", "ticker", "cik", "fiscal_year", "revenue",
    "period_start", "period_end", "concept", "form", "filed", "accession", "source_url",
    "revenue_latest", "latest_filed", "latest_accession", "concepts_found", "review_flag",
]


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def annual_revenue(facts: dict, cik: int) -> list[dict]:
    """One row per fiscal year from 10-K revenue facts (first-filed value).

    For each fiscal year every concept in REVENUE_CONCEPTS is a candidate and
    the largest annual value is used: concepts such as
    RevenueFromContractWithCustomer exclude rental or interest income, so the
    company's total is the largest of them (Herc: $600M contract revenue vs
    $3.3B total in 2023). The chosen concept is recorded. Year-over-year
    changes beyond JUMP_FLAG are flagged for review (e.g. a reused CIK after a
    spin-off), not corrected.
    """
    usgaap = facts.get("facts", {}).get("us-gaap", {})
    candidates: dict[int, list[dict]] = {}
    for concept in REVENUE_CONCEPTS:
        values = usgaap.get(concept, {}).get("units", {}).get("USD", [])
        periods: dict[tuple[str, str], list[dict]] = {}
        for fact in values:
            if (fact.get("form") not in ANNUAL_FORMS or not fact.get("start")
                    or not fact.get("end") or fact.get("val") is None):
                continue
            if not MIN_DAYS <= _days(fact["start"], fact["end"]) <= MAX_DAYS:
                continue
            periods.setdefault((fact["start"], fact["end"]), []).append(fact)
        for (start, end), facts_for_period in periods.items():
            ordered = sorted(facts_for_period, key=lambda f: (f.get("filed", ""), f.get("accn", "")))
            first, latest = ordered[0], ordered[-1]
            accession = first.get("accn", "")
            candidates.setdefault(date.fromisoformat(end).year, []).append({
                "revenue": first["val"],
                "period_start": start,
                "period_end": end,
                "concept": concept,
                "form": first.get("form", ""),
                "filed": first.get("filed", ""),
                "accession": accession,
                "source_url": FILING_URL.format(cik=cik, accession_nodash=accession.replace("-", "")),
                "revenue_latest": latest["val"],
                "latest_filed": latest.get("filed", ""),
                "latest_accession": latest.get("accn", ""),
            })
    rows = []
    for year in sorted(candidates):
        # A changed fiscal year end can give two periods ending in one year:
        # keep the later-ending period, then the largest total within it.
        last_end = max(c["period_end"] for c in candidates[year])
        best = max((c for c in candidates[year] if c["period_end"] == last_end),
                   key=lambda c: c["revenue"])
        rows.append({"fiscal_year": year, **best,
                     "concepts_found": len({c["concept"] for c in candidates[year]})})
    for previous, row in zip(rows, rows[1:]):
        change = row["revenue"] / previous["revenue"] - 1 if previous["revenue"] else None
        if change is not None and abs(change) > JUMP_FLAG:
            row["review_flag"] = f"yoy change {change:+.0%} vs {previous['fiscal_year']}"
    return rows


class Edgar:
    def __init__(self, contact: str, raw_dir: Path):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": contact, "Accept-Encoding": "gzip, deflate"})
        self.raw_dir = raw_dir
        raw_dir.mkdir(parents=True, exist_ok=True)

    def get_json(self, url: str, save_as: str) -> dict | None:
        time.sleep(REQUEST_PAUSE_SECONDS)
        response = self.session.get(url, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        with gzip.open(self.raw_dir / f"{save_as}.json.gz", "wb") as stream:
            stream.write(response.content)       # raw response kept as fetched
        return response.json()


def ticker_map(tickers_json: dict) -> dict[str, int]:
    return {row["ticker"].upper(): int(row["cik_str"]) for row in tickers_json.values()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--contact", default=os.environ.get("SEC_CONTACT"),
                        help='User-Agent contact, e.g. "Qual2Cast research name@example.edu"')
    parser.add_argument("--input", help="company list CSV; defaults to the required snapshot")
    parser.add_argument("--tickers", nargs="*", help="only these tickers")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if not args.contact or "@" not in args.contact:
        raise SystemExit("SEC requires a contact: pass --contact or set SEC_CONTACT.")

    companies = load_companies(find_input(args.input))
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        companies = companies[companies["target_ciq_ticker"].str.upper().isin(wanted)]
    if args.limit:
        companies = companies.head(args.limit)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.out / stamp
    edgar = Edgar(args.contact, run_dir / "raw")
    ciks = ticker_map(edgar.get_json(TICKERS_URL, "company_tickers"))

    rows, coverage = [], []
    for company in companies.to_dict("records"):
        ticker = str(company.get("target_ciq_ticker") or "").upper()
        base = {"IQ_COMPANY_ID": company["IQ_COMPANY_ID"],
                "company_name": company["target_company_name"], "ticker": ticker}
        # Class shares: "ARTN.A" is listed by SEC as "ARTNA" (or "ARTN-A").
        cik = (ciks.get(ticker) or ciks.get(ticker.replace(".", "-"))
               or ciks.get(ticker.replace(".", "")))
        if not cik:
            coverage.append({**base, "cik": "", "status": "ticker_not_in_sec_list", "years": 0})
            continue
        facts = edgar.get_json(FACTS_URL.format(cik=cik), f"companyfacts_CIK{cik:010d}")
        years = annual_revenue(facts, cik) if facts else []
        status = "ok" if years else ("no_companyfacts" if facts is None else "no_10k_revenue")
        coverage.append({**base, "cik": cik, "status": status, "years": len(years),
                         "first_year": years[0]["fiscal_year"] if years else "",
                         "last_year": years[-1]["fiscal_year"] if years else ""})
        rows.extend({**base, "cik": cik, **year} for year in years)
        print(f"{ticker:<6} {status:<22} {len(years)} years", flush=True)

    with (run_dir / "annual_revenue.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, restval="")
        writer.writeheader()
        writer.writerows(rows)
    with (run_dir / "coverage.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["IQ_COMPANY_ID", "company_name", "ticker",
                                                    "cik", "status", "years", "first_year",
                                                    "last_year"])
        writer.writeheader()
        writer.writerows(coverage)
    ok = sum(c["status"] == "ok" for c in coverage)
    print(f"{ok}/{len(coverage)} companies with 10-K revenue -> {run_dir}")


if __name__ == "__main__":
    main()
