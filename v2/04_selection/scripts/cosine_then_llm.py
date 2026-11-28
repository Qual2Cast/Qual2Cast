"""
The model step: an LLM decides, for each target, which of its candidate
comps (step 4) are good comps and which are bad. Each comp gets a score of
1 (good) or 0 (bad), with a short reason.

One call per target (Claude Haiku 5.5 by default, through
fill_facets.call_claude): the target's name, website and facets, then each
candidate's name, website and facets, labeled C1, C2, ... in alphabetical
order, with no similarity, rank or multiple, so the order says nothing
about how close they are. The model answers good or bad for every label;
code checks that every candidate was answered once and maps the labels back
to companies.

Candidates: the pairs at z >= 2 (--z) in the latest step 4 run
(outputs-local/v1/candidates/<run>/candidates.csv), for the training
targets only (that file holds no others).

With --b3 the candidates are instead the B3 comp lists (mutual top 10
topped up to 3): by default the current list named in v2/current.toml
[retrieval] candidates ("Sonnet + Fiona sub-sector"), or --candidates
<a method1_candidates.py run>. The LLM then screens each target's list
(at most 10 comps), shown with the facets that list was built from (the
candidates run.json: Sonnet general facets plus Fiona's sub-sector).

v1a (2026-11-18): new runs write to outputs-local/v1a/04_selection/ (v2: outputs-local/v2/04_selection/); the
v1 runs (Haiku and Sonnet selectors on the Haiku-facet B3 list of 11-04,
and v0's Haiku screen in outputs-local/v1/judge/) stay in the v1 record.
The claude-cli backend always uses the Claude subscription login (an API
key in the environment is removed, common/cli_models.py).

Prompt versions (details and the checks: v1/PROMPT_VERSIONS.md):
  2026-10-25a  SAVED_PROMPT_VERSION. All twelve facets, company size (F9)
               included. Every saved verdict (outputs-local/v1/judge/, 373
               training targets, Haiku) and every saved holdout answer was
               made with it; the holdout replay scripts and the readers of
               saved verdicts pin it, so they keep matching what is saved.
  2026-11-04a  PROMPT_VERSION, the default for new runs. Company size is
               left out of the facet lines (team decision 2026-11-03: too
               generic, hurt the comps). Nothing else in the prompt changed.
  2026-11-28a  2026-11-04a plus one trait line per company (target and every
               candidate): "- Recurring revenue: yes/no/unknown", from the
               02_profiles trait table (E1, v2/02_profiles/scripts/traits.py).
               Data only: the instructions are unchanged (team, 2026-11-28).
  2026-11-28b  the same with "- Big-ticket sales: ..." (E3) instead.
  2026-11-28c  both lines (E1 then E3).
  2026-11-28d  to 2026-11-28k: one trait line each, the same way (data only):
               d cyclical demand (E2), e people-delivered (E4), f large
               customers (E5), g asset-heavy (E6), h maintenance-led (E7),
               i publicly funded (E8), j serial acquirer (E9), k mission-
               critical (E10).
               The round-1 trait table (E1-E6) is current.toml
               [analysis.trait_uplift] traits, or --traits; the round-2 table
               (E7-E10) is current.toml [traits_r2] table, or --traits-r2.
               The path and sha256 of each table a version reads go into
               <out>/manifest.json.
Choose with --prompt-version. A new run writes, by default, to
outputs-local/v2/04_selection/<candidates run>_<prompt version>_<backend>_<model>/.

Every call keeps its prompt, raw answer and logs under
<out>/runs/<IQ_ID>/<time>/. A target is judged once per prompt and model;
a rerun skips finished targets, and a replaced judgment or table moves to
a history folder. The run stops if the API credit runs out or the key is
refused; run it again after fixing that.

  python v2/04_selection/scripts/cosine_then_llm.py --tickers PCTY BV     # a few targets
  python v2/04_selection/scripts/cosine_then_llm.py --workers 4           # every training target
  python v2/04_selection/scripts/cosine_then_llm.py --dry-run             # write the prompts only
  python v2/04_selection/scripts/cosine_then_llm.py --b3 --backend claude-cli --workers 2   # the current list, Sonnet
  python v2/04_selection/scripts/cosine_then_llm.py --tables-only --out <run>               # rebuild judgments.csv
  python v2/04_selection/scripts/cosine_then_llm.py --b3 --backend claude-cli --prompt-version 2026-11-28a \
      --targets-file <ids.txt>                                                              # trait line, some targets
"""

