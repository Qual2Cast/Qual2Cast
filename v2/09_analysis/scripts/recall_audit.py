"""EXPERIMENTAL recall audit: are thin comp profiles thin because the universe has few true peers for a target, or
because B3's retrieval list misses peers? (Michael approved, 2026-11-28; labelled EXPERIMENTAL everywhere.)

The labelled pairs (rubric v3 sheet, v3_final) cover only B3's selected lists. This audit asks the rubric v3 LLM
judge about comps just below those lists, for a few targets:

- Targets (seed 2026): 7 "thin" targets with no direct peer (grade 2) among their labelled pairs and 3 controls
  with >= 2 direct peers, drawn from the v3_final targets whose whole B3 selected list is on the rubric v3 sheet
  (so the in-list counts are the full list). An anchor pair (on the sheet, left out of v3_final) that the pinned
  final labels score 2 counts as a direct peer for the draw (OC-CSL).
- Candidates per target: comps not on the rubric v3 sheet for that target (anchors included), the target left
  out, in B3 rank order: the unselected rows of B3's top 10 first, then ranks 11 and beyond, up to 15 per target.
  The ranking is the pinned B3 run itself (current.toml [retrieval] candidates: ranking.csv.gz, written by
  03_retrieval's B3 code over the training pool, the only pool B3 ranks; holdout companies are never comps here).
- Descriptions: the code that built the sheet's description columns (06_labels extend_label_book.rows_for:
  direct_peer_pairs.shown_companies and the business-scope notes; rubric_v3.pair_pool's facet gap fill is checked
  to be a no-op). `build` checks that it reproduces the sheet's 13 description columns for all 323 sheet pairs.
- Judge: judge_v3.Run unchanged (prompt judge_v3_prompt 2026-11-27a; codex, gpt-5.6-terra, name terra), one call
  per pair, sequential; it sees only the description columns, never a rank, similarity, label or financial column.
  No financial table is read anywhere in this script.

  uv run python v2/09_analysis/scripts/recall_audit.py build                 # new <UTC>_EXPERIMENTAL/ dir
  uv run python v2/09_analysis/scripts/recall_audit.py dry-run <dir>         # render prompts, count calls, leak check
  uv run python v2/09_analysis/scripts/recall_audit.py run <dir>             # judge calls (resumable)
  uv run python v2/09_analysis/scripts/recall_audit.py collect <dir>         # judge_answers + summary tables

Writes outputs-local/v2/09_analysis/recall_audit/<UTC stamp>_EXPERIMENTAL/:
  targets.csv          every eligible v3_final target, its pool, in-list labels and whether / in which order drawn
  candidates.csv       the audit pairs with B3 rank, similarity, band (never shown to the judge)
  audit_sheet.csv      the pairs as the judge sees them: pair id, ids, is_anchor, the sheet's description columns
  repro_check.csv      per description column, sheet pairs the builder reproduces exactly
  dry_run/             one full rendered prompt, leak check, call count
  judge/               judge_v3.Run dir (manifest, inputs, runs/<pair>/<stamp>/ prompts and responses, answers, logs)
  judge_answers.csv    the judge's column set per pair (rubric v3 sheet encoding) and its derived score
  pairs.csv            candidates + judge outcome
  per_target.csv, by_group.csv, by_band.csv, by_band_group.csv   summary tables
  manifest.json        inputs with sha256, seed, design, commands
A file that is replaced moves to history/<stamp>/ first.
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import argparse
import hashlib
import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

KEY = ["target_id", "comp_id"]
SEED = 2026
N_THIN, N_CONTROL, CONTROL_MIN_DIRECT = 7, 3, 2
PER_TARGET, TOP_K, MAX_PAIRS, MAX_CALLS = 15, 10, 150, 160
BANDS = ["selected top-10, not on sheet", "unselected top-10", "11-15", "16-20", "21+"]
JUDGE = {"backend": "codex", "model": "gpt-5.6-terra", "name": "terra", "effort": None}
LABEL = "EXPERIMENTAL"
OUT_ROOT = v2.out("09_analysis") / "recall_audit"
# words that must not appear in any rendered prompt's pair part (financial data, reviewer or method columns)
LEAK_WORDS = ["ebitda", "ev/", "enterprise value", "market cap", "multiple", "similarity", "rank", "matthew",
              "barbara", "riya", "score_", "grade", "selected", "b3"]


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return Path(path).resolve().relative_to(v2.ROOT).as_posix()


# ---------------------------------------------------------------- pure parts (tested offline)

def band(rank: int, selected: bool) -> str:
    """B3 rank band of a candidate."""
    if rank <= TOP_K:
        return BANDS[0] if selected else BANDS[1]
    return "11-15" if rank <= 15 else ("16-20" if rank <= 20 else "21+")


def audit_candidates(ranking: pd.DataFrame, exclude: set[tuple[str, str]], targets: list[str],
                     selected: set[tuple[str, str]], per_target: int = PER_TARGET) -> pd.DataFrame:
    """Per target, the first `per_target` comps of B3's ranking (columns target, comp, rank, similarity) that are
    not in `exclude` (pairs already on the sheet) and not the target itself, in rank order (ties by comp id).
    Columns: target_id, comp_id, rank, similarity, b3_selected, band, audit_order (1..n within the target)."""
    r = ranking.rename(columns={"target": "target_id", "comp": "comp_id"})
    r = r[r["target_id"].isin(targets) & r["target_id"].ne(r["comp_id"])].copy()
    r["rank"] = pd.to_numeric(r["rank"]).astype(int)
    r = r[[(t, c) not in exclude for t, c in zip(r["target_id"], r["comp_id"])]]
    order = {t: i for i, t in enumerate(targets)}
    r = r.assign(_t=r["target_id"].map(order)).sort_values(["_t", "rank", "comp_id"], kind="mergesort")
    r = r.groupby("target_id", sort=False).head(per_target).drop(columns="_t")
    r["b3_selected"] = [(t, c) in selected for t, c in zip(r["target_id"], r["comp_id"])]
    r["band"] = [band(k, s) for k, s in zip(r["rank"], r["b3_selected"])]
    r["audit_order"] = r.groupby("target_id").cumcount() + 1
    return r[[*KEY, "rank", "similarity", "b3_selected", "band", "audit_order"]].reset_index(drop=True)


def target_table(labels: pd.DataFrame, anchors: pd.DataFrame, selected: pd.DataFrame,
                 sheet_keys: set[tuple[str, str]]) -> pd.DataFrame:
    """One row per v3_final target: B3 list size, how much of it is on the sheet, in-list label counts (v3_final:
    grade 2 direct, 1 adjacent, 0 not), the anchor pairs' final scores, and the pool it may be drawn from."""
    g = labels.groupby("target_id")
    t = pd.DataFrame({"target_ticker": g["target_ticker"].first(),
                      "inlist_direct": g["grade"].apply(lambda s: int(s.eq(2).sum())),
                      "inlist_adjacent": g["grade"].apply(lambda s: int(s.eq(1).sum())),
                      "inlist_not": g["grade"].apply(lambda s: int(s.eq(0).sum())),
                      "inlist_labelled": g.size()})
    sel = selected.groupby("target_id")
    t["b3_list_size"] = sel.size().reindex(t.index).fillna(0).astype(int)
    on = selected.assign(on=[(a, b) in sheet_keys for a, b in zip(selected["target_id"], selected["comp_id"])])
    t["b3_list_on_sheet"] = on.groupby("target_id")["on"].sum().reindex(t.index).fillna(0).astype(int)
    t["full_list_on_sheet"] = t["b3_list_size"].eq(t["b3_list_on_sheet"])
    note = anchors["comp_ticker"].astype(str) + " score " + anchors["score"].astype(int).astype(str)
    t["anchor_pairs"] = note.groupby(anchors["target_id"]).agg("; ".join).reindex(t.index).fillna("")
    t["anchor_direct"] = anchors["score"].eq(2).groupby(anchors["target_id"]).sum().reindex(t.index).fillna(0).astype(int)
    thin = t["full_list_on_sheet"] & t["inlist_direct"].eq(0) & t["anchor_direct"].eq(0)
    control = t["full_list_on_sheet"] & t["inlist_direct"].ge(CONTROL_MIN_DIRECT)
    t["pool"] = np.where(thin, "thin (no direct)", np.where(control, f"control (>= {CONTROL_MIN_DIRECT} direct)", ""))
    t["not_eligible_because"] = np.where(
        t["pool"].ne(""), "",
        np.where(~t["full_list_on_sheet"], "B3 list not all on the sheet",
                 np.where(t["inlist_direct"].eq(0), "anchor pair scored direct", "1 direct peer")))
    return t.reset_index().sort_values("target_id").reset_index(drop=True)


