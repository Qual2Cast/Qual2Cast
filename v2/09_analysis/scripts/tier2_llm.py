"""EXPERIMENTAL llm_tier2 rule for the tier-2 fill of thin comp profiles (Michael approved 2026-11-28: one Claude CLI
call per target on his Claude subscription, and GPT-Terra labels for unlabelled picks, at most 100 Codex calls).
Labelled EXPERIMENTAL everywhere; not a pipeline input.

Tier 1 = the baseline selector's keeps (progress.built_in("selector"), prompt 2026-11-04a: "the same business").
For every v3_final target with fewer than 5 tier-1 comps, one call (claude-cli, claude-sonnet-5-5, sequential:
two parallel claude-cli calls can collide on the shared system file on Windows) shows the target and its
candidates = tier2_fill's b3_list_r11_15 pool (the B3 list minus tier 1, plus B3 ranks 11-15), each company
described exactly as the selector prompt 2026-11-04a describes it (cosine_then_llm.build_prompt: name, website,
Sonnet facets without company size, Fiona sub-sector; alphabetical labels C1, C2, ...; no rank, similarity, label,
multiple or any financial figure). Only the instructions differ (INSTRUCTIONS below, prompt version
tier2-2026-11-28a): up to 5 adjacent peers, ranked best first, or none; RUBRIC_V3.md questions 1 and 2 quoted.
For each k, tier 2 = the top (k - |tier 1|) of the ranked list (tier2_fill.fill, rule llm_tier2).

Labels: picks with no v3_final, anchor or recall-audit judge label get the rubric v3 judge (judge_v3.Run unchanged:
prompt judge_v3_prompt 2026-11-27a, codex, gpt-5.6-terra, name terra), descriptions from recall_audit.describe
(the builder that reproduces the sheet's description columns). Order: llm_tier2 picks (by the smallest k that uses
them, then target, then the model's rank), then agent_then_rank and b3_rank picks at k = 3 (pool b3_list_r11_15);
at most 100 calls; sequential; stops on usage limits. These labels are judge-only, never reviewer labels.

  uv run python v2/09_analysis/scripts/tier2_llm.py build [--out DIR]   # inputs + rendered prompts, no calls
  uv run python v2/09_analysis/scripts/tier2_llm.py run DIR             # Claude calls (resumable)
  uv run python v2/09_analysis/scripts/tier2_llm.py judge-build DIR     # unlabelled picks -> judge sheet
  uv run python v2/09_analysis/scripts/tier2_llm.py judge-run DIR       # Codex calls (resumable, capped)
  uv run python v2/09_analysis/scripts/tier2_llm.py score DIR           # judge collect + k sweep tables

DIR (default outputs-local/v2/09_analysis/tier2_fill/<UTC>_EXPERIMENTAL/) holds manifest.json, llm_tier2/ (manifest,
inputs, runs/<target>/<stamp>/ prompts and raw responses, answers/<target>.json, logs, picks.csv, status.csv),
judge/ (judge_v3.Run dir), judge_candidates.csv, judge_sheet.csv, judge_pairs.csv, and the sweep tables:
summary.csv, by_group.csv, picks.csv, targets.csv, llm_shortfall.csv, zero_keep_k3.csv. A replaced file moves to
history/<stamp>/ first. No financial table is read anywhere.
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
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import tier2_fill as tf

KEY = ["target_id", "comp_id"]
LABEL = "EXPERIMENTAL"
PROMPT_VERSION = "tier2-2026-11-28a"
SELECTOR_PROMPT_VERSION = "2026-11-04a"        # company descriptions exactly as this selector prompt shows them
BACKEND, MODEL = "claude-cli", "claude-sonnet-5-5"
MAX_PICKS = 5                                  # the model returns at most this many (k up to 5)
MAX_TIER1 = 5                                  # targets with fewer tier-1 comps than this get a call
POOL = "b3_list_r11_15"
JUDGE = {"backend": "codex", "model": "gpt-5.6-terra", "name": "terra", "effort": None}
MAX_JUDGE_CALLS = 100
JUDGE_EXTRA_K = 3                              # agent_then_rank and b3_rank picks at this k, after llm_tier2
MAX_FAILURES = 3
NONE_LABELS = {"", "none", "null", "n/a", "na", "-"}
OUT_ROOT = v2.out("09_analysis") / "tier2_fill"
# must not appear in the company part of a prompt (financial data, ranking or label columns)
LEAK_PATTERNS = [r"ebitda", r"enterprise value", r"\bev/", r"similarity", r"\bb3\b", r"\brank(ed)? \d",
                 r"\bscore\b", r"\bgrade\b", r"market cap"]

INSTRUCTIONS = """You help a private-equity analyst choose comparable public companies (comps) for a target company.

