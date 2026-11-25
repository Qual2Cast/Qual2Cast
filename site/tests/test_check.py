"""site/scripts/check.py: release mode, placeholders, pins and the typed-number lint, on sites built in temporary
folders (never the real site/).

    uv run pytest site/tests -q
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("site_check", SITE / "scripts" / "check.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

PAGE_WITH_TODO = """# Data {#sec-data}

::: {.prose-todo}
**To write** · draft owner: someone. Scope: the 560 companies.
:::
"""

PAGE_WRITTEN = """# Data {#sec-data}

We keep `{python} f.n_universe` companies, as @sec-data says.
"""


@pytest.fixture(autouse=True)
def _plain_output(monkeypatch):
    """Inside GitHub Actions check.py writes problems as annotations (::error ...); these tests read its plain lines."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


def test_inside_actions_problems_become_annotations(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    site = make_site(tmp_path, release=True, pages={"data.qmd": PAGE_WITH_TODO})
    status, lines = run(site, tmp_path)
    assert status == 1
    assert any(ln.startswith("::error file=site/data.qmd,line=3::data.qmd: 1 ") for ln in lines)


def make_site(root: Path, *, release: bool, pages: dict[str, str], allowlist: str | None = None) -> Path:
    site = root / "site"
    site.mkdir(parents=True)
    (site / "release.toml").write_text(f'as_of = "2026-11-24"\nrelease = {str(release).lower()}\n', encoding="utf-8")
    for name, text in pages.items():
        (site / name).write_text(text, encoding="utf-8")
    if allowlist is not None:
        (site / "scripts").mkdir()
        (site / "scripts" / "number_allowlist.txt").write_text(allowlist, encoding="utf-8")
    return site


def run(site: Path, root: Path, **kw) -> tuple[int, list[str]]:
    lines: list[str] = []
    return check.run(site, root, out=lines.append, **kw), lines


@pytest.mark.parametrize(
    "page",
    [
        PAGE_WITH_TODO,
        PAGE_WRITTEN + '\n![CAPTION TODO](fig.png){fig-alt="described"}\n',
        PAGE_WRITTEN + '\n![A caption](fig.png){fig-alt="ALT TODO"}\n',
    ],
    ids=["prose-todo", "CAPTION TODO", "ALT TODO"],
)
def test_release_mode_fails_on_a_leftover_placeholder(tmp_path, page):
    site = make_site(tmp_path, release=True, pages={"data.qmd": page})
    status, lines = run(site, tmp_path)
    assert status == 1
    assert any(ln.startswith("FAIL data.qmd: 1 ") for ln in lines)
    assert lines[-1].startswith("FAILED (release)")


def test_draft_mode_passes_and_lists_the_placeholders(tmp_path):
    site = make_site(tmp_path, release=False, pages={"data.qmd": PAGE_WITH_TODO, "index.qmd": PAGE_WRITTEN})
    status, lines = run(site, tmp_path)
    assert status == 0
    assert "TODO data.qmd: 1 prose-todo (line 3)" in lines
    assert lines[-1].startswith("OK (draft)") and "1 placeholders in 1 of 2 pages" in lines[-1]


def test_release_flag_overrides_a_draft_release_toml(tmp_path):
    site = make_site(tmp_path, release=False, pages={"data.qmd": PAGE_WITH_TODO})
    assert run(site, tmp_path, release=True)[0] == 1


def test_release_mode_passes_once_everything_is_written(tmp_path):
    site = make_site(tmp_path, release=True, pages={"data.qmd": PAGE_WRITTEN})
    status, lines = run(site, tmp_path)
    assert status == 0 and lines[-1].startswith("OK (release)")


def test_number_lint_finds_a_typed_number_and_respects_the_allowlist(tmp_path):
    page = "# Results\n\nWe keep 533 companies; rubric v3 scores traits E1-E10 against B3.\n"
    assert [t for _, t, _ in check.typed_numbers(page, [])] == ["533", "v3", "E1-E10", "B3"]
    assert [t for _, t, _ in check.typed_numbers(page, ["v[0-9]*", "E[0-9]*", "B3"])] == ["533"]

    site = make_site(tmp_path, release=True, pages={"results.qmd": page}, allowlist="# names\nv[0-9]*\nE[0-9]*\nB3\n")
    status, lines = run(site, tmp_path)
    assert status == 0  # a warning, never a failure
    warnings = [ln for ln in lines if ln.startswith("WARN")]
    assert len(warnings) == 1 and "results.qmd:3: typed number '533'" in warnings[0]


def test_number_lint_skips_code_facts_attributes_references_and_placeholders():
    page = """---
title: "Results 2026"
---

# Results {#sec-results}

```{python}
#| label: fig-1
x = 533
```

Printed from a fact: `{python} f.n_universe`, see @sec-data and @fig-1, [the notes](v2/README.md).

::: {.callout-note #note-1 width=50%}
Nothing typed here.
:::

::: {.prose-todo}
Scope: Aziz's 560 companies.
::: {.inner}
nested 99
:::
:::

1. a list item
"""
    assert check.typed_numbers(page, []) == []


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_pins_must_exist_be_tracked_and_match_even_in_draft_mode(tmp_path):
    from facts.common import sha256

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    data = tmp_path / "out" / "data.csv"
    data.parent.mkdir()
    data.write_bytes(b"a,b\n1,2\n")
    subprocess.run(["git", "add", "out/data.csv"], cwd=tmp_path, check=True)
    site = make_site(tmp_path, release=False, pages={"data.qmd": PAGE_WRITTEN})
    (site / "pins").mkdir()
    pin = f'data = {{ path = "out/data.csv", sha256 = "{sha256(data)}", pinned = "2026-11-24" }}\n'
    (site / "pins" / "ch2.toml").write_text(pin, encoding="utf-8")
    assert run(site, tmp_path)[0] == 0

    data.write_bytes(b"a,b\n1,3\n")
    status, lines = run(site, tmp_path)
    assert status == 1 and any(ln.startswith("FAIL pin ch2.data: out/data.csv: changed since") for ln in lines)

    data.write_bytes(b"a,b\n1,2\n")
    untracked = tmp_path / "out" / "new.csv"
    untracked.write_bytes(b"x\n")
    pin += f'new = {{ path = "out/new.csv", sha256 = "{sha256(untracked)}", pinned = "2026-11-24" }}\n'
    (site / "pins" / "ch2.toml").write_text(pin, encoding="utf-8")
    status, lines = run(site, tmp_path)
    assert status == 1 and any(ln.startswith("FAIL pin ch2.new: out/new.csv: not tracked by git") for ln in lines)
