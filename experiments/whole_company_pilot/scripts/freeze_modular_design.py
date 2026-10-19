"""Freeze an outcome-blind ten-company pilot against the current team snapshot."""
from pathlib import Path
import csv
import hashlib
import json
from datetime import datetime, timezone
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TEAM = Path(r"C:\Users\13156\ChatGPT-Local-Deliveries\Rational-AI-2026-10-18\team-source\da427dbf6b34a41d3b172ced6a2959e2c9335b0a")
OUT = ROOT / "outputs-local/modular-validation"
OUT.mkdir(parents=True, exist_ok=True)
SNAPSHOT = TEAM / "data-local/snapshots/company_list_v3_websites_fixed.csv"
EXPECTED = "3ab9a43e7426c1f41a77055a6d3ca9553845cb3046a954e28dc5c2a82c934eae"
assert hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest() == EXPECTED
columns = ["IQ_COMPANY_ID", "target_company_name", "target_ciq_ticker", "target_ciq_website", "target_sic4_code"]
with SNAPSHOT.open(encoding="utf-8-sig", newline="") as f:
    rows = [{k: row[k] for k in columns} for row in csv.DictReader(f)]
assert len(rows) == 560 and len({r["IQ_COMPANY_ID"] for r in rows}) == 560
rng = np.random.default_rng(4511)
targets, frames = [], {}
for sic in ["7370", "2834"]:
    sector = sorted([r for r in rows if r["target_sic4_code"] == sic], key=lambda r: r["IQ_COMPANY_ID"])
    pool = [r for r in sector if r["target_ciq_ticker"] != "PCTY"]
    frames[sic] = [r["IQ_COMPANY_ID"] for r in pool]
    selected = ([r for r in sector if r["target_ciq_ticker"] == "PCTY"] if sic == "7370" else [])
    selected += [pool[i] for i in rng.choice(len(pool), size=5-len(selected), replace=False)]
    for r in selected:
        r = dict(r)
        r["role"] = "development" if r["target_ciq_ticker"] == "PCTY" else "fresh_pilot"
        r["sector_population"] = len(sector)
        r["inclusion_probability"] = 1.0 if r["role"] == "development" else ((4/54) if sic == "7370" else (5/22))
        targets.append(r)
design = {
    "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
    "team_revision": TEAM.name, "team_root": str(TEAM), "snapshot_sha256": EXPECTED,
    "archive_sha256": "427330b8a9df5e9dbafb839e5390f49f33e7943db7a6de01d9bed165a4c05b13",
    "selection_rule": "The two most populated supplied SIC4 categories, 7370 (55) and 2834 (22). Include team-required PCTY as development, then sorted-ID seeded draws without replacement. No exclusion or replacement for subsequent source/model/outcome failures.",
    "seed": 4511, "rng": "NumPy Generator(PCG64)", "numpy_version": np.__version__,
    "frames": frames, "targets": targets, "target_outcomes_inspected": False,
    "source_boundary": "Current committed website evidence; target filings prohibited. Candidate-only filings require a separately labeled later enrichment arm. Local models only; no external upload.",
    "financial_permission": "Mentor clarification 2026-10-18 17:46 Eastern permits target LTM revenue/EBITDA/debt and public candidate context. Augmented arms are separate from website controls. EV/EBITDA excluded from matching.",
    "primary_k": 5, "sensitivity_k": [3, 10], "tie_break": "ascending stable IQ_COMPANY_ID",
    "sampling_limits": "Two-sector pilot; not a population-representative validation. PCTY and its historical labels are development. Nine fresh cases remain exploratory until independent human review.",
    "methods_predeclared": [
        "team_tfidf", "team_lsa", "team_mpnet_cosine", "team_equal_z_ensemble",
        "doc2vec_dbow_cosine", "mpnet_page_balanced", "mpnet_home_only",
        "mpnet_conservative_cleaning", "balanced_activity_ot", "unbalanced_activity_ot",
        "financial_rank_adapted", "mpnet_financial_rrf", "same_sic4_mpnet", "same_sic4_financial",
        "sector_activity_profile", "source_grounded_local_llm_rerank", "same_sic4_id_baseline"
    ],
    "method_gate": "Every applicable method is run; implementation failures or unavailable inputs are retained in the run ledger. Exact parameters are frozen in the runner config before scores are exposed. No winner tuning on these ten cases.",
    "peer_policies": ["fixed_top5", "fixed_top3_sensitivity", "fixed_top10_sensitivity", "evidence_coverage_abstention"],
    "aggregations": ["median", "positive_harmonic_mean", "nonnegative_rank_weighted_mean"],
    "evaluation": "Full ranking diagnostics; historical PCTY labels only as development; blind common-pool human template; source support and scope audited separately. All-positive finance subset fixed across aggregation choices. Snapshot valuation error is not an aligned-date backtest.",
    "growth_gate": "No three-year forecast or claimed interval calibration without dated historical predictors and observable outcomes. Reuse teammate event collector where available; validate date and source semantics separately."
}
path = OUT / "design_freeze.json"
if path.exists():
    raise FileExistsError("Design already frozen; use a versioned amendment instead of overwriting")
path.write_text(json.dumps(design, indent=2), encoding="utf-8")
(OUT / "design_freeze.sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest()+"\n", encoding="ascii")
print(json.dumps({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "targets": targets}, indent=2))