Below are the target and a list of candidate companies, each with its name, website and a description of its business model. Use the descriptions and what you know about the companies.

These candidates were judged not to be in the same business as the target. Some may still be adjacent peers. Return up to 5 candidates that are adjacent peers of the target, ranked best first. A candidate is an adjacent peer if either of these is true:

1. Same buyers, even if they buy something different: "Do the same buyers, in the same role, also buy from the comp, even if they buy something different from it?" Yes when the same buyers, in the same buying role, buy from both (the plant engineers who buy the target's heaters also buy the comp's pumps). The same industry or the same payer alone is not yes (Medicare paying both a NICU physician group and a hospice). For consumer businesses, "both sell to households" is not enough: the same customer segment must buy for the same kind of need.
2. Same kind of product, even if mostly sold to a different set of buyers: "Can a customer of the target buy the same kind of product or service from the comp instead?" Think of one actual buyer of the target. If that buyer can place the same order with the comp's main business, yes. The main business is the one the comp's description leads with. A smaller line of the comp is no, and so is the same broad category.

Rules:
- Return only candidates that meet 1 or 2, by label (C1, C2, ...), each at most once, best first, at most 5. Return an empty list if none qualify.
- The reason is one short sentence, at most twenty words, naming the shared buyers or the shared product.
- The note is one short sentence about the list as a whole (for example, why few or none qualify).
- Judge the business only. Do not use or mention valuations, multiples, share prices or financial figures."""


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path: Path) -> str:
    p = Path(path).resolve()
    return p.relative_to(v2.ROOT.resolve()).as_posix() if p.is_relative_to(v2.ROOT.resolve()) else str(p)


def save(base: Path, relative: str, value) -> Path:
    """Write a file under base; a file it replaces moves to base/history/<stamp>/ first."""
    path = Path(base) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        hist = Path(base) / "history" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") / relative
        hist.parent.mkdir(parents=True, exist_ok=True)
        path.replace(hist)
    if isinstance(value, pd.DataFrame):
        value.to_csv(path, index=False, encoding="utf-8-sig")
    else:
        path.write_text(value if isinstance(value, str) else json.dumps(value, indent=1, ensure_ascii=False,
                                                                       default=str), encoding="utf-8")
    return path


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"target_id": str, "comp_id": str, "pair": str}, encoding="utf-8-sig",
                       keep_default_na=False)


# ---------------------------------------------------------------- pure parts (tested offline)

def answer_schema(labels: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["comps", "note"],
            "properties": {"comps": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["label", "reason"],
                "properties": {"label": {"type": "string", "enum": labels}, "reason": {"type": "string"}}}},
                "note": {"type": "string"}}}


def parse_answer(raw, labels: dict[str, str], max_picks: int = MAX_PICKS) -> tuple[list[dict], list[str], str]:
    """The model's ranked picks [{label, comp_id, llm_rank (1..), llm_reason}], the issues found and its note. A
    "none"-like label is skipped (issue none_label); an unknown label is skipped (unknown_label:<x>); a repeated
    label keeps its first place (duplicate_label:<x>); picks past max_picks are dropped (over_max:<n>)."""
    if not isinstance(raw, dict) or not isinstance(raw.get("comps", []), list):
        raise ValueError("answer is not an object with a comps list")
    picks, issues, seen = [], [], set()
    for item in raw.get("comps", []):
        label = str((item or {}).get("label", "") if isinstance(item, dict) else item).strip()
        if label.casefold() in NONE_LABELS:
            issues.append("none_label")
            continue
        if label not in labels:
            issues.append(f"unknown_label:{label}")
            continue
        if label in seen:
            issues.append(f"duplicate_label:{label}")
            continue
        seen.add(label)
        reason = str(item.get("reason", "") if isinstance(item, dict) else "").strip()
        picks.append({"label": label, "comp_id": labels[label], "llm_rank": len(picks) + 1, "llm_reason": reason})
    if len(picks) > max_picks:
        issues.append(f"over_max:{len(picks)}")
        picks = picks[:max_picks]
    return picks, issues, str(raw.get("note", "") or "").strip()


def candidates_for(pool: pd.DataFrame, tier1: pd.DataFrame, targets: list[str]) -> dict[str, list[str]]:
    """Per target, the pool comps shown to the model: pool minus tier 1 minus the target itself, B3 rank order."""
    t1 = set(map(tuple, tier1[KEY].to_numpy()))
    p = pool[pool["target_id"].isin(targets)].drop_duplicates(KEY).sort_values(["target_id", "rank", "comp_id"])
    p = p[[(t, c) not in t1 and t != c for t, c in zip(p["target_id"], p["comp_id"])]]
    return {t: p.loc[p["target_id"] == t, "comp_id"].tolist() for t in targets}


def judge_order(llm_picks: pd.DataFrame, other_picks: pd.DataFrame, labelled: set[tuple[str, str]],
                cap: int) -> pd.DataFrame:
    """The unlabelled pairs to judge, in priority order, at most cap. llm_picks: target_id, comp_id, llm_rank,
    tier1_n (every model pick, top 5): ordered by entry_k = tier1_n + llm_rank (the smallest profile size that uses
    the pick), then target, then llm_rank. other_picks: target_id, comp_id, rule, fill_order (the no-model rules at
    k = 3), after the model's, by rule order then target then fill_order. Pairs already labelled or listed earlier are
    skipped. Columns: target_id, comp_id, source, entry_k, priority."""
    a = llm_picks.assign(source=tf.LLM_RULE, entry_k=lambda d: d["tier1_n"].astype(int) + d["llm_rank"].astype(int))
    a = a.sort_values(["entry_k", "target_id", "llm_rank"], kind="mergesort")
    b = other_picks.assign(entry_k=np.nan, source=other_picks["rule"])
    b = b.assign(_r=b["rule"].map({r: i for i, r in enumerate(["agent_then_rank", "b3_rank", "agent"])}))
    b = b.sort_values(["_r", "target_id", "fill_order"], kind="mergesort").drop(columns="_r")
    d = pd.concat([a[[*KEY, "source", "entry_k"]], b[[*KEY, "source", "entry_k"]]], ignore_index=True)
    d = d[[(t, c) not in labelled for t, c in zip(d["target_id"], d["comp_id"])]].drop_duplicates(KEY)
    d = d.head(cap).reset_index(drop=True)
    d["priority"] = np.arange(1, len(d) + 1)
    return d


def shortfall(status: pd.DataFrame, tier1_n: pd.Series, ks=tf.SWEEP_KS) -> pd.DataFrame:
    """Per k: targets needing tier 2 (tier 1 < k), with a model answer, whose answer has fewer picks than needed,
    and whose answer is empty. status: target_id, llm_status, n_picks (targets called)."""
    s = status.set_index("target_id")
    rows = []
    for k in ks:
        need = tier1_n[tier1_n < k]
        ok = [t for t in need.index if t in s.index and s.at[t, "llm_status"] == "ok"]
        short = [t for t in ok if int(s.at[t, "n_picks"]) < k - int(need[t])]
        rows.append({"k": k, "targets_needing_tier2": len(need), "answered": len(ok),
                     "not_answered": len(need) - len(ok), "fewer_than_needed": len(short),
                     "none_returned": sum(int(s.at[t, "n_picks"]) == 0 for t in ok),
                     "slots_needed": int((k - need).sum()),
                     "slots_filled": int(sum(min(int(s.at[t, "n_picks"]), k - int(need[t])) for t in ok))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- inputs

def selector_inputs():
    """The current B3 run's company names/websites and facets as the selector reads them (cosine_then_llm)."""
    import cosine_then_llm as ctl
    _, info, facets = ctl.load_inputs(ctl.CURRENT_B3, ctl.DEFAULT_Z, "selected")
    return ctl, info, facets


