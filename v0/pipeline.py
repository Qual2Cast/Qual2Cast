"""The current comps recipe, with explicit inputs/outputs for each notebook step."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import numpy as np
import pandas as pd

import candidates as cd
import facets as fc
import fill_facets as ff
import judge_comps as jc
import split as sp
import suggest_comps as sg
import universe as uv
import valuation as vl
from project_data import OUTPUTS_LOCAL, load_manifest, sha256, snapshot_path

SHOWCASE = ("PCTY", "BV", "ROAD", "LMB", "BRO", "ADUS", "DXPE", "SLGN", "BGS", "WEN")


@dataclass
class Config:
    backend: str = "codex"       # or "claude-cli"; "claude" retains the original API
    model: str = ""              # empty = selected CLI's configured default
    effort: str | None = None
    workers: int = 2
    company_limit: int | None = None  # quick integration trial, not a full-universe result
    target_tickers: tuple[str, ...] | None = None  # None = every target in target_sample
    target_sample: str = "training"
    train_share: float = sp.TRAIN_SHARE
    seed: int = sp.SEED
    top_k: int = cd.TOP_K
    judge_z: float = jc.DEFAULT_Z
    embed_model: str = cd.EMBED_MODEL
    direct_suggestions: bool = False

    def __post_init__(self):
        if self.backend not in ff.DEFAULT_MODEL:
            raise ValueError("backend must be codex, claude-cli, or claude (Anthropic API)")
        if self.target_sample not in ("training", "holdout"):
            raise ValueError("target_sample must be training or holdout")
        if self.workers < 1 or self.top_k < 1 or not 0 < self.train_share < 1:
            raise ValueError("Use positive workers/top_k and a train_share between 0 and 1")
        if self.company_limit is not None and self.company_limit < 3:
            raise ValueError("A pipeline trial needs at least three companies")


class Pipeline:
    def __init__(self, config: Config, run_dir: Path | str | None = None):
        self.config = config
        self.run_dir = Path(run_dir).resolve() if run_dir else OUTPUTS_LOCAL / "pipeline" / ff.stamp()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        settings = json.loads(json.dumps(asdict(config)))
        path = self.run_dir / "config.json"
        if path.exists() and json.loads(path.read_text()) != settings:
            raise ValueError("This run has different settings. Use a new RUN_DIR to compare configurations.")
        path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    def save(self, relative: str, value, index=False) -> Path:
        path = self.run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            history = self.run_dir / "history" / ff.stamp() / relative
            history.parent.mkdir(parents=True, exist_ok=True)
            path.replace(history)
        if isinstance(value, pd.DataFrame):
            value.to_csv(path, index=index)
        else:
            path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")
        return path

    def prepare(self) -> pd.DataFrame:
        """Recipe 1–2: checked snapshot, company universe, separate financial table."""
        companies, financials = uv.build_universe()
        self.info = companies.loc[companies.in_universe].copy()
        if self.config.company_limit:
            self.info = self.info.head(self.config.company_limit)
        self.info = self.info.set_index("IQ_COMPANY_ID")
        self.financials = financials.set_index("IQ_COMPANY_ID").loc[self.info.index]
        self.id_of = dict(zip(self.info.target_ciq_ticker, self.info.index))
        self.save("universe/companies.csv", companies)
        self.save("universe/universe.csv", self.info.reset_index())
        self.save("universe/financials.csv", self.financials.reset_index())
        source = snapshot_path()
        self.save("universe/run.json", {"snapshot": load_manifest()["required_snapshot"],
                  "snapshot_sha256": sha256(source), "companies_in_snapshot": len(companies),
                  "companies_in_range": int(companies.in_universe.sum()), "companies_in_run": len(self.info),
                  "prompt_version": fc.PROMPT_VERSION, "started_at": ff.now_iso()})
        print(f"Universe: {len(companies)} supplied → {companies.in_universe.sum()} in EV/EBITDA range "
              f"→ {len(self.info)} in this run. Saved company information and separate financials.")
        return self.info.reset_index()

    def fill(self) -> pd.DataFrame:
        """Recipe 3: knowledge fill, saved-page gap fill, and current facet tables."""
        args = ["--out", str(self.run_dir / "facets"), "--backend", self.config.backend,
                "--workers", str(self.config.workers), "--tickers", *self.info.target_ciq_ticker]
        if self.config.model:
            args += ["--model", self.config.model]
        if self.config.effort:
            args += ["--effort", self.config.effort]
        ff.main(args)
        table = pd.read_csv(self.run_dir / "facets/tables/facets.csv", dtype=str).fillna("")
        self.facets = table.loc[table.IQ_COMPANY_ID.isin(self.info.index)
                                & table.llm_status.eq("ok") & table.business_id.eq("B1")].copy()
        missing = self.info.index.difference(self.facets.IQ_COMPANY_ID)
        if len(missing):
            raise RuntimeError(f"Facet stage incomplete for {len(missing)} companies. Inspect facets/codex_runs/ "
                               "and rerun this step with the same RUN_DIR to resume.")
        print(f"Facets: {len(self.facets)} companies; "
              f"{self.facets.needs_review.eq('True').sum()} flagged for manual review.")
        return self.facets

    def split(self) -> pd.DataFrame:
        """Fixed size-stratified split. Target evaluation defaults to training only."""
        strata = sp.size_strata(self.facets).reindex(self.info.index).fillna(sp.SIZE_UNKNOWN)
        forced = [self.id_of[t] for t in SHOWCASE if t in self.id_of]
        self.sample = sp.stratified_split(strata, self.config.train_share, self.config.seed, forced)
        self.training = self.sample.index[self.sample.eq("training")].tolist()
        self.targets = self.sample.index[self.sample.eq(self.config.target_sample)].tolist()
        if self.config.target_tickers is not None:
            wanted = {self.id_of[t] for t in self.config.target_tickers}
            if not wanted <= set(self.targets):
                raise ValueError("Requested targets must belong to target_sample; showcase companies are in training")
            self.targets = [t for t in self.targets if t in wanted]
        if not self.targets or len(self.training) < 2:
            raise ValueError("No targets or fewer than two training-pool companies; increase COMPANY_LIMIT")
        table = self.info.reset_index().assign(
            size_stratum=lambda d: d.IQ_COMPANY_ID.map(strata),
            sample=lambda d: d.IQ_COMPANY_ID.map(self.sample))
        self.save("split/split.csv", table)
        size = sp.share_balance(self.sample, strata)
        sector = sp.share_balance(self.sample, self.info.target_sic2_code.map(sp.sic_division))
        f = self.financials
        numeric = sp.numeric_balance(self.sample, {
            "log revenue": np.log(f.target_revenue.where(f.target_revenue > 0)),
            "EBITDA margin": f.target_margin, "debt / revenue": f.target_debt_to_revenue,
            "EV/EBITDA (balance check only)": f.target_ev_to_ebitda})
        self.save("split/balance_size.csv", size, index=True)
        self.save("split/balance_sector.csv", sector, index=True)
        self.save("split/balance_numeric.csv", numeric, index=True)
        print(f"Split: {len(self.training)} training, {self.sample.eq('holdout').sum()} holdout; "
              f"evaluating {len(self.targets)} {self.config.target_sample} targets. Candidate pool: training only.")
        return size

    def retrieve(self) -> pd.DataFrame:
        """Recipe 4–5: per-facet embeddings, full ranking and candidate profiles."""
        texts = cd.facet_texts(self.facets).reindex(self.info.index)
        self.ids = list(texts.index)
        embeddings, cache = cd.embed_facets(texts, OUTPUTS_LOCAL / "pipeline/embedding_cache", self.config.embed_model)
        matrix, per_facet = cd.similarity(embeddings)
        self.ranking = cd.rank_candidates(matrix, self.ids, self.targets, self.training, self.config.top_k)
        candidates = cd.candidates(self.ranking)
        self.candidates = cd.add_facet_similarities(candidates, per_facet, self.ids)
        self.candidates["target_ticker"] = self.candidates.target.map(self.info.target_ciq_ticker)
        self.candidates["comp_ticker"] = self.candidates.comp.map(self.info.target_ciq_ticker)
        self.save("candidates/candidates.csv", self.candidates)
        self.save("candidates/ranking.csv.gz", self.ranking)
        self.save("candidates/run.json", {"universe_run": str(self.run_dir / "universe"),
                  "split_run": str(self.run_dir / "split"), "facets_out": str(self.run_dir / "facets"),
                  "embedding_cache": str(cache), "embedding_model": self.config.embed_model,
                  "targets": self.config.target_sample, "pool": "training", "top_k": self.config.top_k,
                  "z_levels": list(cd.Z_LEVELS), "weights": "equal", "pairs": len(self.candidates)})
        # A compact diagnostic chart, saved as well as displayed by the notebook.
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 3))
        first = self.ranking[self.ranking.target.eq(self.targets[0])]
        ax.plot(first["rank"], first.similarity)
        ax.set(xlabel="Candidate rank", ylabel="Mean facet cosine similarity",
               title=f"Candidate similarity for {self.info.loc[self.targets[0], 'target_ciq_ticker']}")
        fig.tight_layout()
        self.falloff_path = self.run_dir / "candidates/similarity_falloff.png"
        jc.move_to_history(self.falloff_path, self.run_dir / "history/plots")
        fig.savefig(self.falloff_path, dpi=140)
        plt.close(fig)
        print(f"Candidates: {len(self.candidates)} pairs; full ranking, per-facet scores and plot saved.")
        return self.candidates

    def _args(self):
        return SimpleNamespace(backend=self.config.backend,
                               model=self.config.model or ff.DEFAULT_MODEL[self.config.backend],
                               effort=self.config.effort, refresh=False,
                               candidates=self.run_dir / "candidates", z=self.config.judge_z,
                               split_run=str(self.run_dir / "split"))

    def _batch(self, function, jobs, title):
        """Keep successful calls so rerunning the stage resumes them."""
        stopped = threading.Event()
        def invoke(job):
            if stopped.is_set():
                return {"target": "not started", "status": "not_run"}
            try:
                result = function(job)
            except Exception:
                stopped.set()
                raise
            if result["status"] not in ("ok", "current"):
                stopped.set()
            return result
        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            for i, result in enumerate(executor.map(invoke, jobs), 1):
                print(f"{title} {i}/{len(jobs)}: {result['target']} {result['status']}", flush=True)
                if result["status"] not in ("ok", "current"):
                    raise RuntimeError(f"{title} incomplete: {result}. See saved prompts/responses; rerun to resume.")

    def judge(self) -> pd.DataFrame:
        """Recipe 6: same-business judgment of candidates above the declared z cutoff."""
        pairs = self.ranking.loc[self.ranking.z.ge(self.config.judge_z)].copy()
        self.judge_pairs = pairs
        facets = self.facets.set_index("IQ_COMPANY_ID")
        out = jc.output_paths(self.run_dir / "judge")
        out.judgments.mkdir(parents=True, exist_ok=True)
        groups = list(pairs.groupby("target").comp.apply(list).items())
        args = self._args()
        self._batch(lambda job: jc.judge_one(job[0], job[1], self.info, facets, out, args), groups, "Judge")
        path = jc.write_tables(out, pairs, self.info)
        self.judgments = pd.read_csv(path)
        if self.judgments.score.isna().any():
            raise RuntimeError("Some candidate judgments are missing; inspect judge/tables/judgments.csv before valuation")
        print(f"Judgments: {len(self.judgments)} pairs; {self.judgments.score.eq(1).sum()} accepted. "
              "Targets without candidates remain abstentions in evaluation.")
        return self.judgments

    def suggest(self) -> pd.DataFrame:
        """Optional comparison: direct LLM choices from the same full training pool."""
        self.suggestions = pd.DataFrame(columns=["target", "comp", "rank", "reason"])
        if not self.config.direct_suggestions:
            print("Direct suggestions skipped (DIRECT_SUGGESTIONS=False); this is an optional comparison.")
            return self.suggestions
        out = sg.output_paths(self.run_dir / "suggest")
        out.runs.mkdir(parents=True, exist_ok=True)
        out.suggestions.mkdir(parents=True, exist_ok=True)
        facets, args = self.facets.set_index("IQ_COMPANY_ID"), self._args()
        system, labels = sg.build_system(self.training, self.info, facets)
        jc.move_to_history(out.runs / "system.txt", self.run_dir / "history/suggest_system")
        (out.runs / "system.txt").write_text(system, encoding="utf-8")
        self._batch(lambda target: sg.suggest_one(target, system, labels, self.info, facets, out, args),
                    self.targets, "Suggest")
        self.suggestions = pd.read_csv(sg.write_tables(out, self.info))
        return self.suggestions

    def evaluate(self) -> pd.DataFrame:
        """Recipe 7: held-out target multiples enter error calculations only here."""
        ev = self.financials.target_ev_to_ebitda
        actual = ev.reindex(self.targets)
        baseline = "no matching"
        results = {baseline: vl.no_matching(self.targets, self.training, ev)}
        selectors = {f"top {self.config.top_k}": self.ranking[self.ranking.in_top_k],
                     **{f"z >= {z:g}": self.ranking[self.ranking.z.ge(z)] for z in cd.Z_LEVELS},
                     "LLM good comps": self.judgments[self.judgments.score.eq(1)]}
        for name, pairs in selectors.items():
            for how, weight in [("mean", "similarity"), ("median", None)]:
                results[f"{name}, {'similarity-weighted mean' if weight else how}"] = vl.estimate(pairs, ev, weight, how)
        if self.config.direct_suggestions:
            pairs = self.suggestions.dropna(subset=["comp"])
            for how in ("mean", "median"):
                results[f"LLM direct, {how}"] = vl.estimate(pairs, ev, how=how)
        for level in (2, 3, 4):
            col = f"target_sic{level}_code"
            rows = [{"target": t, "comp": c} for t in self.targets for c in self.training
                    if c != t and self.info.loc[t, col] == self.info.loc[c, col]]
            results[f"SIC{level}, mean"] = vl.estimate(pd.DataFrame(rows, columns=["target", "comp"]), ev)
        summary = vl.summary(results, actual, baseline)
        summary["attempted targets"] = len(self.targets)
        summary["coverage %"] = 100 * summary.targets / len(self.targets)
        summary["% within 25 all targets"] = [100 * (vl.errors(r, actual)["error %"].abs() <= 25).sum()
                                              / len(self.targets) for r in results.values()]
        common = results["LLM good comps, similarity-weighted mean"].index
        if self.config.direct_suggestions:
            common = common.intersection(results["LLM direct, mean"].index)
        common_summary = vl.summary({k: r.loc[r.index.intersection(common)] for k, r in results.items()},
                                    actual.reindex(common), baseline)
        per_target = pd.concat({name: vl.errors(r.reindex(self.targets), actual).assign(
            status=lambda d: np.where(d.estimate.notna(), "estimated", "no_comps"))
            for name, r in results.items()}, names=["comp rule", "IQ_COMPANY_ID"]).reset_index()
        per_target.insert(2, "ticker", per_target.IQ_COMPANY_ID.map(self.info.target_ciq_ticker))
        self.save("valuation/summary.csv", summary, index=True)
        self.save("valuation/summary_common.csv", common_summary, index=True)
        self.save("valuation/per_target.csv", per_target)
        self.save("valuation/run.json", {"target_sample": self.config.target_sample, "targets": self.targets,
                  "pool": self.training, "common_llm_targets": list(common), "rules": list(results),
                  "backend": self.config.backend,
                  "model": self.config.model or ff.DEFAULT_MODEL[self.config.backend] or "CLI configured default",
                  "valuation_date": "unknown", "ebitda_definition": "unknown", "finished_at": ff.now_iso()})
        self.summary, self.per_target = summary, per_target
        print(f"Valuation complete for {len(self.targets)} attempted targets. Coverage and errors saved to "
              f"{self.run_dir / 'valuation'}.")
        return summary
