"""Build and evaluate GPT facet variants on the fixed v1 company split."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import b3_facet_add_drop as b3
import facet_eval as fe
import facet_weighting as fw
import facets as fc
import industry_facets as ind
import method1_candidates as mc
import sector_facets as sec
import valuation as vl


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/gpt_candidates"
GENERAL = V1 / "facets_codex_gpt61sol/tables/facets.csv"
SECTOR = V1 / "sector_facets_codex_gpt61sol/tables/sector_facets.csv"
INDUSTRY = V1 / "industry_facets_codex_gpt61sol/tables/industry_facets_long.csv"


def main() -> None:
    universe, ids, training, sectors = b3.read_inputs()
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    holdout = split.loc[split["sample"] == "holdout", "IQ_COMPANY_ID"].tolist()
    if len(ids) != 533 or len(training) != 373 or len(holdout) != 160:
        raise ValueError("The fixed v1 split changed")

    filled = pd.read_csv(GENERAL, dtype=str).fillna("")
    filled = filled[(filled["prompt_version"] == fc.PROMPT_VERSION) &
                    (filled["llm_status"] == "ok") & (filled["business_id"] == "B1")]
    if filled["IQ_COMPANY_ID"].duplicated().any() or set(filled["IQ_COMPANY_ID"]) != set(ids):
        raise ValueError("GPT general facets must cover the 533 IDs once")
    sector = pd.read_csv(SECTOR, dtype=str).fillna("")
    industry = pd.read_csv(INDUSTRY, dtype=str).fillna("")
    if (sector["IQ_COMPANY_ID"].duplicated().any()
            or set(sector["IQ_COMPANY_ID"]) != set(ids)
            or not sector["llm_status"].eq("ok").all()
            or not sector["model"].eq("gpt-6.1-sol").all()
            or not sector["prompt_version"].eq(sec.PROMPT_VERSION).all()):
        raise ValueError("The GPT sector run must cover all 533 firms once")
    if (set(industry["IQ_COMPANY_ID"]) != set(ids)
            or not industry["model"].eq("gpt-6.1-sol").all()
            or not industry["prompt_version"].eq(ind.PROMPT_VERSION).all()):
        raise ValueError("The GPT SIC2 run must cover all 533 firms")
    if industry.duplicated(["IQ_COMPANY_ID", "facet"]).any():
        raise ValueError("A GPT SIC2 company has duplicate facets")
    dictionary = ind.load_dictionary()
    for iq, rows in industry.groupby("IQ_COMPANY_ID"):
        sic2 = rows["sic2"].unique()
        if (len(sic2) != 1 or set(rows["facet"]) !=
                {item["name"] for item in dictionary[sic2[0]]["facets"]}):
            raise ValueError(f"Incomplete GPT SIC2 facet set: {iq}")

    texts = fw.facet_texts(filled).reindex(ids)
    vectors = b3.vectors_for(b3.required_texts({"gpt": texts}, sector, industry))
    per, information, saturation = b3.general_components(texts, vectors)
    additions = b3.addition_matrices(ids, sectors, vectors, sector, industry)
    variants = {"GPT general": fw.combine(per, information)}
    for name, matrix in additions.items():
        variants[f"GPT + {name}"] = fw.combine({**per, name: matrix}, information)
    variants["GPT + all additions"] = fw.combine({**per, **additions}, information)
    for omitted in additions:
        remaining = {name: matrix for name, matrix in additions.items() if name != omitted}
        variants[f"GPT all except {omitted}"] = fw.combine({**per, **remaining}, information)

    review = pd.read_csv(V1 / "integration/review/pairs.csv")
    labels = review.rename(columns={"target_id": "target", "comp_id": "comp",
                                    "score_barbara": "grade"})[["target", "comp", "grade"]]
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    ticker = universe.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
    results = {"No matching": vl.no_matching(holdout, training, multiples)}
    peer_metrics, selected_rows = [], []
    for name, matrix in variants.items():
        rows, _, _ = b3.score_variant(name, matrix, ids, training,
                                       {"Barbara 293": labels})
        peer_metrics.extend(rows)
        ranking, candidates = mc.tables_from_similarity(matrix, ids, holdout, training, ticker)
        chosen = candidates[candidates["selected"]].copy()
        selected_rows.append(chosen.assign(method=name))
        results[name] = vl.estimate(chosen, multiples, weight="similarity")
        route = OUT / name.lower().replace(" ", "_").replace("+", "plus")
        route.mkdir(parents=True, exist_ok=True)
        ranking.to_csv(route / "ranking.csv.gz", index=False, compression="gzip")
        candidates.to_csv(route / "candidates.csv", index=False)
        fe.rank(matrix, ids, ids, training).query("rank <= 10").to_csv(
            route / "all_targets_top10.csv", index=False)
        (route / "run.json").write_text(json.dumps({
            "split_run": "20261027T204930Z", "universe_run": "20261025T060358Z",
            "method": name, "facet_source": "gpt-6.1-sol",
            "facet_override": str(GENERAL),
            "selected_pairs": int(candidates["selected"].sum()),
            "facet_sha256": hashlib.sha256(GENERAL.read_bytes()).hexdigest(),
            "sector_sha256": hashlib.sha256(SECTOR.read_bytes()).hexdigest(),
            "industry_sha256": hashlib.sha256(INDUSTRY.read_bytes()).hexdigest(),
            "saturation_k": saturation, "targets": "160 holdout", "pool": "373 training",
            "selection": "mutual top 10, topped up to 3",
        }, indent=2), encoding="utf-8")
        print(f"{name}: {len(chosen)} peers", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(peer_metrics).to_csv(OUT / "reviewed_metrics.csv", index=False)
    pd.concat(selected_rows, ignore_index=True).to_csv(OUT / "selected_peers.csv", index=False)
    vl.summary(results, multiples.reindex(holdout), "No matching").to_csv(
        OUT / "valuation_summary.csv")
    vl.bootstrap(results, multiples.reindex(holdout), "No matching").to_csv(
        OUT / "valuation_intervals.csv")
    actual = multiples.reindex(holdout)
    baseline = vl.errors(results["GPT general"], actual)["error %"].abs()
    paired = []
    for name in variants:
        candidate = vl.errors(results[name], actual)["error %"].abs()
        common = baseline.index.intersection(candidate.index)
        left, right = baseline.loc[common].to_numpy(), candidate.loc[common].to_numpy()
        valid = np.isfinite(left) & np.isfinite(right)
        left, right = left[valid], right[valid]
        draws = np.random.default_rng(4511).integers(0, len(left), (2000, len(left)))
        gains = np.median(left[draws], axis=1) - np.median(right[draws], axis=1)
        paired.append({"variant": name, "common_targets": len(left),
                       "gain_vs_general_percentage_points": float(np.median(left) - np.median(right)),
                       "gain_ci_low": float(np.quantile(gains, .025)),
                       "gain_ci_high": float(np.quantile(gains, .975)),
                       "mean_paired_error_gain": float(np.mean(left - right)),
                       "targets_better": int((right < left).sum()),
                       "targets_worse": int((right > left).sum()),
                       "targets_equal": int((right == left).sum())})
    pd.DataFrame(paired).to_csv(OUT / "paired_vs_general.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "general": str(GENERAL), "sector": str(SECTOR), "industry": str(INDUSTRY),
        "variant_count": len(variants), "reviewed_pairs": len(labels),
        "reviewer": "Barbara, one reviewer", "valuation_targets": len(holdout),
        "evaluation_status": "development comparison, not independent final holdout",
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
