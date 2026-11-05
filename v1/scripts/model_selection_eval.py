"""
Model selection (plan item 3, 2026-11-04): does a stronger model pick better
comps? Compares the two LLM selectors run with two models on the same
inputs (B3 lists and the same facets, prompt 2026-11-04a):

- cosine_then_llm.py --b3: Sonnet vs Haiku screening the v1 baseline's lists
  (outputs-local/v1/cosine_then_llm/<candidates run>_<prompt>_{sonnet,haiku}/)
- direct_llm.py: Sonnet vs Haiku picking comps from the whole pool
  (outputs-local/v1/direct_llm/<split run>_<prompt>_{sonnet,haiku}/)

Two views, no model calls and no multiples:
1. Against the reviewers' golden set (round 1, PCTY and WEN, majority grade
   under the agreed rule in similarity_eval.py): per method, the comps listed,
   how many are labeled, precision, direct share, NDCG, and how many graded
   non-comps the list keeps. The B3 list itself is the baseline row.
2. Agreement between the two models on every training target: for the
   screen, the share of pairs with the same verdict and each model's keep
   rate; for the direct picks, the mean overlap (Jaccard) of the two lists
   and each model's mean list length.
3. The facet fills themselves (Haiku's outputs-local/v1/facets/ vs Sonnet's
   facets_sonnet/): per facet, how often the status differs, the word
   overlap of the two values, and how often the leading category (the text
   before the first colon, e.g. "B2B", "high", "brand owner") is the same.

  uv run python v1/scripts/model_selection_eval.py
  uv run python v1/scripts/model_selection_eval.py --screen-runs <folder> <folder> --direct-runs <folder> <folder>
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import golden_set as gs  # noqa: F401  (keeps the import path consistent with similarity_eval)
import similarity_eval as se
from fill_facets import stamp
from project_data import OUTPUTS_LOCAL

V1 = OUTPUTS_LOCAL / "v1"
LABELS = V1 / "golden_set" / "labels" / "reviewer_labels_20261028.json"
OUT = V1 / "model_selection"


def latest(folder: Path) -> Path:
    runs = sorted(p for p in folder.iterdir() if (p / "run.json").exists() or (p / "candidates.csv").exists())
    if not runs:
        raise SystemExit(f"No run in {folder}")
    return runs[-1]


def screen_list(run: Path) -> pd.DataFrame:
    """The comps a cosine_then_llm run kept (score 1), ranked by the B3 rank."""
    t = pd.read_csv(run / "tables" / "judgments.csv", dtype={"target": str, "comp": str})
    kept = t[t["score"] == 1].copy()
    kept["rank"] = kept.groupby("target")["rank"].rank(method="first").astype(int)
    return kept[["target", "comp", "rank"]].reset_index(drop=True)


def direct_list(run: Path) -> pd.DataFrame:
    t = pd.read_csv(run / "tables" / "suggestions.csv", dtype={"target": str, "comp": str})
    t = t[t["comp"].notna() & (t["comp"] != "")].copy()
    t["rank"] = t["rank"].astype(int)
    return t[["target", "comp", "rank"]].reset_index(drop=True)


def b3_list(run: Path) -> pd.DataFrame:
    t = pd.read_csv(run / "candidates.csv", dtype={"target": str, "comp": str})
    t = t[t["selected"].astype(str) == "True"].copy()
    t["rank"] = t.groupby("target")["rank"].rank(method="first").astype(int)
    return t[["target", "comp", "rank"]].reset_index(drop=True)


def golden_view(lists: dict[str, pd.DataFrame], grades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, selected in lists.items():
        m = se.list_metrics(selected, grades)
        for _, r in m.iterrows():
            rows.append({"method": name, **r.to_dict()})
    return pd.DataFrame(rows)


def screen_agreement(a: Path, b: Path, names: tuple[str, str]) -> dict:
    ta = pd.read_csv(a / "tables" / "judgments.csv", dtype={"target": str, "comp": str})
    tb = pd.read_csv(b / "tables" / "judgments.csv", dtype={"target": str, "comp": str})
    m = ta.merge(tb, on=["target", "comp"], suffixes=("_a", "_b"))
    return {"view": "screen", "targets both judged": m["target"].nunique(), "pairs both judged": len(m),
            "same verdict share": float((m["score_a"] == m["score_b"]).mean()) if len(m) else np.nan,
            f"keep rate {names[0]}": float(m["score_a"].mean()) if len(m) else np.nan,
            f"keep rate {names[1]}": float(m["score_b"].mean()) if len(m) else np.nan,
            f"targets with no comp kept {names[0]}": int((m.groupby("target")["score_a"].sum() == 0).sum()),
            f"targets with no comp kept {names[1]}": int((m.groupby("target")["score_b"].sum() == 0).sum())}


def direct_agreement(a: Path, b: Path, names: tuple[str, str]) -> dict:
    la, lb = direct_list(a), direct_list(b)
    common = sorted(set(la["target"]) & set(lb["target"]))
    jac, na, nb = [], [], []
    for t in common:
        sa, sb = set(la.loc[la["target"] == t, "comp"]), set(lb.loc[lb["target"] == t, "comp"])
        jac.append(len(sa & sb) / len(sa | sb) if sa | sb else np.nan)
        na.append(len(sa)); nb.append(len(sb))
    return {"view": "direct", "targets both picked": len(common),
            "mean overlap (Jaccard)": float(np.nanmean(jac)) if jac else np.nan,
            f"mean list length {names[0]}": float(np.mean(na)) if na else np.nan,
            f"mean list length {names[1]}": float(np.mean(nb)) if nb else np.nan}


STOP = {"and", "or", "the", "of", "to", "for", "a", "in", "b2b", "b2c", "b2g", "with", "its", "through"}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP


def facet_fill_comparison(table_a: Path, table_b: Path, names: tuple[str, str]) -> pd.DataFrame:
    """Per facet: status agreement, mean word overlap (Jaccard) of the two
    values where both are filled, and the share with the same leading
    category (text before the first colon)."""
    a = pd.read_csv(table_a, dtype=str).fillna("").set_index("IQ_COMPANY_ID")
    b = pd.read_csv(table_b, dtype=str).fillna("").set_index("IQ_COMPANY_ID")
    common = a.index.intersection(b.index)
    rows = []
    for col in a.columns:
        if not col.endswith("_status") or col == "llm_status":
            continue
        f = col[:-7]
        sa, sb, va, vb = a.loc[common, col], b.loc[common, col], a.loc[common, f], b.loc[common, f]
        both = (sa == "filled") & (sb == "filled")
        jac = [len(_tokens(x) & _tokens(y)) / len(_tokens(x) | _tokens(y)) if _tokens(x) | _tokens(y) else 1.0
               for x, y in zip(va[both], vb[both])]
        lead = lambda s: s.str.split(":").str[0].str.strip().str.lower()
        rows.append({"facet": f, "companies": len(common), "status differs": float((sa != sb).mean()),
                     f"filled {names[0]}": float((sa == "filled").mean()), f"filled {names[1]}": float((sb == "filled").mean()),
                     "word overlap": float(np.mean(jac)) if jac else np.nan,
                     "same leading category": float((lead(va[both]) == lead(vb[both])).mean()) if both.any() else np.nan})
    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--screen-runs", nargs=2, type=Path, metavar=("SONNET", "HAIKU"),
                   default=[V1 / "cosine_then_llm" / "20261104T074915Z_2026-11-04a_sonnet",
                            V1 / "cosine_then_llm" / "20261104T074915Z_2026-11-04a_haiku"])
    p.add_argument("--direct-runs", nargs=2, type=Path, metavar=("SONNET", "HAIKU"),
                   default=[V1 / "direct_llm" / "20261027T204930Z_2026-11-04a_sonnet",
                            V1 / "direct_llm" / "20261027T204930Z_2026-11-04a_haiku"])
    p.add_argument("--b3", type=Path, default=None, help="candidates_method1 run (default: the latest)")
    p.add_argument("--labels", type=Path, default=LABELS)
    p.add_argument("--facets", nargs=2, type=Path, metavar=("HAIKU", "SONNET"),
                   default=[V1 / "facets" / "tables" / "facets.csv", V1 / "facets_sonnet" / "tables" / "facets.csv"])
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    names = ("sonnet", "haiku")

    labels = pd.DataFrame(json.loads(args.labels.read_text(encoding="utf-8"))["labels"]).fillna("")
    majority, unanimous, _ = se.reviewer_sets(labels)
    b3 = args.b3 or latest(V1 / "candidates_method1")
    lists = {"B3 list (no LLM)": b3_list(b3)}
    present = []
    for kind, runs, loader in (("screen", args.screen_runs, screen_list), ("direct", args.direct_runs, direct_list)):
        for run, name in zip(runs, names):
            if (run / "tables").exists():
                lists[f"{kind} {name}"] = loader(run)
                present.append((kind, name))
            else:
                print(f"not run yet: {run}")
    golden = golden_view(lists, majority)
    strict = golden_view(lists, unanimous)
    agree = []
    if all((r / "tables").exists() for r in args.screen_runs):
        agree.append(screen_agreement(*args.screen_runs, names))
    if all((r / "tables").exists() for r in args.direct_runs):
        agree.append(direct_agreement(*args.direct_runs, names))
    agree = pd.DataFrame(agree)

    out = args.out / stamp()
    out.mkdir(parents=True, exist_ok=True)
    golden.to_csv(out / "golden_majority.csv", index=False)
    strict.to_csv(out / "golden_unanimous.csv", index=False)
    agree.to_csv(out / "model_agreement.csv", index=False)
    facets = facet_fill_comparison(*args.facets, ("haiku", "sonnet")) if all(f.exists() for f in args.facets) else pd.DataFrame()
    facets.to_csv(out / "facet_fill_comparison.csv", index=False)
    info = pd.read_csv(V1 / "universe" / sorted((V1 / "universe").iterdir())[-1] / "universe.csv", dtype=str
                       ).set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
    golden.insert(1, "ticker", golden["target"].map(info))
    pd.set_option("display.width", 200)
    cols = ["method", "ticker", "listed", "labeled", "precision@10", "direct share", "NDCG@10",
            "good listed", "good total", "direct listed", "direct total", "non-comps listed"]
    print("\nAgainst the reviewers' majority grades (round 1: PCTY, WEN):")
    print(golden[cols].round(2).to_string(index=False))
    if len(agree):
        print("\nAgreement between the two models on all training targets:")
        for _, r in agree.iterrows():
            print("  " + "; ".join(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}"
                                   for k, v in r.dropna().items()))
    if len(facets):
        print("\nFacet fills, Haiku vs Sonnet, same prompt (share of companies):")
        print(facets.round(2).to_string(index=False))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
