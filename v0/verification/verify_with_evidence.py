"""
Judge facet fills against collected evidence, and measure how much each
evidence source adds.

A stand-in verifier, so the evidence module can be measured on its own; the
team's verifier (Riya's) can read the same Evidence lines instead. One Claude
Haiku call per company and evidence tier:

  P     the saved scrape pages only (what a website-only check sees)
  PW    plus the same-site crawl (evidence.py, W lines)
  PWS   plus web search results (S lines)

For each facet the model gives a verdict, cites the evidence labels and
gives a short reason. Code then applies the rules (as apply_split_check does
for business splits):
- a verdict other than not_found with no cited label that exists becomes
  not_found (issue uncited);
- a contradiction resting only on database sources becomes not_found (issue
  database_only): the 20-company check found the databases unreliable.

  python v0/verification/verify_with_evidence.py --facets outputs-local/comps/facets_verify20 \
      --tickers PCTY ROAD ... --gold outputs-local/comps/facets_verify20/verification/facet_verification_20.csv

Writes outputs-local/comps/evidence_verify/<run>/: verdicts.csv (one row per
company, facet and tier), score.csv (against the gold labels, if given), and
each call's prompt and answer under calls/.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import facets as fc  # noqa: E402
import fill_facets as ff  # noqa: E402
import evidence as evm  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

PROMPT_VERSION = "2026-10-26a"
OUT = OUTPUTS_LOCAL / "comps" / "evidence_verify"
VERDICTS = ["supported", "partly", "contradicted", "missed", "not_found"]
TIERS = ["P", "PW", "PWS"]

INSTRUCTIONS = """\
You check descriptions of a company against evidence. A research project \
uses these descriptions to find comparable companies, so wrong or \
out-of-date facts matter.

You get the company's name and website, the facet values another model \
wrote, and evidence lines. Each evidence line starts with a label: [P1.3] is \
a saved page of the company's website, [W2.4] another page of its website, \
[S3.1] a web search result. Each source says its type: company_site, \
press_release, news, reference or database.

For each facet, compare the value with the evidence only. Do not use what \
you already know about the company.
- "supported": the evidence confirms the category and the main claim. A \
missing minor item is fine.
- "partly": the main claim is confirmed, but an item or detail is wrong, \
not confirmed while others are, or out of date; or a size category is one \
step off what the company says about itself.
- "contradicted": the evidence conflicts with the category or the main \
claim, for example a geography category narrower than the countries the \
evidence names, a business the evidence says was sold, or a single-line \
"niche specialist" when the evidence shows several lines.
- "missed": the facet is "unknown" but the evidence states it.
- "not_found": the evidence doesn't say.

