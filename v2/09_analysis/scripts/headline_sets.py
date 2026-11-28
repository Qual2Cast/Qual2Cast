"""Which rubric v3 pairs count as "agreed"? Score the saved baseline both ways, side by side.

The north star (v2/EVAL_METHOD.md) is overlap with labels two reviewers agree on. "Agree" can mean two things:

  all_four      both reviewers gave the same answer to all four questions (rubric_v3.py consensus, cohort
                v3_agreed); one 0/1/2 score per pair, used for any peer and direct peer alike.
  same_outcome  both reviewers reached the same outcome, whatever their answers to the single questions: the direct
                peer metrics use the pairs where both say direct (score 2) or both say not direct; the any-peer
                metrics use the pairs where both say peer (score >= 1) or both say not a peer. The two outcomes
                can rest on different pairs.

For context the same profiles are scored on each reviewer alone (matthew_v3_311, barbara_v3_311) and on the
current ledger baseline (matthew_v2_262). Profiles and metrics are progress.py's (built-in profiles, target means
with a 1,000-draw target bootstrap, pooled values, kappa). Every set is cut to the pairs that all five profiles'
saved runs cover, so the profiles are compared on the same pairs (the agent run does not cover the 30 extra B3
pairs of the v3 sheet; progress.py would count them as not kept). Reads saved runs only: no model calls, and
nothing is appended to the ledger.

  uv run python v2/09_analysis/scripts/headline_sets.py            # writes outputs-local/v2/09_analysis/headline_sets/<UTC>/
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import progress as pr

KEY = pr.KEY
OUTCOMES = {"peer": 1, "direct": 2}
METRICS = ["positives", "precision_mean", "precision_mean_lo", "precision_mean_hi", "recall_mean", "recall_mean_lo",
           "recall_mean_hi", "precision_pooled", "recall_pooled", "kappa"]


def outcome_sets(m: pd.DataFrame, b: pd.DataFrame) -> dict[str, dict[str, pd.DataFrame]]:
    """{set name: {outcome: cohort (target_id, comp_id, score)}} from two reviewers' 0/1/2 grades on the same pairs.
    all_four comes from the consensus cohort; the others from the two grades."""
    import cohorts
    g = m[[*KEY, "grade"]].merge(b[[*KEY, "grade"]], on=KEY, suffixes=("_m", "_b"), validate="one_to_one")
    g = g.dropna(subset=["grade_m", "grade_b"])
    sets: dict[str, dict[str, pd.DataFrame]] = {}
    if "final" in v2.current()["rubric_v3"]:   # the headline: same outcome, splits tie-broken by the judge
        f = cohorts.load("v3_final")
        f = f[f["grade"].notna()]
        sets["v3_final"] = {o: f[KEY].assign(score=f["grade"].astype(int)) for o in OUTCOMES}
    a = cohorts.load("v3_agreed")
    a = a[a["grade"].notna()]
    agreed = a[KEY].assign(score=a["grade"].astype(int))
    sets["all_four"] = {o: agreed for o in OUTCOMES}
    same = {}
    for o, k in OUTCOMES.items():
        hit_m, hit_b = g["grade_m"].ge(k), g["grade_b"].ge(k)
        d = g[hit_m == hit_b]
        same[o] = d[KEY].assign(score=np.where(hit_m[hit_m == hit_b], k, 0))   # k = outcome yes, 0 = no
    sets["same_outcome"] = same
    for name, d in (("matthew_v3_alone", m), ("barbara_v3_alone", b)):
        d = d[d["grade"].notna()]
        c = d[KEY].assign(score=d["grade"].astype(int))
        sets[name] = {o: c for o in OUTCOMES}
    old = cohorts.load("matthew_v2_262")
    old = old[old["grade"].notna()]
    c = old[KEY].assign(score=old["grade"].astype(int))
    sets["matthew_v2_baseline"] = {o: c for o in OUTCOMES}
    return sets


def common_pairs(keeps: list[pd.DataFrame]) -> pd.MultiIndex:
    """The (target_id, comp_id) pairs present in every keeps table."""
    idx = pd.MultiIndex.from_frame(keeps[0][KEY].drop_duplicates())
    for k in keeps[1:]:
        idx = idx.intersection(pd.MultiIndex.from_frame(k[KEY].drop_duplicates()))
    return idx


def score_sets(sets: dict, profiles: list[str], boot: int = pr.BOOT) -> tuple[pd.DataFrame, dict]:
    """One row per (set, outcome, profile): pairs, targets, kept and the outcome's metrics, on the pairs every
    profile covers. Also {set: {outcome: pairs dropped as not covered}}."""
    cur = v2.current()
    specs = {p: pr.built_in(p, cur) for p in profiles}
    common = common_pairs([s["keeps"] for s in specs.values()])
    rows, dropped = [], {}
    for set_name, by_outcome in sets.items():
        for outcome, cohort in by_outcome.items():
            inside = pd.MultiIndex.from_frame(cohort[KEY]).isin(common)
            dropped.setdefault(set_name, {})[outcome] = int((~inside).sum())
            cohort = cohort[inside]
            for p, spec in specs.items():
                r = pr.evaluate(cohort, spec["keeps"], boot=boot)
                rows.append({"set": set_name, "outcome": outcome, "profile": p,
                             "pairs": r["labelled_pairs"], "targets": r["targets"], "kept": r["kept"],
                             "keeps_cover_pairs": r["keeps_cover_pairs"],
                             **{m: r[f"{outcome}_{m}"] for m in METRICS}})
    return pd.DataFrame(rows), dropped


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--boot", type=int, default=pr.BOOT)
    args = ap.parse_args(argv)
    import cohorts
    m, b = cohorts.load("matthew_v3_311"), cohorts.load("barbara_v3_311")
    sets = outcome_sets(m, b)
    table, dropped = score_sets(sets, pr.BUILT_IN, args.boot)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or v2.out("09_analysis") / "headline_sets" / stamp
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "headline_sets.csv", index=False)
    cur = v2.current()
    scores_dir = v2.path(cur["rubric_v3"]["scores"])
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
    manifest = {
        "created_at": stamp, "script": "v2/09_analysis/scripts/headline_sets.py", "script_sha256": sha(__file__),
        "rubric_v3_scores": cur["rubric_v3"]["scores"],
        "rubric_v3_files_sha256": {f: sha(scores_dir / f) for f in ("scores.csv", "consensus.csv")},
        "rubric_v3_final": cur["rubric_v3"].get("final"),
        "rubric_v3_final_sha256": sha(v2.path(cur["rubric_v3"]["final"]) / "final.csv") if "final" in cur["rubric_v3"] else None,
        "profiles": {p: pr.built_in(p, cur)["run"] for p in pr.BUILT_IN},
        "boot": args.boot, "seed": pr.SEED,
        "sets_before_common_cut": {s: {o: {"pairs": len(c), "targets": int(c["target_id"].nunique()),
                                           "positives": int(c["score"].ge(OUTCOMES[o]).sum())}
                                       for o, c in d.items()} for s, d in sets.items()},
        "dropped_not_covered_by_every_profile": dropped,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    show = table.copy()
    for c in METRICS[1:]:
        show[c] = show[c].round(3)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
        print(show.to_string(index=False))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
