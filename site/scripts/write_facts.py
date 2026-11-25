"""Write every named fact to facts.csv in the site's output folder, so slide makers copy numbers from one file.

A Quarto post-render script (site/_quarto.yml, project: post-render). Quarto runs it from site/ with the Python it
renders with (QUARTO_PYTHON, else the active environment), after every render of the project, including a
single-file render and each re-render in `quarto preview`, and passes the output folder in
QUARTO_PROJECT_OUTPUT_DIR. It imports every facts/ch*.py module in one process, so a fact name used in two
chapters fails here, although each chapter renders on its own.

By hand (writes site/_site/facts.csv, or into the folder given):

    uv run python site/scripts/write_facts.py [<output folder>]
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))

from facts import common  # noqa: E402


def output_dir(argv: list[str]) -> Path:
    """The folder given on the command line, else Quarto's output folder, else site/_site."""
    if len(argv) > 1:
        return Path(argv[1]).resolve()
    env = os.environ.get("QUARTO_PROJECT_OUTPUT_DIR")
    return (SITE / env).resolve() if env else SITE / "_site"  # Quarto passes an absolute path; resolve anyway


def main(argv: list[str]) -> int:
    modules = sorted(p.stem for p in (SITE / "facts").glob("ch*.py"))
    for name in modules:
        try:
            importlib.import_module(f"facts.{name}")
        except common.PinError as e:  # anything else (a fact name used twice, a bug) keeps its traceback
            print(f"write_facts: facts/{name}.py: {e}", file=sys.stderr)
            return 1
    out = output_dir(argv) / "facts.csv"
    common.write_csv(out)
    if os.environ.get("QUARTO_PROJECT_SCRIPT_QUIET") != "1":
        print(f"write_facts: {len(common.REGISTRY)} facts from {len(modules)} chapter modules -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
