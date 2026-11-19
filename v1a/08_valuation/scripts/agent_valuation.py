"""Valuation checks of the agent-grading lists (moved here from 05_agent_grading in v1a, 2026-11-18).

EV/EBITDA is the answer the method predicts, so only 08 and 10 read it. These two functions were in
v1/scripts/agent_ranking.py (--valuation) and v1/scripts/agent_loop_eval.py (section 4):

  ranking_valuation(ranked)  median EV/EBITDA of each agent-ranking ordering's top k vs the target's actual
                             multiple, with "no matching" as the reference (bootstrap over targets).
  filter_valuation(lists)    similarity-weighted EV/EBITDA of B3's list and the agent filters of it.

Use them on chosen comp lists only; never to choose an ordering or a filter (that tunes on the answer key).
"""

from __future__ import annotations

import sys as _sys  # v1a: shared paths (common/paths.py) put every component's scripts on the path
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v1a  # noqa: E402
v1a.setup()

import pandas as pd

import valuation  # noqa: E402


def multiples() -> pd.Series:
    fin = pd.read_csv(v1a.path(v1a.current()["valuation"]["financials"]), dtype={"IQ_COMPANY_ID": str})
    return fin.set_index("IQ_COMPANY_ID")["target_ev_to_ebitda"].astype(float)


def training_pool() -> pd.Series:
    split = pd.read_csv(v1a.path(v1a.current()["universe"]["split"]), dtype={"IQ_COMPANY_ID": str})
    return split.loc[split["sample"].eq("training"), "IQ_COMPANY_ID"]


def ranking_valuation(ranked: pd.DataFrame, ks: tuple[int, ...] = (3, 6)) -> pd.DataFrame:
    import agent_ranking as ar
    m = multiples()
    results = {n: valuation.estimate(l, m, how="median") for n, l in ar.top_lists(ranked, ks).items()}
    results["no matching"] = valuation.no_matching(sorted(ranked["target"].unique()), training_pool(), m)
    return valuation.bootstrap(results, m, "no matching").round(1)


def filter_valuation(lists: dict[str, pd.DataFrame]) -> pd.DataFrame:
    m = multiples()
    results = {n: valuation.estimate(l, m, weight="similarity") for n, l in lists.items() if not n.startswith("_")}
    targets = sorted(lists["B3 as is"]["target"].unique())
    results["no matching"] = valuation.no_matching(targets, training_pool(), m)
    return valuation.bootstrap(results, m, "no matching")
