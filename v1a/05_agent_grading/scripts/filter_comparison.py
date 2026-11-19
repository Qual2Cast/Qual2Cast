"""Agent grade vs the selector as peer filters on the B3 lists, against the people's labels.

No model calls: reads saved runs only (v1a/current.toml names them).

  B3 list    the candidates both filters see (current B3 "Sonnet + Fiona sub-sector", rank and similarity)
  selector   04_selection: Sonnet, listwise (a target's whole list in one call), good/bad, facets + memory
  agent      05_agent_grading: Sonnet, one pair per call, rubric 0/1/2 with cited website/web lines

References (peer = grade 1 or 2, direct = grade 2):
  dev_293         Barbara, old 0/1/2 rubric, 293 pairs / 45 targets
  matthew_v2_262  Matthew, rubric v2 (four yes/no questions, score derived), 262 of the same pairs

Writes outputs-local/v1a/05_agent_grading/filter_comparison/<stamp>/ (never overwrites):
  pairs.csv      one row per labelled pair: rank, similarity, selector keep, agent grade/fits, labels
  filters.csv    each filter vs each reference: kept, precision, recall, F1, Cohen's kappa, bootstrap CIs
  agreement.csv  kappa between every two raters (Barbara, Matthew, agent, selector)
  by_rank.csv    peer rate and what each filter keeps, by B3 rank
  questions.csv  agent fits vs Matthew's yes/no answers (proxy: the agent was not asked the questions)
  summary.json

Run:
  uv run python v1a/05_agent_grading/scripts/filter_comparison.py
"""

from __future__ import annotations

import sys as _sys  # v1a: shared paths (common/paths.py) put every component's scripts on the path
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v1a  # noqa: E402
v1a.setup()

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

import cohorts

BOOT = 2000
SEED = 0


def latest_ranking(run: Path) -> Path:
    return sorted((run / "ranking").glob("*/ranking.csv"))[-1]


def load_pairs(cur: dict | None = None) -> pd.DataFrame:
    """The 293 labelled pairs with B3 rank, selector keep, agent grade and fits, and both reviewers."""
    cur = cur or v1a.current()
    barbara = cohorts.load("dev_293").rename(columns={"grade": "score_barbara"})[
        ["target_id", "comp_id", "target_ticker", "comp_ticker", "rank", "similarity", "score_barbara"]]
    sel = pd.read_csv(v1a.path(cur["selection"]["judgments"]), dtype={"target": str, "comp": str})
    sel = sel.rename(columns={"target": "target_id", "comp": "comp_id", "score": "selector_keep"})
    agent = pd.read_csv(latest_ranking(v1a.path(cur["agent_grading"]["run"])), dtype={"target": str, "comp": str})
    agent = agent.rename(columns={"target": "target_id", "comp": "comp_id", "score": "agent_grade"})
    matthew = pd.read_csv(v1a.out("06_labels") / "round3" / "round3_scores_v2.csv", dtype=str, encoding="utf-8-sig")
    mq = ["same_product_matthew", "same_customers_matthew", "same_revenue_model_matthew",
          "same_chain_step_matthew", "score_matthew"]
    matthew = matthew[["target_id", "comp_id", *mq]]
    d = (barbara
         .merge(sel[["target_id", "comp_id", "selector_keep"]], on=["target_id", "comp_id"], how="left")
         .merge(agent[["target_id", "comp_id", "agent_grade", "offering_fit", "customer_fit",
                       "business_model_fit"]], on=["target_id", "comp_id"], how="left")
         .merge(matthew, on=["target_id", "comp_id"], how="left"))
    d["score_barbara"] = pd.to_numeric(d["score_barbara"])
    d["score_matthew"] = pd.to_numeric(d["score_matthew"])
    for q in mq[:4]:
        d[q] = d[q].map({"True": True, "False": False})
    if d["selector_keep"].isna().any() or d["agent_grade"].isna().all():
        raise SystemExit("selector or agent run does not cover the 293 pairs")
    return d