from __future__ import annotations

import sys as _sys  # v2: shared paths (common/paths.py) put every component's scripts on the path
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import argparse
import hashlib
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facets as fc  # noqa: E402  (also puts website_scrape/ and src/ on the path)
from fill_facets import DEFAULT_MODEL, call_claude, now_iso, output_paths as facet_paths, stamp  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

PROMPT_VERSION = "2026-11-04a"            # new runs: company size (F9) left out of the facet lines
SAVED_PROMPT_VERSION = "2026-10-25a"      # every saved verdict and holdout answer: all twelve facets
PROMPT_EXCLUDES = {                       # facets left out of the prompt, per version
    "2026-10-25a": (),
    "2026-11-04a": ("company_size",),
    "2026-11-28a": ("company_size",),
    "2026-11-28b": ("company_size",),
    "2026-11-28c": ("company_size",),
    **{f"2026-11-28{v}": ("company_size",) for v in "defghijk"},
}
PROMPT_TRAITS = {                         # 02_profiles traits added as data lines, per version (none before 11-28)
    "2026-11-28a": ("recurring_revenue",),
    "2026-11-28b": ("big_ticket",),
    "2026-11-28c": ("recurring_revenue", "big_ticket"),
    "2026-11-28d": ("cyclical_demand",),
    "2026-11-28e": ("people_delivered",),
    "2026-11-28f": ("large_customers",),
    "2026-11-28g": ("asset_heavy",),
    "2026-11-28h": ("maintenance_led",),
    "2026-11-28i": ("publicly_funded",),
    "2026-11-28j": ("serial_acquirer",),
    "2026-11-28k": ("mission_critical",),
}
TRAIT_LABELS = {                          # the traits' names in v2/02_profiles/scripts/traits.py (E1-E10)
    "recurring_revenue": "Recurring revenue",
    "big_ticket": "Big-ticket sales",
    "cyclical_demand": "Cyclical demand",
    "people_delivered": "People-delivered",
    "large_customers": "Large customers",
    "asset_heavy": "Asset-heavy",
    "maintenance_led": "Maintenance-led",
    "publicly_funded": "Publicly funded",
    "serial_acquirer": "Serial acquirer",
    "mission_critical": "Mission-critical",
}
ROUND_2_TRAITS = ("maintenance_led", "publicly_funded", "serial_acquirer", "mission_critical")   # E7-E10: --traits-r2
TRAIT_ANSWERS = ("yes", "no", "unknown")
CUR = v2.current()
SAVED_OUT = OUTPUTS_LOCAL / "v1" / "judge"                # v1 record: the saved 2026-10-25a verdicts (read only)
DEFAULT_OUT_ROOT = v2.out("04_selection")                # new runs: <root>/<candidates run>_<prompt version>_<backend>_<model>/
DEFAULT_OUT = SAVED_OUT                   # kept for older imports; new runs use DEFAULT_OUT_ROOT
CANDIDATES_ROOT = OUTPUTS_LOCAL / "v1" / "candidates"     # v1 record: v0's z >= 2 lists
METHOD1_ROOT = v2.out("03_retrieval") / "candidates"     # new B3 runs (method1_candidates.py)
CURRENT_B3 = v2.path(CUR["retrieval"]["candidates"])     # the current list (current.toml); --b3 default
CURRENT_TRAITS = v2.path(CUR["analysis"]["trait_uplift"]["traits"])   # round-1 trait table (E1-E6); --traits
CURRENT_TRAITS_R2 = v2.path(CUR["traits_r2"]["table"])                 # round-2 trait table (E7-E10); --traits-r2
FACETS_OUT = OUTPUTS_LOCAL / "v1" / "facets"              # v1 record: the Haiku fills (facet_source "haiku")
DEFAULT_Z = 2.0