def build_prompt(target: str, comps: list[str], info: pd.DataFrame, facets: pd.DataFrame) -> tuple[str, dict]:
    """INSTRUCTIONS + the selector prompt's company part (2026-11-04a: target, then C1.. alphabetical)."""
    import cosine_then_llm as ctl
    p, labels = ctl.build_prompt(target, comps, info, facets, SELECTOR_PROMPT_VERSION)
    if not p.startswith(ctl.INSTRUCTIONS):
        raise ValueError("the selector prompt no longer starts with its instructions")
    return INSTRUCTIONS + p[len(ctl.INSTRUCTIONS):], labels


def context(cur: dict | None = None) -> dict:
    """Targets, tier 1 (baseline selector keeps), the b3_list_r11_15 pool and each called target's candidates."""
    import cohorts
    import progress as pr
    cur = cur or v2.current()
    targets = sorted(cohorts.load("v3_final")["target_id"].unique())
    agent, _ = tf.agent_scores(cur)
    pool = tf.pools(cur, targets, agent)[POOL]
    spec = pr.built_in("selector", cur)
    t1 = spec["keeps"]
    t1 = t1[t1["keep"].astype(bool) & t1["target_id"].isin(targets)][KEY].reset_index(drop=True)
    n1 = t1.groupby("target_id").size().reindex(targets, fill_value=0)
    called = [t for t in targets if n1[t] < MAX_TIER1]
    return {"cur": cur, "targets": targets, "pool": pool, "tier1": t1, "tier1_n": n1, "called": called,
            "candidates": candidates_for(pool, t1, called), "selector_file": Path(spec["run_file"])}