For every verdict except "not_found", cite the labels of the 1 to 3 lines \
that decide it. Prefer company_site and press_release sources; a database \
source alone is weak. Keep each reason to one short sentence. Give exactly \
one check per facet. Everything you need is in this message. Do not run \
commands, open files or search the web. Write the JSON on one line."""


def schema() -> dict:
    check = {"type": "object", "additionalProperties": False,
             "required": ["facet", "verdict", "cite", "reason"],
             "properties": {"facet": {"type": "string", "enum": fc.FACET_NAMES},
                            "verdict": {"type": "string", "enum": VERDICTS},
                            "cite": {"type": "array", "items": {"type": "string"}},
                            "reason": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": ["checks", "notes"],
            "properties": {"checks": {"type": "array", "items": check}, "notes": {"type": "string"}}}


def facet_block(row: pd.Series) -> str:
    lines = []
    for f in fc.FACETS:
        status = row.get(f"{f.name}_status", "")
        value = row.get(f.name, "") if status == "filled" else status or "unknown"
        lines.append(f"{fc.FACET_ID[f.name]} {f.name} ({f.label}): {value}")
    return "\n".join(lines)


def build_prompt(row: pd.Series, ev: evm.Evidence, tier: str) -> tuple[str, dict[str, str]]:
    lines = ev.subset(tier)
    body = ev.text(tier) or "(no evidence)"
    head = f"Company: {row['target_company_name']}\nWebsite: {ev.website}"
    return (INSTRUCTIONS + "\n\n" + head + "\n\nFacet values:\n" + facet_block(row)
            + "\n\nEvidence:\n" + body), lines


def apply_rules(raw: dict, lines: dict[str, str], ev: evm.Evidence) -> list[dict]:
    """One checked verdict per facet (see the module docstring)."""
    said = {c["facet"]: c for c in raw.get("checks", []) if c.get("facet") in fc.FACET_BY_NAME}
    out = []
    for f in fc.FACETS:
        c = said.get(f.name, {"verdict": "not_found", "cite": [], "reason": "no check given"})
        labels = [lab for x in c.get("cite", []) for lab in evm_labels(x)]
        found = [lab for lab in dict.fromkeys(labels) if lab in lines]
        types = {ev.sources.get(lab.split(".")[0], {}).get("type", "") for lab in found}
        verdict, issue = c["verdict"], ""
        if verdict != "not_found" and not found:
            verdict, issue = "not_found", "uncited"
        elif verdict == "contradicted" and types == {"database"}:
            verdict, issue = "not_found", "database_only"
        out.append({"facet": f.name, "facet_id": fc.FACET_ID[f.name], "verdict": verdict,
                    "model_verdict": c["verdict"], "cite": "; ".join(found),
                    "cite_urls": " | ".join(dict.fromkeys(ev.sources[lab.split('.')[0]]["url"] for lab in found)),
                    "source_types": "; ".join(sorted(t for t in types if t)),
                    "reason": c.get("reason", ""), "issue": issue})
    return out


def evm_labels(text: str) -> list[str]:
    import re
    return re.findall(r"[PWS]\d+\.\d+", text)


def load_evidence(iq_id: str) -> evm.Evidence | None:
    """The latest saved evidence bundle for a company, if any."""
    runs = sorted((evm.EVIDENCE_OUT / iq_id).glob("*/evidence.json"))
    if not runs:
        return None
    d = json.loads(runs[-1].read_text(encoding="utf-8"))
    return evm.Evidence(**d)


def score(verdicts: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    """Per tier, against gold labels (facet_verification_20.csv format:
    ticker, facet, verdict in supported/partly/contradicted/missed/no_evidence).
    A gold 'problem' is partly, contradicted or missed; gold no_evidence rows
    are left out. decided = verdict is not not_found."""
    g = gold[["ticker", "facet", "verdict"]].rename(columns={"verdict": "gold"})
    m = verdicts.merge(g, on=["ticker", "facet"])
    m = m[m.gold != "no_evidence"]
    m["gold_problem"] = m.gold.isin(["partly", "contradicted", "missed"])
    m["decided"] = m.verdict != "not_found"
    m["flag_problem"] = m.verdict.isin(["partly", "contradicted", "missed"])
    rows = []
    for tier, x in m.groupby("tier"):
        d = x[x.decided]
        rows.append({"tier": tier, "facets": len(x), "decided": len(d),
                     "decided_%": round(100 * len(d) / len(x), 1) if len(x) else None,
                     "agree_on_decided_%": round(100 * (d.flag_problem == d.gold_problem).mean(), 1) if len(d) else None,
                     "exact_verdict_%": round(100 * (d.verdict == d.gold).mean(), 1) if len(d) else None,
                     "problems_in_gold": int(x.gold_problem.sum()),
                     "problems_caught": int((x.gold_problem & x.flag_problem).sum()),
                     "false_alarms": int((~x.gold_problem & x.flag_problem).sum())})
    return pd.DataFrame(rows).set_index("tier").reindex([t for t in TIERS if t in set(m.tier)])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--facets", required=True, help="a fill output folder (has tables/facets.csv)")
    p.add_argument("--tickers", nargs="+", required=True)
    p.add_argument("--tiers", nargs="+", default=TIERS, choices=TIERS)
    p.add_argument("--gold", help="gold labels CSV (ticker, facet, verdict)")
    p.add_argument("--provider", choices=["serper", "brave", "tavily"])
    p.add_argument("--refresh-evidence", action="store_true", help="collect evidence again")
    p.add_argument("--backend", choices=["codex", "claude-cli", "claude"], default="claude")
    p.add_argument("--model")
    p.add_argument("--effort", choices=["low", "medium", "high"])
    args = p.parse_args()
    args.model = args.model or ff.DEFAULT_MODEL[args.backend]

    table = pd.read_csv(Path(args.facets) / "tables" / "facets.csv", dtype=str).fillna("")
    from universe import build_universe
    companies, _ = build_universe()
    table = table.merge(companies[["IQ_COMPANY_ID", "target_ciq_ticker", "target_ciq_website"]], on="IQ_COMPANY_ID")
    table = table[table.target_ciq_ticker.str.upper().isin({t.upper() for t in args.tickers})
                  & table.llm_status.eq("ok")]
    run = OUT / datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    (run / "calls").mkdir(parents=True, exist_ok=True)
    if args.backend == "claude":
        ff.claude_api_key()
    rows = []
    for _, row in table.iterrows():
        ev = None if args.refresh_evidence else load_evidence(row.IQ_COMPANY_ID)
        if ev is None:
            ev = evm.gather(row.IQ_COMPANY_ID, row.target_company_name, row.target_ciq_website,
                            provider=args.provider)
        for tier in args.tiers:
            prompt, lines = build_prompt(row, ev, tier)
            call_dir = run / "calls" / row.IQ_COMPANY_ID / tier
            call_dir.mkdir(parents=True, exist_ok=True)
            (call_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
            res = ff.call_model(prompt, call_dir, schema(), args.model, args.effort,
                                backend=args.backend, instructions_len=len(INSTRUCTIONS))
            if res["llm_status"] != "ok":
                print(f"{row.target_ciq_ticker:<6} {tier:<4} {res['llm_status']} {res.get('error', '')}")
                if res.get("stop_run"):
                    raise SystemExit("Stopped: API key refused or credit ran out.")
                continue
            checked = apply_rules(json.loads(res["text"]), lines, ev)
            for c in checked:
                rows.append({"ticker": row.target_ciq_ticker, "IQ_COMPANY_ID": row.IQ_COMPANY_ID, "tier": tier,
                             "evidence_lines": len(lines), "evidence_dir": ev.log_dir, **c})
            counts = pd.Series([c["verdict"] for c in checked]).value_counts().to_dict()
            print(f"{row.target_ciq_ticker:<6} {tier:<4} lines {len(lines):>4}  {counts}", flush=True)
    verdicts = pd.DataFrame(rows)
    verdicts.to_csv(run / "verdicts.csv", index=False)
    (run / "run.json").write_text(json.dumps({"prompt_version": PROMPT_VERSION, "backend": args.backend, "model": args.model,
                                              "facets": str(args.facets), "tickers": args.tickers,
                                              "tiers": args.tiers}, indent=1), encoding="utf-8")
    print(f"\nVerdicts -> {run / 'verdicts.csv'}")
    if args.gold and len(verdicts):
        s = score(verdicts, pd.read_csv(args.gold, dtype=str).fillna(""))
        s.to_csv(run / "score.csv")
        print("\nAgainst the gold labels (gold 'no_evidence' rows left out):")
        print(s.to_string())


if __name__ == "__main__":
    main()
