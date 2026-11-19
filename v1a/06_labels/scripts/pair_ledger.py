"""Pair ledger: every target-comp pair a person or a model judged, from saved files only.

One place to see where everyone's pair-level work sits: which pairs each reviewer
round, agent-loop run, LLM judge and LLM screen covered, under which rubric or
prompt version, and when. No model calls, no financial tables.

Stages
  human_review  reviewer grades. Rubrics: round 1 (0/1/2, blank = 0 with one of five
                reasons), rounds 2-3 old form (0/1/2, six reasons, multi-business rule;
                GOLDEN_SET_ROUND2.md), rubric v2 (four yes/no questions, score derived;
                RUBRIC_V2.md), Barbara's direct-peer Yes/No (Yes = 2, No is not a 0).
  agent_loop    agent_loop.py runs (0/1/2 with citations; prompt version per run). With
                --facet-scores the prompt also asks for per-facet scores under the same
                version string, so those runs are listed as their own span.
  llm_judge     one-shot graders on 0/1/2 (GPT-6.1 Sol on the 293; Sol cited grades on
                the holdout targets).
  llm_screen    binary good/bad screens of candidate lists (cosine -> LLM).

Pairs whose comp is outside the universe (EXT_*, Barbara's direct-peer list) are left
out and counted in the summary. Matthew's rubric-v2 answers are read from the branch
named by --matthew-ref when they are not in the working tree.

Dates: `sent` is the first commit of the sheet or pair list (when the pairs were set),
`judged` the first commit of the grades, or the time stamps inside the file when it has
them (judged_at, fetched_at_utc). Dates of files seeded into v1 on 2026-11-03/04 are
the seeding date, not the review date; `date_source` says which.

Run:
  uv run python v1a/06_labels/scripts/pair_ledger.py
Writes outputs-local/v1a/06_labels/pair_ledger/<stamp>/ (never overwrites): judgments.csv (long:
one row per source x pair), pairs.csv (wide: one row per pair), sources.csv, spans.csv
(per rubric / prompt version), overlap.csv, summary.md.
"""

from __future__ import annotations

import sys as _sys  # v1a: shared paths (common/paths.py) put every component's scripts on the path
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v1a  # noqa: E402
v1a.setup()

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))
from project_data import OUTPUTS_LOCAL, REPO_ROOT  # noqa: E402

V1 = OUTPUTS_LOCAL / "v1"            # the v1 record: history is read here (the seeded v1a copies are identical)
CUR = v1a.current()
OUT = v1a.out("06_labels") / "pair_ledger"
MATTHEW_V2 = "outputs-local/v1/golden_set_round3/labels/round3_scores_v2.csv"
MATTHEW_SHEET_V2 = "outputs-local/v1/golden_set_round3/labels/round3_sheet_v2.csv"
DIRECT_PEERS = V1 / "direct_peers_barbara/20261117_run"

RUBRIC_R1 = "round 1: 0/1/2, blank = 0 with one of five reasons"
RUBRIC_OLD = "rounds 2-3 old form: 0/1/2, six reasons, multi-business rule"
RUBRIC_V2 = "rubric v2: four yes/no questions, score derived"
RUBRIC_DIRECT = "direct-peer Yes/No (Yes = 2; No is not a 0)"
COLS = ["target_id", "comp_id", "value", "grade", "peer", "status"]


@dataclass
class Source:
    id: str
    stage: str
    who: str
    rubric: str
    path: str                      # repo-relative file the grades come from
    load: Callable[[], pd.DataFrame]
    sent_from: str | None = None   # repo-relative file whose first commit is when the pairs were set
    note: str = ""
    extra: dict = field(default_factory=dict)


def seeded(p: Path) -> bool:
    """A file under outputs-local/v1a/ that is a copy of a v1 file (seed_manifest.json): counted once, from v1."""
    manifest = v1a.OUTPUTS / "seed_manifest.json"
    if not manifest.exists():
        return False
    copies = {c["v1a_path"] for c in json.loads(manifest.read_text(encoding="utf-8"))["copied"]}
    return p.resolve().relative_to(REPO_ROOT).as_posix() in copies