INSTRUCTIONS = """You help a private-equity analyst choose comparable public companies (comps) for valuing a target company. A buyout investor values a target from the EV/EBITDA multiples of companies in the same business: the same main products or services, sold to the same kind of customers, earning money the same way. Scale matters less than being in the same business.

Below are the target and a list of candidate comps, each with its name, website and a description of its business model. Use the descriptions and what you know about the companies.

For every candidate, decide whether it is a good comp for the target:
- good: in the same business as the target, so its multiple says something about the target's.
- bad: a different business, even if it shares an industry label, customers or a technology.

Rules:
- Answer for every candidate, once, by its label (C1, C2, ...).
- The reason is one short sentence, at most twenty words, naming what matches or differs.
- Judge the business only. Do not use or mention valuations, multiples, share prices or financial figures."""


def output_paths(out_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        runs=out_dir / "runs",                          # prompt, raw answer, logs per call
        judgments=out_dir / "judgments",                # one checked judgment per target
        judgments_history=out_dir / "judgments_history",
        prompts_dry_run=out_dir / "prompts_dry_run",
        tables=out_dir / "tables",                      # judgments.csv
        tables_history=out_dir / "tables_history",
        logs=out_dir / "logs",
    )


def answer_schema(labels: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["comps"],
            "properties": {"comps": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["label", "good", "reason"],
                "properties": {"label": {"type": "string", "enum": labels},
                               "good": {"type": "boolean"},
                               "reason": {"type": "string"}}}}}}


# ---------------------------------------------------------------- prompt

def describe(row: pd.Series, exclude: tuple[str, ...] = PROMPT_EXCLUDES[PROMPT_VERSION]) -> str:
    """A company's facets as lines: "unknown" or "none" (not applicable) where
    so. Facets in `exclude` are left out; the default is the current prompt
    version's list (company size). Pass PROMPT_EXCLUDES[SAVED_PROMPT_VERSION]
    to rebuild the saved prompts exactly."""
    lines = []
    for f in fc.FACETS:
        if f.name in exclude:
            continue
        status = row.get(f"{f.name}_status", "unknown")
        value = {"unknown": "unknown", "not_applicable": "none"}.get(status) or row.get(f.name, "") or "unknown"
        lines.append(f"- {f.label}: {value}")
    sector_summary = row.get("sector_summary", "")
    if isinstance(sector_summary, str) and sector_summary:
        lines.append(f"- Sector-specific business characteristics: {sector_summary}")
    sub_sector = row.get("sub_sector", "")
    if isinstance(sub_sector, str) and sub_sector:
        lines.append(f"- Sub-sector: {sub_sector}")
    return "\n".join(lines)


def trait_lines(traits: pd.DataFrame, iq_id: str, names: tuple[str, ...]) -> str:
    """A company's trait answers as lines ("- Recurring revenue: yes"); a
    company or answer missing from the table, or not yes/no, shows unknown."""
    lines = []
    for name in names:
        value = traits.at[iq_id, name] if iq_id in traits.index else "unknown"
        value = value.strip().lower() if isinstance(value, str) else "unknown"
        lines.append(f"- {TRAIT_LABELS[name]}: {value if value in TRAIT_ANSWERS else 'unknown'}")
    return "\n".join(lines)


def load_traits(path: Path) -> pd.DataFrame:
    """A 02_profiles trait table (yes/no/unknown per company), indexed by
    IQ_COMPANY_ID: the trait columns it holds among TRAIT_LABELS. Rows whose
    fill failed (llm_status not ok) answer unknown. Only the trait answers
    are read, never the reasons."""
    t = pd.read_csv(path, dtype=str).fillna("")
    names = [n for n in TRAIT_LABELS if n in t.columns]
    t.loc[t["llm_status"] != "ok", names] = "unknown"
    return t.set_index("IQ_COMPANY_ID")[names]


