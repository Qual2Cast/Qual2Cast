"""Flag source-confirmed mixed-business peers and test a conservative exclusion.

The source audit covers 40 firms, so this is a sensitivity analysis, not a
replacement for the default peer rules or a complete business-mix model.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import valuation as vl
from holdout_evaluation import CANDIDATES, LLM
from project_data import OUTPUTS_LOCAL


SCOPES = (OUTPUTS_LOCAL / "comps_pilot_targets/business_structure_refinement/"
          "split_classification/refined_scopes.json")
OUTPUT = LLM / "evaluation/source_scope_sensitivity"


def run(candidates_dir: Path = CANDIDATES, llm_dir: Path = LLM,
        scopes_path: Path = SCOPES, output: Path = OUTPUT) -> dict:
    llm_meta = json.loads((llm_dir / "llm_run.json").read_text(encoding="utf-8"))
    if llm_meta.get("complete") is not True:
        raise ValueError("Finish the 160-target LLM holdout before testing scope exclusions")
    config = json.loads((candidates_dir / "run.json").read_text(encoding="utf-8"))
    split = pd.read_csv(OUTPUTS_LOCAL / "comps_pilot_targets/split" /
                        config["split_run"] / "split.csv", dtype={"IQ_COMPANY_ID": str})
    targets = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    training = split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"].tolist()
    universe_dir = OUTPUTS_LOCAL / "comps/universe" / config["universe_run"]
    info = pd.read_csv(universe_dir / "universe.csv", dtype=str).set_index("IQ_COMPANY_ID")
    multiples = pd.read_csv(universe_dir / "financials.csv", dtype={"IQ_COMPANY_ID": str})\
        .set_index("IQ_COMPANY_ID")["target_ev_to_ebitda"]
    actual = multiples.reindex(targets)
    scopes = json.loads(scopes_path.read_text(encoding="utf-8"))
    mixed = {record["IQ_COMPANY_ID"]: record for record in scopes.values()
             if record["decision"] == "multiple_businesses"}
    ranking = pd.read_csv(candidates_dir / "ranking.csv.gz", dtype={"target": str, "comp": str})
    judge = pd.read_csv(llm_dir / "judge.csv", dtype={"target": str, "comp": str})
    direct = pd.read_csv(llm_dir / "direct.csv", dtype={"target": str, "comp": str})
    if not set(mixed) <= set(info.index):
        raise ValueError("A source-checked company is outside the universe")
    similarity = ranking[["target", "comp", "similarity"]]
    routes = {
        "cosine z >= 2": (ranking[ranking["z_ge_2"]], "similarity"),
        "cosine then LLM": (judge[judge["score"].eq(1)].merge(
            similarity, on=["target", "comp"], validate="one_to_one"), "similarity"),
        "LLM direct": (direct, None),
        "LLM then cosine": (direct.merge(
            similarity, on=["target", "comp"], validate="one_to_one"), "similarity"),
    }
    flags, sensitivity = [], []
    for name, (pairs, weight) in routes.items():
        flagged = pairs[pairs["comp"].isin(mixed)].copy()
        for row in flagged.itertuples(index=False):
            scope = mixed[row.comp]
            flags.append({"route": name, "target": row.target,
                          "target_ticker": info.loc[row.target, "target_ciq_ticker"],
                          "comp": row.comp,
                          "comp_ticker": info.loc[row.comp, "target_ciq_ticker"],
                          "business_groups": len(scope["groups"]),
                          "source_scope": scope["scope_note"]})
        original = vl.errors(vl.estimate(pairs, multiples, weight=weight), actual)["error %"].abs()
        filtered_pairs = pairs[~pairs["comp"].isin(mixed)]
        filtered = vl.errors(vl.estimate(filtered_pairs, multiples, weight=weight), actual)["error %"].abs()
        common = pd.concat([original.rename("original"), filtered.rename("filtered")], axis=1).dropna()
        affected = common.loc[common.index.isin(flagged["target"])]
        affected_change = affected["filtered"] - affected["original"]
        sensitivity.append({"route": name, "source-audited mixed peers": len(flagged),
                            "affected targets": flagged["target"].nunique(),
                            "affected common targets": len(affected),
                            "original coverage": len(original),
                            "filtered coverage": len(filtered),
                            "common targets": len(common),
                            "original median APE on common": common["original"].median(),
                            "filtered median APE on common": common["filtered"].median(),
                            "median paired change":
                            (common["filtered"] - common["original"]).median(),
                            "affected median APE original": affected["original"].median(),
                            "affected median APE filtered": affected["filtered"].median(),
                            "affected median paired change": affected_change.median(),
                            "affected improved": int((affected_change < 0).sum()),
                            "affected worsened": int((affected_change > 0).sum())})
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(flags, columns=["route", "target", "target_ticker", "comp",
                                 "comp_ticker", "business_groups", "source_scope"]).to_csv(
        output / "flags.csv", index=False)
    pd.DataFrame(sensitivity).to_csv(output / "sensitivity.csv", index=False)
    metadata = {"audited_companies": len(scopes), "mixed_business_companies": len(mixed),
                "definition": "exclude source-confirmed mixed-business comps; no target exception",
                "status": "sensitivity only; default peers unchanged"}
    (output / "run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
