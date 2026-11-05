"""
Write the v1 baseline's comp lists (B3 = method 1, see facet_weighting.py)
as a candidates run that the LLM selectors can read. No API calls; the
embeddings come from the local text cache, and a text not cached yet is
embedded with the local model (all-mpnet-base-v2, downloaded once if
missing).

For every training target (or every company with --targets all) against the
training pool of the split:
  - ranking.csv.gz   every pool firm, most similar first: rank, similarity,
                     z (over the pool), in_top_k (the one-way top 10);
  - candidates.csv   the one-way top 10 only, plus `mutual` (each is in the
                     other's top 10), `selected` (the baseline's comp list:
                     the mutual comps, topped up from the one-way list to
                     MIN_COMPS) and `topped_up`;
  - run.json         inputs and settings.
Runs go to outputs-local/v1/candidates_method1/<time>/, a separate root
from v0's outputs-local/v1/candidates/, so the selectors' default ("the
latest candidates run") is unchanged. `cosine_then_llm.py --b3` reads the
latest run here and asks the LLM about each target's `selected` list.

  uv run python v1/scripts/method1_candidates.py                  # training targets
  uv run python v1/scripts/method1_candidates.py --targets all    # every company (holdout too)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import candidates as cd  # noqa: E402
import facet_weighting as fw  # noqa: E402
import facets as fc  # noqa: E402
from fill_facets import DEFAULT_OUT as FACETS_OUT, output_paths  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

V1 = OUTPUTS_LOCAL / "v1"
OUT_ROOT = V1 / "candidates_method1"
DEFAULT_SPLIT = "20261027T204930Z"          # the SIC2 split every v0/v1 result since 2026-10-27 uses
TEXT_CACHE = V1 / "embeddings" / f"texts_{cd.EMBED_MODEL.split('/')[-1]}.npz"


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


def build(split_run: str = DEFAULT_SPLIT, targets: str = "training") -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """The full ranking, the candidates table and the run record (not yet written)."""
    split_dir = V1 / "split" / split_run
    split_info = json.loads((split_dir / "run.json").read_text(encoding="utf-8"))
    universe = pd.read_csv(V1 / "universe" / split_info["universe_run"] / "universe.csv", dtype=str)
    split = pd.read_csv(split_dir / "split.csv", dtype=str)
    facets = pd.read_csv(output_paths(FACETS_OUT).tables / "facets.csv", dtype=str).fillna("")
    facets = facets[(facets["prompt_version"] == fc.PROMPT_VERSION) & (facets["llm_status"] == "ok")]
    training = split.loc[split["sample"] == "training", "IQ_COMPANY_ID"].tolist()
    target_ids = training if targets == "training" else split["IQ_COMPANY_ID"].tolist()

    texts = fw.facet_texts(facets).reindex(universe["IQ_COMPANY_ID"])
    ids = list(texts.index)
    vectors = fw.embed_texts({t for n in texts for t in texts[n].dropna()}, TEXT_CACHE)
    S, _, k_sat = fw.method1_similarity(texts, vectors)

    ticker = universe.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
    ranking, top = tables_from_similarity(S, ids, target_ids, training, ticker)
    run = {"method": "B3 = method 1 (v1 baseline): 0.5 embedding cosine + 0.5 TF-IDF cosine per facet, "
                     "information weights, 'none' as missing, company size out; mutual top 10 topped up to 3",
           "universe_run": split_info["universe_run"], "split_run": split_run, "facets_version": fc.PROMPT_VERSION,
           "facets": list(texts.columns), "excluded_facets": list(fw.EXCLUDED_FACETS), "alpha": fw.ALPHA,
           "saturation_k": k_sat, "top_k": fw.TOP_K, "min_comps": fw.MIN_COMPS, "targets": targets,
           "n_targets": len(target_ids), "pool": "training", "embed_model": cd.EMBED_MODEL,
           "text_cache": TEXT_CACHE.name, "selected_pairs": int(top["selected"].sum())}
    return ranking, top, run


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--split-run", default=DEFAULT_SPLIT)
    p.add_argument("--targets", choices=["training", "all"], default="training")
    args = p.parse_args()
    ranking, top, run = build(args.split_run, args.targets)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_ROOT / stamp
    out.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(out / "ranking.csv.gz", index=False)
    top.to_csv(out / "candidates.csv", index=False)
    (out / "run.json").write_text(json.dumps({"run": stamp, **run}, indent=1), encoding="utf-8")
    per = top[top["selected"]].groupby("target").size()
    print(f"wrote {out}: {run['n_targets']} targets, {len(top)} one-way top-{fw.TOP_K} pairs, "
          f"{run['selected_pairs']} in the baseline lists (median {per.median():.0f} per target)")


if __name__ == "__main__":
    main()
