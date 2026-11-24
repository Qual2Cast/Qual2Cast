"""Facts for Data (data.qmd).

Pattern for every chapter module: read only pinned files (pinned("<pin name>")), compute the number with code, and
register it with fact(name, value, text, source=<pin name(s), joined with "+">). The chapter's text then prints it
inline with `{python} f.<name>`.
"""

from __future__ import annotations

import pandas as pd

from facts.common import fact, pinned

_universe = pd.read_csv(pinned("universe"), dtype=str)

n_universe = fact("n_universe", len(_universe), f"{len(_universe):,}", source="universe")
