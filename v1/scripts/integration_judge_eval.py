"""Compare source-citing 0–2 decisions with separately held reviewer scores."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
TRUTH = V1 / "integration/review/pairs.csv"


def evaluate(run: Path) -> dict:
    predicted = pd.read_csv(run / "verdicts.csv", dtype={"target": str, "comp": str})
    truth = pd.read_csv(TRUTH, dtype={"target_id": str, "comp_id": str}).rename(
        columns={"target_id": "target", "comp_id": "comp", "score_barbara": "human"})
    if len(truth) != 293 or truth.duplicated(["target", "comp"]).any():
        raise ValueError("Reviewer pair set has changed")
    if predicted.duplicated(["target", "comp"]).any():
        raise ValueError("Duplicate model decisions")
    joined = truth.merge(predicted, on=["target", "comp"], how="left",
                         validate="one_to_one", indicator=True)
    if (joined["_merge"] != "both").any():
        raise ValueError("The model run did not cover all 293 reviewer pairs")
    joined["score"] = pd.to_numeric(joined["score"], errors="coerce")
    joined["human"] = pd.to_numeric(joined["human"], errors="raise")
    scored = joined.dropna(subset=["score"])
    if not scored["score"].isin([0, 1, 2]).all():
        raise ValueError("A model grade falls outside the 0–2 rubric")
    scored = scored.copy()
    scored["exact"] = scored["score"].eq(scored["human"])
    scored["peer_agree"] = scored["score"].ge(1).eq(scored["human"].ge(1))
    scored["absolute_grade_error"] = (scored["score"] - scored["human"]).abs()
    confusion = pd.crosstab(scored["human"], scored["score"], dropna=False)
    for label in range(3):
        if label not in confusion.index:
            confusion.loc[label] = 0
        if label not in confusion.columns:
            confusion[label] = 0
    confusion = confusion.reindex(index=range(3), columns=range(3), fill_value=0)
    summary = {
        "reviewer": "Barbara, one reviewer", "pairs_expected": len(truth),
        "pairs_scored": len(scored), "insufficient_or_failed": len(truth) - len(scored),
        "exact_agreement": float(scored["exact"].mean()) if len(scored) else None,
        "within_one_grade": float(scored["absolute_grade_error"].le(1).mean()) if len(scored) else None,
        "mean_absolute_grade_error": float(scored["absolute_grade_error"].mean()) if len(scored) else None,
        "peer_binary_agreement": float(scored["peer_agree"].mean()) if len(scored) else None,
        "mean_signed_grade_error": float((scored["score"] - scored["human"]).mean()) if len(scored) else None,
        "web_searches": int(pd.to_numeric(joined["web_searches"], errors="coerce").sum()),
        "source_citing_review": True,
        "human_grade_counts": {str(int(k)): int(v) for k, v in truth["human"].value_counts().items()},
        "model_grade_counts": {str(int(k)): int(v) for k, v in scored["score"].value_counts().items()},
    }
    paired = scored.dropna(subset=["agent_score"]).copy()
    if len(paired):
        prior = pd.to_numeric(paired["agent_score"], errors="raise")
        summary.update({
            "same_pairs_as_saved_agent": len(paired),
            "saved_agent_exact_on_same_pairs": float(prior.eq(paired["human"]).mean()),
            "new_agent_exact_on_same_pairs": float(paired["score"].eq(paired["human"]).mean()),
        })
    out = run / "eval_293"
    out.mkdir(exist_ok=True)
    joined.to_csv(out / "all_pairs.csv", index=False)
    confusion.to_csv(out / "confusion.csv")
    scored.loc[~scored["exact"], ["target", "comp", "human", "score", "reason",
                                   "target_citations", "comp_citations", "web_searches"]].to_csv(
        out / "disagreements.csv", index=False)
    by_target = scored.groupby("target").agg(pairs=("score", "size"),
                                              exact_agreement=("exact", "mean"),
                                              peer_binary_agreement=("peer_agree", "mean"))
    by_target.to_csv(out / "by_target.csv")
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    evaluate(parser.parse_args().run)