def filters(d: pd.DataFrame, k: int = 7) -> dict[str, pd.Series]:
    """Which pairs each filter keeps (True/False). A null agent grade counts as not kept."""
    a = d["agent_grade"].fillna(-1)
    s = d["selector_keep"] == 1
    return {
        "B3 list (keep all)": pd.Series(True, index=d.index),
        f"B3 top {k}": d["rank"] <= k,
        "selector keep": s,
        "agent grade >= 1": a >= 1,
        "agent grade 2": a == 2,
        "agent >= 1 AND selector": (a >= 1) & s,
        "agent >= 1 OR selector": (a >= 1) | s,
    }


def scores(kept: pd.Series, truth: pd.Series) -> dict:
    kept, truth = kept.astype(bool), truth.astype(bool)
    tp = int((kept & truth).sum())
    prec = tp / kept.sum() if kept.sum() else np.nan
    rec = tp / truth.sum() if truth.sum() else np.nan
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else np.nan
    kappa = cohen_kappa_score(truth, kept) if kept.nunique() > 1 else np.nan
    return {"kept": int(kept.sum()), "true_kept": tp, "false_kept": int(kept.sum()) - tp,
            "missed": int(truth.sum()) - tp, "precision": prec, "recall": rec, "f1": f1, "kappa": kappa}


def bootstrap(d: pd.DataFrame, kept: pd.Series, truth: pd.Series, stats=("precision", "recall", "kappa")) -> dict:
    """95% intervals, resampling targets (comps of one target are not independent)."""
    rng = np.random.default_rng(SEED)
    groups = [np.flatnonzero(d["target_id"].to_numpy() == t) for t in d["target_id"].unique()]
    k, t = kept.to_numpy(), truth.to_numpy()
    draws = {s: [] for s in stats}
    for _ in range(BOOT):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        r = scores(pd.Series(k[idx]), pd.Series(t[idx]))
        for s in stats:
            draws[s].append(r[s])
    return {f"{s}_lo": float(np.nanpercentile(v, 2.5)) for s, v in draws.items()} | \
           {f"{s}_hi": float(np.nanpercentile(v, 97.5)) for s, v in draws.items()}


def filter_table(d: pd.DataFrame, k: int = 7) -> pd.DataFrame:
    refs = {
        "Barbara peer (>=1)": (d["score_barbara"].notna(), d["score_barbara"] >= 1),
        "Barbara direct (2)": (d["score_barbara"].notna(), d["score_barbara"] == 2),
        "Matthew v2 peer (>=1)": (d["score_matthew"].notna(), d["score_matthew"] >= 1),
        "Matthew v2 direct (2)": (d["score_matthew"].notna(), d["score_matthew"] == 2),
    }
    rows = []
    for ref, (has, truth) in refs.items():
        sub = d[has]
        for name, kept in filters(d, k).items():
            row = {"reference": ref, "filter": name, "pairs": int(has.sum()), "true_peers": int(truth[has].sum())}
            row |= scores(kept[has], truth[has])
            if name != "B3 list (keep all)":
                row |= bootstrap(sub.reset_index(drop=True), kept[has].reset_index(drop=True),
                                 truth[has].reset_index(drop=True))
            rows.append(row)
    return pd.DataFrame(rows)


def agreement_table(d: pd.DataFrame) -> pd.DataFrame:
    """Cohen's kappa for every two raters, on peer yes/no and (where both grade 0/1/2) on the grade."""
    peer = {"Barbara": d["score_barbara"] >= 1, "Matthew v2": d["score_matthew"] >= 1,
            "agent": d["agent_grade"] >= 1, "selector": d["selector_keep"] == 1}
    grade = {"Barbara": d["score_barbara"], "Matthew v2": d["score_matthew"], "agent": d["agent_grade"]}
    has = {"Barbara": d["score_barbara"].notna(), "Matthew v2": d["score_matthew"].notna(),
           "agent": d["agent_grade"].notna(), "selector": d["selector_keep"].notna()}
    names = list(peer)
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = has[a] & has[b]
            row = {"rater_a": a, "rater_b": b, "pairs": int(both.sum()),
                   "peer_agreement": float((peer[a][both] == peer[b][both]).mean()),
                   "peer_kappa": cohen_kappa_score(peer[a][both], peer[b][both])}
            if a in grade and b in grade:
                x, y = grade[a][both].astype(int), grade[b][both].astype(int)
                row |= {"grade_agreement": float((x == y).mean()),
                        "grade_kappa": cohen_kappa_score(x, y),
                        "grade_kappa_linear": cohen_kappa_score(x, y, weights="linear")}
            rows.append(row)
    return pd.DataFrame(rows)


