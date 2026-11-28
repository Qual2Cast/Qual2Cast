"""The rubric v3 LLM judge (tie-breaker): one CLI call per pair, answering the overall call and the four questions.

The judge is one more reviewer column set (<question>_<name>, e.g. same_product_terra). It sees only the guide
(judge_v3_prompt.INSTRUCTIONS, quoted from RUBRIC_V3.md) and the pair's description columns from the blank sheet
pinned in current.toml [rubric_v3] sheet, as the reviewers saw them: never a reviewer's answer, note or score, and
never a method, rank, similarity or financial column. Running it needs Michael's approval (RUBRIC_V3.md).

  uv run python v2/06_labels/scripts/judge_v3.py prompt P318
  uv run python v2/06_labels/scripts/judge_v3.py run --backend codex --model gpt-5.6-terra --name terra --pairs pilot
  uv run python v2/06_labels/scripts/judge_v3.py run ... --pairs all --out <pilot run dir>   # resumes, reuses the pilot
  uv run python v2/06_labels/scripts/judge_v3.py collect <run dir>

--pairs: pilot (the 12 anchors + 20 seeded outcome-split pairs), all (323), split (pairs where Matthew and Barbara
differ on direct or on peer, from the pinned scores: 83), anchors (12), or a file of pair ids (one per line, or a
.csv with a `pair` column).

A run dir holds manifest.json, inputs/ (instructions, schema, the selected pairs' description columns),
runs/<pair>/<stamp>/ (call_cli's prompt, raw output and response), answers/<pair>.json (the parsed answer and
status), logs/, and after `collect`: judge_answers.csv, filled_with_<name>.csv and scores/. Rerunning with the same
--out skips pairs that already have a parsed answer under the same prompt and settings. The run stops cleanly after
--max-failures consecutive failures (default 3) or at once on a usage-limit error, keeping what is done.
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

import cli_models
import judge_v3_prompt as jp
import rubric_v3 as r3

HUMANS = ["matthew", "barbara"]
YES_NO = ["yes", "no"]
UNSURE = ["product", "customers", "revenue_model", "chain_step", "overall"]
ANSWERS = [r3.OVERALL, *r3.QUESTIONS]                 # overall call first, then the four (the guide's order)
PILOT_SPLIT = 20
SEED = r3.SEED
MAX_FAILURES = 3
PROMPT_FILE = Path(jp.__file__).resolve()
GUIDE_FILE = v2.V2 / "06_labels" / "RUBRIC_V3.md"


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- inputs

def pinned() -> dict[str, Path]:
    c = v2.current()["rubric_v3"]
    return {"sheet": v2.path(c["sheet"]), "filled": v2.path(c["filled"]), "scores": v2.path(c["scores"])}


def descriptions(sheet_path: Path | None = None) -> pd.DataFrame:
    """The blank sheet's pairs: pair, ids, is_anchor and the description columns only (nothing a reviewer wrote)."""
    sheet = r3._read(sheet_path or pinned()["sheet"])
    keep = ["pair", *r3.KEY, "is_anchor", *jp.PAIR_COLUMNS]
    missing = [c for c in keep if c not in sheet.columns]
    if missing:
        raise SystemExit(f"the sheet lacks {missing}")
    out = sheet[keep].copy()
    out["is_anchor"] = r3._is_anchor(sheet).to_numpy()
    return out.set_index("pair", drop=False)


def build_prompt(row) -> str:
    """The full prompt for one pair: only the description columns go in, whatever else the row holds."""
    return jp.build_prompt({c: row[c] for c in jp.PAIR_COLUMNS})


