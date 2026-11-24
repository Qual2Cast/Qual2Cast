"""Small helpers every v2 component notebook uses: the inputs table and the checks.

    inputs([...])   one row per input file: rows, sha256, and whether it still matches the seeded copy
                    (outputs-local/v1a/seed_manifest.json) or is new in v1a.
    Checks()        collect named pass/fail checks against the saved v1 numbers; .show() prints them and
                    raises if any failed, so a notebook run fails loudly instead of drifting.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

import paths


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _seeded() -> dict[str, str]:
    manifest = paths.V1A_OUTPUTS / "seed_manifest.json"   # v1a seeded from v1; v2 reads those files in place
    if not manifest.exists():
        return {}
    return {c["v1a_path"]: c["sha256"] for c in json.loads(manifest.read_text(encoding="utf-8"))["copied"]}


def inputs(relative_paths: list[str]) -> pd.DataFrame:
    seeded = _seeded()
    rows = []
    for rel in relative_paths:
        p = paths.path(rel)
        if p.is_dir():
            rows.append({"input": rel, "rows": None, "sha256": "(folder)", "status": "folder"})
            continue
        digest = sha256(p)
        n = None
        if p.suffix == ".csv" or p.name.endswith(".csv.gz"):
            n = len(pd.read_csv(p, usecols=[0]))
        status = ("matches seed" if seeded.get(rel) == digest else
                  "CHANGED since seed" if rel in seeded else "new in v1a")
        rows.append({"input": rel, "rows": n, "sha256": digest[:12], "status": status})
    return pd.DataFrame(rows)


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append({"check": name, "result": "pass" if ok else "FAIL", "detail": detail})

    def show(self) -> pd.DataFrame:
        table = pd.DataFrame(self.rows)
        failed = table[table["result"] == "FAIL"]
        print(f"{len(table) - len(failed)}/{len(table)} checks pass")
        if len(failed):
            raise AssertionError("failed checks:\n" + failed.to_string(index=False))
        return table
