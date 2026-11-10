"""Compare the dated Sonnet scope corrections on the same peers and targets."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import b3_facet_add_drop as b3
import facet_eval as fe
import facet_weighting as fw
import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/scope_eval"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _, ids, training, _ = b3.read_inputs()
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    holdout = split.loc[split["sample"] == "holdout", "IQ_COMPANY_ID"].tolist()
    paths = {
        "Sonnet original": V1 / "facets_sonnet/tables/facets.csv",
        "Sonnet dated corrections": V1 / "integration/sources/facets_sonnet_corrected.csv",
    }
    texts = {name: b3.general_texts(path, ids) for name, path in paths.items()}
    vectors = b3.vectors_for({str(value) for table in texts.values()
                              for column in table for value in table[column].dropna()})
    reviewed = pd.read_csv(V1 / "integration/review/pairs.csv")
    labels = reviewed.rename(columns={"target_id": "target", "comp_id": "comp"})[
        ["target", "comp", "score_barbara"]].rename(columns={"score_barbara": "gain"})
    labels["gain"] = labels["gain"].astype(float) / 2
    if not set(labels["comp"]) <= set(training):
        raise ValueError("A reviewed peer is outside the fixed training pool")
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    results = {"No matching": vl.no_matching(holdout, training, multiples)}
    metrics, pair_rows, selected_rows, top_rows, target_errors = [], [], [], [], []
    for name, table in texts.items():
        per, info, _ = b3.general_components(table, vectors)
        similarity = fw.combine(per, info)
        if name == "Sonnet dated corrections":
            full_top = fe.rank(similarity, ids, ids, training)
            full_top[full_top["rank"] <= 10].to_csv(
                OUT / "all_targets_top10.csv", index=False)
        ranking = fe.rank(similarity, ids, sorted(set(labels["target"])), training)
        metric = fe.rank_metrics(ranking, labels)
        selected = fw.mutual_top_k(similarity, ids, sorted(set(labels["target"])), training)
        chosen = selected.merge(labels, on=["target", "comp"], how="left")
        labeled = chosen[chosen["gain"].notna()]
        metrics.append({"method": name, **metric,
                        "reviewed_good_selected": int((labeled["gain"] >= .5).sum()),
                        "reviewed_bad_selected": int((labeled["gain"] == 0).sum()),
                        "selected_pairs": len(selected)})
        pair = labels.merge(ranking[["target", "comp", "rank", "similarity"]],
                            on=["target", "comp"], how="left")
        pair["method"] = name
        pair["selected"] = pair.set_index(["target", "comp"]).index.isin(
            selected.set_index(["target", "comp"]).index)
        pair_rows.append(pair)
        holdout_rank = fe.rank(similarity, ids, holdout, training)
        holdout_rank["method"] = name
        selected_holdout = fw.mutual_top_k(similarity, ids, holdout, training)
        selected_holdout["method"] = name
        selected_rows.append(selected_holdout)
        top = holdout_rank[holdout_rank["rank"] <= 10]
        top_rows.append(top)
        results[f"{name}: top 10 weighted mean"] = vl.estimate(top, multiples, weight="similarity")
        results[f"{name}: top 10 median"] = vl.estimate(top, multiples, how="median")
        results[f"{name}: mutual/top-up weighted mean"] = vl.estimate(
            selected_holdout, multiples, weight="similarity")
        for rule in (f"{name}: top 10 weighted mean", f"{name}: top 10 median",
                     f"{name}: mutual/top-up weighted mean"):
            errors = vl.errors(results[rule], multiples.reindex(holdout))
            errors["method"] = rule
            errors["target"] = errors.index
            target_errors.append(errors.reset_index(drop=True))
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metrics).to_csv(OUT / "peer_metrics.csv", index=False)
    pd.concat(pair_rows).to_csv(OUT / "reviewed_pair_ranks.csv", index=False)
    pd.concat(selected_rows).to_csv(OUT / "holdout_selected_peers.csv", index=False)
    pd.concat(top_rows).to_csv(OUT / "holdout_top10.csv", index=False)
    pd.concat(target_errors).to_csv(OUT / "holdout_target_errors.csv", index=False)
    summary = vl.summary(results, multiples.reindex(holdout), "No matching")
    summary.to_csv(OUT / "valuation_summary.csv")
    vl.bootstrap(results, multiples.reindex(holdout), "No matching").to_csv(
        OUT / "valuation_intervals.csv")
    record = {"pool": "373 fixed training firms", "peer_labels": "293 Barbara-only pairs / 45 targets",
              "valuation_targets": len(holdout), "facet_versions": list(paths),
              "corrections_file": "integration/sources/yiming_corrections.csv"}
    (OUT / "run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(pd.DataFrame(metrics).to_string(index=False))
    print(summary[["targets", "median abs % error"]].to_string())


if __name__ == "__main__":
    main()
