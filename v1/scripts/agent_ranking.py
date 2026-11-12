"""Rank comps by evidence-supported points from the agent loop's per-facet scores.

The agent loop run with --facet-scores gives each pair a 0/25/50/75/100 score per
general facet, or null (UNKNOWN) when one side has no evidence for it. This
script turns those into Barbara's three numbers (her Similarity_Scoring_Standard,
read only, nothing copied from her repo except the formula and weights):

  w  = facet weight (sums to 1 over the facets below)
  s  = facet score / 100, only for facets with evidence on both sides (observed)
  C  = evidence coverage        = sum(w over observed facets)
  S  = observed similarity      = 100 * sum(w * s) / C    (undefined if C = 0)
  E  = evidence-supported points = 100 * sum(w * s)
  bounds = [E, E + 100 * (1 - C)]   (missing-information bounds, not a CI)

Comps are ranked within each target by E (ties: higher S, then B3 similarity).
Missing evidence lowers E, it never counts as 0 similarity in S.

Weights: Barbara's proposed v3.1 general-facet points, mapped to our facets and
renormalized to 100. Customer Type (5) + Customer Segment (4) -> customer_segment (9).
With industry facets (agent_loop --industry-facets) the target's SIC2 module from her
policy (policy/barbara_scoring_policy_v3.json) is added: base fields only, diagnostic
fields dropped, conditional subtype fields only when activated for the target
(--activate file), points renormalized within the block, then general 60% /
industry 40% (her default block weights). Each pair saves the weights it used.

Evaluation (--labels): per target, how many reviewer peers (score >= 1) are in the
top k when ordering by E, by B3 similarity, and by the agent's 0/1/2 grade; and
pairwise accuracy = share of (peer, non-peer) pairs within a target where the
peer is ranked above.

Run:
  uv run python v1/scripts/agent_ranking.py --run outputs-local/v1/agent_loop/<run>
  uv run python v1/scripts/agent_ranking.py --run <run> --labels outputs-local/v1/integration/barbara_matches/reviewed_pairs.csv
Writes <run>/ranking/<stamp>/ranking.csv and eval.json (never overwrites).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

POLICY = Path(__file__).resolve().parent / "policy" / "barbara_scoring_policy_v3.json"

# facet key -> (Barbara v3.1 points, what the agent compares)
FACET_POINTS: dict[str, tuple[int, str]] = {
    "primary_products": (10, "the main physical or software products sold"),
    "primary_services": (5, "the main services sold"),
    "customer_segment": (9, "who the buyers are (consumers, businesses, government; type and segment)"),
    "end_markets": (7, "the industries or end uses the customers are in"),
    "business_model": (9, "how the company operates and makes money overall (maker, distributor, "
                          "operator, platform, contractor ...)"),
    "revenue_model": (9, "how revenue is earned (product sales, subscription, fees, contracts, rent ...)"),
    "value_chain_position": (5, "where it sits in the value chain (raw material, component, OEM, "
                                "distributor, retailer, service provider)"),
    "geography_served": (3, "where its customers are"),
    "specialization": (3, "how specialized or niche the offering is"),
    "distribution_channels": (3, "how it reaches customers (direct sales, dealers, online, stores ...)"),
    "regulatory_exposure": (3, "regulation that shapes the business"),
}
TOTAL_POINTS = sum(p for p, _ in FACET_POINTS.values())
WEIGHTS = {k: p / TOTAL_POINTS for k, (p, _) in FACET_POINTS.items()}
LEVELS = [0, 25, 50, 75, 100]


def _policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def industry_fields(sic2: str | int | None, active: set[str] | frozenset = frozenset()) -> list[dict]:
    """Scored industry fields for a SIC2 module: base fields plus activated conditional ones."""
    if sic2 is None or pd.isna(sic2):
        return []
    code = f"{int(float(sic2)):02d}"
    module = next((m for m in _policy()["industry_modules"] if m["code"] == code), None)
    if module is None or module.get("reference_only"):
        return []
    out = []
    for f in module["fields"]:
        if f["diagnostic_only"] or not f["importance_points"]:
            continue
        if f["conditional_extension"] and f["id"] not in active:
            continue
        out.append({"key": f["id"], "name": f["name"], "examples": f["examples"][:3],
                    "points": f["importance_points"]})
    return out


def pair_weights(fields: list[dict]) -> dict[str, float]:
    """Facet key -> weight (sums to 1). General only when there are no industry fields."""
    if not fields:
        return dict(WEIGHTS)
    block = _policy()["default_block_weights"]
    g, i = block["general"] / 100, block["industry"] / 100
    total = sum(f["points"] for f in fields)
    return {**{k: g * w for k, w in WEIGHTS.items()}, **{f["key"]: i * f["points"] / total for f in fields}}


def points(scores: dict[str, float | None], weights: dict[str, float] | None = None) -> dict[str, float | None]:
    """C, S, E and bounds (all on 0-100) from {facet: 0..100 or None}."""
    weights = weights or WEIGHTS
    observed = {k: v for k, v in scores.items() if k in weights and v is not None}
    c = sum(weights[k] for k in observed)
    ws = sum(weights[k] * v / 100 for k, v in observed.items())
    gen_w = sum(w for k, w in weights.items() if k in WEIGHTS)
    ind_w = 1 - gen_w
    gen_c = sum(weights[k] for k in observed if k in WEIGHTS)
    extra = {"general_coverage": round(100 * gen_c / gen_w, 2) if gen_w else None,
             "industry_coverage": round(100 * (c - gen_c) / ind_w, 2) if ind_w > 1e-9 else None}
    return extra | {"coverage": round(100 * c, 2),
            "observed_similarity": round(100 * ws / c, 2) if c else None,
            "evidence_points": round(100 * ws, 2),
            "upper_bound": round(100 * ws + 100 * (1 - c), 2),
            "observed_facets": len(observed)}


def rank(verdicts: pd.DataFrame) -> pd.DataFrame:
    """Adds C/S/E and e_rank (1 = best within target) to a verdicts.csv table."""
    rows = []
    for _, r in verdicts.iterrows():
        weights = json.loads(r["facet_weights"]) if isinstance(r.get("facet_weights"), str) else dict(WEIGHTS)
        scores = {k: (None if pd.isna(r.get(f"facet_{k}")) else float(r[f"facet_{k}"])) for k in weights}
        rows.append(points(scores, weights))
    out = pd.concat([verdicts.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    out = out.sort_values(["target_ticker", "evidence_points", "observed_similarity", "similarity"],
                          ascending=[True, False, False, False], na_position="last")
    out["e_rank"] = out.groupby("target_ticker").cumcount() + 1
    return out


def _order_metrics(df: pd.DataFrame, key: str, ascending: bool, k: int) -> dict:
    hits, pair_ok, pair_n = [], 0, 0
    for _, g in df.groupby("target"):
        g = g.sort_values([key, "similarity"], ascending=[ascending, False], na_position="last")
        g = g.reset_index(drop=True)
        hits.append(int(g["peer"].head(k).sum()))
        pos = {i: p for i, p in zip(g.index, g["peer"])}
        for i in pos:
            for j in pos:
                if pos[i] and not pos[j]:
                    pair_n += 1
                    pair_ok += i < j
    n_top = sum(min(k, len(g)) for _, g in df.groupby("target"))
    return {"peers_in_top_k": sum(hits), "slots": n_top,
            "precision_at_k": round(sum(hits) / n_top, 3) if n_top else None,
            "pairwise_accuracy": round(pair_ok / pair_n, 3) if pair_n else None, "pairs_compared": pair_n}


def spearman(a: pd.Series, b: pd.Series) -> float | None:
    """Rank correlation without scipy (average ranks for ties)."""
    ok = a.notna() & b.notna()
    if ok.sum() < 3:
        return None
    return round(float(a[ok].rank().corr(b[ok].rank())), 3)


def evaluate(ranked: pd.DataFrame, labels: pd.DataFrame, label_col: str = "score_barbara",
             ks: tuple[int, ...] = (3, 6, 7)) -> dict:
    lab = labels.rename(columns={"target_id": "target", "comp_id": "comp"})[["target", "comp", label_col]]
    df = ranked.merge(lab.astype({"target": str, "comp": str}), on=["target", "comp"], how="inner")
    df = df[df[label_col].notna()].copy()
    df["peer"] = df[label_col] >= 1
    df["agent_order"] = df["score"].fillna(-1)
    out = {"pairs": len(df), "targets": int(df["target"].nunique()), "peers": int(df["peer"].sum()),
           "spearman_E_vs_label": spearman(df["evidence_points"], df[label_col]),
           "spearman_S_vs_label": spearman(df["observed_similarity"], df[label_col]),
           "spearman_B3_vs_label": spearman(df["similarity"], df[label_col]),
           "mean_coverage": round(df["coverage"].mean(), 1), "by_k": {}}
    for k in ks:
        out["by_k"][k] = {"E": _order_metrics(df, "evidence_points", False, k),
                          "B3": _order_metrics(df, "similarity", False, k),
                          "agent_0_1_2": _order_metrics(df, "agent_order", False, k)}
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True, help="agent loop run folder (with verdicts.csv)")
    ap.add_argument("--labels", type=Path, help="reviewer labels with target_id, comp_id and --label-col")
    ap.add_argument("--label-col", default="score_barbara")
    args = ap.parse_args(argv)

    verdicts = pd.read_csv(args.run / "verdicts.csv", dtype={"target": str, "comp": str})
    missing = [k for k in WEIGHTS if f"facet_{k}" not in verdicts]
    if missing:
        raise SystemExit(f"no facet columns {missing}: run agent_loop.py with --facet-scores")
    ranked = rank(verdicts[verdicts["status"] == "ok"])
    out = args.run / "ranking" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    ranked.to_csv(out / "ranking.csv", index=False)
    report = {"weights_points": {k: p for k, (p, _) in FACET_POINTS.items()}, "total_points": TOTAL_POINTS}
    if args.labels:
        labels = pd.read_csv(args.labels, dtype={"target_id": str, "comp_id": str})
        report["eval"] = evaluate(ranked, labels, args.label_col)
        print(json.dumps(report["eval"], indent=1))
    (out / "eval.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"ranking: {out / 'ranking.csv'}")


if __name__ == "__main__":
    main()
