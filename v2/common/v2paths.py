"""Compatibility name for v2's paths module (v2/common/paths.py).

Scripts written while v2 was layered on v1a (the morning of 2026-11-24: traits, rubric v3, trait X-learner) start
with `import v2paths as v2; v2.setup()`. Since v2 became a full copy of v1a the same day, this module only
re-exports v2's own paths module, so those scripts and `import paths as v2` behave the same. Nothing from v1a is
put on the import path.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import paths as _paths  # noqa: E402  (v2/common/paths.py)
from paths import (COMPONENTS, OUTPUTS, ROOT, V1_OUTPUTS, V1A, V1A_OUTPUTS, V2, current, latest, out,  # noqa: E402,F401
                   path, src, src_roots)


def setup() -> None:
    _paths.setup()
