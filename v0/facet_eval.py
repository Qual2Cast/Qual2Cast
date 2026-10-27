"""
Which facets make a better comp? Facet add/drop review (general demand #1)
and the sector sub-models (recipe steps 5-6), scored against labeled
target-comp pairs: the golden set (human, 2/1/0 rubric) and the step 6
judge (LLM, good/bad). The measure is how well each variant ranks the
labeled comps, not valuation error: EV/EBITDA is never read here.

A variant is a set of similarity facets with weights, and optionally a
pool rule. Every variant ranks every training target's pool the same way
as step 4 (candidates.rank_candidates): the weighted mean of per-facet
similarities over the facets both companies have.

Facet similarities:
- the eleven general facets (F1-F8, F10-F12): embedding cosine, as step 4;
- sector: 1 same FF49 industry, 0.5 same sector group, 0 otherwise
  (sectors.sector_similarity), from the SIC code;
- sub_sector: embedding cosine of the sub-sector text;
- sector-specific category facets: Jaccard overlap of the categories,
  only between two companies of the same sector group (NaN otherwise, so
  the facet is left out of that pair, like an unknown facet).

Variants (variants()):
- generic: the current step 4 similarity;
- generic minus <facet>: one general facet dropped (the add/drop review);
- generic + sector / + sub_sector / + sector facets / + all three;
- sub-model: generic + all three, and comps only from the target's sector
  group when that group has at least MIN_POOL training firms (else the
  whole pool).

Metrics per variant (rank_metrics), over the labeled targets:
- pairwise accuracy: of two labeled comps of one target with different
  labels, how often the better one is ranked higher (0.5 = chance);
- recall@10 of the best-labeled comps (score 1 after scaling);
- MRR: 1 / the rank of the first best-labeled comp;
- top-10 label mean: the mean label of labeled comps that land in the
  top 10, with the share of the top 10 that is labeled (low coverage
  means the variant's top 10 needs judging before that number counts).

Training targets and comps only: a label that touches a holdout company is
dropped and counted.

  python v0/facet_eval.py --gold path/to/golden_set.csv     # + judge labels if present
  python v0/facet_eval.py --no-judge --gold golden.xlsx
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facets as fc  # noqa: E402  (also puts website_scrape/ and src/ on the path)
import sector_facets as sf  # noqa: E402
import sectors as sc  # noqa: E402

MIN_POOL = 8          # sub-model: a sector group needs this many training firms to search only inside it
TOP_K = 10
GENERIC = "generic (step 4)"


# ---------------------------------------------------------------- similarity

def combine(mats: dict[str, np.ndarray], weights: dict[str, float] | None = None) -> np.ndarray:
    """Weighted mean of similarity matrices over the facets both companies
    have (NaN in a matrix = that facet left out for that pair); NaN where a
    pair shares none."""
    weights = weights or {k: 1.0 for k in mats}
    num = den = 0.0
    for name, M in mats.items():
        w = weights.get(name, 0.0)
        if w == 0:
            continue
        have = ~np.isnan(M)
        num = num + w * np.where(have, M, 0.0)
        den = den + w * have
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def category_similarity(cats: pd.Series, group: pd.Series) -> np.ndarray:
    """Jaccard overlap of category sets ("a|b"), only within one sector
    group; NaN if either is missing or the groups differ."""
    sets = [set(c.split("|")) if isinstance(c, str) and c else None for c in cats]
    g = group.to_numpy()
    n = len(sets)
    M = np.full((n, n), np.nan)
    for i in range(n):
        if sets[i] is None:
            continue
        for j in range(i, n):
            if sets[j] is None or g[i] != g[j]:
                continue
            M[i, j] = M[j, i] = len(sets[i] & sets[j]) / len(sets[i] | sets[j])
    return M


def sector_facet_matrices(sector_facets: pd.DataFrame, ids: Sequence[str], sectors: pd.DataFrame
                          ) -> dict[str, np.ndarray]:
    """One Jaccard matrix per sector-specific category facet, keyed
    "sector:<facet>" (the same facet name in two groups, e.g. price_tier,
    stays separate because pairs across groups are NaN)."""
    t = sector_facets.set_index("IQ_COMPANY_ID").reindex(ids)
    group = sectors.reindex(ids)["sector"]
    out = {}
    for name in sf.all_facet_names():
        col = f"{name}_categories"
        if col in t.columns:
            ok = t.get(f"{name}_status", pd.Series(index=t.index, dtype=object)) == "stated"
            out[f"sector:{name}"] = category_similarity(t[col].where(ok), group)
    return out


def restrict_to_sector(S: np.ndarray, ids: Sequence[str], sectors: pd.DataFrame, pool: Sequence[str],
                       min_pool: int = MIN_POOL) -> np.ndarray:
    """S with pairs outside the target's sector group set to NaN, for
    targets whose group has at least min_pool pool firms besides itself."""
    grp = sectors.reindex(ids)["sector"].to_numpy()
    pool_set = set(pool)
    in_pool = np.array([i in pool_set for i in ids])
    S = S.copy()
    for i in range(len(ids)):
        same = grp == grp[i]
        if (same & in_pool).sum() - (1 if in_pool[i] else 0) >= min_pool:
            S[i, ~same] = np.nan
    return S


# ---------------------------------------------------------------- variants

def variants(general: dict[str, np.ndarray], extra: dict[str, np.ndarray]) -> dict[str, dict]:
    """name -> {"mats": {...}, "restrict": bool}. `general`: the step 4
    per-facet cosines; `extra`: any of "sector", "sub_sector" and
    "sector:<facet>" matrices."""
    out = {GENERIC: {"mats": dict(general), "restrict": False}}
    for name in general:
        out[f"generic minus {fc.FACET_ID.get(name, '')} {name}".replace("  ", " ")] = {
            "mats": {k: v for k, v in general.items() if k != name}, "restrict": False}
    sector_specific = {k: v for k, v in extra.items() if k.startswith("sector:")}
    if "sector" in extra:
        out["generic + sector (FF49)"] = {"mats": {**general, "sector": extra["sector"]}, "restrict": False}
    if "sic" in extra:
        out["generic + sub-sector (SIC4)"] = {"mats": {**general, "sic": extra["sic"]}, "restrict": False}
        if "sector" in extra:
            both = {**general, "sector": extra["sector"], "sic": extra["sic"]}
            out["generic + sector (FF49) + sub-sector (SIC4)"] = {"mats": both, "restrict": False}
            if "geography_served" in general:
                out["generic minus F8 + sector + sub-sector (SIC4)"] = {
                    "mats": {k: v for k, v in both.items() if k != "geography_served"}, "restrict": False}
    if "sub_sector" in extra:
        out["generic + sub-sector"] = {"mats": {**general, "sub_sector": extra["sub_sector"]}, "restrict": False}
    if sector_specific:
        out["generic + sector-specific facets"] = {"mats": {**general, **sector_specific}, "restrict": False}
    if len(set(extra) - {"sector", "sic"}) > 0:
        out["generic + all sector facets"] = {"mats": {**general, **extra}, "restrict": False}
    if "sector" in extra or sector_specific:
        out["sub-model (same sector group) + all sector facets"] = {"mats": {**general, **extra}, "restrict": True}
        out["sub-model (same sector group), generic facets"] = {"mats": dict(general), "restrict": True}
    return out


def rank(S: np.ndarray, ids: Sequence[str], targets: Sequence[str], pool: Sequence[str]) -> pd.DataFrame:
    """target, comp, rank (1 = most similar), similarity; every pool firm
    with a similarity, the target itself left out."""
    pos = {x: i for i, x in enumerate(ids)}
    pool_pos = np.array([pos[x] for x in pool])
    rows = []
    for t in targets:
        i = pos[t]
        cand = pool_pos[pool_pos != i]
        s = S[i, cand]
        keep = ~np.isnan(s)
        cand, s = cand[keep], s[keep]
        order = np.argsort(-s, kind="stable")
        rows.append(pd.DataFrame({"target": t, "comp": [ids[j] for j in cand[order]],
                                  "rank": np.arange(1, len(order) + 1), "similarity": s[order]}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["target", "comp", "rank", "similarity"])


# ---------------------------------------------------------------- labels and metrics

def load_labels(path: Path, ticker_to_id: dict[str, str]) -> pd.DataFrame:
    """A labeled pairs file (.csv or .xlsx) -> target, comp (IQ ids), gain
    in [0, 1]. Columns are found by name: target / target_ticker,
    comp / comp_ticker, and score / label / grade. Tickers or IQ ids both
    work. Scores on a 0-2 scale (the comps rubric) are halved; 0 / 0.5 / 1
    stays."""
    d = pd.read_excel(path) if str(path).lower().endswith((".xlsx", ".xls")) else pd.read_csv(path)
    d.columns = [str(c).strip().lower() for c in d.columns]

    def pick(*names):
        for n in names:
            if n in d.columns:
                return d[n]
        raise SystemExit(f"{path}: no column named any of {names}; columns are {list(d.columns)}")

    def to_id(x):
        x = str(x).strip()
        return x if x.startswith("IQ") else ticker_to_id.get(x.upper())

    out = pd.DataFrame({"target": pick("target_iq_id", "target", "target_ticker").map(to_id),
                        "comp": pick("comp_iq_id", "comp", "comp_ticker").map(to_id),
                        "score": pd.to_numeric(pick("score", "label", "grade", "rating"), errors="coerce")})
    bad = out.isna().any(axis=1)
    if bad.any():
        print(f"{path.name}: {int(bad.sum())} rows without a known target, comp or score left out")
    out = out[~bad]
    top = out["score"].max()
    out["gain"] = out["score"] / (2.0 if top > 1 else 1.0)
    return out.drop_duplicates(["target", "comp"], keep="last")[["target", "comp", "gain"]]


def training_only(labels: pd.DataFrame, training: set[str]) -> tuple[pd.DataFrame, int]:
    keep = labels["target"].isin(training) & labels["comp"].isin(training)
    return labels[keep], int((~keep).sum())


def rank_metrics(ranking: pd.DataFrame, labels: pd.DataFrame, k: int = TOP_K) -> dict:
    """See the module docstring. Labeled comps the variant doesn't rank at
    all (pool rule) count as ranked last."""
    r = labels.merge(ranking[["target", "comp", "rank"]], on=["target", "comp"], how="left")
    worst = ranking.groupby("target")["rank"].max()
    r["rank"] = r["rank"].fillna(r["target"].map(worst).fillna(0) + 1)
    pairs_ok = pairs_n = 0
    recall, mrr = [], []
    for t, g in r.groupby("target"):
        gains, ranks = g["gain"].to_numpy(), g["rank"].to_numpy()
        diff = gains[:, None] > gains[None, :]
        pairs_n += int(diff.sum())
        pairs_ok += int((diff & (ranks[:, None] < ranks[None, :])).sum())
        best = ranks[gains >= 1.0]
        if len(best):
            recall.append(float((best <= k).mean()))
            mrr.append(1.0 / best.min())
    top = ranking[ranking["rank"] <= k].merge(labels, on=["target", "comp"], how="left")
    top = top[top["target"].isin(labels["target"])]
    return {"labeled targets": r["target"].nunique(), "labeled pairs": len(r),
            "pairwise accuracy": pairs_ok / pairs_n if pairs_n else np.nan, "pairs compared": pairs_n,
            f"recall@{k} of best comps": np.mean(recall) if recall else np.nan,
            "MRR of best comps": np.mean(mrr) if mrr else np.nan,
            f"top-{k} label mean": top["gain"].mean(),
            f"top-{k} labeled share": top["gain"].notna().mean() if len(top) else np.nan}


def evaluate(variant_defs: dict[str, dict], ids: Sequence[str], training: Sequence[str],
             sectors: pd.DataFrame, label_sets: dict[str, pd.DataFrame], k: int = TOP_K
             ) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """One row per (variant, label set); and each variant's top-k ranking."""
    rows, tops = [], {}
    targets = sorted(set().union(*[set(l["target"]) for l in label_sets.values()])) if label_sets else []
    for name, v in variant_defs.items():
        S = combine(v["mats"])
        if v["restrict"]:
            S = restrict_to_sector(S, ids, sectors, training)
        ranking = rank(S, ids, targets, training)
        tops[name] = ranking[ranking["rank"] <= k]
        for label_name, labels in label_sets.items():
            rows.append({"variant": name, "labels": label_name, "facets": len(v["mats"]),
                         **rank_metrics(ranking, labels, k)})
    return pd.DataFrame(rows), tops


