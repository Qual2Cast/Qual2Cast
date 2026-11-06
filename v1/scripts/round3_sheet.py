"""Round-3 labeling sheet: a larger set of target-comp pairs from Sonnet's facets.

One training target per SIC2 code (random, seeded), leaving out the round-1 and
round-2 targets. Each target's comp list is B3 on Sonnet's facet fills plus
Fiona's sub-sector facet (Eric's "Sonnet + Fiona sub-sector" candidates). Pairs
already in the round-1 or round-2 sheets are left out. Same blind layout as
round 2 (Sonnet's offering and customers shown; no rank or similarity).

  uv run python v1/scripts/round3_sheet.py --candidates <selector_candidates dir>
Writes, never overwriting:
  golden_set_round3/labels/round3_sheet.csv  (blind, for the reviewers)
  golden_set_round3/labels/round3_pairs.csv  (with rank and similarity; not for reviewers)
  golden_set_round3/labels/round3_combined.csv  (with --agent: the sheet, then rank, similarity and the agent
                                                 loop's grade after the reviewer columns; not for reviewers)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import facets as fc  # noqa: E402,F401  (puts src/ on the path)
import similarity_eval as se  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

V1 = OUTPUTS_LOCAL / "v1"
OUT = V1 / "golden_set_round3/labels"
ROUND1 = V1 / "golden_set/labels/reviewer_labels_20261028.json"
ROUND2 = V1 / "golden_set_showcase/labels/round2_sheet.csv"
FACETS = V1 / "facets_sonnet/tables/facets.csv"
SCOPES = V1 / "business_structure_refinement/split_classification/refined_scopes.json"
DONE_TARGETS = ["PCTY", "WEN", "CSL", "AFG", "AZZ", "BBCP", "BUKS"]
REVIEWERS = ["matthew", "barbara"]
SEED = 2026


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--per-sic2", type=int, default=1, help="targets per SIC2 code")
    ap.add_argument("--agent", type=Path, help="an agent_loop.py run on these pairs")
    args = ap.parse_args(argv)

    run = json.loads((args.candidates / "run.json").read_text(encoding="utf-8"))
    universe = pd.read_csv(V1 / "universe" / run["universe_run"] / "universe.csv", dtype=str)
    info = universe.set_index("IQ_COMPANY_ID")
    cand = pd.read_csv(args.candidates / "candidates.csv", dtype={"target": str, "comp": str})
    sel = cand[cand["selected"].astype(str).eq("True") & ~cand["target_ticker"].isin(DONE_TARGETS)]

    targets = pd.DataFrame({"target": sel["target"].unique()})
    targets["sic2"] = info["target_sic2_code"].reindex(targets["target"]).to_numpy()
    picked = (targets.sample(frac=1, random_state=SEED).groupby("sic2").head(args.per_sic2)["target"])
    pairs = sel[sel["target"].isin(picked)].copy()

    labelled = set(zip(pd.read_csv(ROUND2, dtype=str)["target_id"], pd.read_csv(ROUND2, dtype=str)["comp_id"]))
    r1 = pd.DataFrame(json.loads(ROUND1.read_text(encoding="utf-8"))["labels"])
    labelled |= set(zip(r1["target_id"].astype(str), r1["comp_id"].astype(str)))
    pairs = pairs[[(t, c) not in labelled for t, c in zip(pairs["target"], pairs["comp"])]]

    facets = pd.read_csv(FACETS, dtype=str).fillna("")
    b1 = facets[(facets["business_id"] == "B1") & (facets["llm_status"] == "ok")].set_index("IQ_COMPANY_ID")
    scopes = json.loads(SCOPES.read_text(encoding="utf-8"))
    shown = pd.DataFrame({"ticker": info["target_ciq_ticker"], "company": info["target_company_name"],
                          "sic_industry": info["target_primary_sic_industry"], "website": info["target_ciq_website"],
                          "offering": b1["offering_description"].reindex(info.index).fillna(""),
                          "customers": b1["customer_segment"].reindex(info.index).fillna("")})
    target_shown = shown.assign(business_scope=[
        scopes.get(t, {}).get("scope_note", "").removeprefix("Current company scope: ") for t in shown["ticker"]])
    pool = pairs[["target", "comp"]].rename(columns={"target": "target_id", "comp": "comp_id"}).reset_index(drop=True)
    sheet = se.reviewer_sheet(pool, {"target": target_shown, "comp": shown}, REVIEWERS, seed=SEED, prefix="R3")

    keep = ["target", "target_ticker", "comp", "comp_ticker", "rank", "similarity", "mutual", "topped_up"]
    pairs = pairs[keep].assign(sic2=info["target_sic2_code"].reindex(pairs["target"]).to_numpy())
    outputs = [(OUT / "round3_sheet.csv", sheet), (OUT / "round3_pairs.csv", pairs)]
    if args.agent:
        agent = pd.read_csv(args.agent / "verdicts.csv", dtype={"target": str, "comp": str})
        extra = pairs[["target", "comp", "rank", "similarity"]].merge(
            agent[["target", "comp", "score", "verdict", "reason"]], on=["target", "comp"], how="left").rename(
            columns={"target": "target_id", "comp": "comp_id", "score": "agent_score",
                     "verdict": "agent_verdict", "reason": "agent_reason"})
        combined = sheet.drop(columns=["target_id", "comp_id"]).join(sheet[["target_id", "comp_id"]]).merge(
            extra, on=["target_id", "comp_id"], how="left")
        cols = [c for c in combined.columns if c not in ("target_id", "comp_id")] + ["target_id", "comp_id"]
        outputs.append((OUT / "round3_combined.csv", combined[cols]))
    OUT.mkdir(parents=True, exist_ok=True)
    for path, frame in outputs:
        if path.exists():
            print(f"kept {path.name} (never overwritten)")
        else:
            frame.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"wrote {path.name}: {len(frame)} rows")
    print(f"{pairs['target'].nunique()} targets ({pairs['sic2'].nunique()} SIC2 codes), {len(pairs)} pairs")


if __name__ == "__main__":
    main()
