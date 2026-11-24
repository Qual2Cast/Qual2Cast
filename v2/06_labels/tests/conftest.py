"""Tests import modules by name from every v2 component (common/paths.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
import paths  # noqa: E402

paths.setup()
