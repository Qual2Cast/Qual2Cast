"""Paired ten-target test of selective split corrections in the v0 peer judge.

Both modes use the updated SIC2 candidate pool, the same model and valuation
rule. The intervention adds source-corrected current scope for firms with
multiple evidenced business groups or completed exits.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

import pandas as pd

import business_split_refinement as refine
import fill_facets as ff
import judge_comps as judge
import valuation
from project_data import OUTPUTS_LOCAL


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = OUTPUTS_LOCAL / "comps_pilot_targets/candidates/20261027T204930Z"
OUTPUT = OUTPUTS_LOCAL / "comps_pilot_targets/business_structure_refinement/peer_test"
TARGETS = ("PCTY", "WEN", "CSL", "AFG", "BOC", "NWSA", "AZZ", "BBCP", "BUKS", "SNFC.A")
MODEL = "gpt-6.1-sol"


def scope_addendum(target: str, labels: dict[str, str], info: pd.DataFrame,
                   snapshot: dict, refined: dict) -> str:
    corrections = []
    for company_id in [target, *labels.values()]:
        ticker = info.loc[company_id, "target_ciq_ticker"]
        if ticker not in refined:
            continue
        decision = snapshot[ticker]["decision"]
        scope = refined[ticker]
        if len(scope["groups"]) == 1 and not scope["exited"]:
            continue
        corrections.append(f"- {info.loc[company_id, 'target_company_name']}: {refine.scope_note(decision, scope)}")
    if not corrections:
        return ""
    return ("\n\nSource-corrected scope for companies named above. Use this to correct stale "
            "business descriptions. Evaluate the whole company; do not treat "
            "related products as separate businesses or assume that every "
            "activity has equal economic weight.\n" + "\n".join(corrections))


def call_or_load(prompt: str, labels: dict[str, str], path: Path, model: str,
                 workdir: str) -> list[dict]:
    path.mkdir(parents=True, exist_ok=True)
    response = path / "response.json"
    prompt_path = path / "prompt.txt"
    if response.exists():
        meta_path = path / "run.json"
        previous_model = (json.loads(meta_path.read_text(encoding="utf-8")).get("model", MODEL)
                          if meta_path.exists() else MODEL)
        if (not prompt_path.exists() or prompt_path.read_text(encoding="utf-8") != prompt
                or previous_model != model):
            archive = path.with_name(path.name + "_history_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            path.rename(archive)
            path.mkdir()
            response = path / "response.json"
            prompt_path = path / "prompt.txt"
    if not response.exists():
        prompt_path.write_text(prompt, encoding="utf-8")
        schema = path / "schema.json"
        schema.write_text(json.dumps(judge.answer_schema(list(labels)), indent=2), encoding="utf-8")
        result = ff.call_codex(prompt, path, schema, workdir, model, "low")
        (path / "run.json").write_text(json.dumps({"model": model, **{key: value for key, value in result.items()
                                                   if key not in ("text", "command")}}, indent=2),
                                       encoding="utf-8")
        if result["llm_status"] != "ok":
            raise RuntimeError(f"{path.name}: {result.get('error', result['llm_status'])}")
    checked, problems = judge.check_answer(json.loads(response.read_text(encoding="utf-8")), labels)
    if problems:
        raise ValueError(f"Invalid peer response at {path}: {problems}")
    return checked


def evaluate_peers(peers: pd.DataFrame, candidates: pd.DataFrame,
                   targets: dict[str, str], financials: pd.DataFrame,
                   training_pool: list[str]) -> pd.DataFrame:
    multiple = financials.set_index("IQ_COMPANY_ID")["target_ev_to_ebitda"].astype(float)
    fallback = valuation.no_matching(list(targets.values()), training_pool, multiple)
    rows = []
    for mode in ("control", "selective_scope"):
        selected = peers[(peers["mode"] == mode) & peers["score"].eq(1)]
        estimates = (valuation.estimate(selected[["target", "comp", "similarity"]], multiple,
                                        weight="similarity") if not selected.empty
                     else pd.DataFrame(columns=["estimate", "comps"]))
        for ticker, company_id in targets.items():
            matched = company_id in estimates.index
            estimate = estimates.loc[company_id] if matched else fallback.loc[company_id]
            actual = float(multiple[company_id])
            rows.append({"ticker": ticker, "mode": mode,
                         "estimate": float(estimate["estimate"]), "actual": actual,
                         "comps": int(estimate["comps"]),
                         "basis": "matched peers" if matched else "no-matching fallback",
                         "absolute_percentage_error": 100 * abs(float(estimate["estimate"]) / actual - 1)})
    return pd.DataFrame(rows)


def run(snapshot_path: Path, candidates_path: Path, output: Path, model: str,
        target_tickers: tuple[str, ...] = TARGETS) -> dict:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))["companies"]
    corrections = json.loads(refine.CORRECTIONS.read_text(encoding="utf-8")) if refine.CORRECTIONS.exists() else {}
    corrected = {ticker: refine.apply_source_corrections(record["decision"], corrections.get(ticker))
                 for ticker, record in snapshot.items()}
    refined = {ticker: refine.refine_decision(corrected[ticker])
               for ticker, record in snapshot.items()}
    candidates, info, facets = judge.load_inputs(candidates_path, 2.0)
    universe_run = json.loads((candidates_path / "run.json").read_text(encoding="utf-8"))["universe_run"]
    split_run = json.loads((candidates_path / "run.json").read_text(encoding="utf-8"))["split_run"]
    split = pd.read_csv(OUTPUTS_LOCAL / "comps_pilot_targets/split" / split_run / "split.csv",
                        dtype={"IQ_COMPANY_ID": str})
    training_pool = split.loc[split["sample"] == "training", "IQ_COMPANY_ID"].tolist()
    financials = pd.read_csv(OUTPUTS_LOCAL / "comps/universe" / universe_run / "financials.csv",
                             dtype={"IQ_COMPANY_ID": str})
    targets = {ticker: info.index[info["target_ciq_ticker"] == ticker][0]
               for ticker in target_tickers}
    rows = []
    with tempfile.TemporaryDirectory(prefix="split-peer-eval-") as workdir:
        for index, (ticker, target) in enumerate(targets.items(), start=1):
            pool = candidates[candidates["target"] == target].copy()
            prompt, labels = judge.build_prompt(target, pool["comp"].tolist(), info, facets)
            addendum = scope_addendum(target, labels, info,
                                      {key: {"decision": value} for key, value in corrected.items()}, refined)
            control = call_or_load(prompt, labels, output / "calls" / ticker / "control", model, workdir)
            variant = (call_or_load(prompt + addendum, labels,
                                    output / "calls" / ticker / "selective_scope", model, workdir)
                       if addendum else control)
            for mode, answers in (("control", control), ("selective_scope", variant)):
                for answer in answers:
                    candidate = pool.loc[pool["comp"] == answer["comp"]].iloc[0]
                    rows.append({"target": target, "ticker": ticker, "mode": mode,
                                 "comp": answer["comp"], "peer": candidate["comp_ticker"],
                                 "score": answer["score"], "reason": answer["reason"],
                                 "similarity": float(candidate["similarity"]),
                                 "scope_added": bool(addendum)})
            print(f"{index}/{len(targets)} {ticker}: {len(pool)} candidates, scope added={bool(addendum)}", flush=True)
    peers = pd.DataFrame(rows)
    valuation_results = evaluate_peers(peers, candidates, targets, financials, training_pool)
    output.mkdir(parents=True, exist_ok=True)
    peers.to_csv(output / "peer_judgments.csv", index=False)
    valuation_results.to_csv(output / "valuation_comparison.csv", index=False)
    decisions = peers.pivot(index=["target", "comp"], columns="mode", values="score")
    summary = {"run_at_utc": datetime.now(timezone.utc).isoformat(),
               "model": model, "candidates_run": candidates_path.name,
               "targets": len(targets), "candidate_pairs": len(decisions),
               "scope_prompts": sum(peers[peers["mode"] == "control"].groupby("ticker")["scope_added"].first()),
               "changed_peer_decisions": int((decisions["control"] != decisions["selective_scope"]).sum())}
    for mode in ("control", "selective_scope"):
        values = valuation_results[valuation_results["mode"] == mode]
        summary[mode] = {"matched_targets": int(values["basis"].eq("matched peers").sum()),
                         "median_ape": float(values["absolute_percentage_error"].median())}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", type=Path, default=refine.SNAPSHOT)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--targets", nargs="+", default=list(TARGETS))
    args = parser.parse_args()
    print(json.dumps(run(args.snapshot, args.candidates, args.out, args.model,
                         tuple(args.targets)), indent=2))