def rel(p: Path) -> str:
    return p.resolve().relative_to(REPO_ROOT).as_posix()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()


def first_commit_date(path: str, ref: str | None = None) -> str | None:
    out = git("log", *( [ref] if ref else []), "--follow", "--format=%as", "--", path)
    return out.splitlines()[-1] if out else None


def read_tree_or_ref(path: str, ref: str) -> tuple[pd.DataFrame, str]:
    """A CSV from the working tree, else from a git ref. Returns the frame and where it came from."""
    local = REPO_ROOT / path
    if local.exists():
        return pd.read_csv(local, dtype=str, encoding="utf-8-sig"), "working tree"
    text = git("show", f"{ref}:{path}")
    if not text:
        raise FileNotFoundError(f"{path} is neither in the working tree nor in {ref}")
    return pd.read_csv(io.StringIO(text.lstrip("﻿")), dtype=str), f"{ref} ({git('rev-parse', '--short', ref)})"


def frame(target, comp, value, grade, peer, status) -> pd.DataFrame:
    return pd.DataFrame({"target_id": list(map(str, target)), "comp_id": list(map(str, comp)), "value": list(value),
                         "grade": pd.to_numeric(pd.Series(list(grade)), errors="coerce").tolist(),
                         "peer": pd.to_numeric(pd.Series(list(peer)), errors="coerce").tolist(),
                         "status": list(status)})


def graded(target, comp, score, status=None) -> pd.DataFrame:
    """0/1/2 grades: peer = grade >= 1; a missing grade is not judged (never 0)."""
    s = pd.to_numeric(pd.Series(list(score)), errors="coerce")
    st = list(status) if status is not None else ["ok"] * len(s)
    st = [x if pd.notna(g) or x != "ok" else "no grade" for x, g in zip(st, s)]
    return frame(target, comp, s, s, [None if pd.isna(g) else int(g >= 1) for g in s], st)


# ---------- loaders ----------

def round1(reviewer: str) -> Callable[[], pd.DataFrame]:
    def load():
        d = pd.DataFrame(json.loads((V1 / "golden_set/labels/reviewer_labels_20261028.json")
                                    .read_text(encoding="utf-8"))["labels"])
        return graded(d["target_id"], d["comp_id"], d[f"score_{reviewer}"])
    return load


def round2_sheet(slot: str) -> Callable[[], pd.DataFrame]:
    def load():
        d = pd.read_csv(V1 / "golden_set_showcase/labels/round2_sheet.csv", dtype=str)
        return graded(d["target_id"], d["comp_id"], d[f"score_{slot}"])
    return load


def barbara_old(sheet: str) -> Callable[[], pd.DataFrame]:
    def load():
        labels = pd.read_csv(V1 / "integration/review/pairs.csv", dtype={"target_id": str, "comp_id": str})
        batch = pd.read_csv(sheet, dtype=str)[["target_id", "comp_id"]]
        d = batch.merge(labels, on=["target_id", "comp_id"], how="left", validate="one_to_one")
        return graded(d["target_id"], d["comp_id"], d["score_barbara"])
    return load


def matthew_v2(ref: str) -> Callable[[], pd.DataFrame]:
    def load():
        d, _ = read_tree_or_ref(MATTHEW_V2, ref)
        return graded(d["target_id"], d["comp_id"], d["score_matthew"])
    return load


def direct_peers() -> pd.DataFrame:
    m = pd.read_csv(DIRECT_PEERS / "manifest.csv", dtype=str)
    m = m[~m["comp_id"].str.startswith("EXT_")]
    yes = m["Barbara - If Direct"].eq("Yes")
    out = frame(m["target_id"], m["comp_id"], m["Barbara - If Direct"], [2 if y else None for y in yes],
                [1 if y else None for y in yes], ["ok"] * len(m))
    return out.assign(judged=m["Barbara - If Direct"].isin(["Yes", "No"]).to_numpy())  # a No is an answer, not a 0


