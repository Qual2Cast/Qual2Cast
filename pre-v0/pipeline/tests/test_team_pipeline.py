"""Boundary tests for the shared workflow; synthetic fixtures are not results."""

import copy
import numpy as np
import pandas as pd
import pytest
from pipeline.private_inputs import private_financials
from pipeline.team import TeamPipeline, ExperimentRunner
from pipeline.stages import PipelineConfig
from pipeline.workflow import CompanyWorkflow
from matching.private_evidence import digest, allowed_page
from matching.business_gate import validate_pair
from matching.llm_methods import BusinessReview
from growth_signals.stage import GrowthStage


def fixture():
    ids = ["T"] + ["P" + str(i) for i in range(7)]
    data = pd.DataFrame(
        {
            "IQ_COMPANY_ID": ids,
            "target_ciq_ticker": ids,
            "target_company_name": ids,
            "target_ciq_website": [
                "https://" + i.lower() + ".example.com" for i in ids
            ],
            "text": ["We install electrical systems."] * 8,
            "urls": [[]] * 8,
            "words": [5] * 8,
            "status": ["ok"] * 8,
            "page_count": [1] * 8,
        }
    )
    finance = pd.DataFrame(
        {
            "revenue": [100] * 8,
            "ebitda": [10] * 8,
            "margin": [0.1] * 8,
            "debt_to_revenue": [0.5] * 8,
            "debt_derived": [50] * 8,
        },
        index=ids,
    )
    vectors = np.eye(8) + 0.1
    backend = CompanyWorkflow(
        data, finance, {k: vectors for k in ("mpnet", "tfidf", "lsa")}
    )
    docs = {
        cid + ":P1": {
            "source_id": cid + ":P1",
            "company_id": cid,
            "source_url": "https://example.com",
            "text": "We install electrical systems.",
            "eligible": True,
        }
        for cid in ids
    }
    reviews = {}
    for p in ids[1:4]:
        r = {
            "target_id": "T",
            "peer_id": p,
            "decision": "eligible",
            "reviewer_kind": "source_based_assessment",
            "checks": dict.fromkeys(
                ("business_function", "operating_role", "customer_use", "whole_scope"),
                True,
            ),
            "rationale": "Same installation role in supplied fixture.",
            "scope_differences": "Synthetic example only.",
        }
        for side, cid in [("target", "T"), ("peer", p)]:
            r[side + "_evidence"] = [
                {
                    "source_id": cid + ":P1",
                    "quote": docs[cid + ":P1"]["text"],
                    "text_sha256": digest(docs[cid + ":P1"]["text"]),
                }
            ]
            r[side + "_document_hashes"] = {
                cid + ":P1": digest(docs[cid + ":P1"]["text"])
            }
        reviews["T|" + p] = r
    return (
        backend,
        docs,
        reviews,
        pd.Series([900, 5, 10, 15, 100, 200, 300, 400], index=ids),
    )


def test_private_inputs_do_not_implicitly_read_public_finances():
    assert private_financials()["values"]["ebitda"] is None
    with pytest.raises(ValueError):
        private_financials({"market_cap": {"value": 10}})
    with pytest.raises(ValueError):
        private_financials(
            {"revenue": {"value": 10, "source_kind": "stock_api", "source_ref": "x"}}
        )


def test_incompatible_currency_does_not_make_margin():
    base = {
        "source_kind": "client_supplied",
        "source_ref": "client",
        "period_end": "2026-09-30",
        "units": "millions",
    }
    r = private_financials(
        {
            "revenue": {**base, "value": 100, "currency": "USD"},
            "ebitda": {**base, "value": 10, "currency": "EUR"},
        }
    )
    assert r["values"]["margin"] is None and r["issues"]


def test_complete_scope_hash_prevents_reusing_stale_approval():
    _, docs, reviews, _ = fixture()
    r = reviews["T|P0"]
    assert validate_pair(r, docs)["eligible"]
    docs["T:P2"] = {
        "company_id": "T",
        "text": "We also manufacture unrelated products.",
        "eligible": True,
    }
    assert not validate_pair(r, docs)["eligible"]


def test_exact_quote_and_correct_company_are_required():
    _, docs, reviews, _ = fixture()
    r = copy.deepcopy(reviews["T|P0"])
    r["peer_evidence"][0]["quote"] = "We do everything the target does."
    assert not validate_pair(r, docs)["eligible"]


def test_gate_cannot_be_bypassed_by_public_target_multiple_or_size(tmp_path):
    backend, docs, reviews, multiples = fixture()
    p = TeamPipeline(backend, docs, multiples, reviews, cache_dir=tmp_path)
    cfg = PipelineConfig(shortlist=7)
    a = p.run("T", cfg)
    assert {x["peer_id"] for x in a["peers"]} == {"P0", "P1", "P2"}
    assert a["stages"]["valuation"]["result"]["multiple"] == 10
    assert a["stages"]["valuation"]["result"]["enterprise_value_proxy"] is None
    p.peer_multiples.loc["T"] = 1e9
    backend.finance.loc["T", ["revenue", "ebitda"]] = [1e12, 1e11]
    b = p.run("T", cfg)
    assert a["peers"] == b["peers"]
    assert b["target_inputs"]["availability"] == "website_only"


