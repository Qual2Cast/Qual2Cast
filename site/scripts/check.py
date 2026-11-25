"""Check the site before it is built. CI runs this before `quarto render`; run it locally the same way:

    uv run python site/scripts/check.py              # draft or release, as site/release.toml says
    uv run python site/scripts/check.py --release    # what would block a release build right now

1. Pins: every file listed in site/pins/*.toml exists, is tracked by git, and matches its sha256. A problem always
   fails the check (the build would fail on it anyway, or CI would not see the file).
2. Placeholders: `.prose-todo` divs, CAPTION TODO and ALT TODO in site/*.qmd, counted per file. Always listed; they
   fail the check only in release mode (release = true in site/release.toml, or --release).
3. Typed numbers, a warning only: digits in the prose, outside code (cells and inline code such as `{python} f.x`),
   YAML front matter, attributes ({#sec-x}, {.class}), links, cross-references (@sec-x) and the placeholder divs.
   Each one should come from a fact; a token that is a name rather than a quantity (v3, E1-E10) goes on a line of
   site/scripts/number_allowlist.txt. Never fails.

One line per problem, then a summary line. Exit status 1 if anything failed, else 0. Inside GitHub Actions the
problem lines are also annotations, so typed numbers show up on a pull request's changed files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parent
sys.path.insert(0, str(SITE))

PLACEHOLDER_KINDS = ("prose-todo", "CAPTION TODO", "ALT TODO")

# A fenced div opener with the prose-todo class: `::: {.prose-todo}`, `:::: {.prose-todo #id}`, `::: prose-todo`.
PROSE_TODO = re.compile(r"^\s*:{3,}\s*(?:\{[^}]*\.prose-todo(?![\w-])[^}]*\}|prose-todo(?![\w-]))")
DIV_FENCE = re.compile(r"^\s*:{3,}(.*)$")
CODE_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")

# Removed from a prose line before looking for digits, in this order.
NOT_PROSE = [
    (re.compile(r"(`+).+?\1"), " "),  # inline code, including `{python} f.n_universe`
    (re.compile(r"\{\{<.*?>\}\}"), " "),  # shortcodes
    (re.compile(r"<!--.*?-->"), " "),  # HTML comments
    (re.compile(r"^\s*\[(?!\^)[^\]]+\]:\s.*$"), " "),  # reference-link definitions (not footnotes: their text is prose)
    (re.compile(r"\]\([^)]*\)"), "]"),  # link and image targets
    (re.compile(r"<?https?://[^\s>)]+>?"), " "),  # bare URLs
    (re.compile(r"\{[^{}]*\}"), " "),  # attributes: {#sec-x}, {.class key=1}, {width=50%}
    (re.compile(r"\[\^[^\]]*\]"), " "),  # footnote markers
    (re.compile(r"(?<!\w)@[\w:-]+"), " "),  # cross-references and citations: @sec-results, [@key]
    (re.compile(r"<[^>]+>"), " "),  # HTML tags
    (re.compile(r"^\s*(?:>\s*)*\d+[.)]\s"), " "),  # ordered-list markers
]
NUMBER_TOKEN = re.compile(r"\S*\d\S*")
TOKEN_EDGES = "()[]<>\"'.,;:!?*_~“”‘’"  # stripped from both ends of a token; the last four are curly quotes


# --- release.toml --------------------------------------------------------------------------------------------------


def read_release(site: Path) -> tuple[bool, list[str]]:
    """The release switch, and the problems with release.toml (an unreadable switch counts as release mode)."""
    try:
        cfg = tomllib.loads((site / "release.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        return True, [f"release.toml: cannot read it ({e})"]
    problems = []
    release = cfg.get("release")
    if not isinstance(release, bool):
        problems.append(f"release.toml: release must be true or false, not {release!r}")
        release = True
    try:
        dt.date.fromisoformat(str(cfg.get("as_of")))
    except ValueError:
        problems.append(f"release.toml: as_of must be a date such as \"2026-11-24\", not {cfg.get('as_of')!r}")
    return release, problems


# --- pins ----------------------------------------------------------------------------------------------------------


def git_tracked(root: Path, paths: list[str]) -> set[str] | None:
    """The given repo-relative paths that git tracks, or None when git cannot be asked."""
    try:
        r = subprocess.run(
            ["git", "--literal-pathspecs", "ls-files", "-z", "--", *paths],
            cwd=root, capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {p for p in r.stdout.decode("utf-8").split("\0") if p}


def check_pins(site: Path, root: Path) -> tuple[int, list[tuple[str, str, Path]]]:
    """(number of pins, [(where, problem, the pins file)]) for every pin in site/pins/*.toml."""
    problems: list[tuple[str, str, Path]] = []
    pins: dict[str, tuple[str, dict]] = {}
    for f in sorted((site / "pins").glob("*.toml")):
        rel = f"pins/{f.name}"
        try:
            entries = tomllib.loads(f.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            problems.append((rel, f"not valid TOML ({e})", f))
            continue
        for name, e in entries.items():
            if name in pins:
                problems.append((rel, f"pin {name!r} is also in pins/{pins[name][0]}.toml; names must be unique", f))
            elif not isinstance(e, dict) or not {"path", "sha256"} <= e.keys():
                problems.append((rel, f"pin {name!r} needs a path and a sha256; add it with site/scripts/pin.py", f))
            else:
                pins[name] = (f.stem, e)
    if not pins:
        return 0, problems

    try:
        from facts.common import sha256  # the same hash as the build (CRLF read as LF)
    except Exception as e:  # noqa: BLE001 - any failure here also stops the build; say what it is
        msg = f"does not load ({type(e).__name__}: {e})"
        return len(pins), [*problems, ("facts/common.py", msg, site / "facts" / "common.py")]

    tracked = git_tracked(root, [e["path"] for _, e in pins.values()])
    if tracked is None:
        problems.append(("pins", "cannot ask git which files are tracked (is this a git checkout?)", site / "pins"))
    for name, (chapter, e) in pins.items():
        path = root / e["path"]
        if not path.is_file():
            problem = "missing"
        elif tracked is not None and e["path"] not in tracked:
            problem = "not tracked by git; commit it (CI builds from a clean checkout)"
        elif sha256(path) != e["sha256"]:
            problem = (
                f"changed since it was pinned on {e.get('pinned', '?')}; if intended, re-pin it: "
                f"uv run python site/scripts/pin.py refresh {name}"
            )
        else:
            continue
        problems.append((f"pin {chapter}.{name}", f"{e['path']}: {problem}", site / "pins" / f"{chapter}.toml"))
    return len(pins), problems


# --- placeholders --------------------------------------------------------------------------------------------------


def find_placeholders(text: str) -> dict[str, list[int]]:
    """Line numbers of each kind of placeholder (a line with two CAPTION TODO is listed twice)."""
    found: dict[str, list[int]] = {k: [] for k in PLACEHOLDER_KINDS}
    for n, line in enumerate(text.splitlines(), 1):
        if PROSE_TODO.match(line):
            found["prose-todo"].append(n)
        for kind in ("CAPTION TODO", "ALT TODO"):
            found[kind].extend([n] * line.count(kind))
    return found


def describe_placeholders(found: dict[str, list[int]]) -> str:
    parts = []
    for kind, lines in found.items():
        if lines:
            where = f"line {lines[0]}" if len(lines) == 1 else "lines " + ", ".join(map(str, lines))
            parts.append(f"{len(lines)} {kind} ({where})")
    return ", ".join(parts)


# --- typed numbers -------------------------------------------------------------------------------------------------


def prose_lines(text: str) -> Iterator[tuple[int, str]]:
    """(line number, line) for every line of prose: not YAML front matter, code, div fences or placeholder divs."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() in ("---", "..."):
                start = j + 1
                break
    fence = ""  # the open code fence, e.g. "```"
    divs: list[bool] = []  # the open fenced divs, True for a prose-todo div
    in_comment = False
    for i in range(start, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if fence:
            if stripped.startswith(fence) and set(stripped) == {fence[0]}:
                fence = ""
            continue
        if m := CODE_FENCE.match(line):
            fence = m.group(1)
            continue
        if in_comment:
            if "-->" not in line:
                continue
            in_comment, line = False, line.split("-->", 1)[1]
        if m := DIV_FENCE.match(line):
            if m.group(1).strip():
                divs.append(bool(PROSE_TODO.match(line)))
            elif divs:
                divs.pop()
            continue
        if any(divs):
            continue
        line = re.sub(r"<!--.*?-->", " ", line)
        if "<!--" in line:
            line, in_comment = line.split("<!--", 1)[0], True
        yield i + 1, line


def typed_numbers(text: str, allow: list[str]) -> list[tuple[int, str, str]]:
    """(line number, token, the line) for every token with a digit in the prose that the allowlist does not cover."""
    raw = text.splitlines()
    found = []
    for n, line in prose_lines(text):
        for pattern, repl in NOT_PROSE:
            line = pattern.sub(repl, line)
        for m in NUMBER_TOKEN.finditer(line):
            token = m.group().strip(TOKEN_EDGES)
            if any(ch.isdigit() for ch in token) and not any(fnmatch.fnmatchcase(token, a) for a in allow):
                found.append((n, token, raw[n - 1].strip()))
    return found


def read_allowlist(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines = (ln.strip() for ln in path.read_text(encoding="utf-8").splitlines())
    return [ln for ln in lines if ln and not ln.startswith("#")]


# --- report --------------------------------------------------------------------------------------------------------


def _escape(s: str) -> str:
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _rel(path: Path, root: Path) -> str:
    """`path` relative to the repo, with forward slashes (as GitHub annotations want it), if it is inside it."""
    path, root = path.resolve(), root.resolve()
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def run(
    site: Path = SITE, root: Path = ROOT, *, release: bool | None = None, out: Callable[[str], None] = print
) -> int:
    """Run every check on `site` (a repo's site/ folder, `root` the repo) and return the exit status."""
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    failures = 0

    def report(level: str, where: str, msg: str, file: Path | None = None, line: int | None = None) -> None:
        nonlocal failures
        failures += level == "FAIL"
        if in_actions and file is not None and level in ("FAIL", "WARN"):
            kind = "error" if level == "FAIL" else "warning"
            loc = f"file={_rel(file, root)}" + (f",line={line}" if line else "")
            out(f"::{kind} {loc}::{_escape(f'{where}: {msg}')}")
        else:
            out(f"{level:<4} {where}: {msg}")

    switch, release_problems = read_release(site)
    release = switch if release is None else release
    mode = "release" if release else "draft"
    out(f"check: {_rel(site, root)}/ ({mode} mode)")
    for p in release_problems:
        report("FAIL", "release.toml", p.removeprefix("release.toml: "), site / "release.toml")

    # 1. pins
    n_pins, pin_problems = check_pins(site, root)
    for where, msg, pins_file in pin_problems:
        report("FAIL", where, msg, pins_file)
    if not pin_problems:
        out(f"ok   pins: {n_pins} pinned file(s), each present, tracked by git and matching its hash")

    # 2. placeholders
    qmds = sorted(site.glob("*.qmd"))
    n_placeholders = n_files = 0
    for q in qmds:
        found = find_placeholders(q.read_text(encoding="utf-8"))
        count = sum(len(v) for v in found.values())
        if count:
            n_placeholders += count
            n_files += 1
            first = min(n for v in found.values() for n in v)
            report("FAIL" if release else "TODO", q.name, describe_placeholders(found), q, first)

    # 3. typed numbers
    allow = read_allowlist(site / "scripts" / "number_allowlist.txt")
    n_numbers = 0
    for q in qmds:
        for n, token, context in typed_numbers(q.read_text(encoding="utf-8"), allow):
            n_numbers += 1
            short = context if len(context) <= 90 else context[:87] + "..."
            report("WARN", f"{q.name}:{n}", f"typed number {token!r} (use a fact, or allowlist a name): {short}", q, n)

    placeholders = f"{n_placeholders} placeholders in {n_files} of {len(qmds)} pages"
    placeholders += "" if release or not n_placeholders else " (allowed while drafting)"
    out(
        f"{'FAILED' if failures else 'OK'} ({mode}): {failures} failures; {n_pins} pins, "
        f"{len(pin_problems)} with problems; {placeholders}; {n_numbers} typed numbers to review (warnings only)"
    )
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--release", action="store_true", help="check as a release build, whatever release.toml says")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # a Windows console may not print every character of the prose
    return run(release=True if args.release else None)


if __name__ == "__main__":
    sys.exit(main())
