"""Shared end-to-end entry: all methods use the same evidence and stage outputs."""

from pathlib import Path
from datetime import datetime, timezone
from dataclasses import replace
from itertools import product
import json
import hashlib
import uuid
import numpy as np
import pandas as pd
from pipeline.stages import (
    PipelineConfig,
    MatchingStage,
    FactorStage,
    ValuationStage,
    MeasurementStage,
)
from pipeline.collection import EvidenceStage
from pipeline.evaluation_stage import EvaluationStage
from pipeline.sampling import SampleStage
from pipeline.llm import StructuredLLM
from pipeline.private_inputs import private_financials
from pipeline.company import resolve_company, _json_safe
from pipeline.inputs import aligned_inputs
from pipeline.workflow import CompanyWorkflow
from matching.llm_methods import BusinessReview, sentence_cards
from growth_signals.stage import GrowthStage
from pipeline.peer_search import ranked_pool, review_ranked_candidates


class TeamPipeline:
    """Stage objects are public extension points. No hidden target finances.

    Register a teammate's retriever with ``pipeline.matching.register(name, fn)``.
    It returns the same candidate columns as matching/retrieval.py. Business
    review is mandatory and cannot be disabled by a registered retriever.
    """

    def __init__(
        self,
        workflow,
        documents,
        peer_multiples,
        reviews=None,
        growth_records=None,
        cache_dir="outputs-local/llm",
        live_llm=False,
    ):
        self.workflow, self.documents = workflow, documents
        self.peer_multiples = peer_multiples.copy()
        self.reviews, self.growth_records = reviews or {}, growth_records or {}
        self.cache_dir, self.live_llm = Path(cache_dir), live_llm
        self.matching = MatchingStage(workflow)
        self.factors = FactorStage()
        self.valuation = ValuationStage()
        self.collection = EvidenceStage()
        self.sampling = SampleStage()
        self.measurement = MeasurementStage()
        self.evaluation = EvaluationStage()
        self._providers, self._reviewers = {}, {}
        self._growth_cache = {}

    @classmethod
    def from_bundle(cls, path, live_llm=False):
        path = Path(path)
        raw = pd.read_json(
            path / "companies.json",
            dtype={"IQ_COMPANY_ID": str, "target_sic4_code": str},
        )
        manifest = json.loads(
            (path / "features/manifest.json").read_text(encoding="utf-8")
        )
        if (
            manifest["company_ids"] != raw.IQ_COMPANY_ID.tolist()
            or hashlib.sha256("\0".join(raw.text).encode()).hexdigest()
            != manifest["text_sha256"]
        ):
            raise ValueError(
                "Changed evidence: recompute representations before running"
            )
        descriptors, finance, outcomes = aligned_inputs(raw)
        features = {
            n: np.load(path / "features" / ("team_" + n + ".npy"))
            for n in manifest["representations"]
        }
        cluster_path = path / "features/cluster_labels_seed0.npz"
        clusters = dict(np.load(cluster_path)) if cluster_path.exists() else None
        backend = CompanyWorkflow(descriptors, finance, features, clusters)
        docs = json.loads((path / "documents.json").read_text(encoding="utf-8"))
        if isinstance(docs, list):
            docs = {d["source_id"]: d for d in docs}
        reviews_path, growth_path = (
            path / "business_reviews.json",
            path / "growth_records.json",
        )
        pipeline = cls(
            backend,
            docs,
            outcomes.set_index("IQ_COMPANY_ID").target_ev_to_ebitda,
            json.loads(reviews_path.read_text(encoding="utf-8"))
            if reviews_path.exists()
            else {},
            json.loads(growth_path.read_text(encoding="utf-8"))
            if growth_path.exists()
            else {},
            path / "llm",
            live_llm,
        )
        pipeline.outcomes = outcomes  # Used only by ExperimentRunner, after prediction.
        return pipeline

    def _reviewer(self, config):
        key = (
            config.llm_provider,
            config.llm_model,
            config.llm_revision,
            config.llm_max_output_tokens,
        )
        if key not in self._providers:
            self._providers[key] = StructuredLLM(
                self.cache_dir,
                *key[:2],
                revision=key[2],
                replay=not self.live_llm,
                max_output_tokens=key[3],
            )
            self._reviewers[key] = BusinessReview(
                self.documents, self.reviews, self._providers[key]
            )
        return self._reviewers[key], self._providers[key]

    def run(self, company, config=None, financial_inputs=None, measurement_inputs=None):
        config = config or PipelineConfig()
        resolution = resolve_company(self.workflow, company)
        if resolution["status"] != "resolved":
            return {"status": "identity_required", "identity": resolution, "stages": {}}
        identity = resolution["matches"][0]
        cid = identity["IQ_COMPANY_ID"]
        measurement = {
            "method": config.measurement_method,
            "status": "explicit_input_only",
            "value": (financial_inputs or {}).get("ebitda", {}).get("value"),
        }
        if config.measurement_method != "provided":
            if measurement_inputs is None:
                measurement.update(status="measurement_inputs_missing", value=None)
                financial_inputs = {
                    k: v for k, v in (financial_inputs or {}).items() if k != "ebitda"
                }
            else:
                measurement = self.measurement.run(
                    config.measurement_method, **measurement_inputs["arguments"]
                )
                # A reconciliation is not an authorization to invent its provenance.
                supplied = dict(measurement_inputs.get("provenance", {}))
                supplied["value"] = measurement.get("value")
                financial_inputs = {
                    k: v for k, v in (financial_inputs or {}).items() if k != "ebitda"
                }
                if supplied["value"] is not None:
                    financial_inputs["ebitda"] = supplied
        target = private_financials(financial_inputs)
        reviewer, llm = self._reviewer(config)
        if config.profile_method == "sentence_evidence":
            profile = {
                "status": "source_sentences",
                "sentences": sentence_cards(self.documents, cid),
            }
        elif config.profile_method == "llm":
            profile = reviewer.profile(cid)
        else:
            raise ValueError("Unknown profile method")
        candidates = (
            ranked_pool(self.workflow, self.matching, cid, config.matching_method)
            if config.peer_search_policy == "progressive"
            else self.matching.run(
                config.matching_method, company_id=cid, limit=config.shortlist
            )
        )
        # Validate even custom candidate adapters; no self matches or foreign IDs.
        if (
            candidates.peer_id.duplicated().any()
            or cid in set(candidates.peer_id)
            or not set(candidates.peer_id) <= set(self.workflow.ids)
        ):
            raise ValueError(
                "Candidate adapter returned duplicate, self or unknown company IDs"
            )
        search = None
        if config.peer_search_policy == "progressive":
            search = review_ranked_candidates(
                candidates,
                lambda p: reviewer.run(cid, p, config.business_review_method),
                target_count=config.peers,
                review_limit=config.review_limit,
            )
            reviews = search["reviews"]
        else:
            reviews = [
                reviewer.run(cid, p, config.business_review_method)
                for p in candidates.peer_id
            ]
        passed = {r["peer_id"]: r for r in reviews if r["eligible"]}
        eligible = candidates[candidates.peer_id.isin(passed)].copy()
        # Business eligibility is final before the financial stage sees candidates.
        ranked = self.factors.run(
            config.factor_method,
            peers=eligible,
            target=target["values"],
            finance=self.workflow.finance,
        )
        selected = ranked["rows"][: config.peers]
        public = self.peer_multiples.drop(index=cid, errors="ignore")
        for rank, peer in enumerate(selected, 1):
            peer.update(
                selection_rank=rank,
                public_peer_multiple=float(public.get(peer["peer_id"], np.nan)),
                business_review=passed[peer["peer_id"]],
            )
        valuation = self.valuation.run(
            config.valuation_method,
            values=[p["public_peer_multiple"] for p in selected],
            min_peers=config.min_peers,
        )
        ebitda = target["values"]["ebitda"]
        valuation.update(
            enterprise_value_proxy=(
                valuation["multiple"] * ebitda
                if valuation["multiple"] is not None
                and ebitda is not None
                and ebitda > 0
                else None
            ),
            verified_enterprise_value=None,
            equity_value=None,
            financial_basis="Unverified snapshot peer dates/definitions; client input provenance recorded",
            release_status="development_only_not_verified_fair_value",
        )
        if ebitda is None or ebitda <= 0:
            valuation["enterprise_value_status"] = (
                "missing_or_nonpositive_explicit_target_ebitda"
            )
        else:
            valuation["enterprise_value_status"] = (
                "proxy_only"
                if valuation["enterprise_value_proxy"] is not None
                else "insufficient_eligible_peers"
            )
        growth_key = (
            cid,
            config.growth_method,
            config.cutoff,
            config.llm_provider,
            config.llm_model,
            config.llm_revision,
            config.llm_max_output_tokens,
        )
        if growth_key not in self._growth_cache:
            self._growth_cache[growth_key] = GrowthStage(llm).run(
                self.growth_records.get(cid), config.growth_method, config.cutoff
            )
        growth = self._growth_cache[growth_key]
        stages = {
            "evidence": {
                "method": "versioned_team_website",
                "result": [
                    d for d in self.documents.values() if d["company_id"] == cid
                ],
                "evaluation": {
                    "eligible_pages": sum(
                        d["company_id"] == cid and d.get("eligible", False)
                        for d in self.documents.values()
                    ),
                    "whole_company_completeness": "not_established",
                },
            },
            "matching": {
                "method": config.matching_method,
                "result": candidates.to_dict("records"),
                "evaluation": {
                    "candidate_count": len(candidates),
                    "independent_relevance_labels": 0,
                },
            },
            "profile": {
                "method": config.profile_method,
                "result": profile,
                "evaluation": {"independent_human_verified": False},
            },
            "business_review": {
                "method": config.business_review_method,
                "result": reviews,
                "evaluation": {
                    "eligible_pairs": len(passed),
                    "reviewed_pairs": len(reviews),
                    "independent_human_pairs": sum(
                        r.get("independent_human", False) for r in reviews
                    ),
                },
            },
            "factors": {
                "method": config.factor_method,
                "result": ranked,
                "evaluation": {"missing_target_inputs": target["missing"]},
            },
            "growth": {
                "method": config.growth_method,
                "result": growth,
                "evaluation": {
                    "forecast_validated": False,
                    "event_count": len(growth["events"]),
                },
            },
            "measurement": {
                "method": config.measurement_method,
                "result": measurement,
                "evaluation": {"financial_basis_verified": False},
            },
            "valuation": {
                "method": config.valuation_method,
                "result": valuation,
                "evaluation": {
                    "error": None,
                    "reason": "Outcome evaluated only after pipeline returns",
                },
            },
        }
        if search is not None:
            stages["candidate_search"] = {
                "method": "progressive_ranked_review",
                "result": search,
                "evaluation": {
                    "target_count_reached": search["business_approved"] >= config.peers,
                    "search_exhausted": search["status"] == "candidate_pool_exhausted",
                },
            }
        return _json_safe(
            {
                "status": "development_report",
                "identity": identity,
                "configuration": config.to_dict(),
                "target_inputs": target,
                "peers": selected,
                "stages": stages,
                "audit": {
                    "business_gate_enforced": True,
                    "financial_ranking_after_business_gate": True,
                    "target_outcome_used_for_matching": False,
                    "private_target_ir_excluded": True,
                    "independent_human_approval": bool(selected)
                    and all(
                        passed[p["peer_id"]].get("independent_human") for p in selected
                    ),
                },
            }
        )

    def import_human_reviews(self, path):
        from pipeline.human_review import load_human_reviews

        result = load_human_reviews(path, self.documents)
        if result["errors"]:
            return result  # Import is atomic; do not silently accept part of a file.
        self.reviews.update(result["reviews"])
        for reviewer in self._reviewers.values():
            reviewer.reviews = self.reviews
            reviewer.pair_cache.clear()
        return result

    def close(self):
        for model in self._providers.values():
            model.close()


