"""
B3 comp lists for the current setting (v2/current.toml [profiles] and [retrieval]), as a candidates run the
LLM selectors read. No API calls; embeddings come from the text caches, and a text not cached yet is embedded
with the local model (all-mpnet-base-v2).

B3 (facet_weighting.py): per facet 0.5 x MPNet embedding cosine + 0.5 x TF-IDF cosine, combined with
information weights; company size out; "none" is missing. The current variant "Sonnet + Fiona sub-sector"
(Eric, b3_facet_add_drop.py) adds Fiona's sub-sector facet to the Sonnet general facets as one more facet in
the same combination. The comp list is the mutual top 10, topped up to 3 from the one-way list.

For every training target (or every company with --targets all) against the training pool of the split:
  - ranking.csv.gz   every pool firm, most similar first: rank, similarity, z (over the pool), in_top_k;
  - candidates.csv   the one-way top 10, plus `mutual`, `selected` (the comp list) and `topped_up`;
  - run.json         inputs and settings.

v1 history: v1/scripts/method1_candidates.py built plain B3 on the Haiku fills (run 20261104T074915Z); the
current list came from `b3_facet_add_drop.py --export-variant "Sonnet + Fiona sub-sector"`
(outputs-local/v1/facet_add_drop/selector_handoff/selector_candidates). This script builds the current list
directly; the 03_retrieval notebook checks that it reproduces the seeded copy.

  uv run python v2/03_retrieval/scripts/method1_candidates.py                  # training targets
  uv run python v2/03_retrieval/scripts/method1_candidates.py --targets all    # every company (holdout too)
Writes outputs-local/v2/03_retrieval/candidates/<time>/.
"""

from __future__ import annotations

import sys as _sys  # v2: shared paths (common/paths.py) put every component's scripts on the path
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import candidates as cd  # noqa: E402
import facet_weighting as fw  # noqa: E402
import facets as fc  # noqa: E402

OUT_ROOT = v2.out("03_retrieval") / "candidates"
TEXT_CACHE = v2.out("03_retrieval") / "cache" / f"texts_{cd.EMBED_MODEL.split('/')[-1]}.npz"
# vectors already computed in v1 (read only): the shared text cache and the add/drop experiment's cache
V1_CACHES = [v2.V1_OUTPUTS / "embeddings" / f"texts_{cd.EMBED_MODEL.split('/')[-1]}.npz",
             v2.V1_OUTPUTS / "facet_add_drop" / "cache" / "new_texts.npz"]
VARIANTS = {"Sonnet": [], "Sonnet + Fiona sub-sector": ["sub_sector"]}