def draw(t: pd.DataFrame, seed: int = SEED, n_thin: int = N_THIN, n_control: int = N_CONTROL) -> pd.DataFrame:
    """Seeded draw (numpy default_rng(seed)): n_thin from the thin pool, then n_control from the control pool, each
    from the pool's target ids sorted. Adds group ("thin"/"control"/"") and draw_order."""
    rng = np.random.default_rng(seed)
    t = t.copy()
    t["group"], t["draw_order"] = "", 0
    n = 0
    for pool, group, k in (("thin", "thin", n_thin), ("control", "control", n_control)):
        ids = sorted(t.loc[t["pool"].str.startswith(pool), "target_id"])
        if len(ids) < k:
            raise SystemExit(f"{group} pool has {len(ids)} targets, need {k}")
        for tid in rng.choice(ids, size=k, replace=False).tolist():
            n += 1
            t.loc[t["target_id"].eq(tid), ["group", "draw_order"]] = [group, n]
    return t


# ---------------------------------------------------------------- inputs

def inputs() -> dict[str, Path]:
    cur = v2.current()
    cand = v2.path(cur["retrieval"]["candidates"])
    import direct_peer_pairs as dp
    return {"current_toml": v2.V2 / "current.toml", "b3_candidates": cand / "candidates.csv",
            "b3_ranking": cand / "ranking.csv.gz", "b3_run": cand / "run.json",
            "rubric_v3_sheet": v2.path(cur["rubric_v3"]["sheet"]),
            "v3_final": v2.path(cur["rubric_v3"]["final"]) / "final.csv",
            "judge_scores": v2.path(cur["rubric_v3"]["judge"]) / "scores" / "scores.csv",
            "universe": v2.path(cur["universe"]["universe"]), "split": v2.path(cur["universe"]["split"]),
            "general_facets": v2.path(cur["profiles"]["general"]), "business_scopes": dp.SCOPES,
            "judge_v3.py": v2.V2 / "06_labels" / "scripts" / "judge_v3.py",
            "judge_v3_prompt.py": v2.V2 / "06_labels" / "scripts" / "judge_v3_prompt.py",
            "rubric_v3.py": v2.V2 / "06_labels" / "scripts" / "rubric_v3.py",
            "extend_label_book.py": v2.V2 / "06_labels" / "scripts" / "extend_label_book.py",
            "direct_peer_pairs.py": v2.V2 / "05_agent_grading" / "scripts" / "direct_peer_pairs.py",
            "recall_audit.py": Path(__file__).resolve()}