def version_traits(prompt_version: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """A prompt version's trait lines from the round-1 table (E1-E6) and from
    the round-2 table (E7-E10)."""
    names = PROMPT_TRAITS.get(prompt_version, ())
    return (tuple(n for n in names if n not in ROUND_2_TRAITS), tuple(n for n in names if n in ROUND_2_TRAITS))


def build_prompt(target: str, comps: list[str], info: pd.DataFrame, facet_rows: pd.DataFrame,
                 prompt_version: str = PROMPT_VERSION,
                 traits: pd.DataFrame | None = None) -> tuple[str, dict[str, str]]:
    """The prompt for one target, and the label of each candidate (C1, ...).
    Candidates are listed alphabetically by name, so their order carries no
    similarity rank. `prompt_version` sets which facets are listed (see
    PROMPT_EXCLUDES) and which trait lines follow them (PROMPT_TRAITS; those
    versions need `traits`, from load_traits); replays of saved answers pass
    SAVED_PROMPT_VERSION."""
    order = sorted(comps, key=lambda c: (info.loc[c, "target_company_name"].lower(), c))
    labels = {f"C{i}": c for i, c in enumerate(order, 1)}
    exclude = PROMPT_EXCLUDES[prompt_version]
    trait_names = PROMPT_TRAITS.get(prompt_version, ())
    if trait_names and traits is None:
        raise ValueError(f"prompt {prompt_version} lists traits {trait_names}: pass the trait table (load_traits)")

    def block(iq_id: str) -> str:
        r = info.loc[iq_id]
        text = f"{r['target_company_name']} ({r['target_ciq_website']})\n{describe(facet_rows.loc[iq_id], exclude)}"
        if trait_names:
            text += "\n" + trait_lines(traits, iq_id, trait_names)
        return text

    parts = [INSTRUCTIONS, "", f"Target: {block(target)}", "", "Candidates:"]
    parts += [f"\n{label}: {block(c)}" for label, c in labels.items()]
    return "\n".join(parts), labels


def fingerprint(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- answer

def check_answer(raw: dict, labels: dict[str, str]) -> tuple[list[dict], list[str]]:
    """One row per candidate (comp, score 1/0, reason) and the issues found:
    a candidate answered twice keeps its first answer; one never answered
    gets no score."""
    rows, issues, seen = {}, [], set()
    for item in raw.get("comps", []):
        label = item.get("label")
        if label not in labels:
            issues.append(f"unknown_label:{label}")
        elif label in seen:
            issues.append(f"duplicate_label:{label}")
        else:
            seen.add(label)
            rows[label] = {"label": label, "comp": labels[label], "score": int(bool(item.get("good"))),
                           "reason": (item.get("reason") or "").strip()}
    for label, comp in labels.items():
        if label not in rows:
            issues.append(f"not_answered:{label}")
            rows[label] = {"label": label, "comp": comp, "score": None, "reason": ""}
    return [rows[label] for label in labels], issues


# ---------------------------------------------------------------- run

def latest_candidates() -> Path:
    runs = sorted(p for p in CANDIDATES_ROOT.iterdir() if (p / "candidates.csv").exists())
    if not runs:
        raise SystemExit("No step 4 candidates yet: run v0/notebooks/comps_and_valuation.ipynb section 2.")
    return runs[-1]


def latest_method1() -> Path:
    runs = sorted(p for p in METHOD1_ROOT.iterdir() if (p / "candidates.csv").exists()) if METHOD1_ROOT.exists() else []
    if not runs:
        raise SystemExit("No v1 baseline lists yet: run  uv run python v2/03_retrieval/scripts/method1_candidates.py")
    return runs[-1]


def pick_pairs(pairs: pd.DataFrame, z: float, rule: str = "z") -> pd.DataFrame:
    """The candidate rows to judge: z >= z (rule "z"), or the rows marked
    `selected` (rule "selected", a method1_candidates.py run)."""
    if rule == "selected":
        if "selected" not in pairs:
            raise SystemExit("These candidates have no `selected` column: --b3 needs a method1_candidates.py run")
        return pairs[pairs["selected"].astype(str).str.lower() == "true"]
    return pairs[pairs["z"] >= z]


def load_inputs(candidates_run: Path, z: float, rule: str = "z") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """The pairs to judge, company names and websites, and the current facets
    (first business). rule "z": the pairs at z >= z (v0's shortlist);
    rule "selected": the rows marked `selected` (a method1_candidates.py run:
    the v1 baseline's comp lists)."""
    pairs = pick_pairs(pd.read_csv(candidates_run / "candidates.csv", dtype={"target": str, "comp": str}), z, rule)
    run = json.loads((candidates_run / "run.json").read_text(encoding="utf-8"))
    universe_run = run["universe_run"]
    if universe_run != CUR["universe"]["universe_run"]:
        raise SystemExit(f"candidates run uses universe {universe_run}, current.toml {CUR['universe']['universe_run']}")
    info = pd.read_csv(v2.path(CUR["universe"]["universe"]), dtype=str).set_index("IQ_COMPANY_ID")
    facet_override = run.get("facet_override")
    if facet_override:
        facet_path = Path(facet_override)
    else:
        facet_source = run.get("facet_source", "haiku")
        if facet_source not in {"haiku", "sonnet"}:
            raise ValueError(f"unsupported facet source: {facet_source}")
        facet_path = (facet_paths(FACETS_OUT).tables / "facets.csv" if facet_source == "haiku"
                      else v2.path(CUR["profiles"]["general"]))
    facets = pd.read_csv(facet_path, dtype=str).fillna("")
    facets = facets[(facets["prompt_version"] == fc.PROMPT_VERSION) & (facets["llm_status"] == "ok")
                    & (facets["business_id"] == "B1")].set_index("IQ_COMPANY_ID")
    if "Fiona sub-sector" in run.get("method", ""):
        sector = pd.read_csv(v2.path(CUR["profiles"]["sector"]), dtype=str).fillna("").set_index("IQ_COMPANY_ID")
        facets["sub_sector"] = sector["sub_sector"].where(sector["sub_sector_status"] == "stated").reindex(facets.index).fillna("")
    return pairs, info, facets


def move_to_history(path: Path, history: Path) -> None:
    if path.exists():
        history.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), history / f"{path.stem}_{stamp()}{path.suffix}")