def agent_run(folder: Path) -> Callable[[], pd.DataFrame]:
    def load():
        d = pd.read_csv(folder / "verdicts.csv", dtype={"target": str, "comp": str})
        d = d[~d["comp"].str.startswith("EXT_")]
        return graded(d["target"], d["comp"], d["score"].where(d["status"].eq("ok")), d["status"])
    return load


def gpt_judge() -> pd.DataFrame:
    d = pd.read_csv(V1 / "integration/judge_gpt61sol/eval_293/all_pairs.csv", dtype={"target": str, "comp": str})
    return graded(d["target"], d["comp"], d["score"].where(d["status"].eq("ok")), d["status"])


def sol_holdout() -> pd.DataFrame:
    d = pd.read_csv(V1 / "holdout_completion/graded_peer_selection/grades.csv", dtype={"target": str, "comp": str})
    return graded(d["target"], d["comp"], d["score"], ["ok"] * len(d))


def screen(path: Path) -> Callable[[], pd.DataFrame]:
    def load():
        d = pd.read_csv(path, dtype={"target": str, "comp": str})
        s = pd.to_numeric(d["score"], errors="coerce")
        return frame(d["target"], d["comp"], d["score"], [None] * len(d), s,
                     ["ok" if pd.notna(x) else "no answer" for x in s])
    return load


def screen_times(path: Path) -> tuple[str | None, str | None]:
    t = pd.read_csv(path, usecols=["judged_at"])["judged_at"].dropna()
    return (t.min()[:10], t.max()[:10]) if len(t) else (None, None)


def sources(matthew_ref: str) -> list[Source]:
    r1 = "outputs-local/v1/golden_set/labels/reviewer_labels_20261028.json"
    r1_sheet = "outputs-local/v1/golden_set/labels/golden_set_labels.csv"
    r2 = "outputs-local/v1/golden_set_showcase/labels/round2_sheet.csv"
    r2s = rel(V1 / "golden_set_showcase/labels/round2_sonnet_sheet.csv")
    r3 = rel(V1 / "golden_set_round3/labels/round3_sheet.csv")
    out = [Source(f"human:round1:{r}", "human_review", r.capitalize(), RUBRIC_R1, r1, round1(r), r1_sheet,
                  "PCTY and WEN, pooled from the four v0 routes")
           for r in ("riya", "barbara", "matthew")]
    out += [Source(f"human:round2_sheet:{s}", "human_review", f"slot {s[-1].upper()}", RUBRIC_OLD, r2,
                   round2_sheet(s), r2, "CSL, AFG, AZZ, BBCP, BUKS + 2 WEN; sheet not filled in the repo")
            for s in ("reviewer_a", "reviewer_b", "reviewer_c")]
    out += [Source("human:round2_sonnet:barbara", "human_review", "Barbara", RUBRIC_OLD,
                   "outputs-local/v1/integration/review/pairs.csv", barbara_old(REPO_ROOT / r2s), r2s,
                   "round-2 targets, comps from Sonnet-facet B3"),
            Source("human:round3:barbara", "human_review", "Barbara", RUBRIC_OLD,
                   "outputs-local/v1/integration/review/pairs.csv", barbara_old(REPO_ROOT / r3), r3,
                   "one target per SIC2, comps from Sonnet-facet B3"),
            Source("human:round3_v2:matthew", "human_review", "Matthew", RUBRIC_V2, MATTHEW_V2,
                   matthew_v2(matthew_ref), MATTHEW_SHEET_V2, "same 262 pairs as round 3",
                   {"ref": matthew_ref}),
            Source("human:direct_peers:barbara", "human_review", "Barbara", RUBRIC_DIRECT,
                   rel(DIRECT_PEERS / "manifest.csv"), direct_peers, rel(DIRECT_PEERS / "manifest.csv"),
                   "pairs Barbara picked herself; in-universe comps only (all holdout companies)")]
    runs = sorted(p for p in (V1 / "agent_loop").iterdir() if (p / "verdicts.csv").exists())
    runs += [p.parent for p in sorted(v1a.out("05_agent_grading").glob("*/verdicts.csv")) if not seeded(p)]
    for folder in [*runs, DIRECT_PEERS / "agent"]:
        cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        facets = "sonnet" if "facets_sonnet" in str(cfg.get("facets", "")) else "haiku"
        extras = [x for x, on in [("facet scores", cfg.get("facet_scores")),
                                  ("industry facets", cfg.get("industry_facets")),
                                  ("no web search", cfg.get("search") == "none")] if on]
        name = "direct_peers" if folder.parent == DIRECT_PEERS else folder.name
        out.append(Source(f"agent:{name}", "agent_loop", f"{cfg.get('model')} agent",
                          f"agent prompt {cfg.get('prompt_version')}"
                          + (" + facet scores" if cfg.get("facet_scores") else ""), rel(folder / "verdicts.csv"),
                          agent_run(folder), rel(folder / "pairs.csv") if (folder / "pairs.csv").exists() else None,
                          f"{facets} facets" + (", " + ", ".join(extras) if extras else ""),
                          {"facets": facets, "facet_scores": bool(cfg.get("facet_scores"))}))
    out += [Source("judge:gpt61sol_293", "llm_judge", "GPT-6.1 Sol", "source-cited one-shot judge, 0/1/2",
                   "outputs-local/v1/integration/judge_gpt61sol/eval_293/all_pairs.csv", gpt_judge,
                   note="label-blind, same 293 pairs as Barbara"),
            Source("judge:sol_holdout_grades", "llm_judge", "GPT-6.1 Sol", "cited grades, 0/1/2 (v0 holdout)",
                   "outputs-local/v1/holdout_completion/graded_peer_selection/grades.csv", sol_holdout,
                   note="160 holdout targets, comps from the training pool")]
    screens = [V1 / "judge/tables/judgments.csv",
               *sorted((V1 / "cosine_then_llm").glob("*/tables/judgments.csv")),
               *[p for p in sorted(v1a.out("04_selection").glob("*/tables/judgments.csv")) if not seeded(p)]]
    for path in screens:
        p = pd.read_csv(path, usecols=["model", "prompt_version"]).iloc[0]
        name = ("v0_haiku" if path.parts[-3] == "judge" else
                ("v1a:" if "v1a" in path.parts else "") + path.parts[-3])
        out.append(Source(f"screen:{name}", "llm_screen", p["model"], f"binary screen prompt {p['prompt_version']}",
                          rel(path), screen(path), note="cosine -> LLM good/bad on a candidate list"))
    return out


