"""Recompute the fixed holdout shortlist with Fiona's all-sector-facets variant.

The original eleven cosine facets, split, candidate pool, and ranking rule
remain fixed. Fiona's existing variant adds FF49, SIC4, sub-sector text, and
sector-specific category facets. It does not restrict peers by sector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import candidates as cd
import facet_eval as fe
import sector_facets as sf
import sectors as sc
from project_data import OUTPUTS_LOCAL


BASE = OUTPUTS_LOCAL / "comps_pilot_targets/candidates/20261027T204930Z"
FACETS = OUTPUTS_LOCAL / "comps_pilot_targets/sector_facets/tables/sector_facets.csv"
OUT = OUTPUTS_LOCAL / "comps_pilot_targets/sector_facets/holdout_candidates"


def load_sector_facets(path: Path, ids: list[str]) -> pd.DataFrame:
    table = pd.read_csv(path, dtype=str).fillna("")
    table = table[(table.prompt_version == sf.PROMPT_VERSION) &
                  (table.llm_status == "ok")]
    if table.IQ_COMPANY_ID.duplicated().any() or set(table.IQ_COMPANY_ID) != set(ids):
        raise ValueError("Sector facets must cover each eligible firm exactly once")
    return table.set_index("IQ_COMPANY_ID").reindex(ids)


def attach_sector_summary(general: pd.DataFrame, sector: pd.DataFrame) -> pd.DataFrame:
    """Add Fiona's stated values to LLM prompts; baseline calls stay unchanged."""
    result = general.copy()
    summaries = {}
    for company, row in sector.iterrows():
        fields = [f"Sector group: {sc.SECTOR_LABELS[row['sector']]}",
                  f"FF49 industry: {sc.ff49_names().get(row['ff49'], row['ff49'])}",
                  f"SIC4: {row['sic4']}"]
        for facet in sf.facets_for(row["sector"]):
            if row.get(f"{facet.name}_status") == "stated" and row.get(facet.name):
                fields.append(f"{facet.label}: {row[facet.name]}")
        summaries[company] = "; ".join(fields)
    result["sector_summary"] = result.index.map(summaries).fillna("")
    return result


def run(base: Path = BASE, sector_path: Path = FACETS, out: Path = OUT) -> dict:
    config = json.loads((base / "run.json").read_text(encoding="utf-8"))
    split = pd.read_csv(OUTPUTS_LOCAL / "comps_pilot_targets/split" /
                        config["split_run"] / "split.csv", dtype=str)
    training = split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"].tolist()
    holdout = split.loc[split["sample"].eq("holdout"), "IQ_COMPANY_ID"].tolist()
    if len(training) != 373 or len(holdout) != 160:
        raise ValueError("The fixed SIC2 split changed")
    universe = pd.read_csv(OUTPUTS_LOCAL / "comps/universe" /
                           config["universe_run"] / "universe.csv", dtype=str)
    ids = universe["IQ_COMPANY_ID"].tolist()
    if set(ids) != set(training) | set(holdout):
        raise ValueError("Eligible universe and split differ")
    sector = load_sector_facets(sector_path, ids)
    embeddings, cache_error = fe.load_saved_embeddings(
        base, ids, OUTPUTS_LOCAL / "comps/embeddings")
    _, general = cd.similarity(embeddings)
    sectors = sc.sector_table(universe.set_index("IQ_COMPANY_ID")).reindex(ids)
    extra = {"sector": sc.sector_similarity(sectors, ids),
             "sic": sc.sic_similarity(sectors, ids)}
    extra.update(fe.sector_facet_matrices(sector.reset_index(), ids, sectors))
    sub = sector["sub_sector"].where(
        sector["sub_sector_status"].eq("stated") & sector["sub_sector"].ne(""))
    sub_emb, sub_cache = cd.embed_facets(
        pd.DataFrame({"sub_sector": sub}), OUTPUTS_LOCAL / "comps/embeddings")
    _, sub_mat = cd.similarity(sub_emb)
    extra["sub_sector"] = sub_mat["sub_sector"]
    similarity = fe.combine(fe.variants(general, extra)["generic + all sector facets"]["mats"])
    ranking = cd.rank_candidates(similarity, ids, holdout, training)
    candidates = cd.candidates(ranking)
    out.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(out / "ranking.csv.gz", index=False, compression="gzip")
    candidates.to_csv(out / "candidates.csv", index=False)
    metadata = {
        "split_run": config["split_run"], "universe_run": config["universe_run"],
        "facets_version": config["facets_version"],
        "sector_facets_version": sf.PROMPT_VERSION,
        "sector_facets_sha256": hashlib.sha256(sector_path.read_bytes()).hexdigest(),
        "sub_sector_embedding_cache": sub_cache.name,
        "max_saved_pair_cosine_difference": cache_error,
        "configuration": "generic + all sector facets (Fiona's facet_eval variant)",
        "weights": "equal across jointly known facets",
        "targets": len(holdout), "pool": len(training),
        "ranking_pairs": len(ranking), "candidate_pairs": len(candidates),
    }
    (out / "run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sector-facets", type=Path, default=FACETS)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    print(json.dumps(run(sector_path=args.sector_facets, out=args.out), indent=2))