def b3_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The pinned B3 run: full ranking (target, comp, rank, similarity) and the selected lists (target_id,
    comp_id)."""
    src = inputs()
    ranking = pd.read_csv(src["b3_ranking"], dtype={"target": str, "comp": str},
                          usecols=["target", "rank", "comp", "similarity"])
    c = pd.read_csv(src["b3_candidates"], dtype=str)
    sel = c[c["selected"].str.casefold() == "true"].rename(columns={"target": "target_id", "comp": "comp_id"})
    return ranking, sel[KEY].reset_index(drop=True)


def sheet_pairs() -> pd.DataFrame:
    import judge_v3 as jv
    return jv.descriptions().reset_index(drop=True)


def final_with_anchors() -> pd.DataFrame:
    f = pd.read_csv(inputs()["v3_final"], dtype={"target_id": str, "comp_id": str}, encoding="utf-8-sig")
    f["is_anchor"] = f["is_anchor"].astype(str).str.casefold().isin(["true", "1"])
    return f


def describe(pairs: pd.DataFrame) -> pd.DataFrame:
    """The sheet's description columns for (target_id, comp_id) pairs, built by the code that built the label
    workbook's rows (extend_label_book.rows_for, with no agent verdicts), then rubric_v3.pair_pool's gap fill from
    the facet table (offering, customers, company), which must find nothing to fill."""
    import extend_label_book as elb
    import rubric_v3 as r3
    p = pairs.rename(columns={"target_id": "target", "comp_id": "comp"})[["target", "comp"]].reset_index(drop=True)
    p = p.assign(rank=np.nan, similarity=np.nan)
    verdicts = pd.DataFrame(columns=["target", "comp", "score", "verdict", "reason", "status"])
    rows = elb.rows_for(p, verdicts, "recall_audit")
    out = rows[[*KEY, *r3.DESCRIPTION]].copy()
    for side in ("target", "comp"):
        for col in (f"{side}_offering", f"{side}_customers", f"{side}_company"):
            blank = out[col].isna() | out[col].astype(str).str.strip().eq("")
            if blank.any():
                raise SystemExit(f"{int(blank.sum())} blank {col} cells: rubric_v3.pair_pool would fill them from "
                                 "the facet table; this builder does not, so it stops")
    return out.fillna("").astype(str)


def repro_check(sheet: pd.DataFrame) -> pd.DataFrame:
    """Rebuild the description columns of every sheet pair and compare cell by cell with the sheet."""
    import rubric_v3 as r3
    built = describe(sheet[KEY]).set_index(KEY)
    s = sheet.set_index(KEY)
    rows = []
    for col in r3.DESCRIPTION:
        same = built[col].reindex(s.index).eq(s[col].astype(str))
        rows.append({"column": col, "sheet_pairs": len(s), "identical": int(same.sum()),
                     "differ": int((~same).sum()), "first_differing_pair": "" if same.all()
                     else str(s.loc[~same, "pair"].iloc[0])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- run dir

class Audit:
    def __init__(self, out: Path):
        self.out = Path(out)

    def save(self, relative: str, value) -> Path:
        path = self.out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            hist = self.out / "history" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") / relative
            hist.parent.mkdir(parents=True, exist_ok=True)
            path.replace(hist)
        if isinstance(value, pd.DataFrame):
            value.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            path.write_text(value if isinstance(value, str) else json.dumps(value, indent=1, ensure_ascii=False,
                                                                           default=str), encoding="utf-8")
        return path

    def read(self, name: str) -> pd.DataFrame:
        return pd.read_csv(self.out / name, dtype={"target_id": str, "comp_id": str, "pair": str},
                           encoding="utf-8-sig", keep_default_na=False)

    def manifest(self) -> dict:
        return json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))

    def log_command(self, step: str, command: str, **extra) -> None:
        man = self.manifest()
        man.setdefault("commands", []).append({"step": step, "command": command, "at": now_iso(), **extra})
        self.save("manifest.json", man)

    def judge_desc(self) -> pd.DataFrame:
        """The audit sheet as judge_v3.Run reads it: indexed by pair, is_anchor False, description columns."""
        import judge_v3_prompt as jp
        s = self.read("audit_sheet.csv")
        s["is_anchor"] = False
        return s[["pair", *KEY, "is_anchor", *jp.PAIR_COLUMNS]].set_index("pair", drop=False)


def build(out: Path | None, command: str) -> Path:
    import cohorts
    src = inputs()
    sheet = sheet_pairs()
    sheet_keys = set(zip(sheet["target_id"], sheet["comp_id"]))
    ranking, selected = b3_tables()
    labels = cohorts.load("v3_final")
    fin = final_with_anchors()
    tick = sheet.set_index("comp_id")["comp_ticker"].to_dict()
    anchors = fin[fin["is_anchor"]].assign(comp_ticker=lambda d: d["comp_id"].map(tick))
    t = draw(target_table(labels, anchors, selected, sheet_keys))
    chosen = t[t["draw_order"].gt(0)].sort_values("draw_order")
    cands = audit_candidates(ranking, sheet_keys, chosen["target_id"].tolist(),
                             set(zip(selected["target_id"], selected["comp_id"])))
    if len(cands) > MAX_PAIRS:
        raise SystemExit(f"{len(cands)} pairs > cap {MAX_PAIRS}")
    split = pd.read_csv(src["split"], dtype=str).set_index("IQ_COMPANY_ID")["sample"]
    if not cands["comp_id"].map(split).eq("training").all():
        raise SystemExit("a candidate comp is not a training company")
    cands.insert(0, "pair", [f"A{i:03d}" for i in range(1, len(cands) + 1)])
    cands = cands.merge(chosen[["target_id", "group"]], on="target_id", how="left")
    desc = describe(cands[KEY])
    sheet_out = cands[["pair", *KEY]].assign(is_anchor=0).merge(desc, on=KEY, how="left", validate="one_to_one")
    cands.insert(3, "target_ticker", sheet_out["target_ticker"].to_numpy())
    cands.insert(4, "comp_ticker", sheet_out["comp_ticker"].to_numpy())
    check = repro_check(sheet)

    out = out or OUT_ROOT / f"{stamp()}_{LABEL}"
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} exists and is not empty; build writes a new dir")
    a = Audit(out)
    man = {"label": LABEL, "status": "EXPERIMENTAL recall audit (Michael approved 2026-11-28); judge-only labels on "
                                      "the new pairs, not reviewer labels; not a pipeline input",
           "question": "thin comp profiles: few true peers in the universe, or peers missed by B3's retrieval list?",
           "created_at": now_iso(), "seed": SEED,
           "design": {"thin_targets": N_THIN, "control_targets": N_CONTROL,
                      "thin_pool": "v3_final targets, whole B3 selected list on the rubric v3 sheet, no grade-2 pair "
                                   "in v3_final and no anchor pair scored 2 in the pinned final labels",
                      "control_pool": f"v3_final targets, whole B3 selected list on the sheet, >= {CONTROL_MIN_DIRECT} "
                                      "grade-2 pairs in v3_final",
                      "draw": "numpy default_rng(seed); thin pool (sorted ids) first, then control pool",
                      "candidates": "pinned B3 ranking (training pool), comps not on the rubric v3 sheet for the "
                                    f"target, target excluded, rank order, up to {PER_TARGET} per target",
                      "bands": BANDS, "cap_pairs": MAX_PAIRS, "cap_calls": MAX_CALLS,
                      "descriptions": "extend_label_book.rows_for (direct_peer_pairs.shown_companies + scope notes); "
                                      "pair_pool facet gap fill checked to be a no-op",
                      "judge": {**JUDGE, "prompt": "judge_v3_prompt.py (version recorded in judge/manifest.json)"}},
           "inputs": {k: {"path": rel(p), "sha256": sha_file(p)} for k, p in src.items()},
           "counts": {"eligible_thin": int(t["pool"].str.startswith("thin").sum()),
                      "eligible_control": int(t["pool"].str.startswith("control").sum()),
                      "targets": int(len(chosen)), "pairs": int(len(cands)),
                      "pairs_by_band": cands["band"].value_counts().reindex(BANDS).fillna(0).astype(int).to_dict()},
           "repro_check": {"sheet_pairs": int(len(sheet)), "all_identical": bool(check["differ"].eq(0).all())},
           "commands": []}
    a.save("manifest.json", man)
    a.save("targets.csv", t)
    a.save("candidates.csv", cands)
    a.save("audit_sheet.csv", sheet_out)
    a.save("repro_check.csv", check)
    a.log_command("build", command)
    print(f"[{LABEL}] wrote {out}")
    print(chosen[["draw_order", "target_ticker", "group", "b3_list_size", "inlist_direct", "inlist_adjacent",
                  "inlist_not", "anchor_pairs"]].to_string(index=False))
    print(cands.groupby(["group", "band"]).size().unstack(fill_value=0).to_string())
    print("repro check (all 323 sheet pairs):", "all identical" if man["repro_check"]["all_identical"]
          else check.to_string(index=False))
    return out


def dry_run(out: Path, command: str) -> dict:
    import judge_v3 as jv
    import judge_v3_prompt as jp
    a = Audit(out)
    desc = a.judge_desc()
    run = jv.Run(out / "judge", JUDGE["backend"], JUDGE["model"], JUDGE["name"], JUDGE["effort"])
    run.check_settings()
    pairs = list(desc.index)
    todo = [p for p in pairs if not run.done(p, run.fingerprint(jv.build_prompt(desc.loc[p])))]
    leaks, keys_ok = [], True
    for p in pairs:
        prompt = jv.build_prompt(desc.loc[p])
        if not prompt.startswith(jp.INSTRUCTIONS):
            raise SystemExit(f"{p}: prompt does not start with the guide")
        part = prompt[len(jp.INSTRUCTIONS):]
        keys = re.findall(r"^([a-z_]+): ", part, flags=re.M)
        keys_ok &= sorted(keys) == sorted(jp.PAIR_COLUMNS)
        low = part.casefold()
        leaks += [{"pair": p, "word": w} for w in LEAK_WORDS if re.search(rf"(?<![a-z]){re.escape(w)}", low)]
    first = pairs[0]
    a.save(f"dry_run/prompt_{first}.txt", jv.build_prompt(desc.loc[first]))
    leak_df = pd.DataFrame(leaks, columns=["pair", "word"])
    a.save("dry_run/leak_hits.csv", leak_df)
    info = {"label": LABEL, "pairs": len(pairs), "calls_to_make": len(todo), "max_calls": MAX_CALLS,
            "pair_part_keys_are_exactly_the_sheet_columns": bool(keys_ok), "leak_word_hits": len(leak_df),
            "leak_words": LEAK_WORDS, "prompt_version": jp.PROMPT_VERSION, "judge": JUDGE,
            "sample_prompt": f"dry_run/prompt_{first}.txt", "at": now_iso()}
    a.save("dry_run/dry_run.json", info)
    a.log_command("dry-run", command, calls_to_make=len(todo))
    print(json.dumps(info, indent=1))
    if len(leak_df):
        print(leak_df.groupby("word").size().to_string())
    return info


def run(out: Path, command: str, max_failures: int, limit: int | None) -> dict:
    import judge_v3 as jv
    a = Audit(out)
    desc = a.judge_desc()
    pairs = list(desc.index)[:limit] if limit else list(desc.index)
    if len(pairs) > MAX_CALLS:
        raise SystemExit(f"{len(pairs)} pairs > {MAX_CALLS} calls")
    r = jv.Run(out / "judge", JUDGE["backend"], JUDGE["model"], JUDGE["name"], JUDGE["effort"])
    print(f"[{LABEL}] recall audit judge run -> {out / 'judge'}")
    counts = r.run(pairs, desc, "recall_audit" + (f"_first{limit}" if limit else ""), command, max_failures)
    man = r.manifest()
    man["recall_audit"] = {"label": LABEL, "audit_sheet": rel(out / "audit_sheet.csv"),
                           "audit_sheet_sha256": sha_file(out / "audit_sheet.csv"),
                           "note": "pairs come from the audit sheet (inputs/pairs_*.csv), not the rubric v3 sheet; "
                                   "files.sheet and sha256.sheet are what judge_v3.Run records by default"}
    r.save("manifest.json", man)
    a.log_command("run", command, counts=counts)
    return counts


def collect(out: Path, command: str) -> dict[str, pd.DataFrame]:
    import cohorts
    import judge_v3 as jv
    import rubric_v3 as r3
    a = Audit(out)
    name = JUDGE["name"]
    cands, targets = a.read("candidates.csv"), a.read("targets.csv")
    records = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (out / "judge" / "answers").glob("*.json")}
    rows = []
    for _, c in cands.iterrows():
        rec = records.get(c["pair"], {})
        ans = rec.get("answer", {}) if rec.get("status") == "ok" else {}
        row = {"pair": c["pair"], "target_id": c["target_id"], "comp_id": c["comp_id"], "is_anchor": 0}
        for q in jv.ANSWERS:
            row[f"{q}_{name}"] = ans.get(q, "")
        row[f"unsure_{name}"] = ", ".join(ans.get("unsure", []))
        row[f"business_graded_{name}"] = ans.get("business_graded", "")
        row[f"notes_{name}"] = ans.get("reason", "")
        row["judge_status"] = rec.get("status", "not_run")
        rows.append(row)
    answers = pd.DataFrame(rows)
    problems = r3.check_sheet(answers, [name])
    bad = problems[problems["problem"] != "not scored yet"]
    if len(bad):
        raise SystemExit("answers fail rubric_v3 check:\n" + bad.to_string(index=False))
    scored = r3.scores(answers, [name])
    answers[f"score_{name}"] = scored[f"score_{name}"].to_numpy()
    a.save("judge_answers.csv", answers)

    s = answers.set_index("pair")
    p = cands.copy()
    p["judge_status"] = p["pair"].map(s["judge_status"])
    p["judge_score"] = p["pair"].map(s[f"score_{name}"])
    p["judge_overall_call"] = p["pair"].map(s[f"overall_call_{name}"])
    for q in r3.QUESTIONS:
        p[f"judge_{q}"] = p["pair"].map(s[f"{q}_{name}"])
    p["judge_reason"] = p["pair"].map(s[f"notes_{name}"])
    a.save("pairs.csv", p)

    # the same judge on the in-list (labelled) pairs of these targets, from the pinned judge run (like for like)
    js = pd.read_csv(inputs()["judge_scores"], dtype={"target_id": str, "comp_id": str}, encoding="utf-8-sig")
    js = js[~js["is_anchor"].astype(str).str.casefold().isin(["true", "1"])]
    lab = cohorts.load("v3_final")[KEY]
    js = js.merge(lab, on=KEY)
    chosen = targets[targets["draw_order"].astype(int).gt(0)].sort_values("draw_order", key=lambda x: x.astype(int))

    def counts(d: pd.DataFrame, col: str) -> dict:
        g = pd.to_numeric(d[col], errors="coerce")
        return {"direct": int(g.eq(2).sum()), "adjacent": int(g.eq(1).sum()), "not": int(g.eq(0).sum())}

    per = []
    for _, t in chosen.iterrows():
        d = p[p["target_id"].eq(t["target_id"])]
        ok = d[d["judge_status"].eq("ok")]
        new = counts(ok, "judge_score")
        jin = counts(js[js["target_id"].eq(t["target_id"])], f"score_{name}")
        direct_ranks = ok.loc[pd.to_numeric(ok["judge_score"]).eq(2), "rank"].astype(int).tolist()
        per.append({"draw_order": int(t["draw_order"]), "target_ticker": t["target_ticker"], "group": t["group"],
                    "b3_list_size": int(t["b3_list_size"]),
                    "inlist_direct": int(t["inlist_direct"]), "inlist_adjacent": int(t["inlist_adjacent"]),
                    "inlist_not": int(t["inlist_not"]), "anchor_pairs": t["anchor_pairs"],
                    "inlist_judge_direct": jin["direct"], "inlist_judge_adjacent": jin["adjacent"],
                    "inlist_judge_not": jin["not"],
                    "new_candidates": len(d), "new_judged": len(ok), "new_rank_range": f"{d['rank'].astype(int).min()}-{d['rank'].astype(int).max()}",
                    "new_judge_direct": new["direct"], "new_judge_adjacent": new["adjacent"],
                    "new_judge_not": new["not"],
                    "new_overall_call_yes": int(ok["judge_overall_call"].astype(str).str.casefold().eq("yes").sum()),
                    "new_direct_ranks": " ".join(map(str, direct_ranks)), "target_id": t["target_id"]})
    per = pd.DataFrame(per)
    a.save("per_target.csv", per)

    num = [c for c in per.columns if c.startswith(("inlist_", "new_", "b3_list")) and per[c].dtype.kind in "iu"]
    grp = per.groupby("group", sort=False)[num].sum()
    grp.insert(0, "targets", per.groupby("group", sort=False).size())
    grp["targets_with_new_direct"] = per.groupby("group", sort=False)["new_judge_direct"].apply(lambda s: int(s.gt(0).sum()))
    grp["new_direct_rate"] = grp["new_judge_direct"] / grp["new_judged"]
    grp["new_peer_rate"] = (grp["new_judge_direct"] + grp["new_judge_adjacent"]) / grp["new_judged"]
    grp["inlist_direct_rate"] = grp["inlist_direct"] / (grp["inlist_direct"] + grp["inlist_adjacent"] + grp["inlist_not"])
    grp["inlist_judge_direct_rate"] = grp["inlist_judge_direct"] / (
        grp["inlist_judge_direct"] + grp["inlist_judge_adjacent"] + grp["inlist_judge_not"])
    grp = grp.reset_index()
    a.save("by_group.csv", grp)

    def band_table(d: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
        ok = d[d["judge_status"].eq("ok")].assign(sc=lambda x: pd.to_numeric(x["judge_score"]))
        b = d.groupby(keys, observed=False).size().rename("candidates").to_frame()
        b["judged"] = ok.groupby(keys, observed=False).size()
        b["judge_direct"] = ok[ok["sc"].eq(2)].groupby(keys, observed=False).size()
        b["judge_adjacent"] = ok[ok["sc"].eq(1)].groupby(keys, observed=False).size()
        b["judge_not"] = ok[ok["sc"].eq(0)].groupby(keys, observed=False).size()
        b = b.fillna(0).astype(int)
        b["direct_rate"] = b["judge_direct"] / b["judged"].replace(0, np.nan)
        b["peer_rate"] = (b["judge_direct"] + b["judge_adjacent"]) / b["judged"].replace(0, np.nan)
        return b.reset_index()

    p["band"] = pd.Categorical(p["band"], BANDS, ordered=True)
    by_band = band_table(p, ["band"])
    by_band = by_band[by_band["candidates"].gt(0)]
    a.save("by_band.csv", by_band)
    bbg = band_table(p, ["group", "band"])
    bbg = bbg[bbg["candidates"].gt(0)]
    a.save("by_band_group.csv", bbg)
    a.log_command("collect", command, judged_ok=int(answers["judge_status"].eq("ok").sum()))
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(f"[{LABEL}] {int(answers['judge_status'].eq('ok').sum())} of {len(answers)} pairs answered")
        print(per.drop(columns=["target_id", "anchor_pairs"]).to_string(index=False))
        print(grp.to_string(index=False))
        print(by_band.to_string(index=False))
        print(bbg.to_string(index=False))
    return {"answers": answers, "pairs": p, "per_target": per, "by_group": grp, "by_band": by_band}


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="targets, candidates, audit sheet, repro check (no model calls)")
    b.add_argument("--out", type=Path)
    d = sub.add_parser("dry-run", help="render prompts, count calls, leak check (no model calls)")
    d.add_argument("dir", type=Path)
    r = sub.add_parser("run", help="judge calls, one at a time (resumable)")
    r.add_argument("dir", type=Path)
    r.add_argument("--max-failures", type=int, default=3)
    r.add_argument("--limit", type=int, help="only the first N pairs (a pilot)")
    c = sub.add_parser("collect", help="judge_answers.csv and the summary tables")
    c.add_argument("dir", type=Path)
    args = ap.parse_args(argv)
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
    command = "uv run python v2/09_analysis/scripts/recall_audit.py " + " ".join(
        shlex.quote(x) for x in (argv if argv is not None else _sys.argv[1:]))
    if args.cmd == "build":
        build(args.out, command)
    elif args.cmd == "dry-run":
        dry_run(args.dir, command)
    elif args.cmd == "run":
        run(args.dir, command, args.max_failures, args.limit)
    else:
        collect(args.dir, command)


if __name__ == "__main__":
    main()