# ---------- build ----------

def build(matthew_ref: str):
    uni = pd.read_csv(v1a.path(CUR["universe"]["universe"]), dtype=str)
    ticker = uni.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
    sample = pd.read_csv(v1a.path(CUR["universe"]["split"]), dtype=str).set_index("IQ_COMPANY_ID")["sample"]

    long, rows = [], []
    for src in sources(matthew_ref):
        d = src.load()
        judged = d["judged"] if "judged" in d else d["grade"].notna() | d["peer"].notna()
        d = d[COLS]
        if d.duplicated(["target_id", "comp_id"]).any():
            raise ValueError(f"{src.id}: duplicate pairs")
        unknown = sorted(set(d["target_id"]) - set(sample.index) | set(d["comp_id"]) - set(sample.index))
        if unknown:
            raise ValueError(f"{src.id}: companies outside the universe {unknown[:5]}")
        times = screen_times(REPO_ROOT / src.path) if src.stage == "llm_screen" else (None, None)
        if src.id.startswith("human:round1"):
            fetched = json.loads((REPO_ROOT / src.path).read_text(encoding="utf-8"))["fetched_at_utc"][:10]
            times = (fetched, fetched)
        ref = src.extra.get("ref")
        in_tree = (REPO_ROOT / src.path).exists()
        judged_date = times[0] or first_commit_date(src.path, None if in_tree else ref)
        rows.append({
            "source": src.id, "stage": src.stage, "who": src.who, "rubric": src.rubric, "note": src.note,
            "pairs": len(d), "targets": d["target_id"].nunique(), "judged": int(judged.sum()),
            "not_judged": int((~judged).sum()), "answered_no_grade": int((judged & d["grade"].isna() & d["peer"].isna()).sum()),
            "status": json.dumps(d["status"].value_counts().to_dict()),
            "grade_2": int(d["grade"].eq(2).sum()), "grade_1": int(d["grade"].eq(1).sum()),
            "grade_0": int(d["grade"].eq(0).sum()), "peer_yes": int(d["peer"].eq(1).sum()),
            "peer_no": int(d["peer"].eq(0).sum()),
            "sent": first_commit_date(src.sent_from) if src.sent_from and (REPO_ROOT / src.sent_from).exists()
            else (first_commit_date(src.sent_from, ref) if src.sent_from and ref else None),
            "judged_first": judged_date, "judged_last": times[1] or judged_date,
            "date_source": "time stamps in file" if times[0] else "first git commit",
            "file": src.path if in_tree else f"{ref}:{src.path}",
            "sha256": hashlib.sha256((REPO_ROOT / src.path).read_bytes()).hexdigest() if in_tree
            else git("rev-parse", f"{ref}:{src.path}") + " (git blob)",
        })
        long.append(d.assign(source=src.id, stage=src.stage, rubric=src.rubric, judged=judged))
    long = pd.concat(long, ignore_index=True)
    long.insert(2, "target_ticker", long["target_id"].map(ticker))
    long.insert(3, "comp_ticker", long["comp_id"].map(ticker))
    long["comp_sample"] = long["comp_id"].map(sample)
    return long, pd.DataFrame(rows), sample, ticker


