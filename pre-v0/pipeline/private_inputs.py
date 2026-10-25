"""Private-target factor contract: availability is not the same as publicity."""

import math

ALLOWED_SOURCES = {
    "client_supplied",
    "management_accounts",
    "authorized_private_database",
    "sponsor_simulation",
}
FACTOR_REGISTER = [
    {
        "factor": "Products/services and operating role",
        "source": "Company website / supplied business description",
        "availability": "Potentially observable; evidence required",
        "use": "Mandatory business review",
    },
    {
        "factor": "Customers and end markets",
        "source": "Explicit website statements",
        "availability": "Conditional; unknown when absent",
        "use": "Business review",
    },
    {
        "factor": "All observed business lines",
        "source": "Captured home/about/product/service pages",
        "availability": "Partial website coverage, not proven revenue coverage",
        "use": "Scope review; no invented segment weights",
    },
    {
        "factor": "Revenue model",
        "source": "Explicit pricing/contracts or client confirmation",
        "availability": "Conditional",
        "use": "Review only when directly supported; no inference from industry",
    },
    {
        "factor": "LTM revenue",
        "source": "Management accounts / client / authorized database",
        "availability": "Not assumed obtainable from a website",
        "use": "Optional size factor",
    },
    {
        "factor": "LTM EBITDA",
        "source": "Management accounts or supplied reconciliation",
        "availability": "Not assumed public; definition/period required for verified value",
        "use": "Optional profitability factor and valuation denominator",
    },
    {
        "factor": "Debt",
        "source": "Supplied balance sheet / debt schedule",
        "availability": "Not assumed public; gross/net definition matters",
        "use": "Optional debt/revenue factor",
    },
    {
        "factor": "EBITDA margin, debt/revenue",
        "source": "Derived from supplied inputs",
        "availability": "Only if required inputs exist and revenue is positive",
        "use": "Optional secondary factors",
    },
    {
        "factor": "Stock price, market cap, beta, analyst forecasts, target EV/EBITDA, ticker/listing status, SIC",
        "source": "Public-market / classification data",
        "availability": "Excluded from private-target matching",
        "use": "No target-side use; observed multiple is evaluation-only",
    },
]


def private_financials(records=None):
    """Each amount needs value, source_kind and source_ref; no hidden fallback.

    Dates/currency/units may remain unknown for an explicitly labeled proxy.
    They must agree across supplied records before cross-field ratios are used.
    """
    records = records or {}
    if set(records) - {"revenue", "ebitda", "debt"}:
        raise ValueError(
            "Only revenue, EBITDA and debt are permitted target financial inputs"
        )
    values = {
        "revenue": None,
        "ebitda": None,
        "debt": None,
        "margin": None,
        "debt_to_revenue": None,
    }
    for key, record in records.items():
        if record.get("source_kind") not in ALLOWED_SOURCES or not record.get(
            "source_ref"
        ):
            raise ValueError("Financial input requires a permitted, identified source")
        value = record.get("value")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("Financial amount must be finite")
        values[key] = float(value)
    issues = []

    def compatible(*keys):
        if any(values[k] is None for k in keys):
            return False
        for field in ("period_end", "currency", "units"):
            known = {records[k].get(field) for k in keys}
            if len(known) > 1:
                issues.append("incompatible_" + field + ":" + ",".join(keys))
                return False
        return True

    if values["revenue"] is not None and values["revenue"] > 0:
        if compatible("revenue", "ebitda"):
            values["margin"] = values["ebitda"] / values["revenue"]
        if compatible("revenue", "debt"):
            values["debt_to_revenue"] = values["debt"] / values["revenue"]
    return {
        "values": values,
        "sources": records,
        "issues": issues,
        "availability": "website_only" if not records else "explicit_financial_inputs",
        "missing": [k for k in ("revenue", "ebitda", "debt") if values[k] is None],
    }


def sponsor_simulation(workflow, company_id):
    """Explicit adapter for the public-as-private development experiment only."""
    f = workflow.finance.loc[company_id]
    return {
        key: {
            "value": float(value),
            "source_kind": "sponsor_simulation",
            "source_ref": "company_list_v3; simulates client-supplied financials",
            "period_end": None,
            "currency": None,
            "units": "source units",
        }
        for key, value in [
            ("revenue", f.revenue),
            ("ebitda", f.ebitda),
            ("debt", f.debt_derived),
        ]
        if math.isfinite(value)
    }
