"""Named facts for the site: every number in a chapter's text comes from here, never typed by hand.

A chapter starts with a hidden cell:

    from facts import common as F
    from facts import ch2_data as f

and its text uses the facts inline: `{python} f.n_universe` prints "533".

Sources are pinned. Each file a chapter reads is listed in site/pins/<chapter>.toml with its sha256, so a run that
changes after the freeze cannot change the site silently: pinned() refuses a file whose hash differs. Re-pin on
purpose with site/scripts/pin.py. Only files tracked by git can be pinned, because the site is built in CI from a
clean checkout.

Chapter modules (facts/ch*.py) import only light libraries (stdlib, pandas, numpy, matplotlib, openpyxl,
tabulate): CI installs the `site` dependency group, not torch.
"""

from __future__ import annotations

import csv
import hashlib
import tomllib
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parent

RELEASE = tomllib.loads((SITE / "release.toml").read_text(encoding="utf-8"))
AS_OF: str = RELEASE["as_of"]


class PinError(RuntimeError):
    pass


def _load_pins() -> dict[str, dict]:
    pins: dict[str, dict] = {}
    for f in sorted((SITE / "pins").glob("*.toml")):
        for name, entry in tomllib.loads(f.read_text(encoding="utf-8")).items():
            if name in pins:
                raise PinError(f"pin {name!r} is defined in both {pins[name]['file']} and {f.name}")
            pins[name] = {**entry, "file": f.name}
    return pins


PINS = _load_pins()


def sha256(path: Path) -> str:
    """sha256 of the file with CRLF read as LF, so a Windows checkout (core.autocrlf) and CI's Linux checkout of the
    same committed file give the same hash. Binary files are not converted by git, so both sides match anyway."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def pinned(name: str) -> Path:
    """The absolute path of a pinned source file, after checking it still matches its pinned hash."""
    if name not in PINS:
        raise PinError(f"no pin named {name!r}; add one with site/scripts/pin.py add")
    entry = PINS[name]
    p = ROOT / entry["path"]
    if not p.is_file():
        raise PinError(f"pinned file {entry['path']} ({name}) is missing")
    if sha256(p) != entry["sha256"]:
        raise PinError(
            f"{entry['path']} ({name}) changed since it was pinned on {entry['pinned']}; "
            "if the change is intended, re-pin it with site/scripts/pin.py refresh " + name
        )
    return p


class Fact(str):
    """What the page prints (a str), plus the raw value and where it came from."""

    value: object
    source: str
    name: str

    def __new__(cls, text: str, value: object, source: str, name: str) -> "Fact":
        obj = super().__new__(cls, text)
        obj.value, obj.source, obj.name = value, source, name
        return obj


REGISTRY: dict[str, Fact] = {}


def fact(name: str, value: object, text: str | None = None, *, source: str) -> Fact:
    """Register a named fact. `text` is how it prints (default str(value)); `source` names the pin(s) it is from."""
    if name in REGISTRY:
        raise ValueError(f"fact {name!r} is defined twice")
    for pin in source.split("+"):
        if pin.strip() not in PINS:
            raise PinError(f"fact {name!r} cites unknown pin {pin.strip()!r}")
    f = Fact(str(value) if text is None else text, value, source, name)
    REGISTRY[name] = f
    return f


def write_csv(path: Path) -> None:
    """Every registered fact, for the slide makers: name, printed text, raw value, source pins and their files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "text", "value", "source", "files", "as_of"])
        for name in sorted(REGISTRY):
            f = REGISTRY[name]
            files = ";".join(PINS[p.strip()]["path"] for p in f.source.split("+"))
            w.writerow([name, str(f), repr(f.value), f.source, files, AS_OF])