def wide(long: pd.DataFrame, sample: pd.Series, ticker: pd.Series) -> pd.DataFrame:
    j = long[long["judged"]]
    shown = j["grade"].map(lambda g: "" if pd.isna(g) else str(int(g)))
    shown = shown.where(j["grade"].notna(), j["peer"].map({1.0: "good", 0.0: "bad"}).fillna(""))
    grid = j.assign(shown=shown).pivot(index=["target_id", "comp_id"], columns="source", values="shown")
    every = long[["target_id", "comp_id"]].drop_duplicates().set_index(["target_id", "comp_id"])
    grid = every.join(grid)
    counts = long.assign(n=long["judged"].astype(int)).pivot_table(
        index=["target_id", "comp_id"], columns="stage", values="n", aggfunc="sum", fill_value=0)
    counts = counts.add_prefix("n_judged_")
    sent = long.groupby(["target_id", "comp_id"])["source"].agg(lambda s: ";".join(sorted(s))).rename("sources")
    out = every.join(counts).join(sent).join(grid).reset_index()
    out.insert(2, "target_ticker", out["target_id"].map(ticker))
    out.insert(3, "comp_ticker", out["comp_id"].map(ticker))
    out.insert(4, "target_sample", out["target_id"].map(sample))
    out.insert(5, "comp_sample", out["comp_id"].map(sample))
    return out.sort_values(["target_ticker", "comp_ticker"])


