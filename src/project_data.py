"""
Shared paths and data-snapshot checks for every task.

Data lives in the same relative place on every laptop:
  data-local/     read-only input snapshots (committed)
  outputs-local/  derived tables and experiment outputs (mostly local; the
                  current website text is committed, see .gitignore)
data_manifest.json (committed) names the snapshot the current code expects and
its checksum, so every laptop runs the same code on the same data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "data_manifest.json"
DATA_LOCAL = REPO_ROOT / "data-local"
OUTPUTS_LOCAL = REPO_ROOT / "outputs-local"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def snapshot_path(name: str | None = None, verify: bool = True) -> Path:
    """Path of a snapshot listed in data_manifest.json (default: the required
    one). Stops with instructions if it's missing or its checksum differs."""
    manifest = load_manifest()
    name = name or manifest["required_snapshot"]
    entry = manifest["snapshots"][name]
    path = REPO_ROOT / entry["file"]
    if not path.exists():
        raise SystemExit(
            f"Missing data snapshot '{name}': expected {entry['file']}.\n"
            "Get it from the data maintainer (see docs/data_dictionary.md), or, if "
            "you have the raw snapshot, run: python src/prepare_company_list.py")
    if verify and entry.get("sha256") and sha256(path) != entry["sha256"]:
        raise SystemExit(
            f"Snapshot '{name}' at {entry['file']} doesn't match the checksum in "
            "data_manifest.json. You may have an old or edited copy; get the "
            "current one from the data maintainer. Never edit snapshots by hand.")
    return path


def normalize_sic_codes(df: pd.DataFrame) -> pd.DataFrame:
    """SIC codes as 4-character, zero-padded strings, with the 2- and 3-digit
    codes derived from them. Spreadsheets drop leading zeros (BrightView's
    0700, Agricultural Services, was stored as 700 and grouped under SIC 70,
    Hotels), so the 2/3-digit codes in the source can't be trusted."""
    df = df.copy()
    sic4 = (df["target_sic4_code"].astype(str).str.strip()
            .str.replace(r"\.0$", "", regex=True).str.zfill(4))
    df["target_sic4_code"] = sic4
    df["target_sic3_code"] = sic4.str[:3]
    df["target_sic2_code"] = sic4.str[:2]
    return df