# ---------------------------------------------------------------- run

def _latest(root: Path, file: str) -> Path:
    runs = sorted(p for p in root.iterdir() if (p / file).exists()) if root.exists() else []
    if not runs:
        raise SystemExit(f"nothing in {root} with {file}")
    return runs[-1]


def main() -> None:
    import candidates as cd
    from fill_facets import DEFAULT_OUT as FACETS_OUT, output_paths
    from project_data import OUTPUTS_LOCAL

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--gold", nargs="*", default=[], help="golden-set file(s), .csv or .xlsx")
    p.add_argument("--no-judge", action="store_true", help="leave out the step 6 judge labels")
    p.add_argument("--sector-facets", help="sector_facets.csv (default: outputs-local/comps/sector_facets/tables/)")
    p.add_argument("--k", type=int, default=TOP_K)
    p.add_argument("--stage", default="comps",
                   help="outputs-local folder with the split and judge to use: comps (previous baseline) or "
                        "comps_pilot_targets (updated baseline, SIC2 split)")
    args = p.parse_args()

    comps = OUTPUTS_LOCAL / "comps"
    universe_run = _latest(comps / "universe", "universe.csv")
    info = pd.read_csv(universe_run / "universe.csv", dtype=str).set_index("IQ_COMPANY_ID")
    stage = OUTPUTS_LOCAL / args.stage
    split_run = _latest(stage / "split", "split.csv")
    split = pd.read_csv(split_run / "split.csv", dtype=str)
    training = split.loc[split["sample"] == "training", "IQ_COMPANY_ID"].tolist()
    facets = pd.read_csv(output_paths(FACETS_OUT).tables / "facets.csv", dtype=str).fillna("")
    facets = facets[(facets["prompt_version"] == fc.PROMPT_VERSION) & (facets["llm_status"] == "ok")]
    texts = cd.facet_texts(facets).reindex(info.index)
    texts = texts.astype(object).where(texts.notna(), None)   # unknown as None (pandas 3 gives NaN), so the step 4 embedding cache matches
    ids = list(texts.index)
    emb, _ = cd.embed_facets(texts, comps / "embeddings")
    _, general = cd.similarity(emb)

    sectors = sc.sector_table(info)
    extra = {"sector": sc.sector_similarity(sectors, ids), "sic": sc.sic_similarity(sectors, ids)}
    sf_path = Path(args.sector_facets) if args.sector_facets else comps / "sector_facets" / "tables" / "sector_facets.csv"
    if sf_path.exists():
        sft = pd.read_csv(sf_path, dtype=str).fillna("")
        sft = sft[(sft["prompt_version"] == sf.PROMPT_VERSION) & (sft["llm_status"] == "ok")]
        sub = sft.set_index("IQ_COMPANY_ID").reindex(ids)
        sub_text = sub["sub_sector"].where((sub["sub_sector_status"] == "stated") & (sub["sub_sector"] != ""))
        sub_emb, _ = cd.embed_facets(pd.DataFrame({"sub_sector": sub_text}), comps / "embeddings")
        _, sub_mats = cd.similarity(sub_emb)
        extra["sub_sector"] = sub_mats["sub_sector"]
        extra.update(sector_facet_matrices(sft, ids, sectors))
        print(f"sector facets: {len(sft)} companies from {sf_path}")
    else:
        print(f"no sector facets yet ({sf_path}): sector (FF49) only")

    tick = {str(t).upper(): i for i, t in info["target_ciq_ticker"].items()}
    label_sets, dropped = {}, {}
    for g in args.gold:
        labels, n = training_only(load_labels(Path(g), tick), set(training))
        label_sets[f"gold:{Path(g).stem}"], dropped[Path(g).name] = labels, n
    if not args.no_judge:
        import judge_comps as jc
        jt = jc.output_paths(stage / "judge").tables / "judgments.csv"
        if jt.exists():
            j = pd.read_csv(jt, dtype={"target": str, "comp": str})
            j = j[j["prompt_version"] == jc.PROMPT_VERSION].dropna(subset=["score"])
            labels, n = training_only(j.assign(gain=j["score"].astype(float))[["target", "comp", "gain"]],
                                      set(training))
            label_sets["judge (LLM, z>=2 candidates)"], dropped["judge"] = labels, n
    if not label_sets:
        raise SystemExit("no labels: pass --gold, or run judge_comps.py first")
    for name, n in dropped.items():
        if n:
            print(f"{name}: {n} labeled pairs touch a holdout company and were left out")

    table, tops = evaluate(variants(general, extra), ids, training, sectors, label_sets, args.k)
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = stage / "facet_eval" / run
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "summary.csv", index=False)
    pd.concat(tops, names=["variant"]).reset_index(level=0).to_csv(out / f"top{args.k}.csv", index=False)
    sectors.to_csv(out / "sectors.csv")
    (out / "run.json").write_text(json.dumps({
        "run": run, "stage": args.stage, "split_run": split_run.name, "universe_run": universe_run.name, "facets_version": fc.PROMPT_VERSION,
        "sector_facets_version": sf.PROMPT_VERSION if sf_path.exists() else None, "k": args.k,
        "min_pool": MIN_POOL, "labels": {k: len(v) for k, v in label_sets.items()},
        "dropped_holdout_pairs": dropped}, indent=1), encoding="utf-8")
    pd.set_option("display.width", 220)
    for name, g in table.groupby("labels", sort=False):
        print(f"\n== {name}")
        print(g.drop(columns="labels").set_index("variant").sort_values("pairwise accuracy", ascending=False)
              .round(3).to_string())
    print("\nwrote", out)


if __name__ == "__main__":
    main()
