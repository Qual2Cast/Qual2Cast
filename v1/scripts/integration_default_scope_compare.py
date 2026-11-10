"""Compare dated and source-reviewed Sonnet B3 on identical targets."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs-local/v1/integration"
OLD = BASE / "gpt_scope_alignment/sensitivity/sonnet_dated"
NEW = BASE / "source_reviewed_default/candidates"
OUT = BASE / "source_reviewed_default/scope_comparison.json"


def main() -> None:
    old_peers = pd.read_csv(OLD / "selected_peers.csv", dtype=str)
    new_peers = pd.read_csv(NEW / "selected_peers.csv", dtype=str)
    old_errors = pd.read_csv(OLD / "target_errors.csv", index_col=0).squeeze("columns")
    new_errors = pd.read_csv(NEW / "target_errors.csv", index_col=0).squeeze("columns")
    if (len(old_errors) != 160 or len(new_errors) != 160 or
            set(old_errors.index) != set(new_errors.index)):
        raise ValueError("The two B3 runs must use the same 160 targets")
    before = old_peers.groupby("target")["comp"].agg(lambda x: tuple(sorted(x)))
    after = new_peers.groupby("target")["comp"].agg(lambda x: tuple(sorted(x)))
    if set(before.index) != set(after.index) or set(after.index) != set(new_errors.index):
        raise ValueError("B3 peer-list identities differ")
    old = old_errors.reindex(sorted(after.index)).astype(float).to_numpy()
    new = new_errors.reindex(sorted(after.index)).astype(float).to_numpy()
    if not np.isfinite(old).all() or not np.isfinite(new).all():
        raise ValueError("Missing B3 estimates")
    sample = np.random.default_rng(4511).integers(0, len(old), (2000, len(old)))
    gain = np.median(old[sample], axis=1) - np.median(new[sample], axis=1)
    delta = old - new
    result = {"old": "dated Sonnet B3", "new": "source-reviewed Sonnet B3",
              "targets": len(old), "changed_peer_lists": int(before.ne(after).sum()),
              "old_median_ape": float(np.median(old)),
              "new_median_ape": float(np.median(new)),
              "median_ape_gain": float(np.median(old) - np.median(new)),
              "gain_ci_low": float(np.quantile(gain, .025)),
              "gain_ci_high": float(np.quantile(gain, .975)),
              "targets_better": int((delta > 1e-9).sum()),
              "targets_worse": int((delta < -1e-9).sum()),
              "targets_equal": int((np.abs(delta) <= 1e-9).sum()),
              "comparison": "same Sonnet source, B3 rule, split and financials; only reviewed facet text changes"}
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