def input_files(cur: dict) -> dict[str, Path]:
    import cosine_then_llm as ctl
    import progress as pr
    c = v2.path(cur["retrieval"]["candidates"])
    return {"current_toml": v2.V2 / "current.toml", "b3_candidates": c / "candidates.csv",
            "b3_ranking": c / "ranking.csv.gz", "b3_run": c / "run.json",
            "universe": v2.path(cur["universe"]["universe"]), "general_facets": v2.path(cur["profiles"]["general"]),
            "sector_facets": v2.path(cur["profiles"]["sector"]),
            "selector_judgments": Path(pr.built_in("selector", cur)["run_file"]),
            "v3_final": v2.path(cur["rubric_v3"]["final"]) / "final.csv",
            "cosine_then_llm.py": Path(ctl.__file__).resolve(), "tier2_fill.py": Path(tf.__file__).resolve(),
            "tier2_llm.py": Path(__file__).resolve(), "cli_models.py": v2.V2 / "common" / "cli_models.py"}


# ---------------------------------------------------------------- build / run (Claude)

def build(out: Path | None, command: str) -> Path:
    out = out or OUT_ROOT / f"{stamp()}_{LABEL}"
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} exists and is not empty; build writes a new dir")
    ctx = context()
    _, info, facets = selector_inputs()
    rows, prompts, leaks = [], {}, []
    for t in ctx["called"]:
        comps = ctx["candidates"][t]
        missing = sorted(set([t, *comps]) - set(facets.index))
        if missing:
            raise SystemExit(f"{len(missing)} companies have no current facets, e.g. {missing[:3]}")
        prompt, labels = build_prompt(t, comps, info, facets)
        prompts[t] = prompt
        part = prompt[len(INSTRUCTIONS):].casefold()
        leaks += [{"target_id": t, "pattern": p} for p in LEAK_PATTERNS if re.search(p, part)]
        rank = ctx["pool"].set_index(KEY)["rank"]
        rows += [{"target_id": t, "comp_id": c, "label": lab, "b3_rank": int(rank[(t, c)]),
                  "tier1_n": int(ctx["tier1_n"][t]), "prompt_sha256": sha_text(prompt)} for lab, c in labels.items()]
    cand = pd.DataFrame(rows)
    llm = out / "llm_tier2"
    src = input_files(ctx["cur"])
    man = {"label": LABEL, "status": "EXPERIMENTAL llm_tier2 (Michael approved 2026-11-28); not a pipeline input",
           "created_at": now_iso(), "prompt_version": PROMPT_VERSION, "backend": BACKEND, "model": MODEL,
           "effort": None, "selector_prompt_version_for_descriptions": SELECTOR_PROMPT_VERSION,
           "instructions_sha256": sha_text(INSTRUCTIONS), "schema": "answer_schema(labels): comps [{label, reason}], note",
           "max_picks": MAX_PICKS, "targets": f"v3_final targets with < {MAX_TIER1} baseline tier-1 comps",
           "pool": f"tier2_fill {POOL} minus tier 1 (B3 list + B3 ranks 11-15)",
           "n_targets": len(ctx["called"]), "n_candidates": int(len(cand)),
           "inputs": {k: {"path": rel(p), "sha256": sha_file(p)} for k, p in src.items()},
           "inputs_sha256": {"candidates.csv": sha_text(cand.to_csv(index=False))},
           "leak_pattern_hits": len(leaks), "sessions": []}
    save(out, "manifest.json", {"label": LABEL, "created_at": now_iso(), "status": man["status"],
                                "parts": {"llm_tier2": "llm_tier2/manifest.json", "judge": "judge/manifest.json"},
                                "commands": [{"step": "build", "command": command, "at": now_iso()}]})
    save(llm, "manifest.json", man)
    save(llm, "inputs/instructions.txt", INSTRUCTIONS)
    save(llm, "inputs/candidates.csv", cand)
    save(llm, "inputs/leak_hits.csv", pd.DataFrame(leaks, columns=["target_id", "pattern"]))
    first = ctx["called"][0]
    save(llm, f"inputs/prompt_example_{first}.txt", prompts[first])
    print(f"[{LABEL}] {out}: {len(ctx['called'])} targets to call, {len(cand)} candidates "
          f"(per target {cand.groupby('target_id').size().min()}-{cand.groupby('target_id').size().max()}); "
          f"leak pattern hits {len(leaks)}")
    return out