def tables_from_similarity(S, ids: list[str], target_ids: list[str], training: list[str],
                           ticker: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Format any B3-compatible similarity matrix for the existing selector."""
    ranking = cd.rank_candidates(S, ids, targets=target_ids, pool=training, k=fw.TOP_K)
    ranking = ranking[["target", "rank", "comp", "similarity", "z", "in_top_k"]]
    chosen = fw.mutual_top_k(S, ids, target_ids, training, k=fw.TOP_K, min_comps=fw.MIN_COMPS)
    top = ranking[ranking["in_top_k"]].merge(chosen[["target", "comp", "mutual", "topped_up"]],
                                              on=["target", "comp"], how="left")
    top["selected"] = top["mutual"].notna()
    top["mutual"] = top["mutual"].eq(True)
    top["topped_up"] = top["topped_up"].eq(True)
    top.insert(1, "target_ticker", top["target"].map(ticker))
    top.insert(top.columns.get_loc("comp") + 1, "comp_ticker", top["comp"].map(ticker))
    return ranking, top


def vectors(texts: set[str]) -> dict[str, np.ndarray]:
    seed = {}
    for cache in V1_CACHES:
        known = fw.load_text_cache(cache)
        seed.update({t: known[fw._key(t)] for t in texts if fw._key(t) in known and t not in seed})
    return fw.embed_texts(texts, TEXT_CACHE, seed=seed)


def similarity(ids: list[str], cur: dict) -> tuple[np.ndarray, dict]:
    """The current B3 similarity over all companies in `ids` (rows/columns in that order)."""
    per, info, k_sat = per_facet(ids, cur)
    return fw.combine(per, info), {"facets": list(per), "saturation_k": k_sat}


def per_facet(ids: list[str], cur: dict) -> tuple[dict[str, np.ndarray], pd.DataFrame, float]:
    """Each facet's 0.5 embedding + 0.5 TF-IDF similarity of the current variant, before information
    weighting (also read by 09_analysis/facet_uplift.py), the information table and saturation k."""
    variant = cur["retrieval"]["variant"]
    if variant not in VARIANTS:
        raise SystemExit(f"unknown B3 variant {variant!r}; known: {list(VARIANTS)}")
    general = pd.read_csv(v2.path(cur["profiles"]["general"]), dtype=str).fillna("")
    general = general[(general["prompt_version"] == cur["profiles"]["general_prompt_version"])
                      & (general["llm_status"] == "ok")]
    texts = fw.facet_texts(general).reindex(ids)
    if texts.isna().all(axis=1).any():
        raise SystemExit("general facets do not cover every company")
    wanted = {t for n in texts for t in texts[n].dropna()}
    sector = None
    if "sub_sector" in VARIANTS[variant]:
        sector = pd.read_csv(v2.path(cur["profiles"]["sector"]), dtype=str).fillna("").set_index("IQ_COMPANY_ID")
        sector = sector.reindex(ids)
        sub = sector["sub_sector"].where(sector["sub_sector_status"] == "stated")
        wanted |= {t for t in sub.dropna() if t}
    vec = vectors(wanted)
    lex, raw, _ = fw.lexical(texts)
    info, k_sat = fw.information(raw)
    per = fw.blend(fw.embedding_cosines(texts, vec), lex)
    if sector is not None:
        sub_texts = pd.DataFrame({"sub_sector": sector["sub_sector"].where(sector["sub_sector_status"] == "stated")})
        sub_lex, _, _ = fw.lexical(sub_texts)
        per["Fiona sub-sector"] = fw.blend(fw.embedding_cosines(sub_texts, vec), sub_lex)["sub_sector"]
    return per, info, k_sat


def build(targets: str = "training") -> tuple[pd.DataFrame, pd.DataFrame, dict, np.ndarray, list[str]]:
    """The full ranking, the candidates table, the run record (not yet written), S and the id order."""
    cur = v2.current()
    universe = pd.read_csv(v2.path(cur["universe"]["universe"]), dtype=str)
    split = pd.read_csv(v2.path(cur["universe"]["split"]), dtype=str)
    ids = universe["IQ_COMPANY_ID"].tolist()
    training = split.loc[split["sample"] == "training", "IQ_COMPANY_ID"].tolist()
    target_ids = training if targets == "training" else split["IQ_COMPANY_ID"].tolist()
    S, detail = similarity(ids, cur)
    ticker = universe.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
    ranking, top = tables_from_similarity(S, ids, target_ids, training, ticker)
    run = {"method": "B3: 0.5 embedding cosine + 0.5 TF-IDF cosine per facet, information weights, "
                     "'none' as missing, company size out; mutual top 10 topped up to 3",
           "variant": cur["retrieval"]["variant"], "universe_run": cur["universe"]["universe_run"],
           "split_run": cur["universe"]["split_run"], "general_facets": cur["profiles"]["general"],
           "facets_version": cur["profiles"]["general_prompt_version"], "sector_facets": cur["profiles"]["sector"],
           **detail, "excluded_facets": list(fw.EXCLUDED_FACETS), "alpha": fw.ALPHA, "top_k": fw.TOP_K,
           "min_comps": fw.MIN_COMPS, "targets": targets, "n_targets": len(target_ids), "pool": "training",
           "embed_model": cd.EMBED_MODEL, "selected_pairs": int(top["selected"].sum())}
    return ranking, top, run, S, ids


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--targets", choices=["training", "all"], default="training")
    args = p.parse_args()
    ranking, top, run, _, _ = build(args.targets)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_ROOT / stamp
    out.mkdir(parents=True, exist_ok=False)
    ranking.to_csv(out / "ranking.csv.gz", index=False)
    top.to_csv(out / "candidates.csv", index=False)
    (out / "run.json").write_text(json.dumps({"run": stamp, **run}, indent=1), encoding="utf-8")
    per = top[top["selected"]].groupby("target").size()
    print(f"wrote {out}: {run['n_targets']} targets, {len(top)} one-way top-{fw.TOP_K} pairs, "
          f"{run['selected_pairs']} in the comp lists (median {per.median():.0f} per target)")


if __name__ == "__main__":
    main()
