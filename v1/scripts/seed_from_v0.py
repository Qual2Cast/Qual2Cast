"""Copy the team's saved v0 outputs into outputs-local/v1/, so every v1 notebook replays them.

v0 wrote to two places: outputs-local/comps/ (universe, facet fills and fill tests, API checks, embeddings, built before the
SIC2 split) and outputs-local/comps_pilot_targets/ (the SIC2 split and everything after it).
v1 reads and writes only outputs-local/v1/. This script is the one-time bridge: it copies, never
moves, so v0's folders stay as they were. Existing files in v1 are left alone, and
outputs-local/v1/seed_manifest.json records what came from where.

  python v1/scripts/seed_from_v0.py            # copy
  python v1/scripts/seed_from_v0.py --dry-run  # list what would be copied
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from project_data import OUTPUTS_LOCAL  # noqa: E402

V1 = OUTPUTS_LOCAL / "v1"

# (source folder, destination folder under v1, entries skipped by name)
SOURCES = [
    (OUTPUTS_LOCAL / "comps", "", {"universe", "facets", "embeddings", "fill_test", "api_checks"}),  # only these
    (OUTPUTS_LOCAL / "comps_pilot_targets", "", None),                           # all of it ...
]
SKIP_NAMES = {"history", "prompts_dry_run", "__pycache__"}                       # ... except reruns and dry runs
SKIP_SUFFIX = ("_history",)


def wanted(relative: Path) -> bool:
    """False if any folder or the file itself on the path is a rerun archive or dry run."""
    return not any(part in SKIP_NAMES or part.endswith(SKIP_SUFFIX) for part in relative.parts)


def plan() -> list[tuple[Path, Path]]:
    pairs = []
    for root, dest, only in SOURCES:
        if not root.exists():
            continue
        for top in sorted(root.iterdir()):
            if only is not None and top.name not in only:
                continue
            files = [top] if top.is_file() else [p for p in top.rglob("*") if p.is_file()]
            pairs += [(p, V1 / dest / p.relative_to(root)) for p in files if wanted(p.relative_to(root))]
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    pairs = plan()
    todo = [(s, d) for s, d in pairs if not d.exists()]
    print(f"{len(pairs)} files in the v0 outputs; {len(pairs) - len(todo)} already in v1; {len(todo)} to copy")
    if args.dry_run:
        return
    for s, d in todo:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
    V1.mkdir(parents=True, exist_ok=True)
    manifest = V1 / "seed_manifest.json"
    prior = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    prior.append({"seeded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "sources": [str(r.relative_to(OUTPUTS_LOCAL)) for r, _, _ in SOURCES],
                  "skipped": sorted(SKIP_NAMES) + [f"*{s}" for s in SKIP_SUFFIX],
                  "files_copied": len(todo), "files_already_present": len(pairs) - len(todo)})
    manifest.write_text(json.dumps(prior, indent=1), encoding="utf-8")
    print("copied", len(todo), "files; wrote", manifest.relative_to(OUTPUTS_LOCAL.parent))


if __name__ == "__main__":
    main()