def answer_schema() -> dict:
    yn = {"type": "string", "enum": YES_NO}
    props = {q: yn for q in ANSWERS}
    props["business_graded"] = {"type": "string"}
    props["unsure"] = {"type": "array", "items": {"type": "string", "enum": UNSURE}}
    props["reason"] = {"type": "string"}
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def split_pairs(scores_dir: Path | None = None, humans=HUMANS) -> list[str]:
    """Scored (non-anchor) pairs where the two reviewers reach a different outcome: direct (score 2 vs not) or peer
    (score >= 1 vs 0), from the pinned scores.csv."""
    s = pd.read_csv(Path(scores_dir or pinned()["scores"]) / "scores.csv", dtype={"pair": str})
    s = s[~s["is_anchor"].astype(str).str.casefold().isin(["true", "1"])]
    a, b = (s[f"score_{h}"] for h in humans)
    split = (a.eq(2) != b.eq(2)) | (a.ge(1) != b.ge(1))
    return s.loc[split & a.notna() & b.notna(), "pair"].tolist()


def select_pairs(which: str, desc: pd.DataFrame, scores_dir: Path | None = None) -> list[str]:
    """Pair ids in sheet order for a --pairs choice."""
    order = list(desc.index)
    anchors = [p for p in order if desc.at[p, "is_anchor"]]
    if which == "all":
        chosen = set(order)
    elif which == "anchors":
        chosen = set(anchors)
    elif which == "split":
        chosen = set(split_pairs(scores_dir))
    elif which == "pilot":
        split = sorted(split_pairs(scores_dir))
        rng = np.random.default_rng(SEED)
        chosen = set(anchors) | set(rng.choice(split, size=min(PILOT_SPLIT, len(split)), replace=False).tolist())
    else:
        path = Path(which)
        if not path.exists():
            raise SystemExit(f"--pairs {which!r}: not pilot/all/split/anchors and not a file")
        if path.suffix.lower() == ".csv":
            ids = pd.read_csv(path, dtype=str)["pair"].dropna().str.strip().tolist()
        else:
            ids = [t for t in re.split(r"[\s,]+", path.read_text(encoding="utf-8-sig")) if t]
        unknown = sorted(set(ids) - set(order))
        if unknown:
            raise SystemExit(f"unknown pair ids in {path}: {unknown[:10]}")
        chosen = set(ids)
    return [p for p in order if p in chosen]


# ---------------------------------------------------------------- run

