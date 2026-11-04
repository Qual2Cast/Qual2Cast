"""Reverse hybrid baseline: LLM selects peers, then cosine ranks and weights them.

The LLM selection is frozen before joining cosine scores. Financial labels are
never read here. The existing valuation.estimate function is the only stage
that subsequently reads peer multiples.
"""

from __future__ import annotations

import pandas as pd


def rank_selected(suggestions: pd.DataFrame, ranking: pd.DataFrame,
                  max_peers: int = 10) -> pd.DataFrame:
    """Return up to max_peers LLM picks per target, sorted by cosine score.

    A missing cosine score is an input error, rather than a reason to silently
    discard a peer. No z-score gate is applied: this direction lets the LLM
    search the complete pool before cosine reranks its choices.
    """
    if max_peers < 1:
        raise ValueError("max_peers must be positive")
    selected = suggestions.dropna(subset=["target", "comp"]).copy()
    selected = selected[selected["comp"].astype(str).str.strip().ne("")]
    if (selected["target"] == selected["comp"]).any():
        raise ValueError("LLM suggestions contain a target as its own peer")
    if selected.duplicated(["target", "comp"]).any():
        raise ValueError("LLM suggestions contain duplicate target-peer pairs")
    if ranking.duplicated(["target", "comp"]).any():
        raise ValueError("cosine ranking contains duplicate target-peer pairs")
    selected = selected.rename(columns={"rank": "llm_rank"})
    scores = ranking[["target", "comp", "rank", "similarity", "z"]].rename(
        columns={"rank": "cosine_rank"})
    result = selected.merge(scores, on=["target", "comp"], how="left", validate="one_to_one")
    if result["similarity"].isna().any():
        missing = result.loc[result["similarity"].isna(), ["target", "comp"]].to_dict("records")
        raise ValueError(f"LLM-selected peers missing cosine scores: {missing[:5]}")
    result = result.sort_values(["target", "similarity", "cosine_rank", "comp"],
                                ascending=[True, False, True, True], kind="stable")
    result = result.groupby("target", sort=False).head(max_peers).copy()
    result["rank"] = result.groupby("target", sort=False).cumcount() + 1
    return result.reset_index(drop=True)
