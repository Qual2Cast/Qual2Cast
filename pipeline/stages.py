"""Shared stage objects: select by method name or register a new implementation."""

from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from pipeline.config import FACTOR_SETS, AGGREGATORS
from matching.factors import rank_distances
from valuation.aggregators import aggregate_multiple


class MethodStage:
    """Small explicit registry; method functions receive the same stage inputs."""

    def __init__(self):
        self.methods = {}

    def register(self, name, function, description="", source=""):
        if name in self.methods:
            raise ValueError("Method already registered: " + name)
        self.methods[name] = {
            "function": function,
            "description": description,
            "source": source,
        }
        return self

    def run(self, method, **inputs):
        if method not in self.methods:
            raise ValueError("Unknown method: " + method)
        return self.methods[method]["function"](**inputs)

    def catalog(self):
        return [
            {"method": name, **{k: v for k, v in item.items() if k != "function"}}
            for name, item in self.methods.items()
        ]


class MatchingStage(MethodStage):
    def __init__(self, workflow):
        super().__init__()
        available = (
            list(workflow.retrieval.geometry) + ["rrf"] + list(workflow.retrieval.sets)
        )
        for name in available:
            self.register(
                name,
                lambda company_id, limit, _name=name: workflow.retrieve(
                    company_id, _name, limit
                ),
                "Candidate generation; business eligibility is evaluated separately",
                "matching/retrieval.py",
            )


class FactorStage(MethodStage):
    def __init__(self):
        super().__init__()
        for name, columns in FACTOR_SETS.items():
            self.register(
                name,
                lambda peers, target, finance, _cols=columns: self._rank(
                    peers, target, finance, _cols
                ),
                "Equal-weight percentile distances after business eligibility",
                "SARD-inspired adaptation",
            )

    @staticmethod
    def _rank(peers, target, finance, columns):
        peers = peers.copy()
        missing = [c for c in columns if target.get(c) is None]
        if missing:
            return {
                "status": "missing_target_factors",
                "missing": missing,
                "rows": [],
                "factors": list(columns),
            }
        if peers.empty:
            return {
                "status": "no_business_eligible_peers",
                "rows": [],
                "factors": list(columns),
            }
        if columns:
            # Only eligible public peers form the factor reference population.
            ref = finance.loc[peers.peer_id]
            peers["factor_distance"] = rank_distances(
                pd.Series(target), ref, ref, columns
            )
            peers = peers[np.isfinite(peers.factor_distance)].sort_values(
                ["factor_distance", "retrieval_rank", "peer_id"], kind="stable"
            )
        else:
            peers["factor_distance"] = None
        return {
            "status": "ranked",
            "rows": peers.to_dict("records"),
            "factors": list(columns),
        }


class ValuationStage(MethodStage):
    def __init__(self):
        super().__init__()
        for name in AGGREGATORS:
            self.register(
                name,
                lambda values, min_peers, _name=name: aggregate_multiple(
                    values, _name, min_peers
                ),
                "Positive public-peer multiples; no target outcome input",
                "valuation/aggregators.py",
            )


class MeasurementStage(MethodStage):
    def __init__(self):
        super().__init__()
        from valuation.ebitda import from_net_income, ltm_ebitda, adjust_ebitda

        self.register(
            "net_income_bridge",
            from_net_income,
            "NI + signed interest, tax, D&A",
            "SEC C&DI 103",
        )
        self.register(
            "four_quarters",
            lambda periods, as_of: ltm_ebitda(periods, "four_quarters", as_of),
            "Four nonoverlapping discrete quarters; metadata required",
            "valuation/ebitda.py",
        )
        self.register(
            "fy_plus_ytd",
            lambda periods, as_of: ltm_ebitda(periods, "fy_plus_ytd", as_of),
            "FY + current YTD - corresponding prior YTD",
            "valuation/ebitda.py",
        )
        self.register(
            "reviewed_adjustments",
            lambda base, adjustments: adjust_ebitda(base, adjustments, "reviewed"),
            "Only source-backed accepted nonrecurring adjustments",
            "SEC C&DI 100",
        )


@dataclass(frozen=True)
class PipelineConfig:
    peer_search_policy: str = "fixed"
    review_limit: int | None = None
    measurement_method: str = "provided"
    profile_method: str = "sentence_evidence"
    matching_method: str = "rrf"
    business_review_method: str = "source_review"
    growth_method: str = "rules"
    factor_method: str = "business_only"
    valuation_method: str = "median"
    llm_max_output_tokens: int = 1400
    llm_provider: str = "local"
    llm_model: str = "Qwen/Qwen2.5-3B-Instruct"
    llm_revision: str = "aa8e72537993ba99e69dfaafa59ed015b17504d1"
    shortlist: int = 10
    peers: int = 5
    min_peers: int = 3
    cutoff: str = "2026-10-19"

    def __post_init__(self):
        if self.peer_search_policy not in ("fixed", "progressive"):
            raise ValueError("Unknown peer search policy")
        if self.review_limit is not None and self.review_limit < 1:
            raise ValueError("Review limit must be positive or None")
        if not 1 <= self.min_peers <= self.peers <= self.shortlist:
            raise ValueError("Require 1 <= min_peers <= peers <= shortlist")
        if self.llm_max_output_tokens < 1:
            raise ValueError("LLM output budget must be positive")

    def to_dict(self):
        return asdict(self)
