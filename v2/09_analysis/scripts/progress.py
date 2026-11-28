"""Improvement ledger: does each pipeline version's comp profile get closer to the human labels?

The north star (v2/EVAL_METHOD.md, section 1) is the overlap between the comps a pipeline version keeps and the
comps reviewers call peers. This script measures it the same way every time and appends one row per pipeline
version to an append-only ledger, so the team (and the website) can show improvement version by version.

A **profile** is the set of labelled pairs a pipeline version keeps for each target. Built-in profiles, read from
the saved runs that v2/current.toml names:

  b3_all      every B3 pair (the retrieval list, nothing filtered)
  b3_top7     B3 rank <= 7
  selector    04_selection: the selector's keeps (score = 1)
  agent_ge1   05_agent_grading: agent grade >= 1 (any-peer filter)
  agent_2     05_agent_grading: agent grade 2 (direct-peer filter)

Any other run: `--keeps <csv>` with target_id, comp_id, keep (1/0, yes/no, true/false); a labelled pair missing
from the file counts as not kept (the file's coverage of the labelled pairs is reported).

Metrics, on labelled pairs only (an unlabelled pair is never a non-peer), for **any peer** (score >= 1) and
**direct peer** (score 2):
  precision   share of kept pairs that are peers: mean over targets with at least one kept pair, and pooled
  recall      share of peers that are kept: mean over targets with at least one peer, and pooled
  kappa       Cohen's kappa of keep vs peer (pooled)
  coverage    share of targets with at least one kept pair
95% intervals for the target means come from a target bootstrap (1,000 draws).

Label cohorts: `matthew_v2_262` (Matthew, rubric v2, one reviewer) now; a rubric v3 consensus file
(06_labels/scripts/rubric_v3.py consensus) with `--cohort-file` when the v3 labels arrive. Barbara's old dev_293
labels are not used as an outcome.

  uv run python v2/09_analysis/scripts/progress.py score                       # print, write nothing
  uv run python v2/09_analysis/scripts/progress.py record --who "Michael (baseline)" --change "baseline ..."
  uv run python v2/09_analysis/scripts/progress.py record --keeps my_run_keeps.csv --profile selector \\
      --component "04 selection" --prompt-version 2026-11-25a --model claude-sonnet-5-5 \\
      --who Kethan --change "selector prompt weighs services, customers, end markets" --targets checking_half.txt
  uv run python v2/09_analysis/scripts/progress.py show                        # latest.csv + progress.png

Ledger: outputs-local/v2/09_analysis/progress/ledger.csv. Rows are only ever appended.
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import argparse
import csv
import hashlib
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

KEY = ["target_id", "comp_id"]
BUILT_IN = ["b3_all", "b3_top7", "selector", "agent_ge1", "agent_2"]
COMPONENTS = ["03 retrieval", "04 selection", "05 agent grading"]
BOOT = 1000
SEED = 2026
COHORT_NOTES = {
    "matthew_v2_262": "Matthew, rubric v2, single reviewer, loose customers wording",
    "v3_final": "rubric v3, Matthew + Barbara; split outcomes tie-broken 2 of 3 by GPT-Terra (rubric_v3.py final)",
}
OUTCOMES = {"peer": 1, "direct": 2}       # outcome -> minimum score
LEDGER_COLUMNS = [
    "entry_utc", "who", "component", "profile", "change", "prompt_version", "model", "run", "run_sha256",
    "cohort", "cohort_note", "split", "split_sha256", "labelled_pairs", "targets", "kept", "coverage",
    "keeps_cover_pairs",
    *[f"{o}_{m}" for o in OUTCOMES for m in (
        "positives", "precision_mean", "precision_mean_lo", "precision_mean_hi", "recall_mean", "recall_mean_lo",
        "recall_mean_hi", "precision_pooled", "recall_pooled", "kappa")],
    "script_sha256",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def default_dir() -> Path:
    return v2.out("09_analysis") / "progress"


# ---------------------------------------------------------------- label cohorts

def load_cohort(name: str = "matthew_v2_262", file: Path | None = None,
                include_tiebroken: bool = False) -> tuple[pd.DataFrame, str, str]:
    """(pairs with target_id, comp_id, score 0/1/2; cohort name; note). From a named cohort, or from a rubric v3
    consensus file: anchors left out, pairs answered by at least two reviewers with a score, and tie-broken pairs
    only with include_tiebroken."""
    if file is not None:
        d = pd.read_csv(file, dtype=str, encoding="utf-8-sig").fillna("")
        truthy = lambda s: s.astype(str).str.strip().str.casefold().isin(["1", "true", "yes"])  # noqa: E731
        keep = ~truthy(d.get("is_anchor", pd.Series("", index=d.index)))
        keep &= pd.to_numeric(d["n_reviewers"], errors="coerce").fillna(0).ge(2)
        keep &= pd.to_numeric(d["score"], errors="coerce").notna()
        tb = truthy(d.get("tie_broken", pd.Series("", index=d.index)))
        if not include_tiebroken:
            keep &= ~tb
        d = d[keep]
        note = "rubric v3 consensus, two reviewers, agreed pairs" + (" + tie-broken" if include_tiebroken else "")
        out = d[KEY].assign(score=pd.to_numeric(d["score"]).astype(int))
        return out.reset_index(drop=True), name, note
    if name == "dev_293":
        raise SystemExit("dev_293 (Barbara's old 0/1/2 labels) is not used as an outcome (EVAL_METHOD.md section 6)")
    import cohorts
    d = cohorts.load(name)
    d = d[d["grade"].notna()]
    out = d[KEY].assign(score=pd.to_numeric(d["grade"]).astype(int))
    return out.reset_index(drop=True), name, COHORT_NOTES.get(name, name)


def read_targets(file: Path) -> list[str]:
    """Target ids from a file: one per line, or a CSV with a target_id column."""
    text = Path(file).read_text(encoding="utf-8-sig").strip().splitlines()
    if text and "target_id" in text[0].split(","):
        return pd.read_csv(file, dtype=str, encoding="utf-8-sig")["target_id"].dropna().str.strip().tolist()
    return [t.strip() for t in text if t.strip()]


# ---------------------------------------------------------------- profiles (what a pipeline version keeps)

def _b3(cur: dict) -> pd.DataFrame:
    c = pd.read_csv(v2.path(cur["retrieval"]["candidates"]) / "candidates.csv", dtype=str)
    c = c[c["selected"].str.casefold() == "true"]
    return c.rename(columns={"target": "target_id", "comp": "comp_id"})[[*KEY, "rank"]].assign(
        rank=lambda x: pd.to_numeric(x["rank"]))


def _agent_ranking(cur: dict) -> Path:
    return sorted((v2.path(cur["agent_grading"]["run"]) / "ranking").glob("*/ranking.csv"))[-1]


def built_in(profile: str, cur: dict | None = None) -> dict:
    """{keeps: DataFrame target_id, comp_id, keep; run; component; prompt_version; model} for a built-in profile."""
    cur = cur or v2.current()
    if profile in ("b3_all", "b3_top7"):
        b = _b3(cur)
        keep = True if profile == "b3_all" else b["rank"] <= 7
        return {"keeps": b[KEY].assign(keep=keep), "run": cur["retrieval"]["candidates"],
                "run_file": v2.path(cur["retrieval"]["candidates"]) / "candidates.csv",
                "component": "03 retrieval", "prompt_version": cur["retrieval"]["variant"],
                "model": cur["retrieval"]["rule"]}
    if profile == "selector":
        s = pd.read_csv(v2.path(cur["selection"]["judgments"]), dtype={"target": str, "comp": str})
        s = s.rename(columns={"target": "target_id", "comp": "comp_id"})
        return {"keeps": s[KEY].assign(keep=pd.to_numeric(s["score"]).eq(1)), "run": cur["selection"]["judgments"],
                "run_file": v2.path(cur["selection"]["judgments"]), "component": "04 selection",
                "prompt_version": cur["selection"]["prompt_version"], "model": cur["selection"]["model"]}
    if profile in ("agent_ge1", "agent_2"):
        path = _agent_ranking(cur)
        extra = [v2.path(p) for p in cur["agent_grading"].get("extra_verdicts", [])]
        a = pd.concat([pd.read_csv(p, dtype={"target": str, "comp": str}) for p in [path, *extra]],
                      ignore_index=True).rename(columns={"target": "target_id", "comp": "comp_id"})
        if a.duplicated(KEY).any():
            raise ValueError("agent runs overlap: extra_verdicts must not repeat pairs of the main run")
        g = pd.to_numeric(a["score"], errors="coerce")
        keep = g.ge(1) if profile == "agent_ge1" else g.eq(2)
        run = " + ".join(str(p.relative_to(v2.ROOT).as_posix()) for p in [path, *extra])
        return {"keeps": a[KEY].assign(keep=keep.fillna(False)), "run": run,
                "run_file": path, "run_files": [path, *extra], "component": "05 agent grading",
                "prompt_version": cur["agent_grading"]["prompt_version"], "model": cur["agent_grading"]["model"]}
    raise ValueError(f"unknown profile {profile!r}; built-in: {BUILT_IN}")


def read_keeps(file: Path) -> pd.DataFrame:
    d = pd.read_csv(file, dtype=str, encoding="utf-8-sig").rename(columns={"target": "target_id", "comp": "comp_id"})
    missing = {"target_id", "comp_id", "keep"} - set(d.columns)
    if missing:
        raise SystemExit(f"{file}: needs columns target_id, comp_id, keep (missing {sorted(missing)})")
    v = d["keep"].astype(str).str.strip().str.casefold()
    bad = ~v.isin(["1", "0", "true", "false", "yes", "no", "y", "n", "1.0", "0.0"])
    if bad.any():
        raise SystemExit(f"{file}: keep must be 1/0, yes/no or true/false (row {int(np.flatnonzero(bad)[0]) + 2})")
    return d[KEY].assign(keep=v.isin(["1", "true", "yes", "y", "1.0"]))


# ---------------------------------------------------------------- metrics

def _kappa(keep: np.ndarray, truth: np.ndarray) -> float:
    if len(set(keep)) < 2 or len(set(truth)) < 2:
        return float("nan")
    return float(cohen_kappa_score(truth, keep))


def per_target(d: pd.DataFrame, min_score: int) -> pd.DataFrame:
    """One row per target: kept, true positives among kept, positives."""
    pos = d["score"].ge(min_score)
    g = d.assign(pos=pos, tp=d["keep"] & pos).groupby("target_id", sort=True)
    return pd.DataFrame({"kept": g["keep"].sum(), "tp": g["tp"].sum(), "pos": g["pos"].sum()}).astype(int)


def target_means(t: pd.DataFrame) -> tuple[float, float]:
    has_kept, has_pos = t["kept"] > 0, t["pos"] > 0
    prec = float((t.loc[has_kept, "tp"] / t.loc[has_kept, "kept"]).mean()) if has_kept.any() else float("nan")
    rec = float((t.loc[has_pos, "tp"] / t.loc[has_pos, "pos"]).mean()) if has_pos.any() else float("nan")
    return prec, rec


def bootstrap_means(t: pd.DataFrame, boot: int = BOOT, seed: int = SEED) -> dict:
    """95% intervals of the target-mean precision and recall, resampling targets."""
    kept, tp, pos = (t[c].to_numpy(dtype=float) for c in ("kept", "tp", "pos"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(t), size=(boot, len(t)))
    with np.errstate(invalid="ignore", divide="ignore"):
        p_t = np.where(kept > 0, tp / np.where(kept > 0, kept, 1), np.nan)
        r_t = np.where(pos > 0, tp / np.where(pos > 0, pos, 1), np.nan)
    with warnings.catch_warnings():          # a draw with no kept pair (or no peer) gives NaN, left out below
        warnings.simplefilter("ignore", RuntimeWarning)
        p = np.nanmean(p_t[idx], axis=1) if np.isfinite(p_t).any() else np.full(boot, np.nan)
        r = np.nanmean(r_t[idx], axis=1) if np.isfinite(r_t).any() else np.full(boot, np.nan)
    pct = lambda a, q: float(np.nanpercentile(a, q)) if np.isfinite(a).any() else float("nan")  # noqa: E731
    return {"precision_mean_lo": pct(p, 2.5), "precision_mean_hi": pct(p, 97.5),
            "recall_mean_lo": pct(r, 2.5), "recall_mean_hi": pct(r, 97.5)}


def evaluate(cohort: pd.DataFrame, keeps: pd.DataFrame, targets: list[str] | None = None,
             boot: int = BOOT) -> dict:
    """All ledger metrics for one profile on one cohort (labelled pairs only)."""
    d = cohort.copy()
    if targets is not None:
        d = d[d["target_id"].isin(set(targets))]
        if d.empty:
            raise SystemExit("no labelled pairs left for the given targets")
    k = keeps.drop_duplicates(KEY).set_index(KEY)["keep"]
    idx = pd.MultiIndex.from_frame(d[KEY])
    covered = idx.isin(k.index)
    got = k.reindex(idx).to_numpy()
    d["keep"] = np.array([bool(v) if pd.notna(v) else False for v in got], dtype=bool)
    row = {"labelled_pairs": len(d), "targets": int(d["target_id"].nunique()), "kept": int(d["keep"].sum()),
           "keeps_cover_pairs": int(covered.sum())}
    t_any = per_target(d, 1)
    row["coverage"] = float((t_any["kept"] > 0).mean())
    for name, min_score in OUTCOMES.items():
        t = per_target(d, min_score)
        pm, rm = target_means(t)
        tp, kept, pos = int(t["tp"].sum()), int(t["kept"].sum()), int(t["pos"].sum())
        row |= {f"{name}_positives": pos, f"{name}_precision_mean": pm, f"{name}_recall_mean": rm,
                f"{name}_precision_pooled": tp / kept if kept else float("nan"),
                f"{name}_recall_pooled": tp / pos if pos else float("nan"),
                f"{name}_kappa": _kappa(d["keep"].to_numpy(), d["score"].ge(min_score).to_numpy())}
        row |= {f"{name}_{k2}": v for k2, v in bootstrap_means(t, boot).items()}
    return row


# ---------------------------------------------------------------- ledger

def read_ledger(path: Path) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def append_rows(path: Path, rows: list[dict], force: bool = False) -> list[dict]:
    """Append rows to the ledger (never rewrites earlier rows). A row with the same run, cohort, split and profile as
    an existing row is skipped unless force. Returns the rows written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    old = read_ledger(path)
    if len(old.columns) and list(old.columns) != LEDGER_COLUMNS:
        raise SystemExit(f"{path}: columns differ from this script's ledger columns; not appending")
    seen = set(zip(old.get("run", []), old.get("cohort", []), old.get("split", []), old.get("profile", [])))
    written = []
    new_file = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_COLUMNS)
        if new_file:
            w.writeheader()
        for r in rows:
            key = (r["run"], r["cohort"], r["split"], r["profile"])
            if key in seen and not force:
                print(f"skipped (already in the ledger; --force to add anyway): {r['profile']} {r['run']}")
                continue
            w.writerow({c: _fmt(r.get(c, "")) for c in LEDGER_COLUMNS})
            seen.add(key)
            written.append(r)
    return written


