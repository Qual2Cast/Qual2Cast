"""Paths and settings shared by every v2 component.

v2 is a full working copy of v1a (2026-11-24), the way v1 was a copy of v0: all ten components, the pipeline
runner, notebooks, tests and docs. v1a stays frozen as the record of 2026-11-19.

Scripts and notebooks start with:

    import sys; from pathlib import Path
    sys.path.insert(0, str(<repo>/"v2"/"common"))
    import paths as v2; v2.setup()

setup() puts src/ (project_data), v2/common and every v2 component's scripts/ on the import path, so modules keep
importing each other by name as they did in v1/scripts. Only v2 code is on the path, never v1a's.

Outputs: v2 does not copy v1a's 199 MB of saved runs. Existing runs stay in outputs-local/v1a/ and are read from
there; new runs are written to outputs-local/v2/.
- out(component): outputs-local/v2/<component>/, where a new run is WRITTEN.
- src(component, *parts): where an existing file or folder is READ: outputs-local/v2/<component>/<parts> if it
  exists there (made in v2), else outputs-local/v1a/<component>/<parts> (made in v1a or seeded from v1).
- latest(component, *parts, pattern="2*"): the newest time-stamped run folder matching pattern in either place.
- current() reads v2/current.toml, whose paths name the current runs explicitly (most still in outputs-local/v1a/).
"""

from __future__ import annotations

from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "v2"
V1A = ROOT / "v1a"                                   # frozen record of the code (2026-11-19); never imported from v2
OUTPUTS = ROOT / "outputs-local" / "v2"              # new runs
V1A_OUTPUTS = ROOT / "outputs-local" / "v1a"         # existing runs and seeded tables (read only)
V1_OUTPUTS = ROOT / "outputs-local" / "v1"           # frozen v1 record
COMPONENTS = ["01_universe", "02_profiles", "03_retrieval", "04_selection", "05_agent_grading",
              "06_labels", "07_judges", "08_valuation", "09_analysis", "10_final_holdout"]


def setup() -> None:
    for p in [ROOT / "src", V2 / "common", *(V2 / c / "scripts" for c in COMPONENTS)]:
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


def current() -> dict:
    with open(V2 / "current.toml", "rb") as fh:
        return tomllib.load(fh)


def path(relative: str) -> Path:
    """A repository-relative path from current.toml as an absolute Path."""
    return ROOT / relative


def _check(component: str) -> None:
    if component not in COMPONENTS:
        raise ValueError(f"unknown component {component!r}")


def out(component: str) -> Path:
    """Where v2 writes new runs of a component: outputs-local/v2/<component>/."""
    _check(component)
    return OUTPUTS / component


def src(component: str, *parts: str) -> Path:
    """Where an existing output is read: the v2 copy if v2 made one, else v1a's."""
    _check(component)
    mine = OUTPUTS.joinpath(component, *parts)
    return mine if mine.exists() else V1A_OUTPUTS.joinpath(component, *parts)


def src_roots(component: str, *parts: str) -> list[Path]:
    """Both places a component's outputs can be (v2 first), for globbing over runs."""
    _check(component)
    return [OUTPUTS.joinpath(component, *parts), V1A_OUTPUTS.joinpath(component, *parts)]


def latest(component: str, *parts: str, pattern: str = "2*") -> Path:
    """The newest run folder (or file) matching pattern under <component>/<parts> in v2 or v1a, by name (runs are
    named by UTC time stamp, so the name order is the time order)."""
    hits = [p for root in src_roots(component, *parts) for p in root.glob(pattern)]
    if not hits:
        raise FileNotFoundError(f"no {pattern} under {component}/{'/'.join(parts)} in outputs-local/v2 or v1a")
    return max(hits, key=lambda p: p.name)
