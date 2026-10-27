"""Transport contracts and notebook integration, without live model calls."""

import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import cli_models as cli
import facets as fc
import fill_facets as ff
import pipeline as pl


@pytest.mark.parametrize("backend", ["codex", "claude-cli"])
def test_cli_structured_response_and_logs(tmp_path, monkeypatch, backend):
    seen = {}
    monkeypatch.setattr(cli, "executable", lambda name: name)
    def run(command, **kwargs):
        seen.update(command=command, **kwargs)
        if backend == "codex":
            Path(command[command.index("--output-last-message") + 1]).write_text('{"answer":42}')
            stdout = '{"type":"turn.completed","usage":{"output_tokens":7}}\n'
        else:
            stdout = json.dumps({"subtype": "success", "is_error": False,
                                 "structured_output": {"answer": 42}, "usage": {"output_tokens": 7}})
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="diagnostic")
    monkeypatch.setattr(cli.subprocess, "run", run)
    result = cli.call_cli("evidence only", tmp_path, {"type": "object"}, backend, "test-model", "low")
    assert result["llm_status"] == "ok" and json.loads(result["text"]) == {"answer": 42}
    assert result["usage"]["output_tokens"] == 7
    assert seen["input"] == "evidence only" and seen["capture_output"]
    assert (tmp_path / "schema.json").exists() and (tmp_path / "stderr.txt").read_text() == "diagnostic"
    assert not Path(seen["cwd"]).exists()  # subprocess work directory is cleaned
    if backend == "claude-cli":
        assert "--json-schema" in seen["command"] and "-p" in seen["command"]


@pytest.mark.parametrize("returncode, stdout", [
    (1, "login required"),
    (0, '{"is_error":true,"result":"usage limit"}'),
    (0, '{"subtype":"error_max_structured_output_retries","is_error":false}'),
    (0, '{"subtype":"success","result":"not JSON"}'),
])
def test_failed_cli_call_keeps_raw_response_and_stops(tmp_path, monkeypatch, returncode, stdout):
    monkeypatch.setattr(cli, "executable", lambda _: "claude")
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=returncode, stdout=stdout, stderr=""))
    result = cli.call_cli("prompt", tmp_path, {}, "claude-cli")
    assert result["llm_status"] == "cli_error" and result["stop_run"]
    assert (tmp_path / "stdout.txt").read_text() == stdout


def test_cli_timeout_keeps_partial_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "executable", lambda _: "codex")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("codex", 1, output=b"partial", stderr=b"timeout")
    monkeypatch.setattr(cli.subprocess, "run", timeout)
    result = cli.call_cli("prompt", tmp_path, {}, "codex", timeout=1)
    assert result["llm_status"] == "timeout" and result["stop_run"]
    assert (tmp_path / "stdout.txt").read_text() == "partial"


def synthetic_cli(calls):
    def call(prompt, run_dir, schema, backend, model=None, effort=None, timeout=600):
        calls.append((backend, model, prompt))
        if "knows_company" in schema.get("properties", {}):
            business = {"business": "Test software services"}
            for f in fc.FACETS:
                if f.kind == "text":
                    item = {"value": "Software services for business customers"}
                elif f.kind == "any of":
                    item = {"items": [{"category": f.categories[0], "detail": "business customers"}]}
                else:
                    item = {"category": f.categories[0]}
                    if f.detail:
                        item["detail"] = "business customers"
                business[f.name] = {"status": "filled", **item}
            answer = {"knows_company": True, "company": business, "notes": ""}
        else:
            props = schema["properties"]["comps"]["items"]["properties"]
            labels = props["label"].get("enum") or re.findall(r"^(P\d+):", prompt, re.M)[:4]
            answer = {"comps": [{"label": label, "reason": "Synthetic integration fixture",
                                  **({"good": True} if "good" in props else {})} for label in labels]}
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps(answer)
        (run_dir / "prompt.txt").write_text(prompt)
        (run_dir / "response.json").write_text(text)
        return {"llm_status": "ok", "text": text, "usage": {}}
    return call


def patch_inference(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ff, "call_cli", synthetic_cli(calls))
    monkeypatch.setattr(ff, "executable", lambda _: "test-cli")
    def embeddings(texts, cache_dir, model_name):
        rng = np.random.default_rng(42)
        arrays = {}
        for name in texts:
            values = rng.normal(size=(len(texts), 16)).astype(np.float32)
            arrays[name] = values / np.linalg.norm(values, axis=1, keepdims=True)
        return arrays, tmp_path / "synthetic-embeddings.npz"
    monkeypatch.setattr(pl.cd, "embed_facets", embeddings)
    return calls


@pytest.mark.parametrize("backend", ["codex", "claude-cli"])
def test_pipeline_all_stages_resumes_and_keeps_holdout_out_of_pool(tmp_path, monkeypatch, backend):
    calls = patch_inference(monkeypatch, tmp_path)
    config = pl.Config(backend=backend, model="test-model", company_limit=12,
                       judge_z=-100, direct_suggestions=True)
    p = pl.Pipeline(config, tmp_path / "run")
    p.prepare(); p.fill(); p.split(); p.retrieve(); p.judge(); p.suggest(); summary = p.evaluate()
    assert calls and {c[0] for c in calls} == {backend}
    assert set(p.ranking.comp) <= set(p.training)
    assert not (p.ranking.target == p.ranking.comp).any()
    assert set(p.targets) <= set(p.training)
    assert (summary["attempted targets"] == len(p.targets)).all()
    assert "LLM direct, mean" in summary.index
    assert (p.run_dir / "valuation/per_target.csv").exists()
    # Resume the same settings: expensive model calls are skipped, tables are archived.
    before = len(calls)
    p.fill(); p.judge(); p.suggest()
    assert len(calls) == before
    assert list((p.run_dir / "facets/tables_history").glob("*/facets.csv"))
    with pytest.raises(ValueError, match="different settings"):
        pl.Pipeline(pl.Config(backend=backend, model="other"), p.run_dir)
    # Changing the target's outcome cannot affect prompts/judgments already produced.
    saved = p.judgments.copy()
    p.financials.loc[p.targets[0], "target_ev_to_ebitda"] = 999
    p.evaluate()
    pd.testing.assert_frame_equal(saved, p.judgments)


def test_main_notebook_code_cells_run_sequentially(tmp_path, monkeypatch):
    patch_inference(monkeypatch, tmp_path)
    notebook = json.loads((Path(__file__).resolve().parents[2] / "pipeline.ipynb").read_text())
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if "parameters" in cell["metadata"].get("tags", []):
            source = source.replace('MODEL = ""', 'MODEL = "test-model"').replace(
                'COMPANY_LIMIT = None', 'COMPANY_LIMIT = 12').replace('RUN_DIR = None', f'RUN_DIR = {str(tmp_path / "notebook-run")!r}')
        exec(compile(source, "pipeline.ipynb", "exec"), namespace)
    assert (namespace["pipeline"].run_dir / "valuation/summary.csv").exists()
    assert len(namespace["pipeline"].targets) > 0


def test_backend_is_part_of_facet_cache_identity():
    record = {"company_name": "Example", "website": "example.com", "pages": []}
    profile = {"llm_status": "ok", "prompt_version": fc.PROMPT_VERSION, "model": "same-name",
               "backend": "codex", "effort": "", "input_sha256": fc.input_fingerprint(record, False)}
    assert ff.is_current(profile, record, "same-name", "codex")
    assert not ff.is_current(profile, record, "same-name", "claude-cli")