def _fmt(v):
    if isinstance(v, float):
        return "" if np.isnan(v) else f"{v:.4f}"
    return v


# ---------------------------------------------------------------- show: latest table and chart

def latest(ledger: pd.DataFrame) -> pd.DataFrame:
    """The most recent row per profile, cohort and split (ledger order is entry order)."""
    if ledger.empty:
        return ledger
    return ledger.drop_duplicates(["profile", "cohort", "split"], keep="last").reset_index(drop=True)


SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COLOR = {"precision": "#2a78d6", "recall": "#eb6834"}     # categorical slots 1 and 2 of the validated palette


def chart(ledger: pd.DataFrame, out: Path, cohort: str | None = None, split: str = "all") -> Path | None:
    """Precision and recall (target means, 95% intervals) per ledger entry in entry order, any peer and direct peer
    side by side. One cohort and split per chart (default: the latest entry's cohort, split all)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if ledger.empty:
        return None
    cohort = cohort or ledger["cohort"].iloc[-1]
    d = ledger[(ledger["cohort"] == cohort) & (ledger["split"] == split)].reset_index(drop=True)
    if d.empty:
        return None
    labels = [f"{r.profile}   {r.entry_utc[:10]}\n{_short(r.change, 40)}" for r in d.itertuples()]
    n = len(d)
    fig, axes = plt.subplots(1, 2, figsize=(12, 1.6 + 0.62 * n), sharey=True, facecolor=SURFACE)
    y = np.arange(n)[::-1]
    for ax, (outcome, title) in zip(axes, (("peer", "Any peer (score 1 or 2)"), ("direct", "Direct peer (score 2)"))):
        ax.set_facecolor(SURFACE)
        for k, (metric, off) in enumerate((("precision", 0.14), ("recall", -0.14))):
            val = pd.to_numeric(d[f"{outcome}_{metric}_mean"], errors="coerce").to_numpy() * 100
            lo = pd.to_numeric(d[f"{outcome}_{metric}_mean_lo"], errors="coerce").to_numpy() * 100
            hi = pd.to_numeric(d[f"{outcome}_{metric}_mean_hi"], errors="coerce").to_numpy() * 100
            ax.hlines(y + off, lo, hi, color=COLOR[metric], linewidth=2, zorder=2)
            ax.scatter(val, y + off, s=64, color=COLOR[metric], edgecolor=SURFACE, linewidth=2, zorder=3,
                       label=metric.capitalize(), clip_on=False)
        ax.set_xlim(-2, 103)
        ax.set_xticks([0, 20, 40, 60, 80, 100])
        ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
        ax.tick_params(colors=INK_2, labelsize=9, length=0)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels, fontsize=8.5, color=INK, linespacing=1.4)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="upper right", ncol=2, frameon=False, fontsize=9, labelcolor=INK_2,
               handletextpad=0.3, columnspacing=1.2, bbox_to_anchor=(0.99, 0.995))
    note = d["cohort_note"].iloc[-1]
    fig.suptitle("Comp profiles vs human labels", x=0.01, ha="left", fontsize=12, color=INK, y=0.995)
    fig.text(0.01, 0.955, f"Labels: {cohort} ({note}). Targets: {split}.", fontsize=8.5, color=INK_2, va="top")
    fig.text(0.01, 0.005, "Target means with 95% target-bootstrap intervals. Labelled pairs only; unlabelled pairs "
             "never count as non-peers.", fontsize=8, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out


def _short(text: str, n: int = 44) -> str:
    text = str(text).replace("baseline: ", "baseline, ")
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


# ---------------------------------------------------------------- CLI

def build_rows(args, cur: dict) -> list[dict]:
    cohort, cohort_name, note = load_cohort(args.cohort, args.cohort_file, args.include_tiebroken)
    if args.cohort_file:
        cohort_name = args.cohort_name or Path(args.cohort_file).stem
    targets, split, split_sha = None, "all", ""
    if args.targets:
        targets, split, split_sha = read_targets(args.targets), Path(args.targets).name, sha256(args.targets)
    script = sha256(Path(__file__))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    specs = []
    if args.keeps:
        if not args.profile or not args.component:
            raise SystemExit("--keeps needs --profile (a short name) and --component")
        specs.append((args.profile, {"keeps": read_keeps(args.keeps), "run": Path(args.keeps).as_posix(),
                                     "run_file": Path(args.keeps), "component": args.component,
                                     "prompt_version": args.prompt_version or "", "model": args.model or ""}))
    else:
        for p in args.profiles or BUILT_IN:
            specs.append((p, built_in(p, cur)))
    rows = []
    for name, spec in specs:
        m = evaluate(cohort, spec["keeps"], targets, args.boot)
        rows.append({"entry_utc": stamp, "who": args.who or "", "component": spec["component"], "profile": name,
                     "change": args.change or "", "prompt_version": args.prompt_version or spec["prompt_version"],
                     "model": args.model or spec["model"], "run": spec["run"],
                     "run_sha256": " + ".join(sha256(f) for f in spec.get("run_files", [spec["run_file"]])),
                     "cohort": cohort_name, "cohort_note": note, "split": split, "split_sha256": split_sha,
                     **m, "script_sha256": script})
    return rows


def print_rows(rows: list[dict] | pd.DataFrame) -> None:
    d = pd.DataFrame(rows)
    if d.empty:
        print("(no rows)")
        return
    cols = ["profile", "cohort", "split", "labelled_pairs", "kept", "coverage",
            "peer_precision_mean", "peer_recall_mean", "peer_precision_pooled", "peer_recall_pooled", "peer_kappa",
            "direct_precision_mean", "direct_recall_mean", "direct_precision_pooled", "direct_recall_pooled",
            "direct_kappa"]
    show = d[[c for c in cols if c in d.columns]].copy()
    for c in show.columns[3:]:
        show[c] = pd.to_numeric(show[c], errors="coerce").round(3)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(show.to_string(index=False))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("score", "record"):
        p = sub.add_parser(name, help="print the metrics" if name == "score" else "append rows to the ledger")
        p.add_argument("--profiles", nargs="*", choices=BUILT_IN, help="built-in profiles (default: all five)")
        p.add_argument("--keeps", type=Path, help="CSV with target_id, comp_id, keep for any other run")
        p.add_argument("--profile", help="short name for the --keeps run (e.g. selector, agent_ge1)")
        p.add_argument("--component", choices=COMPONENTS)
        p.add_argument("--prompt-version")
        p.add_argument("--model")
        p.add_argument("--cohort", default="matthew_v2_262", help="named label cohort (06_labels/scripts/cohorts.py)")
        p.add_argument("--cohort-file", type=Path, help="rubric v3 consensus CSV (rubric_v3.py consensus)")
        p.add_argument("--cohort-name", help="name to record for --cohort-file (default: its file name)")
        p.add_argument("--include-tiebroken", action="store_true")
        p.add_argument("--targets", type=Path, help="restrict to these target ids (e.g. the checking half)")
        p.add_argument("--who")
        p.add_argument("--change", help="what changed in this version, in a few words")
        p.add_argument("--boot", type=int, default=BOOT)
        p.add_argument("--ledger", type=Path, default=default_dir() / "ledger.csv")
        if name == "record":
            p.add_argument("--force", action="store_true", help="append even if the same run is already recorded")
    s = sub.add_parser("show", help="print the ledger; write latest.csv and progress.png")
    s.add_argument("--ledger", type=Path, default=default_dir() / "ledger.csv")
    s.add_argument("--cohort", help="cohort to chart (default: the latest entry's)")
    s.add_argument("--split", default="all")
    args = ap.parse_args(argv)

    if args.cmd == "show":
        ledger = read_ledger(args.ledger)
        if ledger.empty:
            raise SystemExit(f"{args.ledger}: empty; run `record` first")
        print_rows(ledger)
        out_dir = Path(args.ledger).parent
        latest(ledger).to_csv(out_dir / "latest.csv", index=False)
        png = chart(ledger, out_dir / "progress.png", args.cohort, args.split)
        print(f"wrote {out_dir / 'latest.csv'}" + (f" and {png}" if png else ""))
        return
    if args.cmd == "record" and (not args.who or not args.change):
        raise SystemExit("record needs --who and --change")
    rows = build_rows(args, v2.current())
    print_rows(rows)
    if args.cmd == "record":
        written = append_rows(args.ledger, rows, args.force)
        print(f"appended {len(written)} row(s) to {args.ledger}")


if __name__ == "__main__":
    main()