class ExperimentRunner:
    """Factorial configurations and each stage's outputs, with coverage reported.

    Same companies and inputs are retained when a method abstains. Evaluation
    never selects a method from lower error among only its easiest survivors.
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    @staticmethod
    def configurations(base=None, **choices):
        base = base or PipelineConfig()
        return [
            replace(base, **dict(zip(choices, values)))
            for values in product(*choices.values())
        ]

    def run(
        self, companies, configs, financial_inputs=None, output_dir=None, compact=False
    ):
        reports, rows, blobs = [], [], {}

        def intern(value):
            payload = json.dumps(_json_safe(value), sort_keys=True, ensure_ascii=False)
            key = hashlib.sha256(payload.encode()).hexdigest()
            if key not in blobs:
                blobs[key] = json.loads(payload)
            return key

        for config in configs:
            for company in companies:
                inputs = (financial_inputs or {}).get(company)
                report = self.pipeline.run(company, config, inputs)
                if compact:
                    reports.append(
                        {
                            "identity": report.get("identity"),
                            "configuration": config.to_dict(),
                            "stages": {
                                k: intern(v) for k, v in report["stages"].items()
                            },
                            "peer_ids": [p["peer_id"] for p in report.get("peers", [])],
                            "audit": report.get("audit"),
                        }
                    )
                else:
                    reports.append(report)
                if report["status"] == "identity_required":
                    rows.append(
                        {
                            "company": company,
                            **config.to_dict(),
                            "status": report["status"],
                        }
                    )
                    continue
                cid = report["identity"]["IQ_COMPANY_ID"]
                v = report["stages"]["valuation"]["result"]
                actual = float(self.pipeline.peer_multiples.get(cid, np.nan))
                estimate = v["multiple"]
                row = {
                    "company": company,
                    **config.to_dict(),
                    "estimate": estimate,
                    "observed_multiple": actual,
                    "selected_peers": len(report["peers"]),
                    "business_eligible": report["stages"]["business_review"][
                        "evaluation"
                    ]["eligible_pairs"],
                    "status": v["status"],
                    "absolute_percentage_error": 100 * abs(estimate / actual - 1)
                    if estimate is not None and np.isfinite(actual) and actual > 0
                    else None,
                }
                rows.append(row)
        if output_dir:
            out = Path(output_dir) / (
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                + "-"
                + uuid.uuid4().hex[:6]
            )
            out.mkdir(parents=True)
            if compact:
                (out / "stage_objects.json").write_text(
                    json.dumps(blobs, ensure_ascii=False), encoding="utf-8"
                )
            self.last_output = out
            (out / "stage_results.json").write_text(
                json.dumps(_json_safe(reports), indent=1), encoding="utf-8"
            )
            pd.DataFrame(rows).to_csv(out / "combination_results.csv", index=False)
            (out / "design.json").write_text(
                json.dumps(
                    {
                        "companies": list(companies),
                        "configurations": [c.to_dict() for c in configs],
                        "scope": "Development experiment, not independent economic validation",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        return reports, pd.DataFrame(rows)
