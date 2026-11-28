"""Round 4 (final reviewer round, Matthew and Barbara): a blind rubric v3 sheet under the 2026-11-27 rulings.

Decided by Michael 2026-11-28: one last sheet of about 120-150 pairs, made of
  (a) profile pairs without a human label: comps the comp profile would show (tier 1: the selector's keeps; tier 2:
      the EXPERIMENTAL fill up to k comps, `v2/09_analysis/scripts/tier2_fill.py`) that `v3_final` does not cover;
  (c) a check of the LLM judge's tie-breaks: a seeded sample of `v3_final` pairs whose direct or peer outcome was
      decided by GPT-Terra (2 of 3), stratified by which outcome split.
(b) of the plan (the rest of the unlabelled B3-list pairs) is covered by (a) for the targets whose profiles use them.

The sheet is blind like the first: no method, rank, similarity, source, multiple or earlier answer; pair ids P001...;
targets in a random order, a target's comps together. Which part a pair belongs to is in `round4_key.csv`, beside
the sheet, never in it. The key above the header uses the 11-27 wording (rubric_v3.KEY_ROWS_1127). Written once.

  uv run python v2/06_labels/scripts/round4_sheet.py --tier2-run <tier2_fill run dir> --rule <rule> --k 3 [--tiebreak-n 30]
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import rubric_v3 as r3  # noqa: E402

KEY = ["target_id", "comp_id"]
REVIEWERS = ["matthew", "barbara"]
SEED = 2026
TIEBREAK_N = 30


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tiebreak_sample(final: pd.DataFrame, n: int = TIEBREAK_N, seed: int = SEED) -> pd.DataFrame:
    """n non-anchor pairs whose direct or peer outcome came from the judge, stratified by which outcome split
    (direct only, peer only, both), each stratum in proportion to its size (largest remainder), seeded."""
    f = final[~final["is_anchor"].astype(bool)].copy()
    d, p = f["direct_source"].str.startswith("tiebreak"), f["peer_source"].str.startswith("tiebreak")
    f["stratum"] = np.select([d & p, d, p], ["both", "direct_only", "peer_only"], default="")
    f = f[f["stratum"] != ""]
    sizes = f["stratum"].value_counts().sort_index()
    n = min(n, len(f))
    raw = sizes / sizes.sum() * n
    take = np.floor(raw).astype(int)
    for s in (raw - take).sort_values(ascending=False).index[: n - int(take.sum())]:
        take[s] += 1
    rng = np.random.default_rng(seed)
    parts = [g.iloc[np.sort(rng.choice(len(g), size=int(take[s]), replace=False))] for s, g in f.groupby("stratum")]
    out = pd.concat(parts)[[*KEY, "stratum"]].assign(part="c_tiebreak_check")
    return out.reset_index(drop=True)


def profile_pairs(selector_keeps: pd.DataFrame, picks: pd.DataFrame, labelled: set, targets: set) -> pd.DataFrame:
    """Tier-1 keeps and tier-2 picks for the given targets that have no human label (not in `labelled`)."""
    t1 = selector_keeps[selector_keeps["keep"].astype(bool) & selector_keeps["target_id"].isin(targets)][KEY]
    t1 = t1.assign(part="a_tier1_unlabelled")
    t2 = picks[picks["target_id"].isin(targets)][KEY].assign(part="a_tier2_unlabelled")
    both = pd.concat([t1, t2]).drop_duplicates(KEY)
    keep = [k not in labelled for k in zip(both["target_id"], both["comp_id"])]
    return both[keep].reset_index(drop=True)


def tier2_picks(run: Path, rule: str, k: int, tier1_source: str = "baseline", pool: str | None = None) -> pd.DataFrame:
    """The tier-2 picks of one rule at one k from a tier2_fill run's picks.csv, for one tier-1 source (the pinned
    selector run: "baseline") and one candidate pool (default: the widest in the file)."""
    p = pd.read_csv(run / "picks.csv", dtype={"target_id": str, "comp_id": str}, encoding="utf-8-sig")
    p = p[p["rule"] == rule]
    if "k" in p.columns:
        p = p[pd.to_numeric(p["k"]) == k]
    if "tier1_source" in p.columns:
        p = p[p["tier1_source"] == tier1_source]
    if "pool" in p.columns:
        pools = sorted(p["pool"].unique(), key=len)
        p = p[p["pool"] == (pool or (pools[-1] if pools else None))]
    for c in ("tier1", "tier1_source", "tier1_run", "pool"):
        if c in p.columns and p[c].nunique() > 1:
            raise SystemExit(f"picks.csv has several {c} values; choose one before building the sheet")
    if p.empty:
        raise SystemExit(f"no picks for rule {rule!r} at k={k} in {run}")
    return p[KEY].drop_duplicates()


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tier2-run", type=Path, required=True, help="a tier2_fill run dir (picks.csv)")
    ap.add_argument("--rule", required=True, help="tier-2 rule whose picks go on the sheet")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--tier1-source", default="baseline", help="tier-1 run in picks.csv (baseline = the pinned selector)")
    ap.add_argument("--pool", help="candidate pool in picks.csv (default: the widest)")
    ap.add_argument("--tiebreak-n", type=int, default=TIEBREAK_N)
    ap.add_argument("--out", type=Path, default=v2.out("06_labels") / "rubric_v3" / "round4")
    ap.add_argument("--dry-run", action="store_true", help="print the counts only")
    args = ap.parse_args(argv)

    import cohorts
    import progress as pr
    from recall_audit import describe

    cur = v2.current()
    final_path = v2.path(cur["rubric_v3"]["final"]) / "final.csv"
    final = pd.read_csv(final_path, dtype={"target_id": str, "comp_id": str}, encoding="utf-8-sig")
    sheet_v3 = r3._read(v2.path(cur["rubric_v3"]["sheet"]))
    labelled = set(zip(sheet_v3["target_id"].astype(str), sheet_v3["comp_id"].astype(str)))   # all 323, anchors too
    targets = set(cohorts.load("v3_final")["target_id"])
    keeps = pr.built_in("selector", cur)["keeps"]
    picks = tier2_picks(args.tier2_run, args.rule, args.k, args.tier1_source, args.pool)

    a = profile_pairs(keeps, picks, labelled, targets)
    c = tiebreak_sample(final, args.tiebreak_n)
    pool = pd.concat([a, c]).drop_duplicates(KEY).reset_index(drop=True)
    counts = pool["part"].value_counts().to_dict()
    print(f"{len(pool)} pairs, {pool['target_id'].nunique()} targets: {counts}; tie-break strata "
          f"{c['stratum'].value_counts().to_dict()}")
    if args.dry_run:
        return args.out

    dest, xlsx = args.out / "round4_sheet.csv", args.out / "round4_sheet.xlsx"
    if dest.exists() or xlsx.exists():
        raise SystemExit(f"{dest} exists: the sheet is written once (move it to history/ first)")
    desc = describe(pool[KEY])
    full = pool.merge(desc, on=KEY, how="left", validate="one_to_one")
    sheet = r3.build_sheet(full, reviewers=REVIEWERS, seed=SEED, anchors={})   # no anchors this round
    args.out.mkdir(parents=True, exist_ok=True)
    r3.save_sheet(sheet, dest, xlsx, key_rows=r3.KEY_ROWS_1127)
    key = sheet[["pair", *KEY]].merge(pool, on=KEY, how="left")
    key.to_csv(args.out / "round4_key.csv", index=False, encoding="utf-8-sig")
    info = {"created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "seed": SEED,
            "reviewers": REVIEWERS, "pairs": len(sheet), "targets": int(sheet["target_id"].nunique()),
            "parts": counts, "tiebreak_strata": c["stratum"].value_counts().to_dict(),
            "tier2": {"run": str(args.tier2_run.as_posix()), "rule": args.rule, "k": args.k,
                      "tier1_source": args.tier1_source, "pool": args.pool or "widest",
                      "picks_sha256": sha(args.tier2_run / "picks.csv")},
            "inputs_sha256": {"final.csv": sha(final_path), "rubric_v3_sheet.csv": sha(v2.path(cur["rubric_v3"]["sheet"]))},
            "key_wording": "rubric_v3.KEY_ROWS_1127 (2026-11-27 rulings)",
            "sheet_sha256": sha(dest), "xlsx_sha256": sha(xlsx),
            "note": "final reviewer round; blind; part per pair only in round4_key.csv. Tier-2 picks are EXPERIMENTAL."}
    (args.out / "manifest.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"wrote {dest} and {xlsx.name}")
    return dest


if __name__ == "__main__":
    main()