def log_command(out: Path, step: str, command: str, **extra) -> None:
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    man.setdefault("commands", []).append({"step": step, "command": command, "at": now_iso(), **extra})
    save(out, "manifest.json", man)


def fingerprint(prompt: str, labels: list[str]) -> str:
    return sha_text(json.dumps([BACKEND, MODEL, None, answer_schema(labels), prompt], sort_keys=True))


def run(out: Path, command: str, max_failures: int = MAX_FAILURES, limit: int | None = None, call=None) -> dict:
    """One Claude call per target, sequential; a target with an ok answer under the same prompt is skipped."""
    import cli_models
    call = call or cli_models.call_cli
    llm = out / "llm_tier2"
    man = json.loads((llm / "manifest.json").read_text(encoding="utf-8"))
    if man["instructions_sha256"] != sha_text(INSTRUCTIONS) or man["prompt_version"] != PROMPT_VERSION:
        raise SystemExit("the instructions changed since build: use a new dir")
    cand = read_csv(llm / "inputs" / "candidates.csv")
    _, info, facets = selector_inputs()
    targets = list(dict.fromkeys(cand["target_id"]))[:limit] if limit else list(dict.fromkeys(cand["target_id"]))
    counts = {"selected": len(targets), "skipped_done": 0, "ok": 0, "failed": 0, "not_run": 0}
    session = {"command": command, "started_at": now_iso(), "counts": counts, "stopped": ""}
    log = llm / "logs" / f"run_{stamp()}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    streak, started = 0, time.time()
    with log.open("w", encoding="utf-8") as lf:
        def say(line):
            print(line, flush=True)
            lf.write(line + "\n")
        say(f"[{LABEL}] {len(targets)} targets; {BACKEND} {MODEL}; prompt {PROMPT_VERSION}; out {llm}")
        for n, t in enumerate(targets, 1):
            c = cand[cand["target_id"] == t]
            prompt, labels = build_prompt(t, c["comp_id"].tolist(), info, facets)
            if labels != dict(zip(c["label"], c["comp_id"])) or sha_text(prompt) != c["prompt_sha256"].iloc[0]:
                raise SystemExit(f"{t}: the prompt differs from the one built (inputs changed?)")
            fp = fingerprint(prompt, list(labels))
            path = llm / "answers" / f"{t}.json"
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
                if old.get("status") == "ok" and old.get("fingerprint") == fp:
                    counts["skipped_done"] += 1
                    continue
            run_dir = llm / "runs" / t / stamp()
            result = call(prompt, run_dir, answer_schema(list(labels)), BACKEND, model=MODEL, effort=None,
                          instructions_len=len(INSTRUCTIONS))
            rec = {"target_id": t, "prompt_version": PROMPT_VERSION, "backend": BACKEND, "model": MODEL,
                   "fingerprint": fp, "prompt_sha256": sha_text(prompt), "labels": labels,
                   "run_dir": rel(run_dir), "finished_at": now_iso(), "status": result["llm_status"],
                   "seconds": result.get("seconds"), "usage": result.get("usage", {})}
            if result["llm_status"] == "ok":
                try:
                    rec["picks"], rec["issues"], rec["note"] = parse_answer(json.loads(result["text"]), labels)
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    rec.update(status="invalid_answer", error=str(exc))
            else:
                rec["error"] = result.get("error", result["llm_status"])
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(json.dumps({k: v for k, v in result.items() if k != "text"}, indent=1,
                                                         default=str), encoding="utf-8")
            save(llm, f"answers/{t}.json", rec)
            ok = rec["status"] == "ok"
            counts["ok" if ok else "failed"] += 1
            streak = 0 if ok else streak + 1
            say(f"[{n}/{len(targets)}] {t} {info.loc[t, 'target_ciq_ticker']}: {rec['status']}"
                + (f" picks {len(rec['picks'])}" + (f" issues {rec['issues']}" if rec["issues"] else "") if ok
                   else f" {str(rec.get('error', ''))[:200]}") + f" ({result.get('seconds')} s)")
            if result.get("stop_run") or streak >= max_failures:
                session["stopped"] = ("fatal CLI error (usage limit or login)" if result.get("stop_run")
                                      else f"{streak} consecutive failures")
                say(f"stopping: {session['stopped']}; finished targets are kept; rerun the same command")
                break
    counts["not_run"] = counts["selected"] - counts["skipped_done"] - counts["ok"] - counts["failed"]
    session.update(ended_at=now_iso(), seconds=round(time.time() - started, 1))
    man["sessions"].append(session)
    save(llm, "manifest.json", man)
    collect_llm(out)
    log_command(out, "run", command, counts=counts)
    print(json.dumps(counts))
    return counts


