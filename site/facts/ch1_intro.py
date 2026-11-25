"""Facts for Introduction (index.qmd). Pattern: see ch2_data.py.

The scale facts are the ones chapters 2 and 3 register, re-exported here so each number has one source (a fact is
registered once; importing it again does not register a copy). New here: the reviewer labels, counted from the pair
ledger in 06_labels (outputs-local/v1a/06_labels/pair_ledger/20261119T014543Z, the latest), which counts every
target-comp pair a person or a model judged. It already leaves out the pairs whose comp is outside the universe
(Barbara's external direct-peer list), so only Aziz's universe is counted.
"""

from __future__ import annotations

import pandas as pd

from facts.ch2_data import n_holdout, n_supplied, n_training, n_universe  # noqa: F401  (re-exported)
from facts.ch3_describing import n_facets, n_traits  # noqa: F401  (re-exported)
from facts.common import fact, pinned

_pairs = pd.read_csv(pinned("labels_ledger_pairs"), dtype=str)
_sources = pd.read_csv(pinned("labels_ledger_sources"), dtype=str)

_human = _pairs[_pairs["n_judged_human_review"].astype(int) > 0]          # pairs at least one person graded
_judged = _sources[_sources["stage"].eq("human_review") & (_sources["judged"].astype(int) > 0)]
_who = _judged.set_index("source")["who"]                                  # e.g. human:round3:barbara -> Barbara
# distinct people per pair: a source column holds that source's grade, blank when it did not grade the pair
_people = _human[list(_who.index)].notna().rename(columns=_who).T.groupby(level=0).any().T.sum(axis=1)


def _n(name: str, value, source: str):
    return fact(name, int(value), f"{int(value):,}", source=source)


n_labelled_pairs = _n("n_labelled_pairs", len(_human), "labels_ledger_pairs")
n_labelled_targets = _n("n_labelled_targets", _human["target_id"].nunique(), "labels_ledger_pairs")
n_labelled_twice = _n("n_labelled_twice", (_people >= 2).sum(), "labels_ledger_pairs+labels_ledger_sources")
n_reviewers = _n("n_reviewers", _who.nunique(), "labels_ledger_sources")