class Run:
    """One judge run dir. Settings (backend, model, effort, name, prompt) are fixed per dir; pair selections can
    grow (pilot first, then all, reusing the pilot's answers)."""

    def __init__(self, out: Path, backend: str, model: str, name: str, effort: str | None = None,
                 timeout: int = 600):
        if backend not in ("codex", "claude-cli"):
            raise SystemExit("--backend must be codex or claude-cli")
        if not re.fullmatch(r"[a-z][a-z0-9]*", name) or name in r3.REVIEWERS:
            raise SystemExit(f"--name {name!r}: lowercase letters/digits, not a human reviewer's name")
        self.out, self.backend, self.model, self.name, self.effort, self.timeout = \
            Path(out), backend, model, name, effort, timeout
        self.settings = {"backend": backend, "model": model, "effort": effort, "name": name,
                         "prompt_version": jp.PROMPT_VERSION, "instructions_sha256": sha_text(jp.INSTRUCTIONS),
                         "schema": answer_schema()}

    def save(self, relative: str, value) -> Path:
        """Write a file in the run dir; a file it replaces moves to history/<stamp>/ first."""
        path = self.out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            hist = self.out / "history" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") / relative
            hist.parent.mkdir(parents=True, exist_ok=True)
            path.replace(hist)
        if isinstance(value, pd.DataFrame):
            value.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            path.write_text(value if isinstance(value, str) else json.dumps(value, indent=1, ensure_ascii=False),
                            encoding="utf-8")
        return path

    def manifest(self) -> dict:
        path = self.out / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def check_settings(self) -> None:
        old = self.manifest()
        if old and old.get("settings") != json.loads(json.dumps(self.settings)):
            raise SystemExit(f"{self.out} was run with other settings (backend, model, effort, name or prompt); "
                             "use a new --out")

    def fingerprint(self, prompt: str) -> str:
        return sha_text(json.dumps([self.backend, self.model, self.effort, answer_schema(), prompt], sort_keys=True))

    def done(self, pair: str, fp: str) -> bool:
        path = self.out / "answers" / f"{pair}.json"
        if not path.exists():
            return False
        old = json.loads(path.read_text(encoding="utf-8"))
        return old.get("status") == "ok" and old.get("fingerprint") == fp

    def call(self, pair: str, row: pd.Series) -> dict:
        prompt = build_prompt(row)
        fp = self.fingerprint(prompt)
        run_dir = self.out / "runs" / pair / stamp()
        result = cli_models.call_cli(prompt, run_dir, answer_schema(), self.backend, self.model or None,
                                     self.effort, self.timeout,
                                     instructions_len=len(jp.INSTRUCTIONS) if self.backend == "claude-cli" else 0)
        record = {"pair": pair, "target_id": row["target_id"], "comp_id": row["comp_id"],
                  "is_anchor": bool(row["is_anchor"]), "name": self.name, "backend": self.backend,
                  "model": self.model, "effort": self.effort, "prompt_version": jp.PROMPT_VERSION,
                  "fingerprint": fp, "run_dir": str(run_dir.relative_to(self.out)).replace("\\", "/"),
                  "finished_at": now_iso(), "status": result["llm_status"]}
        if result["llm_status"] == "ok":
            try:
                record["answer"] = check_answer(json.loads(result["text"]))
            except (ValueError, KeyError, TypeError) as exc:
                record.update(status="invalid_answer", error=str(exc))
        else:
            record["error"] = result.get("error", result["llm_status"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(json.dumps({k: v for k, v in result.items() if k != "text"}, indent=1,
                                                     default=str), encoding="utf-8")
        self.save(f"answers/{pair}.json", record)
        record["stop_run"] = bool(result.get("stop_run"))
        return record

    def run(self, pairs: list[str], desc: pd.DataFrame, selection: str, command: str,
            max_failures: int = MAX_FAILURES) -> dict:
        self.check_settings()
        self.out.mkdir(parents=True, exist_ok=True)
        started = now_iso()
        man = self.manifest()
        if not man:
            p = pinned()
            man = {"settings": self.settings, "backend": self.backend, "model": self.model, "effort": self.effort,
                   "name": self.name, "prompt_version": jp.PROMPT_VERSION, "created_at": started,
                   "sha256": {"guide": sha_file(GUIDE_FILE), "prompt_template": sha_file(PROMPT_FILE),
                              "instructions_text": sha_text(jp.INSTRUCTIONS), "sheet": sha_file(p["sheet"]),
                              "scores": sha_file(p["scores"] / "scores.csv")},
                   "files": {"guide": "v2/06_labels/RUBRIC_V3.md",
                             "prompt_template": "v2/06_labels/scripts/judge_v3_prompt.py",
                             "sheet": v2.current()["rubric_v3"]["sheet"],
                             "scores": v2.current()["rubric_v3"]["scores"]},
                   "sessions": []}
            self.save("inputs/instructions.txt", jp.INSTRUCTIONS)
            self.save("inputs/schema.json", answer_schema())
        self.save(f"inputs/pairs_{stamp()}.csv", desc.loc[pairs, ["pair", *r3.KEY, "is_anchor", *jp.PAIR_COLUMNS]])
        counts = {"selected": len(pairs), "skipped_done": 0, "ok": 0, "failed": 0, "not_run": 0}
        session = {"selection": selection, "command": command, "started_at": started, "ended_at": None,
                   "pairs": pairs, "counts": counts, "stopped": ""}
        man["sessions"].append(session)
        self.save("manifest.json", man)
        log = self.out / "logs" / f"run_{stamp()}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        streak = 0
        with log.open("w", encoding="utf-8") as lf:
            def say(line):
                print(line, flush=True)
                lf.write(line + "\n")
            say(f"{len(pairs)} pairs ({selection}); {self.backend} {self.model} effort={self.effort} "
                f"name={self.name} prompt {jp.PROMPT_VERSION}; out {self.out}")
            for n, pair in enumerate(pairs, 1):
                row = desc.loc[pair]
                if self.done(pair, self.fingerprint(build_prompt(row))):
                    counts["skipped_done"] += 1
                    continue
                rec = self.call(pair, row)
                ok = rec["status"] == "ok"
                counts["ok" if ok else "failed"] += 1
                streak = 0 if ok else streak + 1
                say(f"[{n}/{len(pairs)}] {pair} {row['target_ticker']}-{row['comp_ticker']}: {rec['status']}"
                    + ("" if ok else f" {str(rec.get('error', ''))[:200]}"))
                if rec["stop_run"] or streak >= max_failures:
                    session["stopped"] = ("fatal CLI error (usage limit or login)" if rec["stop_run"]
                                          else f"{streak} consecutive failures")
                    say(f"stopping: {session['stopped']}; finished pairs are kept; rerun with --out {self.out}")
                    break
        counts["not_run"] = counts["selected"] - counts["skipped_done"] - counts["ok"] - counts["failed"]
        session["ended_at"] = now_iso()
        man["answered_ok"] = sum(1 for p in (self.out / "answers").glob("*.json")
                                 if json.loads(p.read_text(encoding="utf-8")).get("status") == "ok")
        self.save("manifest.json", man)
        print(json.dumps(counts))
        return counts


def check_answer(raw: dict) -> dict:
    """Validate one response against the schema; returns the answer with unsure de-duplicated."""
    if not isinstance(raw, dict):
        raise ValueError("answer is not an object")
    out = {}
    for q in ANSWERS:
        v = str(raw[q]).strip().casefold()
        if v not in YES_NO:
            raise ValueError(f"{q}: {raw[q]!r} is not yes or no")
        out[q] = v
    unsure = raw["unsure"]
    if not isinstance(unsure, list) or any(u not in UNSURE for u in unsure):
        raise ValueError(f"unsure: {unsure!r}")
    out["unsure"] = list(dict.fromkeys(unsure))
    out["business_graded"] = str(raw["business_graded"]).strip()
    out["reason"] = str(raw["reason"]).strip()
    if not out["business_graded"] or not out["reason"]:
        raise ValueError("business_graded and reason must not be empty")
    return out


# ---------------------------------------------------------------- collect

def collect(run_dir: Path, filled_path: Path | None = None) -> dict[str, pd.DataFrame]:
    """judge_answers.csv (the judge's column set, sheet encoding), filled_with_<name>.csv (the pinned filled sheet
    plus the judge's columns; unanswered pairs blank) and scores/ (rubric_v3 scores on it)."""
    run_dir = Path(run_dir)
    man = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    name = man["name"]
    run = Run(run_dir, man["backend"], man["model"], name, man.get("effort"))
    filled = r3._read(filled_path or pinned()["filled"])
    if any(c in filled.columns for c in r3.columns(name)):
        raise SystemExit(f"the filled sheet already has {name}'s columns")
    selected = list(dict.fromkeys(p for s in man["sessions"] for p in s["pairs"]))
    records = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((run_dir / "answers").glob("*.json"))}
    by_pair = filled.set_index("pair")
    rows = []
    for pair in [p for p in filled["pair"] if p in set(selected) | set(records)]:
        rec = records.get(pair, {})
        a = rec.get("answer", {}) if rec.get("status") == "ok" else {}
        row = {"pair": pair, "target_id": by_pair.at[pair, "target_id"], "comp_id": by_pair.at[pair, "comp_id"],
               "is_anchor": by_pair.at[pair, "is_anchor"]}
        for q in ANSWERS:
            row[f"{q}_{name}"] = a.get(q, "")
        row[f"unsure_{name}"] = ", ".join(a.get("unsure", []))
        row[f"business_graded_{name}"] = a.get("business_graded", "")
        row[f"notes_{name}"] = a.get("reason", "")
        row["judge_status"] = rec.get("status", "not_run")
        rows.append(row)
    answers = pd.DataFrame(rows, columns=["pair", *r3.KEY, "is_anchor", *r3.columns(name), "judge_status"])
    with_judge = filled.merge(answers[["pair", *r3.columns(name)]], on="pair", how="left").fillna("")
    problems = r3.check_sheet(with_judge, [name])
    bad = problems[problems["problem"] != "not scored yet"]
    if len(bad):
        raise SystemExit("the judge's answers don't pass rubric_v3 check:\n" + bad.to_string(index=False))
    scored = r3.scores(with_judge)
    run.save("judge_answers.csv", answers)
    run.save(f"filled_with_{name}.csv", with_judge)
    run.save("scores/scores.csv", scored)
    run.save("scores/agreement.csv", r3.agreement(scored))
    run.save("scores/overall_vs_derived.csv", r3.overall_vs_derived(scored))
    ok = answers["judge_status"].eq("ok")
    print(f"{int(ok.sum())} of {len(answers)} selected pairs answered; judge score counts: "
          f"{scored[f'score_{name}'].value_counts(dropna=True).sort_index().to_dict()}")
    print(f"wrote {run_dir / 'judge_answers.csv'} and filled_with_{name}.csv; headline labels: "
          f"uv run python v2/06_labels/scripts/rubric_v3.py final {run_dir / f'filled_with_{name}.csv'} <out dir> "
          f"--judge {name}")
    return {"answers": answers, "filled": with_judge, "scores": scored}


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompt", help="print the prompt for one pair id")
    p.add_argument("pair")
    p.add_argument("--part", choices=["all", "instructions", "pair"], default="all")
    r = sub.add_parser("run", help="one CLI call per pair (needs approval)")
    r.add_argument("--backend", required=True, choices=["codex", "claude-cli"])
    r.add_argument("--model", required=True)
    r.add_argument("--name", required=True, help="column suffix, e.g. terra")
    r.add_argument("--effort")
    r.add_argument("--pairs", required=True, help="pilot, all, split, anchors or a file of pair ids")
    r.add_argument("--out", type=Path, help="run dir (default outputs-local/v2/06_labels/rubric_v3/judge/"
                                            "<name>_<UTC stamp>/); an existing dir resumes")
    r.add_argument("--max-failures", type=int, default=MAX_FAILURES)
    r.add_argument("--timeout", type=int, default=600)
    c = sub.add_parser("collect", help="judge_answers.csv and filled_with_<name>.csv from a run dir")
    c.add_argument("run_dir", type=Path)
    args = ap.parse_args(argv)
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "prompt":
        desc = descriptions()
        if args.pair not in desc.index:
            raise SystemExit(f"no pair {args.pair}")
        text = {"all": build_prompt(desc.loc[args.pair]), "instructions": jp.INSTRUCTIONS,
                "pair": jp.render_pair({c: desc.at[args.pair, c] for c in jp.PAIR_COLUMNS})}[args.part]
        print(text)
        return
    if args.cmd == "collect":
        collect(args.run_dir)
        return
    desc = descriptions()
    pairs = select_pairs(args.pairs, desc)
    out = args.out or v2.out("06_labels") / "rubric_v3" / "judge" / f"{args.name}_{stamp()}"
    command = "uv run python v2/06_labels/scripts/judge_v3.py " + " ".join(
        shlex.quote(a) for a in (argv if argv is not None else _sys.argv[1:]))
    Run(out, args.backend, args.model, args.name, args.effort, args.timeout).run(
        pairs, desc, args.pairs, command, args.max_failures)


if __name__ == "__main__":
    main()
