"""Pin the files the site reads, so a changed run cannot change the site silently.

    uv run python site/scripts/pin.py add <chapter> <name> <repo-relative path>
        e.g.  add ch2 universe outputs-local/v1a/01_universe/universe/universe.csv
        writes the entry to site/pins/<chapter>.toml (path, sha256, date pinned)
    uv run python site/scripts/pin.py refresh <name> [<name> ...]    # re-hash after an intended change
    uv run python site/scripts/pin.py verify                          # every pin exists, is tracked, matches

Only git-tracked files can be pinned: the site is built in CI from a clean checkout.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
import tomllib
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parent
sys.path.insert(0, str(SITE))
from facts.common import sha256  # noqa: E402

PINS_DIR = SITE / "pins"


def tracked(rel: str) -> bool:
    r = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True)
    return r.returncode == 0


def read(chapter: str) -> dict[str, dict]:
    f = PINS_DIR / f"{chapter}.toml"
    return tomllib.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def write(chapter: str, pins: dict[str, dict]) -> None:
    PINS_DIR.mkdir(exist_ok=True)
    lines = [f"# Files the {chapter} facts read (site/scripts/pin.py). Do not edit hashes by hand.", ""]
    for name in sorted(pins):
        e = pins[name]
        lines.append(f'{name} = {{ path = "{e["path"]}", sha256 = "{e["sha256"]}", pinned = "{e["pinned"]}" }}')
    (PINS_DIR / f"{chapter}.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def all_pins() -> dict[str, tuple[str, dict]]:
    out = {}
    for f in sorted(PINS_DIR.glob("*.toml")):
        for name, e in tomllib.loads(f.read_text(encoding="utf-8")).items():
            out[name] = (f.stem, e)
    return out


def add(chapter: str, name: str, rel: str) -> None:
    rel = rel.replace("\\", "/")
    p = ROOT / rel
    if not p.is_file():
        sys.exit(f"not a file: {rel}")
    if not tracked(rel):
        sys.exit(f"{rel} is not tracked by git; commit it first (CI only sees committed files)")
    existing = all_pins()
    if name in existing and existing[name][0] != chapter:
        sys.exit(f"pin {name!r} already exists in {existing[name][0]}.toml")
    pins = read(chapter)
    pins[name] = {"path": rel, "sha256": sha256(p), "pinned": dt.date.today().isoformat()}
    write(chapter, pins)
    print(f"pinned {name} -> {rel}")


def refresh(names: list[str]) -> None:
    existing = all_pins()
    for name in names:
        if name not in existing:
            sys.exit(f"no pin named {name!r}")
        chapter, e = existing[name]
        pins = read(chapter)
        pins[name] = {**e, "sha256": sha256(ROOT / e["path"]), "pinned": dt.date.today().isoformat()}
        write(chapter, pins)
        print(f"re-pinned {name}")


def verify() -> int:
    bad = 0
    for name, (chapter, e) in all_pins().items():
        p = ROOT / e["path"]
        problem = (
            "missing" if not p.is_file()
            else "not tracked by git" if not tracked(e["path"])
            else "hash differs" if sha256(p) != e["sha256"]
            else None
        )
        if problem:
            bad += 1
            print(f"{chapter}.{name}: {e['path']}: {problem}")
    print(f"{len(all_pins())} pins, {bad} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["verify"]
    if cmd == "add" and len(args) == 3:
        add(*args)
    elif cmd == "refresh" and args:
        refresh(args)
    elif cmd == "verify":
        sys.exit(verify())
    else:
        sys.exit(__doc__)