def rank_table(d: pd.DataFrame) -> pd.DataFrame:
    a = d["agent_grade"].fillna(-1)
    g = d.assign(barbara_peer=d["score_barbara"] >= 1, barbara_zero=d["score_barbara"] == 0,
                 selector=d["selector_keep"] == 1, agent=a >= 1,
                 agent_keeps_zero=(a >= 1) & (d["score_barbara"] == 0),
                 selector_keeps_zero=(d["selector_keep"] == 1) & (d["score_barbara"] == 0))
    out = g.groupby("rank").agg(pairs=("target_id", "size"),
                                barbara_peers=("barbara_peer", "sum"), barbara_zeros=("barbara_zero", "sum"),
                                agent_keeps=("agent", "sum"), agent_keeps_zero=("agent_keeps_zero", "sum"),
                                selector_keeps=("selector", "sum"), selector_keeps_zero=("selector_keeps_zero", "sum"),
                                mean_similarity=("similarity", "mean"))
    out["zero_rate"] = out["barbara_zeros"] / out["pairs"]
    return out.reset_index()


FITS = {"same_product": "offering_fit", "same_customers": "customer_fit", "same_revenue_model": "business_model_fit"}


def question_table(d: pd.DataFrame) -> pd.DataFrame:
    """Agent fit (match = yes) vs Matthew's answer, per question. A proxy: the agent rated fit on its own
    three-level scale, not Matthew's questions; business_model_fit is closest to the revenue-model question.
    'partial' is counted as no (strict) and as yes (lenient)."""
    rows = []
    for q, fit in FITS.items():
        m = d[f"{q}_matthew"]
        f = d[fit]
        ok = m.notna() & f.isin(["match", "partial", "mismatch"])
        for rule, yes in {"strict (match)": ["match"], "lenient (match or partial)": ["match", "partial"]}.items():
            x, y = m[ok].astype(bool), f[ok].isin(yes)
            rows.append({"question": q, "agent_field": fit, "rule": rule, "pairs": int(ok.sum()),
                         "matthew_yes": int(x.sum()), "agent_yes": int(y.sum()),
                         "agreement": float((x == y).mean()), "kappa": cohen_kappa_score(x, y)})
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top-k", type=int, default=7, help="B3 rank cut shown as its own filter")
    args = ap.parse_args(argv)
    cur = v1a.current()
    d = load_pairs(cur)
    out = v1a.out("05_agent_grading") / "filter_comparison" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    tables = {"pairs": d, "filters": filter_table(d, args.top_k), "agreement": agreement_table(d),
              "by_rank": rank_table(d), "questions": question_table(d)}
    for name, t in tables.items():
        t.to_csv(out / f"{name}.csv", index=False)
    summary = {"pairs": len(d), "targets": int(d["target_id"].nunique()),
               "matthew_pairs": int(d["score_matthew"].notna().sum()),
               "selector": {k: cur["selection"][k] for k in ("model", "prompt_version", "judgments")},
               "agent": {k: cur["agent_grading"][k] for k in ("model", "prompt_version", "run")},
               "agent_ranking_file": str(latest_ranking(v1a.path(cur["agent_grading"]["run"])).relative_to(v1a.ROOT)),
               "bootstrap": {"draws": BOOT, "seed": SEED, "unit": "target"}, "top_k": args.top_k}
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    with pd.option_context("display.width", 200, "display.max_columns", 30, "display.precision", 3):
        for name in ("filters", "agreement", "by_rank", "questions"):
            print(f"\n== {name}\n{tables[name]}")
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
