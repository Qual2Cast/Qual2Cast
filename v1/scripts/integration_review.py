"""Evaluate the shared 0–2 reviewer sheet without inventing consensus labels."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs-local/v1/integration/sources/sonnet_label.xlsx"
OUT = ROOT / "outputs-local/v1/integration/review"


def main() -> None:
    data = pd.read_excel(SOURCE, sheet_name="pairs")
    if len(data) != 293 or data[["target_id", "comp_id"]].duplicated().any():
        raise ValueError("The shared pair list must contain 293 unique pairs")
    human = pd.to_numeric(data["score_barbara"], errors="raise")
    agent = pd.to_numeric(data["agent_score"], errors="coerce")
    if not human.isin([0, 1, 2]).all() or not agent.dropna().isin([0, 1, 2]).all():
        raise ValueError("Scores must use the exact shared 0–2 rubric")
    if data["score_matthew"].notna().any():
        raise ValueError("Review attribution changed; inspect the workbook before rerunning")
    pairs = data[["pair", "target_id", "comp_id", "target_ticker", "comp_ticker",
                  "rank", "similarity", "score_barbara", "agent_score",
                  "agent_verdict", "agent_reason", "reason_if_0_barbara",
                  "notes_barbara"]].copy()
    pairs["exact_match"] = (human == agent).where(agent.notna())
    pairs["binary_match"] = ((human >= 1) == (agent >= 1)).where(agent.notna())
    OUT.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(OUT / "pairs.csv", index=False)
    common = pairs[pairs["agent_score"].notna()]
    confusion = pd.crosstab(common["score_barbara"], common["agent_score"],
                            rownames=["Barbara"], colnames=["Agent"])
    confusion = confusion.reindex(index=[0, 1, 2], columns=[0, 1, 2], fill_value=0)
    confusion.to_csv(OUT / "confusion.csv")
    disagreements = common[~common["exact_match"].astype(bool)]
    disagreements.to_csv(OUT / "disagreements.csv", index=False)
    summary = {"cohort": "Barbara single reviewer; not consensus gold",
               "pairs": len(pairs), "targets": int(pairs["target_id"].nunique()),
               "agent_scored": len(common), "exact_agreement": float(common["exact_match"].mean()),
               "binary_agreement": float(common["binary_match"].mean()),
               "disagreements": len(disagreements)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