def test_missing_factors_abstain_instead_of_using_snapshot(tmp_path):
    backend, docs, reviews, multiples = fixture()
    p = TeamPipeline(backend, docs, multiples, reviews, cache_dir=tmp_path)
    r = p.run("T", PipelineConfig(shortlist=7, factor_method="revenue"))
    assert r["stages"]["factors"]["result"]["status"] == "missing_target_factors"
    assert not r["peers"]


def test_explicit_client_ebitda_produces_proxy_only(tmp_path):
    backend, docs, reviews, multiples = fixture()
    p = TeamPipeline(backend, docs, multiples, reviews, cache_dir=tmp_path)
    r = p.run(
        "T",
        PipelineConfig(shortlist=7),
        {
            "ebitda": {
                "value": 8,
                "source_kind": "client_supplied",
                "source_ref": "client accounts",
            }
        },
    )
    v = r["stages"]["valuation"]["result"]
    assert v["enterprise_value_proxy"] == 80 and v["verified_enterprise_value"] is None


def test_teammate_retriever_extension_retains_gate(tmp_path):
    backend, docs, reviews, multiples = fixture()
    p = TeamPipeline(backend, docs, multiples, reviews, cache_dir=tmp_path)
    p.matching.register(
        "teammate",
        lambda company_id, limit: backend.retrieve(company_id, "tfidf", limit),
    )
    r = p.run("T", PipelineConfig(matching_method="teammate", shortlist=7))
    assert len(r["peers"]) == 3 and r["audit"]["business_gate_enforced"]


def test_human_only_does_not_relabel_automated_assessment():
    _, docs, reviews, _ = fixture()
    r = BusinessReview(docs, reviews).run("T", "P0", "human_only")
    assert not r["eligible"]


def test_invalid_llm_sentence_ids_cannot_pass_gate():
    _, docs, _, _ = fixture()

    class Stub:
        model = "synthetic_stub"

        def complete(self, *args):
            return {
                "status": "ok",
                "request_id": "fixture",
                "data": {
                    "checks": dict.fromkeys(
                        (
                            "business_function",
                            "operating_role",
                            "customer_use",
                            "whole_scope",
                        ),
                        "yes",
                    ),
                    "target_sentence_id": "nonexistent",
                    "peer_sentence_id": "P0",
                    "scope_differences": "none",
                    "rationale": "fixture",
                },
            }

    r = BusinessReview(docs, llm=Stub()).run("T", "P0", "llm_direct")
    assert not r["eligible"] and r["status"] == "invalid_citations"


def record(url="https://example.com/news/launch"):
    return {
        "IQ_COMPANY_ID": "T",
        "company_name": "Example Company",
        "website": "https://example.com",
        "pages": [
            {
                "page_id": "P1",
                "category": "article",
                "source_url": url,
                "via_ir_fallback": False,
                "raw_title": "Example Company launches a new product for builders.",
                "raw_meta": "",
                "raw_blocks": [],
                "published_date": "2026-10-10",
                "published_date_precision": "day",
                "fetched_at": "2026-10-19T12:00:00Z",
            }
        ],
    }


@pytest.mark.parametrize(
    "url", ["https://example.com/investors/news/a", "https://ir.example.com/a"]
)
def test_ir_url_is_excluded_even_when_fallback_flag_is_false(url):
    r = GrowthStage().run(record(url))
    assert not r["events"] and len(r["excluded_pages"]) == 1
    assert not allowed_page(url)


def test_historical_cutoff_requires_capture_available_at_the_time():
    r = GrowthStage().run(record(), cutoff="2022-12-31")
    assert (
        not r["features"]
        and r["excluded_pages"][0]["reason"] == "not_captured_by_cutoff"
    )


def test_experiment_config_product_and_stages_are_saved(tmp_path):
    backend, docs, reviews, multiples = fixture()
    p = TeamPipeline(backend, docs, multiples, reviews, cache_dir=tmp_path / "cache")
    configs = ExperimentRunner.configurations(
        PipelineConfig(shortlist=7),
        matching_method=["mpnet", "tfidf"],
        valuation_method=["median", "harmonic"],
    )
    reports, results = ExperimentRunner(p).run(
        ["T"], configs, output_dir=tmp_path / "runs"
    )
    assert len(results) == 4
    assert all(
        set(r["stages"])
        == {
            "evidence",
            "profile",
            "matching",
            "business_review",
            "factors",
            "growth",
            "measurement",
            "valuation",
        }
        for r in reports
    )
    assert len(list((tmp_path / "runs").glob("*/stage_results.json"))) == 1