def collect_llm(out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """llm_tier2/picks.csv (target_id, comp_id, llm_rank, llm_reason, label) and status.csv (per called target)."""
    llm = out / "llm_tier2"
    cand = read_csv(llm / "inputs" / "candidates.csv")
    picks, status = [], []
    for t in dict.fromkeys(cand["target_id"]):
        path = llm / "answers" / f"{t}.json"
        rec = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "not_run"}
        ok = rec["status"] == "ok"
        status.append({"target_id": t, "tier1_n": int(cand.loc[cand["target_id"] == t, "tier1_n"].iloc[0]),
                       "candidates": int((cand["target_id"] == t).sum()), "llm_status": rec["status"],
                       "n_picks": len(rec.get("picks", [])) if ok else 0,
                       "issues": "; ".join(rec.get("issues", [])), "note": rec.get("note", ""),
                       "seconds": rec.get("seconds"), "error": rec.get("error", "")})
        if ok:
            picks += [{"target_id": t, "comp_id": p["comp_id"], "llm_rank": p["llm_rank"],
                       "llm_reason": p["llm_reason"], "label": p["label"]} for p in rec["picks"]]
    picks = pd.DataFrame(picks, columns=["target_id", "comp_id", "llm_rank", "llm_reason", "label"])
    status = pd.DataFrame(status)
    save(llm, "picks.csv", picks)
    save(llm, "status.csv", status)
    return picks, status


# ---------------------------------------------------------------- judge (GPT-Terra)

def judge_build(out: Path, command: str) -> pd.DataFrame:
    """judge_candidates.csv and judge_sheet.csv: the unlabelled picks to judge, in priority order, at most
    MAX_JUDGE_CALLS. Written once: an existing sheet is kept (the run resumes on it)."""
    import judge_v3_prompt as jp
    import recall_audit as ra
    if (out / "judge_sheet.csv").exists():
        raise SystemExit(f"{out / 'judge_sheet.csv'} exists; judge-run resumes on it")
    ctx = context()
    picks, _ = collect_llm(out)
    lab, _ = tf.labels(ctx["cur"])
    labelled = set(zip(lab["target_id"], lab["comp_id"]))
    lp = picks.assign(tier1_n=picks["target_id"].map(ctx["tier1_n"]))
    t1 = ctx["tier1"].merge(ctx["pool"], on=KEY, how="left")
    other = pd.concat([tf.fill(t1, ctx["pool"], r, JUDGE_EXTRA_K, ctx["targets"]).assign(rule=r)
                       for r in ("agent_then_rank", "b3_rank")], ignore_index=True)
    d = judge_order(lp, other, labelled, MAX_JUDGE_CALLS)
    d.insert(0, "pair", [f"F{i:03d}" for i in range(1, len(d) + 1)])
    desc = ra.describe(d[KEY])
    sheet = d[["pair", *KEY]].assign(is_anchor=0).merge(desc, on=KEY, how="left", validate="one_to_one")
    if sheet[jp.PAIR_COLUMNS].isna().any().any():
        raise SystemExit("a description cell is missing")
    tick = sheet.set_index(KEY)
    d["target_ticker"] = [tick.at[(t, c), "target_ticker"] for t, c in zip(d["target_id"], d["comp_id"])]
    d["comp_ticker"] = [tick.at[(t, c), "comp_ticker"] for t, c in zip(d["target_id"], d["comp_id"])]
    all_needed = judge_order(lp, other, labelled, 10 ** 6)
    save(out, "judge_candidates.csv", d)
    save(out, "judge_sheet.csv", sheet)
    counts = {"unlabelled_llm_top5": int(all_needed["source"].eq(tf.LLM_RULE).sum()),
              "unlabelled_other_k3": int(all_needed["source"].ne(tf.LLM_RULE).sum()),
              "selected": len(d), "selected_by_source": d["source"].value_counts().to_dict(), "cap": MAX_JUDGE_CALLS}
    log_command(out, "judge-build", command, counts=counts)
    print(json.dumps(counts, indent=1))
    return d