def judge_one(target: str, comps: list[str], info, facets, out: SimpleNamespace, args) -> dict:
    prompt, labels = build_prompt(target, comps, info, facets, args.prompt_version, args.traits_table)
    fp = fingerprint(prompt, json.dumps([args.backend, args.model, args.effort]))
    path = out.judgments / f"{target}.json"
    if path.exists() and not args.refresh:
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") == fp and old.get("llm_status") == "ok":
            return {"target": target, "status": "current"}
    run_dir = out.runs / target / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    if args.backend in ("claude-cli", "codex"):
        from cli_models import call_cli
        result = call_cli(prompt, run_dir, answer_schema(list(labels)), args.backend, model=args.model,
                          effort=args.effort, instructions_len=len(INSTRUCTIONS))
    else:
        result = call_claude(prompt, run_dir, answer_schema(list(labels)), args.model, args.effort,
                             instructions_len=len(INSTRUCTIONS))
    run_info = {"backend": args.backend, "model": args.model, "effort": args.effort or "", "prompt_version": args.prompt_version,
                "fingerprint": fp, "finished_at": now_iso(),
                **{k: v for k, v in result.items() if k != "text"}}
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=1), encoding="utf-8")
    judgment = {"target": target, "candidates_run": args.candidates.name,
                "z_min": None if args.b3 else args.z, "list_rule": "b3_selected" if args.b3 else "z",
                "prompt_version": args.prompt_version, "model": args.model, "fingerprint": fp,
                "run_dir": str(run_dir.relative_to(out.runs.parent)), "llm_status": result["llm_status"],
                "judged_at": now_iso(), "labels": labels, "comps": [], "issues": []}
    if args.traits_table is not None and args.traits_sha256:
        judgment["traits_sha256"] = args.traits_sha256
    if getattr(args, "traits_r2_sha256", None):
        judgment["traits_r2_sha256"] = args.traits_r2_sha256
    if result["llm_status"] == "ok":
        try:
            judgment["comps"], judgment["issues"] = check_answer(json.loads(result["text"]), labels)
        except json.JSONDecodeError:
            judgment["llm_status"] = "invalid_json"
    else:
        judgment["error"] = result.get("error", "")
    move_to_history(path, out.judgments_history)
    path.write_text(json.dumps(judgment, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"target": target, "status": judgment["llm_status"], "issues": judgment["issues"],
            "stop_run": result.get("stop_run", False), "usage": result.get("usage", {}),
            "seconds": result.get("seconds")}


def write_tables(out: SimpleNamespace, pairs: pd.DataFrame, info: pd.DataFrame,
                 prompt_version: str = PROMPT_VERSION) -> Path:
    """judgments.csv: one row per judged target-comp pair made with
    `prompt_version`, with its step 4 rank, similarity and z, the score (1
    good, 0 bad) and the reason. Refuses to write an empty table over saved
    judgments made with another version (pass that version instead)."""
    rows, other_versions = [], set()
    for path in sorted(out.judgments.glob("*.json")):
        j = json.loads(path.read_text(encoding="utf-8"))
        if j.get("llm_status") == "ok" and j.get("prompt_version") != prompt_version:
            other_versions.add(j.get("prompt_version"))
        if j.get("llm_status") != "ok" or j.get("prompt_version") != prompt_version:
            continue
        for c in j["comps"]:
            rows.append({"target": j["target"], "comp": c["comp"], "label": c["label"], "score": c["score"],
                         "reason": c["reason"], "model": j["model"], "prompt_version": j["prompt_version"],
                         "candidates_run": j["candidates_run"], "judged_at": j["judged_at"],
                         "issues": "; ".join(j["issues"])})
    if not rows and other_versions:
        raise SystemExit(f"No judgments made with prompt {prompt_version} in {out.judgments}; the ones there use "
                         f"{sorted(other_versions)}. Pass --prompt-version with that version to rebuild their table.")
    table = pd.DataFrame(rows, columns=["target", "comp", "label", "score", "reason", "model", "prompt_version",
                                        "candidates_run", "judged_at", "issues"])
    table = table.merge(pairs[["target", "comp", "rank", "similarity", "z"]], on=["target", "comp"], how="left")
    for col, src in [("target_ticker", "target"), ("comp_ticker", "comp")]:
        table.insert(table.columns.get_loc(src) + 1, col, table[src].map(info["target_ciq_ticker"]))
    table.insert(table.columns.get_loc("comp_ticker") + 1, "comp_company", table["comp"].map(info["target_company_name"]))
    out.tables.mkdir(parents=True, exist_ok=True)
    dest = out.tables / "judgments.csv"
    move_to_history(dest, out.tables_history)
    table.sort_values(["target", "rank"]).to_csv(dest, index=False)
    return dest


def read_target_ids(path: Path) -> list[str]:
    """IQ ids, one per line ('#' starts a comment), or a CSV with a target_id column."""
    text = path.read_text(encoding="utf-8-sig")
    first = text.splitlines()[0] if text.strip() else ""
    if "target_id" in first.split(","):
        return sorted(set(pd.read_csv(path, dtype=str, encoding="utf-8-sig")["target_id"].dropna()))
    return sorted({line.split("#")[0].strip() for line in text.splitlines()} - {""})


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repo_relative(path) -> str:
    p = Path(path).resolve()
    return p.relative_to(v2.ROOT.resolve()).as_posix() if p.is_relative_to(v2.ROOT.resolve()) else p.name


def write_manifest(out: SimpleNamespace, args, groups: pd.Series) -> Path:
    """<out>/manifest.json: what this run read (candidates, the trait table
    with its sha256, the target filter) and its settings. A changed manifest
    moves the old one to manifest_history/."""
    m = {"prompt_version": args.prompt_version, "model": args.model, "backend": args.backend,
         "effort": args.effort or "", "candidates": repo_relative(args.candidates),
         "list_rule": "b3_selected" if args.b3 else f"z >= {args.z:g}",
         "traits": None, "targets": None, "n_targets": int(len(groups)), "n_pairs": int(groups.str.len().sum()),
         "script_sha256": file_sha256(Path(__file__))}
    r1, r2 = version_traits(args.prompt_version)
    if args.traits_table is not None and args.traits_sha256:
        m["traits"] = {"path": repo_relative(args.traits), "sha256": args.traits_sha256,
                       "lines": [TRAIT_LABELS[n] for n in r1]}
    if args.traits_table is not None and getattr(args, "traits_r2_sha256", None):
        m["traits_r2"] = {"path": repo_relative(args.traits_r2), "sha256": args.traits_r2_sha256,
                          "lines": [TRAIT_LABELS[n] for n in r2]}
    if args.targets_file:
        m["targets"] = {"path": repo_relative(args.targets_file), "sha256": file_sha256(Path(args.targets_file)),
                        "ids": sorted(groups.index)}
    dest = out.runs.parent / "manifest.json"
    if dest.exists():
        old = json.loads(dest.read_text(encoding="utf-8"))
        if {k: v for k, v in old.items() if k != "written_at"} == m:
            return dest
        move_to_history(dest, out.runs.parent / "manifest_history")
    dest.write_text(json.dumps({**m, "written_at": now_iso()}, indent=1), encoding="utf-8")
    return dest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", help="output folder (default: outputs-local/v2/04_selection/<candidates run>_<prompt "
                                 "version>_<backend>_<model>/)")
    p.add_argument("--candidates", help="step 4 run folder (default: the latest)")
    p.add_argument("--prompt-version", choices=sorted(PROMPT_EXCLUDES), default=PROMPT_VERSION,
                   help=f"default {PROMPT_VERSION} (no company size); {SAVED_PROMPT_VERSION} rebuilds the saved prompts")
    p.add_argument("--z", type=float, default=DEFAULT_Z, help="candidates at z >= this (default 2)")
    p.add_argument("--b3", action="store_true",
                   help="screen the v1 baseline's lists (B3, mutual top 10) from the latest method1_candidates.py run "
                        "instead of v0's z >= 2 shortlist")
    p.add_argument("--tickers", nargs="*", help="only these targets")
    p.add_argument("--targets-file", help="only these targets: IQ ids, one per line, or a CSV with target_id")
    p.add_argument("--traits", help="round-1 trait table (E1-E6) for the 2026-11-28 versions (default: current.toml "
                                    "[analysis.trait_uplift] traits)")
    p.add_argument("--traits-r2", default=str(CURRENT_TRAITS_R2),
                   help="round-2 trait table (E7-E10) for 2026-11-28h to k (default: current.toml [traits_r2] table)")
    p.add_argument("--limit", type=int, help="stop after N targets")
    p.add_argument("--refresh", action="store_true", help="judge current targets again")
    p.add_argument("--backend", choices=["claude", "claude-cli", "codex"], default="claude",
                   help="claude: Anthropic API; claude-cli: Claude Code CLI; codex: Codex CLI")
    p.add_argument("--model", help="default: claude-haiku-5-5 for claude, claude-sonnet-5-5 for claude-cli, gpt-6.1-sol for codex")
    p.add_argument("--effort", choices=["low", "medium", "high"], help="default: the model's own")
    p.add_argument("--workers", type=int, default=2, help="targets in parallel")
    p.add_argument("--dry-run", action="store_true", help="write the prompts only")
    p.add_argument("--tables-only", action="store_true", help="only rebuild judgments.csv")
    args = p.parse_args()
    args.model = args.model or ("gpt-6.1-sol" if args.backend == "codex" else DEFAULT_MODEL[args.backend])
    args.candidates = (Path(args.candidates) if args.candidates
                       else CURRENT_B3 if args.b3 else latest_candidates())
    out = output_paths(Path(args.out) if args.out else DEFAULT_OUT_ROOT /
                       f"{'b3_' if args.b3 else ''}{args.candidates.name}_{args.prompt_version}_{args.backend}_{args.model}")
    for d in (out.runs, out.judgments, out.logs):
        d.mkdir(parents=True, exist_ok=True)

    pairs, info, facets = load_inputs(args.candidates, args.z, "selected" if args.b3 else "z")
    groups = pairs.groupby("target")["comp"].apply(list)
    if args.tickers:
        wanted = set(args.tickers)
        groups = groups[groups.index.map(info["target_ciq_ticker"]).isin(wanted)]
    if args.targets_file:
        ids = read_target_ids(Path(args.targets_file))
        unknown = sorted(set(ids) - set(groups.index))
        if unknown:
            raise SystemExit(f"{len(unknown)} ids in {args.targets_file} have no candidate list, e.g. {unknown[:3]}")
        groups = groups[groups.index.isin(ids)]
    if args.limit:
        groups = groups.iloc[:args.limit]
    missing = sorted((set(pairs["target"]) | set(pairs["comp"])) - set(facets.index))
    if missing:
        raise SystemExit(f"{len(missing)} companies have no current facets, e.g. {missing[:3]}")
    args.traits_table, args.traits_sha256, args.traits_r2_sha256 = None, None, None
    r1, r2 = version_traits(args.prompt_version)
    tables = []
    if r1:
        args.traits = Path(args.traits) if args.traits else CURRENT_TRAITS
        args.traits_sha256 = file_sha256(args.traits)
        tables.append((args.traits, r1, load_traits(args.traits)))
    if r2:
        args.traits_r2 = Path(args.traits_r2)
        args.traits_r2_sha256 = file_sha256(args.traits_r2)
        tables.append((args.traits_r2, r2, load_traits(args.traits_r2)))
    for path, names, table in tables:
        if set(names) - set(table.columns):
            raise SystemExit(f"the trait table {path} has no column {sorted(set(names) - set(table.columns))}")
        no_traits = sorted((set(pairs["target"]) | set(pairs["comp"])) - set(table.index))
        if no_traits:
            raise SystemExit(f"{len(no_traits)} companies are not in the trait table {path}, e.g. {no_traits[:3]}")
    if tables:
        args.traits_table = pd.concat([t[list(names)] for _, names, t in tables], axis=1)

    if args.dry_run:
        out.prompts_dry_run.mkdir(parents=True, exist_ok=True)
        for target, comps in groups.items():
            (out.prompts_dry_run / f"{target}.txt").write_text(
                build_prompt(target, comps, info, facets, args.prompt_version, args.traits_table)[0],
                encoding="utf-8")
        print(f"wrote {len(groups)} prompts to {out.prompts_dry_run}")
        return

    if not args.tables_only:
        write_manifest(out, args, groups)
        log = out.logs / f"judge_{stamp()}.log"
        rule = "v1 baseline lists (B3)" if args.b3 else f"z >= {args.z:g}"
        print(f"candidates {args.candidates.name}, {rule}: {len(groups)} targets, "
              f"{groups.str.len().sum()} pairs; model {args.model}; prompt {args.prompt_version}; log {log.name}")
        totals, started = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}, time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as pool, log.open("w", encoding="utf-8") as lf:
            futures = {pool.submit(judge_one, t, c, info, facets, out, args): t for t, c in groups.items()}
            for n, fut in enumerate(as_completed(futures), 1):
                r = fut.result()
                for k in totals:
                    totals[k] += r.get("usage", {}).get(k, 0) or 0
                line = (f"[{n}/{len(groups)}] {info.loc[r['target'], 'target_ciq_ticker']:<8} {r['status']:<12}"
                        + (f" issues: {'; '.join(r['issues'])}" if r.get("issues") else ""))
                print(line)
                lf.write(line + "\n")
                if r.get("stop_run"):
                    print("stopping: usage limit, login or credit refused; finished targets are kept (rerun the same command later)")
                    for f in futures:
                        f.cancel()
                    break
        print(f"tokens: {totals}; {time.time() - started:.0f} s")
    dest = write_tables(out, pairs, info, args.prompt_version)
    print("wrote", dest)


if __name__ == "__main__":
    main()
