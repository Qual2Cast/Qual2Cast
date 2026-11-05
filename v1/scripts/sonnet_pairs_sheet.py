"""Labeling sheet for the round-2 targets' comps from Sonnet's facets.

The comp lists are B3 on Sonnet's facet fills plus Fiona's sub-sector facet
(Eric's "Sonnet + Fiona sub-sector", exported by b3_facet_add_drop.py). Each
pair was checked by the agent loop (Sonnet). The sheet holds all the pairs in
round2_sheet.csv's blind layout (Sonnet's offering and customers shown), for two
reviewers; `round2_pair` names the same pair in round2_sheet.csv, if it is there.

  uv run python v1/scripts/sonnet_pairs_sheet.py --candidates <selector_candidates dir> \
      --agent outputs-local/v1/agent_loop/round2_targets_sonnet_b3
Writes, never overwriting:
  golden_set_showcase/labels/round2_sonnet_sheet.csv  (blind, for the reviewers)
  golden_set_showcase/labels/round2_sonnet_pairs.csv  (all pairs, with rank, similarity, agent grade; not for reviewers)
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
LABELS = V1 / "golden_set_showcase/labels"
ROUND2_SHEET = LABELS / "round2_sheet.csv"
FACETS = V1 / "facets_sonnet/tables/facets.csv"
SCOPES = V1 / "business_structure_refinement/split_classification/refined_scopes.json"
TARGETS = ["CSL", "AFG", "AZZ", "BBCP", "BUKS"]
REVIEWERS = ["matthew", "barbara"]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--agent", type=Path, required=True)
    args = ap.parse_args(argv)

    run = json.loads((args.candidates / "run.json").read_text(encoding="utf-8"))
    universe = pd.read_csv(V1 / "universe" / run["universe_run"] / "universe.csv", dtype=str)
    info = universe.set_index("IQ_COMPANY_ID")
    cand = pd.read_csv(args.candidates / "candidates.csv", dtype={"target": str, "comp": str})
    pairs = cand[cand["selected"].astype(str).eq("True") & cand["target_ticker"].isin(TARGETS)]
    agent = pd.read_csv(args.agent / "verdicts.csv", dtype={"target": str, "comp": str})
    pairs = pairs.merge(agent[["target", "comp", "score", "verdict", "reason"]].rename(
        columns={"score": "agent_score", "verdict": "agent_verdict", "reason": "agent_reason"}),
        on=["target", "comp"], how="left")

    old = pd.read_csv(ROUND2_SHEET, dtype=str)
    old_keys = set(zip(old["target_id"], old["comp_id"]))
    pairs["in_round2_sheet"] = [(t, c) in old_keys for t, c in zip(pairs["target"], pairs["comp"])]

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
    sheet = se.reviewer_sheet(pool, {"target": target_shown, "comp": shown}, REVIEWERS, seed=2026, prefix="R2S")
    old_pair = old.set_index(["target_id", "comp_id"])["pair"]
    sheet.insert(1, "round2_pair", [old_pair.get((t, c), "") for t, c in zip(sheet["target_id"], sheet["comp_id"])])

    LABELS.mkdir(parents=True, exist_ok=True)
    for path, frame in [(LABELS / "round2_sonnet_sheet.csv", sheet), (LABELS / "round2_sonnet_pairs.csv", pairs)]:
        if path.exists():
            print(f"kept {path.name} (never overwritten)")
        else:
            frame.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"wrote {path.name}: {len(frame)} rows")
    print(f"{len(pairs)} pairs; {int(pairs['in_round2_sheet'].sum())} already in round2_sheet.csv; "
          f"{len(pairs) - int(pairs['in_round2_sheet'].sum())} new")


if __name__ == "__main__":
    main()