def judge_desc(out: Path) -> pd.DataFrame:
    import judge_v3_prompt as jp
    s = read_csv(out / "judge_sheet.csv")
    s["is_anchor"] = False
    return s[["pair", *KEY, "is_anchor", *jp.PAIR_COLUMNS]].set_index("pair", drop=False)


def judge_run(out: Path, command: str, max_failures: int = MAX_FAILURES) -> dict:
    import judge_v3 as jv
    import judge_v3_prompt as jp
    desc = judge_desc(out)
    for p in desc.index:                                   # the company part holds only the sheet's columns
        part = jv.build_prompt(desc.loc[p])[len(jp.INSTRUCTIONS):]
        if sorted(re.findall(r"^([a-z_]+): ", part, flags=re.M)) != sorted(jp.PAIR_COLUMNS):
            raise SystemExit(f"{p}: the prompt's pair part is not exactly the sheet's description columns")
    r = jv.Run(out / "judge", JUDGE["backend"], JUDGE["model"], JUDGE["name"], JUDGE["effort"])
    made = len(list((out / "judge" / "runs").glob("*/*"))) if (out / "judge" / "runs").exists() else 0
    todo = [p for p in desc.index if not r.done(p, r.fingerprint(jv.build_prompt(desc.loc[p])))]
    allowed = max(0, MAX_JUDGE_CALLS - made)
    pairs = todo[:allowed]
    print(f"[{LABEL}] judge: {len(desc)} pairs, {len(todo)} to do, {made} calls made, {allowed} allowed")
    counts = r.run(pairs, desc, "tier2_unlabelled_picks", command, max_failures) if pairs else {"selected": 0}
    man = r.manifest()
    man["tier2_fill"] = {"label": LABEL, "judge_sheet": rel(out / "judge_sheet.csv"),
                         "judge_sheet_sha256": sha_file(out / "judge_sheet.csv"),
                         "note": "pairs come from judge_sheet.csv (unlabelled tier-2 picks), not the rubric v3 sheet; "
                                 "files.sheet and sha256.sheet are what judge_v3.Run records by default"}
    if man:
        r.save("manifest.json", man)
    log_command(out, "judge-run", command, counts=counts, calls_before=made)
    return counts


def judge_collect(out: Path) -> pd.DataFrame:
    """judge_pairs.csv: target_id, comp_id, judge_status, judge_score (rubric v3 derived score) and the answers."""
    import judge_v3 as jv
    import rubric_v3 as r3
    name = JUDGE["name"]
    cand = read_csv(out / "judge_candidates.csv")
    adir = out / "judge" / "answers"
    records = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in adir.glob("*.json")} if adir.exists() else {}
    rows = []
    for _, c in cand.iterrows():
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
    bad = r3.check_sheet(answers, [name])
    bad = bad[bad["problem"] != "not scored yet"]
    if len(bad):
        raise SystemExit("answers fail rubric_v3 check:\n" + bad.to_string(index=False))
    answers[f"score_{name}"] = r3.scores(answers, [name])[f"score_{name}"].to_numpy()
    p = cand.merge(answers[["pair", "judge_status", f"score_{name}", f"overall_call_{name}", f"notes_{name}"]],
                   on="pair", how="left").rename(columns={f"score_{name}": "judge_score",
                                                          f"overall_call_{name}": "judge_overall_call",
                                                          f"notes_{name}": "judge_reason"})
    save(out, "judge_answers.csv", answers)
    save(out, "judge_pairs.csv", p)
    return p


