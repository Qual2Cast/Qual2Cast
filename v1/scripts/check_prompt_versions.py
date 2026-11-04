"""
Check that the saved LLM-selector answers still match the prompts the code
builds for the saved prompt version (v1/PROMPT_VERSIONS.md). No API calls.

For every saved verdict (cosine_then_llm.py, outputs-local/v1/judge/) and
every saved direct pick (direct_llm.py, outputs-local/v1/suggest/), the
prompt is rebuilt with SAVED_PROMPT_VERSION from the same inputs, and its
fingerprint (model + prompt) is compared with the one saved beside the
answer. All matching means a rerun or replay reuses the saved answers and
makes no new call. It also reports how the current prompt differs (company
size left out), so a new run is known to need new calls.

  uv run python v1/scripts/check_prompt_versions.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cosine_then_llm as jc  # noqa: E402
import direct_llm as dl  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402


def check_judge(out: Path = jc.SAVED_OUT) -> tuple[int, int, int]:
    """(saved verdicts, fingerprints matched at the saved version, matched at the current version).
    The prompt needs only company names and facets, so a verdict whose candidates run is not under
    outputs-local/v1/candidates/ uses the latest run there (same universe; reported)."""
    total = saved_ok = current_ok = 0
    inputs, fallback = {}, set()
    for path in sorted(jc.output_paths(out).judgments.glob("*.json")):
        j = json.loads(path.read_text(encoding="utf-8"))
        if j.get("llm_status") != "ok":
            continue
        run = j["candidates_run"]
        if run not in inputs:
            folder = jc.CANDIDATES_ROOT / run
            if not (folder / "candidates.csv").exists():
                folder = jc.latest_candidates()
                fallback.add(f"{run} -> {folder.name}")
            inputs[run] = jc.load_inputs(folder, j.get("z_min", jc.DEFAULT_Z))
        _, info, facets = inputs[run]
        comps = list(j["labels"].values())
        total += 1
        saved_ok += jc.fingerprint(jc.build_prompt(j["target"], comps, info, facets, jc.SAVED_PROMPT_VERSION)[0],
                                   j["model"]) == j["fingerprint"]
        current_ok += jc.fingerprint(jc.build_prompt(j["target"], comps, info, facets)[0], j["model"]) == j["fingerprint"]
    for f in sorted(fallback):
        print(f"  (candidates run not in v1/candidates, names and facets read from: {f})")
    return total, saved_ok, current_ok


def check_direct(out: Path = dl.SAVED_OUT) -> tuple[int, int, int]:
    """The same for the saved direct picks; the pool comes from a candidates run with the pick's split."""
    by_split = {}
    for run in sorted(p for p in jc.CANDIDATES_ROOT.iterdir() if (p / "run.json").exists()):
        by_split.setdefault(json.loads((run / "run.json").read_text(encoding="utf-8"))["split_run"], run)
    total = saved_ok = current_ok = 0
    systems = {}
    for path in sorted(dl.output_paths(out).suggestions.glob("*.json")):
        s = json.loads(path.read_text(encoding="utf-8"))
        if s.get("llm_status") != "ok" or s["split_run"] not in by_split:
            continue
        if s["split_run"] not in systems:
            training, info, facets, _ = dl.load_inputs(by_split[s["split_run"]])
            systems[s["split_run"]] = (dl.build_system(training, info, facets)[0], info, facets)
        system, info, facets = systems[s["split_run"]]
        total += 1
        saved_ok += jc.fingerprint(dl.build_prompt(system, s["target"], info, facets, dl.SAVED_PROMPT_VERSION),
                                   s["model"]) == s["fingerprint"]
        current_ok += jc.fingerprint(dl.build_prompt(system, s["target"], info, facets), s["model"]) == s["fingerprint"]
    return total, saved_ok, current_ok


def main() -> None:
    ok = True
    for name, (total, saved_ok, current_ok), version, current in [
            ("cosine_then_llm (judge/)", check_judge(), jc.SAVED_PROMPT_VERSION, jc.PROMPT_VERSION),
            ("direct_llm (suggest/)", check_direct(), dl.SAVED_PROMPT_VERSION, dl.PROMPT_VERSION)]:
        print(f"{name}: {total} saved answers; {saved_ok} match the rebuilt {version} prompt; "
              f"{current_ok} match the current {current} prompt")
        ok &= total > 0 and saved_ok == total
    print("OK: every saved answer is reproduced by the saved prompt version" if ok
          else "MISMATCH: see PROMPT_VERSIONS.md before re-running or replaying anything")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
