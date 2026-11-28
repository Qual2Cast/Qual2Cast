"""
Trait-line experiments (2026-11-28): does adding one 02_profiles trait line
(yes/no/unknown, data only) to the selector prompt change which comps it keeps,
beyond the selector's own run-to-run noise?

Runs compared, all Sonnet 5.5 through the Claude CLI on the 67 v3_final
targets' B3 lists:
  baseline   the pinned 2026-11-04a selector (progress.built_in("selector"))
  repeat1/2  2026-11-04a rerun unchanged (noise checks)
  28a-28k    2026-11-04a plus one trait line (cosine_then_llm.py PROMPT_TRAITS; 28c not run)

On the labelled pairs (cohorts.load("v3_final")), one row per run: kept pairs
by human grade 0/1/2, flips (labelled pairs whose keep differs) against the
baseline and both repeats, and the ledger's direct and peer precision/recall
target means with their 95% intervals (progress.py ledger rows of each run).

Noise band: the min-max of each metric across baseline, repeat1 and repeat2,
and the largest flip count among those three. A trait version is "outside
noise" only if its direct precision or direct recall lies outside the band's
min-max AND its flips vs the baseline exceed that largest flip count. For
every trait version, flips.csv lists the flipped pairs with both companies'
trait answers (as the prompt showed them) and whether the flip goes the way
the trait would push: dropped when the answers differ, kept when they match
(unknown on either side pushes neither way).

  uv run python v2/04_selection/scripts/trait_line_experiments.py
Writes outputs-local/v2/04_selection/trait_line_experiments_20261128/
(summary.csv, flips.csv, manifest.json); replaced files move to history/.
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import hashlib  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from itertools import combinations  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(v2.ROOT / "v2" / "09_analysis" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cosine_then_llm as jc  # noqa: E402
import progress  # noqa: E402

COHORT = "v3_final"
OUT = v2.out("04_selection") / "trait_line_experiments_20261128"
RUN = "b3_selector_candidates_{}_claude-cli_claude-sonnet-5-5"
NOISE = ["baseline", "repeat1", "repeat2"]
VERSIONS = ["2026-11-28a", "2026-11-28b", *[f"2026-11-28{v}" for v in "defghijk"]]
METRICS = [f"{o}_{m}_mean{s}" for o in ("direct", "peer") for m in ("precision", "recall") for s in ("", "_lo", "_hi")]
KEY = ["target_id", "comp_id"]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return Path(path).resolve().relative_to(v2.ROOT.resolve()).as_posix()


def runs() -> dict[str, dict]:
    """name -> {prompt_version, trait, keeps (DataFrame), file}."""
    root = v2.out("04_selection")
    b = progress.built_in("selector")
    out = {"baseline": {"prompt_version": b["prompt_version"], "trait": "", "keeps": b["keeps"],
                        "file": Path(b["run_file"])}}
    for r in ("repeat1", "repeat2"):
        f = root / (RUN.format("2026-11-04a") + f"_{r}") / "tables" / "keeps.csv"
        out[r] = {"prompt_version": "2026-11-04a", "trait": "", "keeps": progress.read_keeps(f), "file": f}
    for v in VERSIONS:
        f = root / RUN.format(v) / "tables" / "keeps.csv"
        if not f.exists():
            print(f"not run yet: {v}")
            continue
        out[v] = {"prompt_version": v, "trait": "+".join(jc.PROMPT_TRAITS[v]), "keeps": progress.read_keeps(f),
                  "file": f}
    return out


def ledger_row(ledger: pd.DataFrame, file: Path) -> pd.Series:
    """The latest ledger row of this run on the v3_final cohort, all targets; its sha256 must match the file."""
    rows = ledger[(ledger["run"] == rel(file)) & (ledger["cohort"] == COHORT) & (ledger["split"] == "all")
                  & (ledger["profile"] == "selector")]
    if rows.empty:
        raise SystemExit(f"no ledger row for {rel(file)} on {COHORT}: record it with progress.py record")
    row = rows.iloc[-1]
    if row["run_sha256"] != sha256(file):
        raise SystemExit(f"ledger row for {rel(file)} has another sha256 than the file now")
    return row


def keep_on(cohort: pd.DataFrame, keeps: pd.DataFrame) -> pd.Series:
    """Keep (bool) for every labelled pair; a pair missing from the run counts as not kept (as in progress.py)."""
    k = keeps.drop_duplicates(KEY).set_index(KEY)["keep"]
    return pd.Series(k.reindex(pd.MultiIndex.from_frame(cohort[KEY])).fillna(False).astype(bool).to_numpy(),
                     index=cohort.index)


def trait_answers() -> tuple[pd.DataFrame, dict]:
    t1, t2 = jc.load_traits(jc.CURRENT_TRAITS), jc.load_traits(jc.CURRENT_TRAITS_R2)
    files = {"traits": {"path": rel(jc.CURRENT_TRAITS), "sha256": sha256(jc.CURRENT_TRAITS)},
             "traits_r2": {"path": rel(jc.CURRENT_TRAITS_R2), "sha256": sha256(jc.CURRENT_TRAITS_R2)}}
    t = pd.concat([t1, t2], axis=1)
    t = t.apply(lambda c: c.str.strip().str.lower().where(c.str.strip().str.lower().isin(jc.TRAIT_ANSWERS), "unknown"))
    return t, files


def push(change: str, a: str, b: str) -> str:
    if "unknown" in (a, b):
        return "none (unknown)"
    if change == "dropped":
        return "with trait" if a != b else "against trait"
    return "with trait" if a == b else "against trait"


def move_to_history(path: Path) -> None:
    if path.exists():
        h = path.parent / "history"
        h.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), h / f"{path.stem}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}{path.suffix}")


def main() -> None:
    cohort, _, note = progress.load_cohort(COHORT)
    if len(cohort) != 311:
        raise SystemExit(f"{COHORT} has {len(cohort)} labelled pairs, expected 311")
    ledger = progress.read_ledger(progress.default_dir() / "ledger.csv")
    rs = runs()
    if not all(n in rs for n in NOISE):
        raise SystemExit("baseline, repeat1 and repeat2 are all needed")
    keep = {n: keep_on(cohort, r["keeps"]) for n, r in rs.items()}
    rows = []
    for n, r in rs.items():
        led = ledger_row(ledger, r["file"])
        row = {"run": n, "prompt_version": r["prompt_version"], "trait": r["trait"], "keeps": rel(r["file"]),
               "keeps_sha256": sha256(r["file"]), "ledger_entry_utc": led["entry_utc"],
               "labelled_pairs": len(cohort), "kept": int(keep[n].sum())}
        for g in (0, 1, 2):
            row[f"kept_grade{g}"] = int(keep[n][cohort["score"] == g].sum())
        for ref in NOISE:
            row[f"flips_vs_{ref}"] = int((keep[n] != keep[ref]).sum())
        row |= {m: float(led[m]) for m in METRICS}
        # the ledger metrics must be what progress.evaluate gives on these keeps now
        check = progress.evaluate(cohort, r["keeps"])
        for m in ("direct_precision_mean", "direct_recall_mean", "peer_precision_mean", "peer_recall_mean"):
            if not np.isclose(check[m], row[m], atol=1e-4):
                raise SystemExit(f"{n}: ledger {m} {row[m]} != evaluate {check[m]}")
        rows.append(row)
    s = pd.DataFrame(rows)
    noise = s[s["run"].isin(NOISE)]
    band = {m: [float(noise[m].min()), float(noise[m].max())] for m in METRICS}
    noise_flips = {f"{a}_vs_{b}": int((keep[a] != keep[b]).sum()) for a, b in combinations(NOISE, 2)}
    max_noise_flips = max(noise_flips.values())
    out_p = ~s["direct_precision_mean"].between(*band["direct_precision_mean"])
    out_r = ~s["direct_recall_mean"].between(*band["direct_recall_mean"])
    trait_run = ~s["run"].isin(NOISE)
    s["direct_precision_outside_band"] = out_p & trait_run
    s["direct_recall_outside_band"] = out_r & trait_run
    s["flips_exceed_noise"] = (s["flips_vs_baseline"] > max_noise_flips) & trait_run
    s["outside_noise"] = (out_p | out_r) & s["flips_exceed_noise"]

    traits, trait_files = trait_answers()
    names = pd.read_csv(v2.path(jc.CUR["universe"]["universe"]), dtype=str).set_index("IQ_COMPANY_ID")
    flips = []
    for n in s.loc[trait_run, "run"]:
        diff = keep[n] != keep["baseline"]
        for i in cohort.index[diff]:
            t, c = cohort.at[i, "target_id"], cohort.at[i, "comp_id"]
            change = "dropped" if keep["baseline"][i] else "kept"
            for name in jc.PROMPT_TRAITS[n]:
                a = traits.at[t, name] if t in traits.index else "unknown"
                b = traits.at[c, name] if c in traits.index else "unknown"
                flips.append({"run": n, "flagged": bool(s.loc[s["run"] == n, "outside_noise"].iloc[0]),
                              "target_id": t, "target": names["target_company_name"].get(t, ""),
                              "comp_id": c, "comp": names["target_company_name"].get(c, ""),
                              "grade": int(cohort.at[i, "score"]), "baseline_keep": int(keep["baseline"][i]),
                              "run_keep": int(keep[n][i]), "change": change,
                              "also_flips_in_repeat1": bool(keep["repeat1"][i] != keep["baseline"][i]),
                              "also_flips_in_repeat2": bool(keep["repeat2"][i] != keep["baseline"][i]),
                              "trait": name, "target_answer": a, "comp_answer": b, "push": push(change, a, b)})
    f = pd.DataFrame(flips)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, table in (("summary.csv", s), ("flips.csv", f)):
        move_to_history(OUT / name)
        table.to_csv(OUT / name, index=False, float_format="%.4f")
    manifest = {
        "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "script": rel(Path(__file__)), "script_sha256": sha256(Path(__file__)),
        "cohort": COHORT, "cohort_note": note, "labelled_pairs": len(cohort),
        "ledger": {"path": rel(progress.default_dir() / "ledger.csv")},
        "runs": {n: {"keeps": rel(r["file"]), "sha256": sha256(r["file"]), "prompt_version": r["prompt_version"]}
                 for n, r in rs.items()},
        "trait_tables": trait_files,
        "noise_band": {"runs": NOISE, "metrics_min_max": band, "flips": noise_flips, "max_flips": max_noise_flips},
        "rule": "outside noise = direct precision or direct recall outside the noise band's min-max AND flips vs "
                "baseline > the largest flips among baseline/repeat1/repeat2",
        "flagged": s.loc[s["outside_noise"], "run"].tolist(),
        "outputs": {"summary.csv": sha256(OUT / "summary.csv"), "flips.csv": sha256(OUT / "flips.csv")},
    }
    move_to_history(OUT / "manifest.json")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(s[["run", "kept", "kept_grade0", "kept_grade1", "kept_grade2", "flips_vs_baseline", "flips_vs_repeat1",
                 "flips_vs_repeat2", "direct_precision_mean", "direct_recall_mean", "peer_precision_mean",
                 "peer_recall_mean", "outside_noise"]].to_string(index=False))
    print("noise flips", noise_flips, "flagged", manifest["flagged"])


if __name__ == "__main__":
    main()
