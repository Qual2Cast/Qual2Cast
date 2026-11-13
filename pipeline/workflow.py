"""Two pipelines sharing fresh facets, B3 retrieval and an evidence-only judge.

The mathematical methods and prompts live in v1/scripts. This module owns
configuration, stage orchestration and the provider/model-specific run layout.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import tomllib
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "v1/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "src"))
import candidates as cd
import cosine_then_llm as selector
import facet_weighting as fw
import facets as fc
from cli_models import executable
from method1_candidates import tables_from_similarity
from peer_evaluation import Config as JudgeConfig, PeerEvaluation
from project_data import sha256, snapshot_path
from universe import build_universe
from valuation import estimate

ROUTES = ("b3", "b3_llm_filter")


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def slug(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value)


def resolve(value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else ROOT / path


class Workflow:
    def __init__(self, config="pipeline/configs/codex.toml", run_dir=None):
        self.config_path = resolve(config)
        self.config = tomllib.loads(self.config_path.read_text(encoding="utf-8"))
        c = self.config
        if c["provider"] not in ("codex", "claude"):
            raise ValueError("provider must be codex or claude (Claude Code CLI)")
        if c["targets"] not in ("training", "holdout", "all"):
            raise ValueError("targets must be training, holdout or all")
        if c["workers"] < 1:
            raise ValueError("workers must be positive")
        self.backend = "codex" if c["provider"] == "codex" else "claude-cli"
        variant = "__".join(f"{role}-{slug(c[role]['model'])}-{c[role]['effort']}"
                            for role in ("fill", "filter", "judge"))
        self.run_dir = resolve(run_dir) if run_dir else ROOT / "outputs-local/pipeline" / c["provider"] / variant / stamp()
        self.facets_dir = self.run_dir / "shared" / f"facets-{slug(c['fill']['model'])}"
        self.candidates_dir = self.run_dir / "shared/b3_candidates"
        self.filter_dir = self.run_dir / "pipelines/b3_llm_filter" / f"filter-{slug(c['filter']['model'])}"
        self.judge_dir = self.run_dir / "shared" / f"judge-{slug(c['judge']['model'])}"

    def plan(self):
        print("Provider:", self.config["provider"], "via", self.backend)
        for role in ("fill", "filter", "judge"):
            print(f"  {role}: {self.config[role]['model']} ({self.config[role]['effort']})")
        print("Pipelines: B3; B3 + LLM filter. Same facets, candidate pool and judge.")
        print("Targets:", self.config["targets"], self.config.get("target_tickers") or "all in split")
        print("Stages: inputs → facets → B3 → filter → judge → valuation + comparison")
        print("Outputs:", self.run_dir)

    def save(self, relative, value):
        path = self.run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            history = self.run_dir / "history" / stamp() / relative
            history.parent.mkdir(parents=True, exist_ok=True)
            path.replace(history)
        if isinstance(value, pd.DataFrame):
            value.to_csv(path, index=False)
        else:
            path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def table(self, relative):
        return pd.read_csv(self.run_dir / relative, dtype={"IQ_COMPANY_ID": str, "target": str, "comp": str})

    def prepare(self):
        """Freeze the snapshot, original split, company metadata and financial table."""
        snapshot = snapshot_path()
        split_file = resolve(self.config["split_file"])
        inputs = {str(p.relative_to(ROOT)): sha256(p) for p in (snapshot, split_file)}
        pages = ROOT / "outputs-local/website_scrape/page_text"
        inputs.update({str(p.relative_to(ROOT)): sha256(p) for p in sorted(pages.glob("*.json"))})
        settings = {"config": self.config, "input_hashes": inputs}
        path = self.run_dir / "run.json"
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            if any(old[k] != v for k, v in settings.items()):
                raise ValueError("Config or inputs changed. Start a new run instead of mixing experiments.")
            print("Resuming", self.run_dir)
            return self.table("inputs/targets.csv")
        companies, financials = build_universe()
        info = companies[companies.in_universe].copy()
        split = pd.read_csv(split_file, dtype=str)
        if set(split.IQ_COMPANY_ID) != set(info.IQ_COMPANY_ID):
            raise ValueError("The frozen split does not match the current universe")
        target_ids = split if self.config["targets"] == "all" else split[split["sample"].eq(self.config["targets"])]
        targets = info[info.IQ_COMPANY_ID.isin(target_ids.IQ_COMPANY_ID)]
        wanted = {s.upper() for s in self.config.get("target_tickers", [])}
        if wanted:
            targets = targets[targets.target_ciq_ticker.str.upper().isin(wanted)]
            if missing := wanted - set(targets.target_ciq_ticker.str.upper()):
                raise ValueError(f"Tickers absent from the chosen target split: {sorted(missing)}")
        self.save("inputs/companies.csv", info)
        self.save("inputs/financials.csv", financials) # never passed to any model
        self.save("inputs/split.csv", split)
        self.save("inputs/targets.csv", targets)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        code_files = [Path(__file__), ROOT / "pipeline/run.py", *[SCRIPTS / f"{name}.py" for name in
                      ("facets", "fill_facets", "facet_weighting", "method1_candidates", "cosine_then_llm",
                       "peer_evaluation", "cli_models", "valuation", "universe", "candidates")]]
        self.save("run.json", {**settings, "created_at": stamp(), "git_commit": commit,
                  "code_hashes": {str(p.relative_to(ROOT)): sha256(p) for p in code_files},
                  "pipelines": list(ROUTES), "judge_rubric": "0–3, separate from selection",
                  "pool": "training only; self excluded", "targets": len(targets),
                  "split_note": "Existing split reused; holdout is development evidence, not fresh validation."})
        print(f"Inputs: {len(info)} companies, {len(targets)} targets. Financial fields saved separately.")
        return targets

    def fill(self):
        """Fresh provider-specific profiles for the whole pool, with resumable gap fills."""
        executable(self.backend)
        role = self.config["fill"]
        command = [sys.executable, str(SCRIPTS / "fill_facets.py"), "--backend", self.backend,
                   "--model", role["model"], "--effort", role["effort"],
                   "--out", str(self.facets_dir), "--workers", str(self.config["workers"])]
        self.save("shared/fill_command.json", command)
        print("Facets: filling all universe companies, including peers; completed profiles are reused.", flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
        facets = pd.read_csv(self.facets_dir / "tables/facets.csv", dtype=str).fillna("")
        print(f"Facet coverage: {facets.loc[facets.llm_status.eq('ok'), 'IQ_COMPANY_ID'].nunique()} companies.")
        return facets

    def rank(self):
        """The same B3 mathematics as v1, using only this run's new profiles."""
        info, split, targets = (self.table(f"inputs/{name}.csv") for name in ("companies", "split", "targets"))
        facet_path = self.facets_dir / "tables/facets.csv"
        facets = pd.read_csv(facet_path, dtype=str).fillna("")
        facets = facets[facets.prompt_version.eq(fc.PROMPT_VERSION) & facets.llm_status.eq("ok")]
        available = set(facets.loc[facets.business_id.eq("B1"), "IQ_COMPANY_ID"])
        coverage = info[["IQ_COMPANY_ID", "target_ciq_ticker"]].assign(has_profile=info.IQ_COMPANY_ID.isin(available))
        self.save("shared/profile_coverage.csv", coverage)
        if not available:
            raise ValueError("No usable profiles yet. Check the fill logs and resume the facet stage.")
        info = info[info.IQ_COMPANY_ID.isin(available)]
        texts = fw.facet_texts(facets).reindex(info.IQ_COMPANY_ID)
        vectors = fw.embed_texts({t for name in texts for t in texts[name].dropna()},
                                self.run_dir / "shared/embeddings/texts_all-mpnet-base-v2.npz")
        similarity, _, saturation = fw.method1_similarity(texts, vectors)
        pool = split.loc[split["sample"].eq("training") & split.IQ_COMPANY_ID.isin(available), "IQ_COMPANY_ID"].tolist()
        ids = targets.loc[targets.IQ_COMPANY_ID.isin(available), "IQ_COMPANY_ID"].tolist()
        ranking, top = tables_from_similarity(similarity, list(texts.index), ids, pool,
                                              info.set_index("IQ_COMPANY_ID").target_ciq_ticker)
        self.save("shared/b3_candidates/ranking.csv.gz", ranking)
        self.save("shared/b3_candidates/candidates.csv", top)
        self.save("shared/b3_candidates/run.json", {
            "method": "B3: 50% MPNet cosine + 50% TF-IDF cosine; information weights; none missing; F9 excluded",
            "facets_sha256": sha256(facet_path), "facet_override": str(facet_path),
            "prompt_version": fc.PROMPT_VERSION, "embedding_model": cd.EMBED_MODEL,
            "top_k": fw.TOP_K, "min_comps": fw.MIN_COMPS, "saturation_k": saturation,
            "pool_companies": len(pool), "requested_targets": len(targets), "ranked_targets": len(ids),
            "missing_profile_ids": sorted(set(coverage.loc[~coverage.has_profile, "IQ_COMPANY_ID"])),
            "representation": "B1 only; IDF and information saturation use all available universe profiles"})
        chosen = top[top.selected].copy()
        self.save("pipelines/b3/peers.csv", chosen)
        print(f"B3: {len(chosen)} selected pairs, {len(ids)}/{len(targets)} targets with profiles.")
        return top

    def filter(self):
        """Binary selector on B3 pairs. Failed/missing decisions never become rejects."""
        pairs = self.table("pipelines/b3/peers.csv")
        info = self.table("inputs/companies.csv").set_index("IQ_COMPANY_ID")
        facets = pd.read_csv(self.facets_dir / "tables/facets.csv", dtype=str).fillna("")
        facets = facets[facets.business_id.eq("B1") & facets.llm_status.eq("ok")].set_index("IQ_COMPANY_ID")
        role = self.config["filter"]
        args = SimpleNamespace(backend=self.backend, model=role["model"], effort=role["effort"],
                               prompt_version=selector.PROMPT_VERSION, refresh=False, b3=True,
                               z=selector.DEFAULT_Z, candidates=self.candidates_dir)
        paths = selector.output_paths(self.filter_dir)
        for folder in (paths.runs, paths.judgments, paths.logs):
            folder.mkdir(parents=True, exist_ok=True)
        groups = list(pairs.groupby("target")["comp"].apply(list).items())
        executable(self.backend)
        stopped = threading.Event()
        def screen(group):
            target, comps = group
            if stopped.is_set():
                return {"target": target, "status": "not_run"}
            result = selector.judge_one(target, comps, info, facets, paths, args)
            if result.get("stop_run"):
                stopped.set()
            print(f"Filter {info.loc[target, 'target_ciq_ticker']}: {result['status']}", flush=True)
            return result
        with ThreadPoolExecutor(max_workers=self.config["workers"]) as pool:
            list(pool.map(screen, groups))
        selector.write_tables(paths, pairs, info)
        raw = pd.read_csv(paths.tables / "judgments.csv", dtype={"target": str, "comp": str})
        complete = {}
        for target, comps in groups:
            path = paths.judgments / f"{target}.json"
            row = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"llm_status": "not_run"}
            complete[target] = row["llm_status"] == "ok" and not row["issues"] and len(row["comps"]) == len(comps)
        decisions = pairs.merge(raw[["target", "comp", "score", "reason"]], on=["target", "comp"], how="left", validate="one_to_one")
        decisions["filter_complete"] = decisions.target.map(complete).fillna(False)
        decisions["accepted"] = decisions.score.eq(1).where(decisions.filter_complete)
        self.save("pipelines/b3_llm_filter/decisions.csv", decisions)
        peers = decisions[decisions.accepted.eq(True)].copy()
        self.save("pipelines/b3_llm_filter/peers.csv", peers)
        print(f"Filter: {len(peers)}/{len(pairs)} pairs accepted; {sum(not v for v in complete.values())} incomplete targets.")
        return decisions

    def judge(self, start_pair=1):
        """Grade the union once; neither filter reasons nor facets enter judge prompts."""
        pairs = self.table("pipelines/b3/peers.csv")
        role = self.config["judge"]
        evaluator = PeerEvaluation(JudgeConfig(backend=self.backend, model=role["model"], effort=role["effort"],
                                    candidates_run=str(self.candidates_dir),
                                    judgments_file=str(self.filter_dir / "tables/judgments.csv"),
                                    upstream_prompt_version=selector.PROMPT_VERSION,
                                    evidence_words=self.config["evidence_words"], passing_score=self.config["passing_score"]),
                                   self.judge_dir)
        evaluator.prepare_pairs(pairs, self.table("inputs/targets.csv"), self.table("inputs/companies.csv"),
                                [self.run_dir / "run.json", self.run_dir / "pipelines/b3/peers.csv"])
        self.evaluator = evaluator
        return evaluator.run(execute=True, start_pair=start_pair)

    def analyze(self):
        """Join shared grades to each route and calculate a median peer multiple."""
        targets = self.table("inputs/targets.csv")
        financials = self.table("inputs/financials.csv").set_index("IQ_COMPANY_ID")
        multiples = pd.to_numeric(financials.target_ev_to_ebitda, errors="coerce")
        grades = pd.read_csv(self.judge_dir / "tables/pair_judgments.csv", dtype={"target": str, "comp": str})
        grade_cols = ["target", "comp", *[c for c in grades if c.startswith("judge_")],
                      "verdict", "offering_fit", "customer_fit", "business_model_fit", "missing_evidence", "citations", "passes_rubric"]
        decisions = self.table("pipelines/b3_llm_filter/decisions.csv")
        audit = decisions.merge(grades[grade_cols], on=["target", "comp"], how="left", validate="one_to_one")
        self.save("comparison/filter_audit.csv", audit)
        summaries, valuations, judgments = [], {}, {}
        for route in ROUTES:
            peers = self.table(f"pipelines/{route}/peers.csv")
            assessed = peers.merge(grades[grade_cols], on=["target", "comp"], how="left", validate="one_to_one")
            self.save(f"pipelines/{route}/pair_results.csv", assessed)
            result = estimate(peers, multiples, how="median")
            result.index.name = "target"
            result = targets[["IQ_COMPANY_ID", "target_ciq_ticker"]].rename(columns={"IQ_COMPANY_ID": "target"}).merge(
                result.reset_index(), on="target", how="left")
            result["comps"] = result.comps.fillna(0).astype(int)
            result["actual_multiple"] = result.target.map(multiples)
            result["absolute_pct_error"] = 100 * (result.estimate - result.actual_multiple).abs() / result.actual_multiple
            result["selection_status"] = "complete"
            unavailable = set(self.table("shared/profile_coverage.csv").loc[lambda d: ~d.has_profile, "IQ_COMPANY_ID"])
            result.loc[result.target.isin(unavailable), "selection_status"] = "missing_profile"
            if route == "b3_llm_filter":
                incomplete = set(decisions.loc[~decisions.filter_complete, "target"])
                result.loc[result.target.isin(incomplete), "selection_status"] = "filter_incomplete"
            self.save(f"pipelines/{route}/valuation.csv", result)
            valid = assessed.judge_status.eq("ok") & assessed.judge_score.notna()
            row = {"pipeline": route, "requested_targets": len(targets), "selected_pairs": len(peers),
                   "targets_with_estimate": int(result.estimate.notna().sum()),
                   "valuation_coverage": float(result.estimate.notna().mean()),
                   "median_absolute_pct_error": result.absolute_pct_error.median(),
                   "graded_pairs": int(valid.sum()), "judge_mean_score": assessed.loc[valid, "judge_score"].mean(),
                   "judge_pass_rate_on_graded": assessed.loc[valid, "passes_rubric"].mean(),
                   "insufficient_evidence": int(assessed.verdict.eq("insufficient_evidence").sum()),
                   "judge_not_run": int(assessed.judge_status.eq("not_run").sum()),
                   "judge_failures": int((~assessed.judge_status.isin(["ok", "not_run"])).sum())}
            summaries.append(row)
            valuations[route], judgments[route] = result, assessed
        summary = pd.DataFrame(summaries)
        self.save("comparison/summary.csv", summary)
        paired = valuations["b3"][["target", "absolute_pct_error"]].merge(
            valuations["b3_llm_filter"][["target", "absolute_pct_error"]], on="target", suffixes=("_b3", "_filter")).dropna()
        self.save("comparison/common_target_errors.csv", paired)
        self.save("comparison/common_target_summary.json", {"targets": len(paired),
                  "b3_median_absolute_pct_error": paired.absolute_pct_error_b3.median() if len(paired) else None,
                  "filter_median_absolute_pct_error": paired.absolute_pct_error_filter.median() if len(paired) else None})
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
        summary.plot.bar(x="pipeline", y="valuation_coverage", legend=False, ax=axes[0], rot=0)
        axes[0].set(title="Targets with an estimate", ylim=(0, 1), xlabel="", ylabel="Fraction of requested targets")
        counts = pd.DataFrame({r: d.loc[d.judge_status.eq("ok"), "judge_score"].value_counts().reindex(range(4), fill_value=0)
                               for r, d in judgments.items()})
        counts.plot.bar(ax=axes[1], rot=0)
        axes[1].set(title="Evidence-only judge grades", xlabel="Grade (0–3)", ylabel="Pairs")
        fig.tight_layout()
        chart = self.run_dir / "comparison/overview.png"
        if chart.exists():
            previous = self.run_dir / "history" / stamp() / "overview.png"
            previous.parent.mkdir(parents=True, exist_ok=True)
            chart.replace(previous)
        fig.savefig(chart, dpi=150)
        plt.close(fig)
        print(summary.to_string(index=False))
        print("Judge scores are model assessments, not human accuracy. Compare errors on common targets too.")
        print("Saved comparison and per-pipeline outputs:", self.run_dir)
        return summary
