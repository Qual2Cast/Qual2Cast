"""
The training / holdout split (recipe: 70/30, balanced).

Stratified on company size (facet F9: small, mid-sized, large, among the
largest; decided 2026-10-25), so each size category is split 70/30. The
showcase targets, examined during development, are always in training.
Within each stratum firms are drawn at random with a fixed seed; the number
of training firms per stratum is set by largest remainder, so the total is
round(share x n).

Balance is checked afterwards on what the split doesn't stratify on: sector
(SIC division) shares and standardized mean differences of the financials.
The financials are read only for that check; nothing is fit on them.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

TRAIN_SHARE = 0.7
SEED = 2026
SIZE_UNKNOWN = "unknown"     # stratum for companies whose size facet is unknown

# SIC divisions: a letter for a range of 2-digit major groups (as in pre-v0/matching)
DIVISIONS = [(1, 9, "A Agriculture, Forestry, Fishing"), (10, 14, "B Mining"), (15, 17, "C Construction"),
             (20, 39, "D Manufacturing"), (40, 49, "E Transportation, Communications, Utilities"),
             (50, 51, "F Wholesale Trade"), (52, 59, "G Retail Trade"),
             (60, 67, "H Finance, Insurance, Real Estate"), (70, 89, "I Services"),
             (91, 97, "J Public Administration"), (99, 99, "K Nonclassifiable")]


def sic_division(sic2: str) -> str:
    return next((name for lo, hi, name in DIVISIONS if lo <= int(sic2) <= hi), "unknown")


def size_strata(facets: pd.DataFrame) -> pd.Series:
    """Company size category (F9) per IQ_COMPANY_ID, from the first business
    profile; a blank category (size unknown) becomes its own stratum."""
    b1 = facets[facets["business_id"] == "B1"].set_index("IQ_COMPANY_ID")
    return b1["company_size_category"].fillna("").replace("", SIZE_UNKNOWN).rename("size_stratum")


def train_counts(sizes: pd.Series, share: float = TRAIN_SHARE) -> pd.Series:
    """Training firms per stratum: share x stratum size, rounded by largest
    remainder so the total is round(share x n). Ties go to the stratum listed first."""
    quota = sizes * share
    counts = np.floor(quota).astype(int)
    extra = int(round(share * sizes.sum())) - int(counts.sum())
    remainders = (quota - counts).sort_values(ascending=False, kind="stable")
    counts[remainders.index[:extra]] += 1
    return counts


def stratified_split(strata: pd.Series, share: float = TRAIN_SHARE, seed: int = SEED,
                     forced_train: Iterable[str] = ()) -> pd.Series:
    """'training' or 'holdout' per id (the index of `strata`). Forced ids go to
    training and count toward their stratum's quota; the rest of each quota is
    drawn at random. The result depends only on the ids, strata, share and
    seed, not on the order they come in."""
    forced = set(forced_train)
    if missing := forced - set(strata.index):
        raise ValueError(f"forced ids not in the strata: {sorted(missing)}")
    rng = np.random.default_rng(seed)
    counts = train_counts(strata.value_counts().sort_index(), share)
    sample = pd.Series("holdout", index=strata.index, name="sample")
    for stratum, n_train in counts.items():
        ids = sorted(strata.index[strata == stratum])
        fixed = [i for i in ids if i in forced]
        rest = [i for i in ids if i not in forced]
        drawn = list(rng.permutation(rest)[:max(n_train - len(fixed), 0)]) if rest else []
        sample[fixed + drawn] = "training"
    return sample


def smd(values: pd.Series, sample: pd.Series) -> float:
    """Standardized mean difference, training minus holdout, over the pooled SD."""
    a, b = values[sample == "training"].dropna(), values[sample == "holdout"].dropna()
    return float((a.mean() - b.mean()) / np.sqrt((a.var() + b.var()) / 2))


def share_balance(sample: pd.Series, groups: pd.Series) -> pd.DataFrame:
    """% of each sample in each group, and the difference in points."""
    t = pd.crosstab(groups, sample, normalize="columns") * 100
    t = t.reindex(columns=["training", "holdout"], fill_value=0)
    t["difference"] = t["training"] - t["holdout"]
    return t


def numeric_balance(sample: pd.Series, numeric: dict[str, pd.Series]) -> pd.DataFrame:
    """Mean and median per sample, and the SMD, for each numeric variable."""
    rows = []
    for name, x in numeric.items():
        a, b = x[sample == "training"], x[sample == "holdout"]
        rows.append({"variable": name, "training mean": a.mean(), "holdout mean": b.mean(),
                     "training median": a.median(), "holdout median": b.median(), "SMD": smd(x, sample)})
    return pd.DataFrame(rows).set_index("variable")
