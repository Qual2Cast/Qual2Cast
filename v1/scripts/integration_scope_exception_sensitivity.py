"""Test source-specific scope exceptions without altering teammate facet files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

import b3_facet_add_drop as b3
import facet_eval as fe
import facet_weighting as fw
import method1_candidates as mc
import valuation as vl
from integration_reviewed_ranks import score_cohort


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
BASE = V1 / "integration"
OUT = BASE / "gpt_scope_alignment/sensitivity"
INPUTS = {
    "Sonnet dated": BASE / "sources/facets_sonnet_corrected.csv",
    "GPT general": V1 / "facets_codex_gpt61sol/tables/facets.csv",
    "GPT cited": V1 / "facets_source_gpt61sol/tables/facets.csv",
}
OVERRIDES = {
    "Sonnet source exceptions": {
        "HLTC": ("offering_description", "end_markets", "specialization"),
        "ENSG": ("offering_description", "primary_services", "end_markets", "specialization"),
    },
    "GPT source exception": {"TKR": ("primary_products",)},
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    universe, ids, training, _ = b3.read_inputs()
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    holdout = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    ticker = universe.set_index("target_ciq_ticker")["IQ_COMPANY_ID"].to_dict()
    source = {name: pd.read_csv(path, dtype=str).fillna("").set_index("IQ_COMPANY_ID")
              for name, path in INPUTS.items()}
    cited = source["GPT cited"]
    exceptions = pd.read_csv(OUT.parent / "source_exceptions.csv").set_index("ticker")
    profiles = {name: source[name].copy() for name in ("Sonnet dated", "GPT general")}
    changes = []
    for variant, cases in OVERRIDES.items():
        parent = "Sonnet dated" if variant.startswith("Sonnet") else "GPT general"
        target = profiles[parent].copy()
        for symbol, fields in cases.items():
            company = ticker[symbol]
            for field in fields:
                value = cited.at[company, field]
                if not value or cited.at[company, f"{field}_status"] != "filled":
                    raise ValueError(f"No cited replacement for {symbol} {field}")
                changes.append({"variant": variant, "ticker": symbol,
                                "IQ_COMPANY_ID": company, "facet": field,
                                "old": target.at[company, field], "new": value,
                                "replacement": "GPT source-cited facet",
                                "primary_url": exceptions.at[symbol, "url"]})
                target.at[company, field] = value
                target.at[company, f"{field}_status"] = "filled"
        target.reset_index().to_csv(OUT / f"{variant.lower().replace(' ', '_')}.csv", index=False)
        profiles[variant] = target
    pd.DataFrame(changes).to_csv(OUT / "overrides.csv", index=False)

    texts = {name: fw.facet_texts(table.reset_index()).reindex(ids)
             for name, table in profiles.items()}
    vectors = b3.vectors_for({str(value) for table in texts.values()
                              for column in table for value in table[column].dropna()})
    labels = b3.load_labels(training)["human_majority"]
    targets = set(labels["target"])
    financials = pd.read_csv(V1 / "universe/20261025T060358Z/financials.csv",
                             dtype={"IQ_COMPANY_ID": str}).set_index("IQ_COMPANY_ID")
    multiples = financials["target_ev_to_ebitda"]
    tickers = universe.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
    rows = []
    targets_by_variant = {}
    peers_by_variant = {}
    for name, table in texts.items():
        per, info, _ = b3.general_components(table, vectors)
        matrix = fw.combine(per, info)
        ranking = fe.rank(matrix, ids, sorted(targets), training)
        selected = fw.mutual_top_k(matrix, ids, sorted(targets), training)
        score, _ = score_cohort(name, "B3", ranking, selected[["target", "comp"]],
                                "human_majority", labels)
        holdout_selected = fw.mutual_top_k(matrix, ids, holdout, training)
        folder = OUT / name.lower().replace(" ", "_")
        folder.mkdir(parents=True, exist_ok=True)
        holdout_selected.to_csv(folder / "selected_peers.csv", index=False)
        peers_by_variant[name] = holdout_selected.groupby("target")["comp"].agg(
            lambda values: tuple(sorted(values))).to_dict()
        if name in OVERRIDES:
            full_ranking, candidates = mc.tables_from_similarity(
                matrix, ids, holdout, training, tickers)
            full_ranking.to_csv(folder / "ranking.csv.gz", index=False, compression="gzip")
            candidates.to_csv(folder / "candidates.csv", index=False)
            (folder / "run.json").write_text(json.dumps({
                "split_run": "20261027T204930Z", "universe_run": "20261025T060358Z",
                "method": name, "source": "primary-source exception sensitivity",
                "targets": len(holdout), "pool": len(training),
                "facet_sha256": hashlib.sha256((OUT / f"{name.lower().replace(' ', '_')}.csv")
                                                .read_bytes()).hexdigest(),
                "selected_pairs": int(candidates["selected"].sum()),
            }, indent=2), encoding="utf-8")
            if set(map(tuple, candidates.loc[candidates["selected"],
                                              ["target", "comp"]].itertuples(index=False, name=None))) != set(
                    map(tuple, holdout_selected[["target", "comp"]].itertuples(index=False, name=None))):
                raise ValueError(f"Saved B3 candidates differ: {name}")
        estimate = vl.estimate(holdout_selected, multiples, weight="similarity")
        error = vl.errors(estimate, multiples.reindex(holdout))["error %"].abs()
        error.rename("absolute_percentage_error").to_csv(folder / "target_errors.csv")
        targets_by_variant[name] = error
        rows.append({"variant": name, "good_selected": score["good_selected"],
                     "good_total": score["good_total"], "bad_selected": score["bad_selected"],
                     "valuation_targets": int(error.count()), "median_ape": float(error.median()),
                     "selected_peers": len(holdout_selected)})
        print(f"{name}: {score['good_selected']} reviewed peers, {error.median():.2f}% median APE", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "comparison.csv", index=False)
    paired = []
    for old, new in (("Sonnet dated", "Sonnet source exceptions"),
                     ("GPT general", "GPT source exception")):
        left, right = targets_by_variant[old], targets_by_variant[new]
        delta = left - right
        paired.append({"old": old, "new": new,
                       "targets": int(delta.notna().sum()),
                       "changed_peer_lists": sum(peers_by_variant[old][target] !=
                                                 peers_by_variant[new][target] for target in holdout),
                       "better": int((delta > 0).sum()), "worse": int((delta < 0).sum()),
                       "unchanged_error": int((delta == 0).sum()),
                       "median_paired_gain": float(delta.median())})
    pd.DataFrame(paired).to_csv(OUT / "paired.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "scope": "B3-only source-exception sensitivity; original team files unchanged",
        "sources": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for name, path in INPUTS.items()},
        "replacements": len(changes), "companies": sorted({row["ticker"] for row in changes}),
        "limits": "Two reviewed targets and 160 development valuations; LLM route prompts are not rerun here.",
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
