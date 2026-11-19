"""Seed outputs-local/v1a/ from the current v1 outputs (one-off, like v1/scripts/seed_from_v0.py).

Copies the tables each component reads; raw per-call folders (prompts, model
answers, per-pair traces, caches) stay in outputs-local/v1 and are recorded in
the manifest by path, file count and size, not copied. Matthew's rubric-v2 sheets
come from his branch (git show). Barbara's direct-peer pairs: only the 24 whose
comp is in the universe, into the locked 10_final_holdout; the 66 with comps
outside the universe are not seeded.

  uv run python v1a/common/seed_from_v1.py
Writes outputs-local/v1a/<component>/... and outputs-local/v1a/seed_manifest.json.
Never overwrites: stops if a destination exists.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pandas as pd

import paths

V1 = paths.V1_OUTPUTS
OUT = paths.OUTPUTS
# folder names whose contents are raw per-call or per-pair records: linked, not copied
RAW = {"runs", "profiles", "judgments", "pairs", "suggestions", "calls", "codex_runs", "cache", "history",
       "logs", "prompts_dry_run"}
MATTHEW_REF = "origin/matt/rubric-yes-no"
MATTHEW_FILES = ["outputs-local/v1/golden_set_round3/labels/round3_sheet_v2.csv",
                 "outputs-local/v1/golden_set_round3/labels/round3_scores_v2.csv"]

# (component, v1 path, v1a path within the component)
SEED = [
    ("01_universe", "universe/20261025T060358Z", "universe"),
    ("01_universe", "split/20261027T204930Z", "split"),
    # EV/EBITDA is the answer the method predicts: kept with valuation, away from the comp-finding components
    ("08_valuation", "universe/20261025T060358Z/financials.csv", "financials.csv"),
    ("02_profiles", "facets_sonnet", "facets_sonnet"),
    ("02_profiles", "sector_facets_sonnet", "sector_facets_sonnet"),
    ("02_profiles", "industry_facets_sonnet", "industry_facets_sonnet"),
    ("02_profiles", "integration/sources/facets_sonnet_corrected.csv", "facets_sonnet_corrected.csv"),
    ("03_retrieval", "facet_add_drop/selector_handoff/selector_candidates", "selector_candidates"),
    ("03_retrieval", "facet_add_drop/selector_handoff", "facet_add_drop_eval"),
    ("04_selection", "cosine_then_llm/20261104T074915Z_2026-11-04a_sonnet", "cosine_then_llm_sonnet"),
    ("04_selection", "cosine_then_llm/20261104T074915Z_2026-11-04a_haiku", "cosine_then_llm_haiku"),
    ("04_selection", "direct_llm/20261027T204930Z_2026-11-04a_sonnet", "direct_llm_sonnet"),
    ("04_selection", "direct_llm/20261027T204930Z_2026-11-04a_haiku", "direct_llm_haiku"),
    ("05_agent_grading", "agent_loop/ranking_45targets_sonnet", "ranking_45targets_sonnet"),
    ("06_labels", "golden_set/labels", "round1"),
    ("06_labels", "golden_set_showcase/labels", "round2"),
    ("06_labels", "golden_set_round3/labels", "round3"),
    ("06_labels", "integration/sources/sonnet_label.xlsx", "barbara_293/sonnet_label.xlsx"),
    ("06_labels", "integration/review", "barbara_293/review"),
    ("06_labels", "integration/barbara_matches", "barbara_published"),
    ("07_judges", "integration/judge_gpt61sol", "gpt61sol_293"),
    ("09_analysis", "facet_uplift/20261113T190330202875Z", "facet_uplift/20261113T190330202875Z"),
    ("09_analysis", "facet_uplift/20261113T201612982633Z", "facet_uplift/20261113T201612982633Z"),
    ("10_final_holdout", "holdout_completion", "v1_holdout_runs"),
]
SKIP_INSIDE = {"universe/20261025T060358Z": {"financials.csv"},                    # seeded in 08_valuation
               "facet_add_drop/selector_handoff": {"selector_candidates"},       # seeded on its own
               "holdout_completion": {"direct_peers_20261118T014938Z"}}          # seeded with the 24 below
LINKED = ["embeddings/texts_all-mpnet-base-v2.npz", "facet_uplift/cache"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def folder_stats(path: Path) -> dict:
    n = size = 0
    for dp, _, files in os.walk(path):
        for f in files:
            n += 1
            size += os.path.getsize(os.path.join(dp, f))
    return {"files": n, "bytes": size}


def copy_tree(src: Path, dst: Path, skip: set[str], copied: list, linked: list) -> None:
    for entry in sorted(src.iterdir()):
        if entry.name in skip:
            continue
        if entry.is_dir():
            if entry.name in RAW:
                linked.append({"v1_path": entry.relative_to(paths.ROOT).as_posix(), **folder_stats(entry)})
            else:
                copy_tree(entry, dst / entry.name, set(), copied, linked)
        else:
            copy_file(entry, dst / entry.name, copied)


def copy_file(src: Path, dst: Path, copied: list) -> None:
    if dst.exists():
        raise SystemExit(f"{dst} exists (never overwritten)")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied.append({"v1_path": src.relative_to(paths.ROOT).as_posix(),
                   "v1a_path": dst.relative_to(paths.ROOT).as_posix(), "sha256": sha256(dst)})


def seed_direct_peers(copied: list, linked: list) -> dict:
    """The 24 in-universe direct-peer pairs (all comps are holdout companies) into the locked final check."""
    run = V1 / "direct_peers_barbara/20261117_run"
    dst = OUT / "10_final_holdout/direct_peers_24"
    if dst.exists():
        raise SystemExit(f"{dst} exists (never overwritten)")
    dst.mkdir(parents=True)
    manifest = pd.read_csv(run / "manifest.csv", dtype=str)
    inside = manifest[~manifest["comp_id"].str.startswith("EXT_")]
    keys = set(zip(inside["target_id"], inside["comp_id"]))
    verdicts = pd.read_csv(run / "agent/verdicts.csv", dtype={"target": str, "comp": str})
    verdicts = verdicts[[k in keys for k in zip(verdicts["target"], verdicts["comp"])]]
    if len(inside) != 24 or len(verdicts) != 24:
        raise SystemExit(f"expected 24 in-universe pairs, found {len(inside)} and {len(verdicts)} verdicts")
    inside.to_csv(dst / "manifest.csv", index=False)
    verdicts.to_csv(dst / "agent_verdicts.csv", index=False)
    for name in ("config.json", "instructions.txt"):
        copy_file(run / "agent" / name, dst / f"agent_{name}", copied)
    for f in ("freeze.json",):
        copy_file(run / f, dst / f, copied)
    for f in ("manifest.csv", "agent_verdicts.csv"):
        copied.append({"v1_path": f"{run.relative_to(paths.ROOT).as_posix()} (24 in-universe rows)",
                       "v1a_path": (dst / f).relative_to(paths.ROOT).as_posix(), "sha256": sha256(dst / f)})
    for folder in (run / "agent/pairs").iterdir():
        if tuple(folder.name.split("__")) in keys:
            linked.append({"v1_path": folder.relative_to(paths.ROOT).as_posix(), **folder_stats(folder)})
    held = V1 / "holdout_completion/direct_peers_20261118T014938Z"
    copy_tree(held, dst / "assembled_20261118T014938Z", set(), copied, linked)
    return {"pairs": len(inside), "yes": int(inside["Barbara - If Direct"].eq("Yes").sum()),
            "external_pairs_not_seeded": int(len(manifest) - len(inside))}


def seed_matthew(copied: list) -> str:
    commit = subprocess.run(["git", "rev-parse", MATTHEW_REF], cwd=paths.ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    for f in MATTHEW_FILES:
        text = subprocess.run(["git", "show", f"{commit}:{f}"], cwd=paths.ROOT, capture_output=True,
                              check=True).stdout
        dst = OUT / "06_labels/round3" / Path(f).name
        if dst.exists():
            raise SystemExit(f"{dst} exists (never overwritten)")
        dst.write_bytes(text)
        copied.append({"v1_path": f"{MATTHEW_REF}@{commit[:8]}:{f}",
                       "v1a_path": dst.relative_to(paths.ROOT).as_posix(), "sha256": sha256(dst)})
    return commit


def main() -> None:
    if (OUT / "seed_manifest.json").exists():
        raise SystemExit("already seeded (outputs-local/v1a/seed_manifest.json exists)")
    copied, linked = [], []
    for component, src, dst in SEED:
        s, d = V1 / src, paths.out(component) / dst
        if s.is_file():
            copy_file(s, d, copied)
        else:
            if d.exists():
                raise SystemExit(f"{d} exists (never overwritten)")
            copy_tree(s, d, SKIP_INSIDE.get(src, set()), copied, linked)
    matthew = seed_matthew(copied)
    direct = seed_direct_peers(copied, linked)
    for p in LINKED:
        q = V1 / p
        linked.append({"v1_path": q.relative_to(paths.ROOT).as_posix(),
                       **(folder_stats(q) if q.is_dir() else {"files": 1, "bytes": q.stat().st_size})})
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=paths.ROOT, capture_output=True, text=True).stdout.strip()
    manifest = {
        "created": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), "git_commit": commit,
        "rule": "tables copied; raw per-call folders linked from outputs-local/v1 (not copied)",
        "matthew_rubric_v2_commit": matthew, "direct_peers": direct,
        "copied_files": len(copied), "copied_bytes": sum((paths.ROOT / c["v1a_path"]).stat().st_size for c in copied),
        "linked_folders": len(linked), "linked_bytes": sum(x["bytes"] for x in linked),
        "copied": copied, "linked": linked,
    }
    (OUT / "seed_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("copied_files", "copied_bytes", "linked_folders",
                                               "linked_bytes", "direct_peers")}, indent=1))


if __name__ == "__main__":
    paths.setup()
    main()