def spans(src: pd.DataFrame, long: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (stage, rubric), g in src.groupby(["stage", "rubric"], sort=False):
        part = long[long["source"].isin(g["source"]) & long["judged"]]
        done = g[g["judged"] > 0]
        rows.append({"stage": stage, "rubric": rubric, "sources": ";".join(done["source"]),
                     "who": ";".join(sorted(set(done["who"]))),
                     "first": done["judged_first"].dropna().min() if len(done) else None,
                     "last": done["judged_last"].dropna().max() if len(done) else None,
                     "judgments": int(g["judged"].sum()),
                     "unique_pairs_judged": len(part[["target_id", "comp_id"]].drop_duplicates()),
                     "targets": part["target_id"].nunique(),
                     "sent_not_judged": ";".join(f"{r.source} ({r.pairs})" for r in g[g["judged"] == 0].itertuples())})
    return pd.DataFrame(rows).sort_values(["first", "stage"], na_position="last")


def overlap(long: pd.DataFrame, stages=("human_review", "agent_loop", "llm_judge")) -> pd.DataFrame:
    j = long[long["judged"] & long["stage"].isin(stages)]
    sets = {s: set(zip(g["target_id"], g["comp_id"])) for s, g in j.groupby("source", sort=False)}
    return pd.DataFrame({a: {b: len(sets[a] & sets[b]) for b in sets} for a in sets})


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def summary(src, long, pairs, sp, excluded: int) -> str:
    j = long[long["judged"]]
    by_stage = (j.groupby("stage").apply(lambda g: pd.Series({
        "sources": g["source"].nunique(), "judgments": len(g),
        "unique_pairs": len(g[["target_id", "comp_id"]].drop_duplicates()),
        "targets": g["target_id"].nunique()}), include_groups=False).reset_index())
    human = pairs[pairs["n_judged_human_review"] > 0]
    reviewers = j[j["stage"].eq("human_review")].groupby(["target_id", "comp_id"])["source"].nunique()
    agent_and_human = pairs[(pairs["n_judged_human_review"] > 0) & (pairs["n_judged_agent_loop"] > 0)]
    keep = ["source", "who", "rubric", "pairs", "targets", "judged", "answered_no_grade", "grade_2", "grade_1", "grade_0",
            "peer_yes", "peer_no", "sent", "judged_first", "date_source", "note"]
    return "\n\n".join([
        f"# Pair ledger ({datetime.now(timezone.utc):%Y-%m-%d})",
        "Every target-comp pair a person or a model judged, from saved files. Unique pairs are "
        "(target, comp) once, whatever the number of judgments. A blank grade is not judged, never 0.",
        f"Left out: {excluded} pairs whose comp is outside the universe (Barbara's direct-peer list).",
        "## By stage\n\n" + md_table(by_stage),
        f"## Human review\n\n{len(human)} unique pairs have at least one human judgment "
        f"({human['target_id'].nunique()} targets); {int((reviewers >= 2).sum())} have two or more "
        f"(round 1 three reviewers; round 3 Barbara old form + Matthew v2). "
        f"{len(agent_and_human)} have both a human judgment and an agent-loop grade.",
        "## Rubric and prompt spans\n\n" + md_table(sp),
        "## Sources\n\n" + md_table(src[keep]),
        "Not in this checkout: Kethan's focused pipeline (`kethan/wip`, `outputs-local/pipeline/`), "
        "Sol filter + Luna 0-3 judge on 2,438 B3 pairs, kept on his machine.",
    ]) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matthew-ref", default="origin/matt/rubric-yes-no",
                    help="git ref holding Matthew's rubric-v2 scores when they are not in the working tree")
    ap.add_argument("--out", type=Path, help="output folder (default pair_ledger/<stamp>)")
    args = ap.parse_args(argv)
    long, src, sample, ticker = build(args.matthew_ref)
    pairs = wide(long, sample, ticker)
    sp = spans(src, long)
    m = pd.read_csv(DIRECT_PEERS / "manifest.csv", dtype=str)
    excluded = int(m["comp_id"].str.startswith("EXT_").sum())
    out = args.out or OUT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    long.to_csv(out / "judgments.csv", index=False)
    pairs.to_csv(out / "pairs.csv", index=False)
    src.to_csv(out / "sources.csv", index=False)
    sp.to_csv(out / "spans.csv", index=False)
    overlap(long).to_csv(out / "overlap.csv")
    (out / "summary.md").write_text(summary(src, long, pairs, sp, excluded), encoding="utf-8")
    (out / "run.json").write_text(json.dumps({
        "commit": git("rev-parse", "HEAD"), "matthew_ref": args.matthew_ref,
        "matthew_ref_commit": git("rev-parse", args.matthew_ref), "excluded_external_pairs": excluded,
        "sources": len(src), "judgments": int(long["judged"].sum()), "unique_pairs": len(pairs)}, indent=1),
        encoding="utf-8")
    print((out / "summary.md").read_text(encoding="utf-8")[:4000])
    print(f"ledger: {out}")


if __name__ == "__main__":
    main()
