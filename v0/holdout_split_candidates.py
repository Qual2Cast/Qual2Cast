"""Build candidates for source-pilot or all companies in the fixed holdout.

Uses the exact saved v0 facet embeddings, equal weights, SIC2 split, training
comp universe, and z >= 2 rule. No embedding model is loaded or fitted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import business_split_refinement as bs
from project_data import OUTPUTS_LOCAL


BASE_RUN = OUTPUTS_LOCAL / "comps_pilot_targets/candidates/20261027T204930Z"
OUTPUT = OUTPUTS_LOCAL / "comps_pilot_targets/business_structure_refinement/holdout_candidates"


def run(base_run: Path = BASE_RUN, output: Path = OUTPUT,
        all_holdout: bool = False) -> dict:
    config = json.loads((base_run / "run.json").read_text(encoding="utf-8"))
    universe = pd.read_csv(OUTPUTS_LOCAL / "comps/universe" / config["universe_run"] /
                           "universe.csv", dtype=str)
    ids = universe["IQ_COMPANY_ID"].tolist()
    cache = OUTPUTS_LOCAL / "comps/embeddings" / config["embedding_cache"]
    # The checked-in facet table may have changed since this cache was made.
    # Validate its row order against saved training-pair cosines instead of
    # silently assuming the current facet text reproduces the old hash.
    saved_pairs = pd.read_csv(base_run / "candidates.csv")
    pos = {company_id: i for i, company_id in enumerate(ids)}
    with np.load(cache) as vectors:
        errors = []
        for name in config["similarity_facets"]:
            observed = saved_pairs[f"sim_{name}"].to_numpy(dtype=float)
            calculated = np.array([float(vectors[name][pos[target]] @ vectors[name][pos[comp]])
                                   for target, comp in zip(saved_pairs["target"], saved_pairs["comp"])])
            errors.extend(abs(observed[np.isfinite(observed)] - calculated[np.isfinite(observed)]))
    cache_check = float(max(errors))
    if cache_check > 1e-5:
        raise ValueError(f"The embedding cache does not reproduce saved training pairs: {cache_check}")
    split = pd.read_csv(OUTPUTS_LOCAL / "comps_pilot_targets/split" /
                        config["split_run"] / "split.csv", dtype={"IQ_COMPANY_ID": str})
    pilot = set(json.loads(bs.SNAPSHOT.read_text(encoding="utf-8"))["companies"])
    holdout_rows = split[split["sample"] == "holdout"]
    if not all_holdout:
        holdout_rows = holdout_rows[holdout_rows["target_ciq_ticker"].isin(pilot)]
    holdout = holdout_rows["IQ_COMPANY_ID"].tolist()
    training = split.loc[split["sample"] == "training", "IQ_COMPANY_ID"].tolist()
    target_pos = np.array([pos[x] for x in holdout])
    train_pos = np.array([pos[x] for x in training])
    numerator = np.zeros((len(holdout), len(training)), dtype=float)
    denominator = np.zeros_like(numerator)
    per_facet = {}
    with np.load(cache) as vectors:
        for name in config["similarity_facets"]:
            target_vectors = vectors[name][target_pos]
            comp_vectors = vectors[name][train_pos]
            valid = (np.linalg.norm(target_vectors, axis=1)[:, None] > 0) & \
                    (np.linalg.norm(comp_vectors, axis=1)[None, :] > 0)
            cosine = target_vectors @ comp_vectors.T
            per_facet[name] = np.where(valid, cosine, np.nan)
            numerator += np.nan_to_num(per_facet[name])
            denominator += valid
    similarity = np.divide(numerator, denominator, out=np.full_like(numerator, np.nan),
                           where=denominator > 0)
    info = universe.set_index("IQ_COMPANY_ID")
    rows = []
    for row, target in enumerate(holdout):
        scores = similarity[row]
        finite = np.isfinite(scores)
        choices = np.where(finite)[0]
        ordered = choices[np.argsort(-scores[choices], kind="stable")]
        z = (scores[ordered] - scores[choices].mean()) / scores[choices].std()
        for rank, (column, standardized) in enumerate(zip(ordered, z), start=1):
            comp = training[column]
            record = {"target": target, "target_ticker": info.loc[target, "target_ciq_ticker"],
                      "rank": rank, "comp": comp,
                      "comp_ticker": info.loc[comp, "target_ciq_ticker"],
                      "comp_company": info.loc[comp, "target_company_name"],
                      "similarity": float(scores[column]), "z": float(standardized),
                      "in_top_k": rank <= 10, "z_ge_2": standardized >= 2,
                      "z_ge_2.5": standardized >= 2.5}
            record.update({f"sim_{name}": float(per_facet[name][row, column])
                           for name in config["similarity_facets"]})
            rows.append(record)
    ranking = pd.DataFrame(rows)
    selected = ranking[(ranking["in_top_k"]) | (ranking["z_ge_2"])].copy()
    output.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(output / "ranking.csv.gz", index=False, compression="gzip")
    selected.to_csv(output / "candidates.csv", index=False)
    metadata = {**config, "targets": "all holdout firms" if all_holdout else
                "all six 40-company pilot firms in holdout",
                "pool": "373 training firms", "holdout_tickers":
                info.loc[holdout, "target_ciq_ticker"].tolist(),
                "pairs": len(selected), "embedding_cache_checked": config["embedding_cache"],
                "checked_saved_training_pairs": len(saved_pairs),
                "max_saved_pair_cosine_difference": cache_check}
    (output / "run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="all 160 fixed-holdout targets")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    out = args.out or (OUTPUT.parent / "holdout_all_candidates" if args.all else OUTPUT)
    print(json.dumps(run(output=out, all_holdout=args.all), indent=2))
