"""Paths and settings shared by every v1a component.

Scripts and notebooks start with:

    import sys; from pathlib import Path
    sys.path.insert(0, str(<repo>/"v1a"/"common"))
    import paths; paths.setup()

setup() puts src/ (project_data), common/ and every component's scripts/ on the
import path, so modules keep importing each other by name as they did in
v1/scripts. current() reads v1a/current.toml; out(component) is that component's
folder under outputs-local/v1a/.
"""

from __future__ import annotations

from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
V1A = ROOT / "v1a"
OUTPUTS = ROOT / "outputs-local" / "v1a"
V1_OUTPUTS = ROOT / "outputs-local" / "v1"          # frozen record
COMPONENTS = ["01_universe", "02_profiles", "03_retrieval", "04_selection", "05_agent_grading",
              "06_labels", "07_judges", "08_valuation", "09_analysis", "10_final_holdout"]


def setup() -> None:
    for p in [ROOT / "src", V1A / "common", *(V1A / c / "scripts" for c in COMPONENTS)]:
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


def current() -> dict:
    with open(V1A / "current.toml", "rb") as fh:
        return tomllib.load(fh)


def path(relative: str) -> Path:
    """A repository-relative path from current.toml as an absolute Path."""
    return ROOT / relative


def out(component: str) -> Path:
    if component not in COMPONENTS:
        raise ValueError(f"unknown component {component!r}")
    return OUTPUTS / component
