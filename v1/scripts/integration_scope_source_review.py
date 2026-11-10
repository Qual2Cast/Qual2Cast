"""Record dated primary-source exceptions to automatic business-scope edits."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration"
OUT = BASE / "gpt_scope_alignment"
CASES = [
    {"ticker": "HLTC", "activity": "outpatient medical facilities",
     "source_date": "2026-09-28", "decision": "retain_current_business",
     "evidence": "30 of 86 facilities had closed; 56 and another 40 were pending, with four under a letter of intent.",
     "url": "https://investors.nhpreit.com/Investors/investor-news/news-details/2026/National-Healthcare-Properties-Announces-Definitive-Agreement-to-Sell-40-Additional-Outpatient-Medical-Facilities-for-531-Million-Signs-LOI-for-Remaining-Four-OMFs-and-Provides-SHOP-Acquisition-Pipeline-Update/default.aspx"},
    {"ticker": "ENSG", "activity": "senior living services",
     "source_date": "2026-10-02", "decision": "retain_current_business",
     "evidence": "Ensign reported that its subsidiaries still operated 50 senior living operations after the 2019 Pennant separation.",
     "url": "https://investor.ensigngroup.net/news/news-details/2026/The-Ensign-Group-Adds-New-Operations-in-Colorado/default.aspx"},
    {"ticker": "TKR", "activity": "industrial belts",
     "source_date": "2026-09-28", "decision": "remove_divested_business",
     "evidence": "Timken announced completion of its belts-business sale to Gates.",
     "url": "https://news.timken.com/2026-09-28-Timken-Completes-Sale-of-Belts-Business-to-Gates"},
    {"ticker": "SKIL", "activity": "instructor-led training",
     "source_date": "2026-07-06", "decision": "distinguish_owned_from_partner_access",
     "evidence": "Skillsoft sold Global Knowledge but said its customers would retain training access through a partnership.",
     "url": "https://investor.skillsoft.com/news-events/press-releases/detail/457/skillsoft-completes-sale-of-global-knowledge-business-advancing-focus-on-ai-native-skills-management-platform"},
]


def main() -> None:
    changes = pd.read_csv(BASE / "sources/yiming_corrections.csv", dtype=str).fillna("")
    scope = pd.read_csv(OUT / "specificity.csv", dtype=str).fillna("")
    rows = []
    for case in CASES:
        corrected = changes[(changes["ticker"].eq(case["ticker"])) &
                            (changes["applied"].eq("True"))]
        flagged = scope[scope["ticker"].eq(case["ticker"])]
        if corrected.empty or flagged.empty:
            raise ValueError(f"Missing dated comparison for {case['ticker']}")
        rows.append({**case, "company_id": corrected.iloc[0]["IQ_COMPANY_ID"],
                     "corrected_fields": "; ".join(corrected["facet"]),
                     "gpt_flagged_fields": "; ".join(flagged["facet"]),
                     "review_action": {
                         "retain_current_business": "test retained-business exception",
                         "remove_divested_business": "test cited replacement for GPT field",
                         "distinguish_owned_from_partner_access": "record ownership and access separately",
                     }[case["decision"]]})
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "source_exceptions.csv", index=False)
    (OUT / "source_exceptions_run.json").write_text(json.dumps({
        "as_of": "2026-10-28", "cases": len(rows),
        "rule": "A pending partial divestiture does not remove a whole business; a spin-off does not remove retained or reacquired operations.",
        "effect": "Original teammate facets remain frozen; the integrated Sonnet default applies these reviewed exceptions through integration_default_scope.py.",
    }, indent=2), encoding="utf-8")
    print(pd.DataFrame(rows)[["ticker", "activity", "decision"]].to_string(index=False))


if __name__ == "__main__":
    main()
