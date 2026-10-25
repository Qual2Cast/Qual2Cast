"""
The comp universe: recipe steps 1 and 2.

1. Candidate comps: companies headquartered in the US whose 2-digit SIC code
   is one of the codes in the target list.
2. Drop firms whose EV/EBITDA is outside 3-30, from both the targets and
   the comps.

The universe is the 560-company list itself (decided 2026-10-24): every
company is a target in turn, and its candidate comps are the others. The
functions take any list with the same columns, so a wider universe (e.g. a
Capital IQ pull) can be passed in later without changing them.

Financial columns are split off as soon as the list is read and kept in their
own table, keyed by IQ_COMPANY_ID. EV/EBITDA is used here only to apply the
3-30 range; it is never a matching input.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project_data import normalize_sic_codes, snapshot_path  # noqa: E402

FINANCIAL_COLUMNS = [
    "target_revenue",
    "target_ebitda",
    "target_margin",
    "target_debt_to_revenue",
    "target_ev_to_ebitda",
]
EV_EBITDA_RANGE = (3.0, 30.0)   # inclusive: 3.0 and 30.0 are kept


def load_list(path: str | Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The company list (default: the snapshot in data_manifest.json, checksum-
    checked) as two tables: company information, and financials keyed by
    IQ_COMPANY_ID. SIC codes are 4-character strings, 2/3-digit codes derived."""
    df = normalize_sic_codes(pd.read_csv(path or snapshot_path(), dtype=str))
    info = df.drop(columns=FINANCIAL_COLUMNS)
    financials = df[["IQ_COMPANY_ID", *FINANCIAL_COLUMNS]].copy()
    financials[FINANCIAL_COLUMNS] = financials[FINANCIAL_COLUMNS].astype(float)
    return info, financials


def select_candidates(info: pd.DataFrame, target_sic2: set[str] | None = None) -> pd.DataFrame:
    """Step 1. Flags each company: HQ in the US (Capital IQ country), and SIC2
    among the target list's codes (default: the codes in `info` itself)."""
    target_sic2 = target_sic2 or set(info["target_sic2_code"])
    out = info.copy()
    out["us_hq"] = out["target_country_iso3"].eq("USA")
    out["sic2_in_target_list"] = out["target_sic2_code"].isin(target_sic2)
    out["candidate"] = out["us_hq"] & out["sic2_in_target_list"]
    return out


def multiple_check(financials: pd.DataFrame, low: float = EV_EBITDA_RANGE[0],
                   high: float = EV_EBITDA_RANGE[1]) -> pd.DataFrame:
    """Step 2. One row per company: its EV/EBITDA, whether it is kept, and the
    reason if not (missing, below range, above range)."""
    ev = financials["target_ev_to_ebitda"]
    reason = np.select([ev.isna(), ev < low, ev > high],
                       ["missing", f"below_{low:g}", f"above_{high:g}"], default="")
    return pd.DataFrame({"IQ_COMPANY_ID": financials["IQ_COMPANY_ID"],
                         "ev_to_ebitda": ev,
                         "kept": reason == "",
                         "drop_reason": reason})


def build_universe(path: str | Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Steps 1 and 2 together. Returns the company table (with `candidate`,
    `kept_multiple`, `drop_reason` and `in_universe`) and the financials
    table, both keyed by IQ_COMPANY_ID. A company is in
    the universe if it is a candidate and its multiple is in range; the same
    set serves as targets and comps."""
    info, financials = load_list(path)
    companies = select_candidates(info)
    check = multiple_check(financials)
    companies = companies.merge(check[["IQ_COMPANY_ID", "kept", "drop_reason"]]
                                .rename(columns={"kept": "kept_multiple"}), on="IQ_COMPANY_ID")
    companies["in_universe"] = companies["candidate"] & companies["kept_multiple"]
    return companies, financials
