"""Compare two fills of the same companies (fill_traits.py run twice) and apply the keep rule (decided 2026-11-24):
a question whose yes/no answer flips between the runs for more than 20% of companies, or that is "unknown" for more
than 20% of companies in either run, is reworded or dropped before the full fill.

  uv run python v2/02_profiles/scripts/trait_stability.py \
      outputs-local/v2/02_profiles/traits_test/run1 outputs-local/v2/02_profiles/traits_test/run2

Writes <run1>/../stability/stability.csv (one row per question) and flips.csv (every flipped answer, with both
reasons); an earlier result moves to stability/history/.
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import v2paths as v2  # noqa: E402
v2.setup()

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import traits as tr

MAX_FLIP = 0.20
MAX_UNKNOWN = 0.20


def load(run: Path) -> pd.DataFrame:
    t = pd.read_csv(run / "tables" / "traits.csv", dtype=str).set_index("IQ_COMPANY_ID")
    return t[t["llm_status"] == "ok"]


def compare(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    both = a.index.intersection(b.index)
    a, b = a.loc[both], b.loc[both]
    rows, flips = [], []
    present = [q for q in [*tr.QUESTIONS, *tr.ROUND_2] if q.name in a.columns and q.name in b.columns]
    for q in present:
        x, y = a[q.name], b[q.name]
        answered = x.isin(["yes", "no"]) & y.isin(["yes", "no"])
        flipped = answered & (x != y)
        n_ans = int(answered.sum())
        flip_rate = flipped.sum() / n_ans if n_ans else float("nan")
        unk = max((x == "unknown").mean(), (y == "unknown").mean())
        verdict = "keep"
        if n_ans and flip_rate > MAX_FLIP:
            verdict = "reword or drop (unstable)"
        if unk > MAX_UNKNOWN:
            verdict = "reword or drop (too many unknown)"
        rows.append({"id": q.id, "question": q.name, "kind": q.kind, "companies": len(both),
                     "answered_both": n_ans, "flips": int(flipped.sum()), "flip_rate": round(flip_rate, 3),
                     "unknown_rate_max": round(unk, 3), "yes_rate_run1": round((x == "yes").mean(), 3),
                     "yes_rate_run2": round((y == "yes").mean(), 3), "verdict": verdict})
        for iq in flipped[flipped].index:
            flips.append({"IQ_COMPANY_ID": iq, "ticker": a.at[iq, "ticker"], "question": q.name,
                          "run1": x[iq], "run2": y[iq], "reason_run1": a.at[iq, f"{q.name}_reason"],
                          "reason_run2": b.at[iq, f"{q.name}_reason"]})
    return pd.DataFrame(rows), pd.DataFrame(flips)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("run1", type=Path)
    p.add_argument("run2", type=Path)
    args = p.parse_args()
    summary, flips = compare(load(args.run1), load(args.run2))
    dest = args.run1.resolve().parent / "stability"
    if dest.exists() and any(dest.glob("*.csv")):
        hist = dest / "history" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        hist.mkdir(parents=True)
        for f in dest.glob("*.csv"):
            shutil.move(str(f), hist / f.name)
    dest.mkdir(parents=True, exist_ok=True)
    summary.to_csv(dest / "stability.csv", index=False)
    flips.to_csv(dest / "flips.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(summary.to_string(index=False))
    print(f"\n{len(flips)} flipped answers -> {dest / 'flips.csv'}")


if __name__ == "__main__":
    main()
