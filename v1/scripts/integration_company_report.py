"""Return a ranked public-peer report for a company name or website."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/company_reports"


def domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").lower().removeprefix("www.")


def report_company(query: str, target_ebitda: float | None = None,
                   method: str = "source_reviewed") -> dict:
    info = pd.read_csv(V1 / "universe/20261025T060358Z/universe.csv", dtype=str)
    needle = query.strip().lower()
    matches = info[(info["IQ_COMPANY_ID"].str.lower() == needle)
                   | (info["target_company_name"].str.lower() == needle)
                   | (info["target_ciq_ticker"].str.lower() == needle)]
    if matches.empty:
        matches = info[info["target_ciq_website"].map(domain) == domain(query)]
    if len(matches) != 1:
        raise ValueError(f"Company lookup returned {len(matches)} exact matches; provide a unique name, ticker, ID or website")
    company = matches.iloc[0]
    target = company["IQ_COMPANY_ID"]
    if method == "source_reviewed":
        ranking_path = V1 / "integration/source_reviewed_default/all_targets_top10.csv"
        method_label = "source-reviewed Sonnet facets; B3 top-10 weighted mean"
        facet_path = V1 / "integration/source_reviewed_default/facets.csv"
    elif method == "dated_sonnet":
        ranking_path = V1 / "integration/scope_eval/all_targets_top10.csv"
        method_label = "dated Sonnet facets; B3 top-10 weighted mean"
        facet_path = V1 / "integration/sources/facets_sonnet_corrected.csv"
    else:
        route = V1 / "integration/gpt_candidates" / method
        run = json.loads((route / "run.json").read_text(encoding="utf-8"))
        ranking_path = route / "all_targets_top10.csv"
        method_label = f"{run['method']}; B3 top-10 weighted mean"
        facet_path = Path(run["facet_override"])
    ranked = pd.read_csv(ranking_path,
                         dtype={"target": str, "comp": str})
    peers = ranked[ranked["target"] == target].sort_values("rank").copy()
    if len(peers) != 10:
        raise ValueError("The fixed B3 shortlist is incomplete")
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    peer_info = info.set_index("IQ_COMPANY_ID")
    peers["company"] = peers["comp"].map(peer_info["target_company_name"])
    peers["ticker"] = peers["comp"].map(peer_info["target_ciq_ticker"])
    peers["public_peer_ev_ebitda"] = peers["comp"].map(financials["target_ev_to_ebitda"])
    valid = peers[peers["public_peer_ev_ebitda"].gt(0)]
    weights = valid["similarity"].clip(lower=0).to_numpy(float)
    estimate = (float(np.average(valid["public_peer_ev_ebitda"], weights=weights))
                if len(valid) >= 3 and weights.sum() > 0 else None)
    if target_ebitda is not None and target_ebitda <= 0:
        raise ValueError("Target EBITDA must be positive for an EV calculation")
    return {"query": query, "company_id": target, "company": company["target_company_name"],
            "website": company["target_ciq_website"], "method": method_label,
            "ranked_peers": peers[["rank", "comp", "company", "ticker", "similarity",
                                    "public_peer_ev_ebitda"]].to_dict("records"),
            "multiple_estimate": estimate,
            "target_ebitda_supplied": target_ebitda,
            "enterprise_value_estimate": estimate * target_ebitda
            if estimate is not None and target_ebitda is not None else None,
            "financial_units": "original Capital IQ snapshot units; period and currency need case-level confirmation",
            "source_files": [str(facet_path), str(ranking_path),
                             str(V1 / "universe/20261025T060358Z/financials.csv")]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("company", help="exact name, website, ticker or IQ company ID")
    parser.add_argument("--ebitda", type=float)
    parser.add_argument("--method", default="source_reviewed",
                        help="source_reviewed, dated_sonnet, or a GPT candidate route directory name")
    args = parser.parse_args()
    result = report_company(args.company, args.ebitda, args.method)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{result['company_id']}_{args.method}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"company": result["company"], "peers": len(result["ranked_peers"]),
                      "multiple_estimate": result["multiple_estimate"],
                      "enterprise_value_estimate": result["enterprise_value_estimate"],
                      "file": str(path)}, indent=2))


if __name__ == "__main__":
    main()
