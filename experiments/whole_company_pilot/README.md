# Pilot implementation and reproducibility

Start with [the notebook](../../notebooks/whole_company_pilot.ipynb). Each section pairs the workflow step with code, results and its sources. This directory exposes the implementation for review and integration.

## Reproduce the reported results

From this directory, use Python 3.12 in your chosen environment:

```bash
python -m pip install -r requirements-replay.txt
python reproduce.py
```

The executed copy goes to `.local/`. This reuses saved inference and recomputes the analysis. It needs no GPU, model downloads, API keys or external project data. The notebook also runs interactively in Jupyter with the same Python environment.

## Find the implementation

| Task | File |
|---|---|
| Data and source identity | `src/modular_validation/data.py` |
| Text representations | `src/modular_validation/features.py` |
| Cosine, financial distance, OT and fusion | `src/modular_validation/numeric.py` |
| Whole-business evidence | `profile_validation.py`, `evidence_policy.py` in the same module directory |
| LLM response checks | `judgments.py`, `judgment_protocol.py` |
| Peer multiples and evaluation | `evaluation.py`, `experiment_comparison.py` |
| Growth evidence/date checks | `growth_readiness.py` |
| Stage runners | `scripts/run_modular_validation.py`, `run_factor_ablation.py`, `evaluate_modular_validation.py` |
| Method → source → adaptation → result | `method_evidence.csv` |

`workflow.py` is a presentation adapter: it executes the original analysis steps in `replay_stages.json` and exposes their tables. Model and numeric logic lives in the files above. The notebook embeds these assets, so editing an external module does not silently change its frozen results.

## Run implementation checks

```bash
python -m pip install -r requirements-test.txt
python run_checks.py
```

These check implementation, not independent business relevance.

## Run a new model experiment

In notebook Section 9, enable the explicit workspace export. Open the resulting `local_pilot_workspace/rerun-project/`:

```bash
python rerun_workflow.py
```

This prints the dry plan. Full inference requires the recorded model revisions, model-specific dependencies and cached weights. `requirements-inference-recorded.txt` records the original CUDA environment; choose the appropriate Torch build for your machine. Add `--run` only when ready for CPU/GPU work. The exported Windows `scripts/gentle_run.py` can monitor an owned worker.

Edit the exported run's modules for a new experiment, preserving the archived results. Port reviewed changes back to this contribution. The existing runners use the exported source paths; they are not expected to recreate private source folders on another computer.

Independent human judgments, financial alignment and a fresh evaluation sample remain required. The growth module still needs a point-in-time revenue/outcome panel.