# ---------------------------------------------------------------- score

def score(out: Path, command: str) -> dict[str, pd.DataFrame]:
    picks, status = collect_llm(out)
    extra = []
    if (out / "judge_candidates.csv").exists():
        judge_collect(out)
        extra = [out / "judge_pairs.csv"]
    llm = picks[[*KEY, "llm_rank", "llm_reason"]]
    tables, meta = tf.sweep(llm=llm, extra_judge=extra)
    ctx_n1 = status.set_index("target_id")["tier1_n"]
    import cohorts
    import progress as pr
    targets = sorted(cohorts.load("v3_final")["target_id"].unique())
    k1 = pr.built_in("selector")["keeps"]
    n1 = k1[k1["keep"].astype(bool) & k1["target_id"].isin(targets)].groupby("target_id").size()
    n1 = n1.reindex(targets, fill_value=0)
    if not ctx_n1.eq(n1.reindex(ctx_n1.index)).all():
        raise SystemExit("tier-1 counts differ from the build's")
    tables["llm_shortfall"] = shortfall(status, n1)
    t = tables["targets"]
    zero = t[(t["k"] == 3) & (t["rule"] == tf.LLM_RULE) & (t["tier1_n"] == 0)].copy()
    pk = tables["picks"]
    pk = pk[(pk["k"] == 3) & (pk["rule"] == tf.LLM_RULE)]
    zero["tier2_reasons"] = zero["target_id"].map(
        pk.groupby("target_id").apply(lambda d: " | ".join(f"{a}: {b}" for a, b in zip(d["comp_ticker"], d["llm_reason"])),
                                      include_groups=False))
    zero["llm_note"] = zero["target_id"].map(status.set_index("target_id")["note"])
    tables["zero_keep_k3"] = zero[["target_id", "target_ticker", "group", "tier2_n", "tier2", "tier2_reasons",
                                   "llm_note"]]
    for name, df in tables.items():
        save(out, f"{name}.csv", df)
    src = meta["inputs"] | {"llm_picks": out / "llm_tier2" / "picks.csv", "tier2_llm.py": Path(__file__).resolve()}
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    man["score"] = {"at": now_iso(), "ks": list(tf.SWEEP_KS), "tier1": "baseline (progress.built_in('selector'))",
                    "rules": {**{r: "tier2_fill rules, pools b3_list and b3_list_r11_15" for r in tf.RULES},
                              tf.LLM_RULE: f"model rank, pool {POOL}"},
                    "label_views": {"v3_final": "headline (tier2_ge1_prec_*, profile_*_prec_*)",
                                    "all_sources": "v3_final + anchors + judge-only (recall audit and judge_pairs.csv) "
                                                   "(*_all_sources_*)"},
                    "bootstrap": "targets, 1,000 draws, seed 2026 (progress.bootstrap_means)",
                    "inputs": {k: {"path": rel(p), "sha256": sha_file(p)} for k, p in src.items()},
                    "outputs": sorted(f"{n}.csv" for n in tables)}
    save(out, "manifest.json", man)
    log_command(out, "score", command)
    return tables


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", type=Path)
    for name in ("run", "judge-build", "judge-run", "score"):
        s = sub.add_parser(name)
        s.add_argument("dir", type=Path)
        if name in ("run", "judge-run"):
            s.add_argument("--max-failures", type=int, default=MAX_FAILURES)
        if name == "run":
            s.add_argument("--limit", type=int)
    args = ap.parse_args(argv)
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
    command = "uv run python v2/09_analysis/scripts/tier2_llm.py " + " ".join(
        shlex.quote(x) for x in (argv if argv is not None else _sys.argv[1:]))
    print(f"*** {LABEL}: llm_tier2 ***")
    if args.cmd == "build":
        build(args.out, command)
    elif args.cmd == "run":
        run(args.dir, command, args.max_failures, args.limit)
    elif args.cmd == "judge-build":
        judge_build(args.dir, command)
    elif args.cmd == "judge-run":
        judge_run(args.dir, command, args.max_failures)
    else:
        score(args.dir, command)


if __name__ == "__main__":
    main()
