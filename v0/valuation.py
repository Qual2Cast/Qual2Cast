"""
Recipe step 7 and the evaluation: an estimate from the comps' EV/EBITDA, and
how far it is from the target's actual multiple (the answer key, from the
financials table). This is the first place the multiples are read.

A comp set is a table of (target, comp) pairs, optionally with a weight
column (the cosine similarity, or later the LLM's score). Comps without a
multiple are left out. The no-matching baseline is the median multiple of
the whole pool (without the target): any comp rule has to beat it.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def estimate(pairs: pd.DataFrame, multiples: pd.Series, weight: str | None = None,
             how: str = "mean") -> pd.DataFrame:
    """Per target: the (weighted) mean or the median of its comps' multiples,
    and how many comps it used. Weights below zero count as zero. A target
    with no comps (or none with a multiple) gets no row."""
    d = pairs.assign(multiple=pairs["comp"].map(multiples)).dropna(subset=["multiple"])
    d = d.assign(w=d[weight].clip(lower=0) if weight else 1.0)
    g = d.groupby("target")
    if how == "median":
        est = g["multiple"].median()
    elif how == "mean":
        est = (d["multiple"] * d["w"]).groupby(d["target"]).sum() / g["w"].sum()
    else:
        raise ValueError(f"how must be 'mean' or 'median', not {how!r}")
    return pd.DataFrame({"estimate": est, "comps": g.size()})


def no_matching(targets: Sequence[str], pool: Sequence[str], multiples: pd.Series) -> pd.DataFrame:
    """Per target: the median multiple of every pool firm except itself."""
    m = multiples.reindex(list(pool)).dropna()
    rows = {t: (m.drop(t, errors="ignore").median(), len(m.drop(t, errors="ignore"))) for t in targets}
    return pd.DataFrame.from_dict(rows, orient="index", columns=["estimate", "comps"])


def errors(result: pd.DataFrame, actual: pd.Series) -> pd.DataFrame:
    """Each target's estimate, actual multiple, and error as % of the actual."""
    out = result.join(actual.rename("actual"), how="left")
    out["error %"] = 100 * (out["estimate"] - out["actual"]) / out["actual"]
    return out


def summary(results: dict[str, pd.DataFrame], actual: pd.Series, baseline: str) -> pd.DataFrame:
    """One row per comp rule: targets with an estimate, comps per target,
    median absolute % error, % of targets within 25%, Spearman(estimate,
    actual), and % of targets closer than the baseline (on the targets both
    estimate)."""
    base = errors(results[baseline], actual)
    rows = []
    for name, result in results.items():
        e = errors(result, actual)
        ape = e["error %"].abs()
        both = e.index.intersection(base.index)
        closer = (np.abs(e.loc[both, "estimate"] - e.loc[both, "actual"])
                  < np.abs(base.loc[both, "estimate"] - base.loc[both, "actual"]))
        rows.append({"comp rule": name, "targets": len(e), "comps per target (median)": e["comps"].median(),
                     "median abs % error": ape.median(), "% within 25%": 100 * (ape <= 25).mean(),
                     "Spearman(estimate, actual)": np.nan if name == baseline
                     else e["estimate"].corr(e["actual"], method="spearman"),
                     "% closer than no matching": np.nan if name == baseline else 100 * closer.mean()})
    return pd.DataFrame(rows).set_index("comp rule")
