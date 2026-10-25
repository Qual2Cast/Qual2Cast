"""Boundaries added for sequential sampling and structured hosted inference."""

import json
from types import SimpleNamespace
import pandas as pd
import pytest
from pipeline.sampling import SampleStage
from matching.private_evidence import source_document
from pipeline.llm import StructuredLLM, object_schema
from pipeline.catalog import method_catalog, REFERENCES


def test_random_sample_is_repeatable_excludes_declared_ids_and_ignores_outcomes():
    frame = pd.DataFrame(
        {
            "IQ_COMPANY_ID": ["c", "b", "a", "d"],
            "target_ciq_ticker": ["C", "B", "A", "D"],
        }
    )
    workflow = SimpleNamespace(ids=frame.IQ_COMPANY_ID.tolist(), data=frame)
    stage = SampleStage()
    first = stage.run("seeded_random", workflow, n=2, seed=4511, exclude_ids=["a"])
    assert first == stage.run(
        "seeded_random", workflow, n=2, seed=4511, exclude_ids=["a"]
    )
    assert "a" not in first["company_ids"] and len(set(first["company_ids"])) == 2


@pytest.mark.parametrize(
    "title", ["404 | Example", "Page Not Found :: Example", "Request Unavailable"]
)
def test_error_pages_cannot_supply_company_evidence(title):
    doc = source_document(
        "test",
        dict(
            page_id="P1",
            title=title,
            url="https://example.com/",
            blocks=["Navigation and promotion that appear on an error page."],
        ),
    )
    assert not doc["eligible"] and doc["removed"][0]["reason"] == "error_page_title"


def test_hosted_adapter_replay_requires_exact_request_and_never_invokes_cli(
    tmp_path, monkeypatch
):
    from pipeline import cli_backend

    calls = []

    def backend(*args):
        calls.append(args)
        return json.dumps({"value": "supported"}), {"unexpected_tool_events": []}

    monkeypatch.setattr(cli_backend, "structured_cli", backend)
    schema = object_schema({"value": {"type": "string"}})
    model = StructuredLLM(tmp_path, provider="cli", model="test-model")
    answer = model.complete("test", {"source": "one"}, schema, "Use only the source")
    replay = StructuredLLM(tmp_path, provider="cli", model="test-model", replay=True)
    assert (
        replay.complete("test", {"source": "one"}, schema, "Use only the source")[
            "data"
        ]
        == answer["data"]
    )
    assert (
        replay.complete("test", {"source": "changed"}, schema, "Use only the source")[
            "status"
        ]
        == "not_run_cache_missing"
    )
    assert len(calls) == 1


def test_every_catalog_method_has_resolvable_sources():
    for row in method_catalog():
        assert row["procedure"] and row["limitation"] and row["sources"]
        assert all(key in REFERENCES for key in row["sources"])


def test_unrun_extraction_is_not_reported_as_zero_accuracy():
    from pipeline.evaluation_stage import event_metrics

    labels = {"a": {"truth": {"P1": ["hiring"]}}}
    records = {
        "a": {"pages": [{"source_url": "https://example.com/news", "page_id": "P1"}]}
    }
    result = event_metrics(
        {"a": {"status": "incomplete_llm_run", "events": []}}, labels, records
    )
    assert result["incomplete_companies"] == 1
    assert (
        result["precision"] is None
        and result["recall"] is None
        and result["f1"] is None
    )
