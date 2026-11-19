"""Offline: configs parse, roles map to backends, the holdout is refused, the runner's module calls exist."""
from pathlib import Path

import pytest

import workflow as wf

CONFIGS = Path(wf.__file__).with_name("configs")


def test_configs_preview_without_creating_output():
    for name in ("v1a", "codex", "claude"):
        w = wf.Workflow(CONFIGS / f"{name}.toml")
        assert set(w.backends) == set(wf.ROLES) and not w.run_dir.exists()
    w = wf.Workflow(CONFIGS / "v1a.toml")
    assert w.backends == {"fill": "claude-cli", "filter": "claude-cli", "judge": "codex"}
    assert wf.v1a.OUTPUTS in w.run_dir.parents


def test_holdout_targets_are_refused(tmp_path):
    text = (CONFIGS / "v1a.toml").read_text(encoding="utf-8").replace('targets = "training"', 'targets = "holdout"')
    (tmp_path / "c.toml").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="locked"):
        wf.Workflow(tmp_path / "c.toml")


def test_runner_uses_existing_component_functions():
    import cosine_then_llm as sel
    import peer_evaluation as pe
    for name in ("output_paths", "judge_one", "write_tables", "PROMPT_VERSION", "DEFAULT_Z"):
        assert hasattr(sel, name), name
    assert hasattr(pe.PeerEvaluation, "prepare_pairs") and hasattr(pe.PeerEvaluation, "run")
    assert all(wf.code_file(n).exists() for n in wf.CODE)
