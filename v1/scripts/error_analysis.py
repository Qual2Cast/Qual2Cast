"""Trace saved peer-selection disagreements and possible facet failures.

Offline by default: no model, scraping, embedding, or financial-table reads.
Human labels, model judgments, and causal hypotheses remain separate.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

import facets as fc
import similarity_eval as se
from project_data import REPO_ROOT, OUTPUTS_LOCAL, sha256, snapshot_path

V1 = OUTPUTS_LOCAL / "v1"
KEY = ["target", "comp"]


@dataclass
class Config:
    b3: str = "candidates_method1/20261104T074915Z"
    similarity: str = "similarity_methods/20261104T075557Z"
    round1: str = "golden_set/labels/reviewer_labels_20261028.json"
    round2: str = "golden_set_showcase/labels/round2_filled.csv"
    facet_labels: str = "gold_labels/source/facet_gold_labels - Labels.csv"
    haiku_facets: str = "facets/tables/facets.csv"
    sonnet_facets: str = "facets_sonnet/tables/facets.csv"
    screen_sonnet: str = "cosine_then_llm/20261104T074915Z_2026-11-04a_sonnet/tables/judgments.csv"
    screen_haiku: str = "cosine_then_llm/20261104T074915Z_2026-11-04a_haiku/tables/judgments.csv"
    direct_sonnet: str = "direct_llm/20261027T204930Z_2026-11-04a_sonnet/tables/suggestions.csv"
    direct_haiku: str = "direct_llm/20261027T204930Z_2026-11-04a_haiku/tables/suggestions.csv"
    agent_runs: tuple[str, ...] = ("agent_loop/gold_sonnet", "agent_loop/round2_targets_sonnet")
    sol_gold: str = "golden_set/graded_batch_check/grades.csv"


def path(value):
    p = Path(value)
    return p if p.is_absolute() else V1 / p


def norm(value):
    """Whitespace/case normalization only, not a semantic-equivalence judgment."""
    return " ".join(str(value).split()).casefold()


class Analysis:
    def __init__(self, config=None, out=None):
        self.config = config or Config()
        self.out = Path(out) if out else V1 / "error_analysis" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.out.mkdir(parents=True, exist_ok=True)
        if (self.out / "manifest.json").exists():
            raise ValueError("Use a fresh output directory; existing analyses are preserved.")
        self.sources, self.gaps, self.frames = {}, [], {}

    def register(self, p):
        p = Path(p)
        key = str(p.relative_to(REPO_ROOT)) if p.is_relative_to(REPO_ROOT) else str(p)
        self.sources[key] = {"sha256": sha256(p), "bytes": p.stat().st_size}
        return key

    def read(self, value, optional=False):
        p = path(value)
        if not p.exists() and optional:
            self.gaps.append(f"Not available: {value}")
            return pd.DataFrame()
        self.register(p)
        return pd.read_csv(p, dtype=str, encoding="utf-8-sig").fillna("")

    def table(self, name, df):
        self.frames[name] = df
        df.to_csv(self.out / f"{name}.csv", index=False)
        return df

    def human_labels(self):
        p = path(self.config.round1)
        self.register(p)
        raw = pd.DataFrame(json.loads(p.read_text(encoding="utf-8"))["labels"]).fillna("")
        groups = [(raw, se.REVIEWERS, self.config.round1, 1)]
        r2 = self.read(self.config.round2, optional=True)
        if not r2.empty:
            reviewers = tuple(c[6:] for c in r2 if c.startswith("score_"))
            if len(reviewers) != 3:
                raise ValueError("Round 2 must identify exactly three reviewers")
            scored = r2[[f"score_{r}" for r in reviewers]].isin(["0", "1", "2"]).all(axis=1)
            self.gaps.append(f"Round 2: {int((~scored).sum())} pairs lack three valid scores; excluded from metrics.")
            if scored.any():
                groups.append((r2.loc[scored].copy(), reviewers, self.config.round2, 2))
        all_rows, raw_notes = [], {}
        for frame, reviewers, source, round_no in groups:
            majority, unanimous, unresolved = se.reviewer_sets(frame, reviewers)
            grades = majority.set_index(KEY).grade.to_dict()
            strict = set(map(tuple, unanimous[KEY].to_numpy()))
            for row in frame.to_dict("records"):
                key = (row["target_id"], row["comp_id"])
                all_rows.append({"target": key[0], "comp": key[1], "grade": grades.get(key),
                                 "unanimous": key in strict, "round": round_no,
                                 "source": source, "pair_label": row.get("pair", "")})
                raw_notes[key] = {k: v for k, v in row.items() if k.startswith(("score_", "notes_", "reason_if_0_"))}
        labels = pd.DataFrame(all_rows)
        if labels.duplicated(KEY).any():
            raise ValueError("Duplicate human pair across rounds: reconcile labels before analysis")
        labels["grade"] = pd.to_numeric(labels.grade, errors="coerce")
        self.human_notes = raw_notes
        return self.table("human_labels", labels)

    def profiles_and_facet_audit(self):
        self.profiles = {}
        for model, value in [("haiku", self.config.haiku_facets), ("sonnet", self.config.sonnet_facets)]:
            df = self.read(value)
            df = df.loc[df.business_id.eq("B1") & df.llm_status.eq("ok")]
            if df.IQ_COMPANY_ID.duplicated().any():
                raise ValueError(f"Multiple current {model} profiles for a company")
            self.profiles[model] = df.set_index("IQ_COMPANY_ID").to_dict("index")
        gold = self.read(self.config.facet_labels)
        gold["facet_name"] = gold.facet_id.map({v: k for k, v in fc.FACET_ID.items()})
        if gold.facet_name.isna().any():
            raise ValueError("Unknown human facet ID")
        rows = []
        for index, row in enumerate(gold.to_dict("records"), 1):
            iq = self.ticker_id.get(row["ticker"].upper())
            f = row["facet_name"]
            label = row["label"].lower().strip().replace("’", "'")
            if label not in {"correct", "partly correct", "wrong", "outdated", "can't tell"}:
                raise ValueError(f"Unknown facet label: {label}")
            values = {m: self.profiles[m].get(iq, {}).get(f, "") for m in self.profiles}
            rows.append({"reference": f"FACET:{index}", "company_id": iq, "ticker": row["ticker"],
                         "facet": f, "human_label": label, "labeled_text": row["haiku_value"],
                         "human_note": row["note"], "evidence_url": row["evidence_url"],
                         "labeler": row["labeler"], "source": self.config.facet_labels,
                         **{f"{m}_text": v for m, v in values.items()},
                         **{f"exact_{m}_text": bool(v) and norm(v) == norm(row["haiku_value"])
                            for m, v in values.items()}})
        audit = self.table("facet_audit", pd.DataFrame(rows))
        priorities = []
        for f, group in audit.groupby("facet", sort=False):
            checkable = group.human_label.ne("can't tell")
            problem = group.human_label.isin(["partly correct", "wrong", "outdated"])
            record = {"facet": f, "labeled_claims": len(group), "labeled_companies": group.ticker.nunique(),
                      "checkable_historical_claims": int(checkable.sum()),
                      "historical_problem_claims": int(problem.sum()),
                      "historical_problem_rate": problem.sum() / checkable.sum() if checkable.any() else None,
                      "excluded_from_b3": f == "company_size"}
            for model in self.profiles:
                exact = group[f"exact_{model}_text"] & checkable
                record[f"current_{model}_exact_checkable"] = int(exact.sum())
                record[f"current_{model}_exact_problem"] = int((exact & problem).sum())
            priorities.append(record)
        self.table("facet_priorities", pd.DataFrame(priorities).sort_values("historical_problem_rate", ascending=False))
        differences = []
        for iq in sorted(self.profiles["haiku"].keys() & self.profiles["sonnet"].keys()):
            for f in fc.FACET_NAMES:
                a, b = self.profiles["haiku"][iq], self.profiles["sonnet"][iq]
                va, vb = a[f], b[f]
                # A leading category is defined only for explicit category facets.
                category_a, category_b = a.get(f + "_category", ""), b.get(f + "_category", "")
                differences.append({"company_id": iq, "ticker": self.names[iq]["ticker"], "facet": f,
                                    "haiku_text": va, "sonnet_text": vb,
                                    "haiku_status": a[f + "_status"], "sonnet_status": b[f + "_status"],
                                    "haiku_source": a.get(f + "_source", ""), "sonnet_source": b.get(f + "_source", ""),
                                    "text_differs": norm(va) != norm(vb),
                                    "category_differs": bool(category_a and category_b) and
                                        {norm(v) for v in category_a.split(";")} != {norm(v) for v in category_b.split(";")},
                                    "category_comparable": bool(category_a and category_b),
                                    "status_differs": a[f + "_status"] != b[f + "_status"]})
        diff = self.table("profile_differences", pd.DataFrame(differences))
        self.table("profile_disagreement_by_facet", diff.groupby("facet", sort=False).agg(
            companies=("company_id", "size"), text_difference_rate=("text_differs", "mean"),
            category_comparisons=("category_comparable", "sum"), category_differences=("category_differs", "sum"),
            status_difference_rate=("status_differs", "mean")).reset_index())

    def pair_comparison(self):
        human = self.frames["human_labels"]
        self.b3 = self.read(self.config.b3 + "/candidates.csv")
        b3 = self.b3.loc[self.b3.selected.str.lower().eq("true")].copy()
        rows = []
        for r in b3.to_dict("records"):
            rows.append({**{k: r[k] for k in KEY}, "method": "B3", "kept": True,
                         "rank": r["rank"], "reason": "Selected by B3 mutual/top-up rule", "source": self.config.b3 + "/candidates.csv"})
        # Existing similarity alternatives are replayed from their own saved lists.
        lists_source = self.config.similarity + "/comp_lists.csv"
        lists = self.read(lists_source)
        for r in lists.loc[lists["sample"].eq("training")].to_dict("records"):
            if r["method"].startswith("B3"):
                continue  # B3 is loaded from the selector's exact candidate run above.
            rows.append({**{k: r[k] for k in KEY}, "method": "similarity: " + r["method"],
                         "kept": True, "rank": r["rank"], "reason": "Saved similarity-method selection",
                         "source": lists_source})
        self.screen_tables = {}
        for model in ["haiku", "sonnet"]:
            value = getattr(self.config, "screen_" + model)
            df = self.read(value)
            if df.duplicated(KEY).any():
                raise ValueError(f"Duplicate {model} selector pairs")
            if set(df.candidates_run) != {Path(self.config.b3).name}:
                raise ValueError(f"{model} screen uses another candidates run")
            if set(map(tuple, df[KEY].to_numpy())) != set(map(tuple, b3[KEY].to_numpy())):
                raise ValueError(f"{model} screen and B3 selected pair sets differ")
            self.screen_tables[model] = df
            for r in df.to_dict("records"):
                rows.append({**{k: r[k] for k in KEY}, "method": "screen_" + model,
                             "kept": r["score"] == "1", "rank": r["rank"], "reason": r["reason"], "source": value})
            value = getattr(self.config, "direct_" + model)
            df = self.read(value)
            self.direct_targets = getattr(self, "direct_targets", {})
            self.direct_targets[model] = set(df.target)
            for r in df.loc[df.comp.ne("")].to_dict("records"):
                rows.append({**{k: r[k] for k in KEY}, "method": "direct_" + model,
                             "kept": True, "rank": r["rank"], "reason": r["reason"], "source": value})
        disagreement = self.screen_tables["haiku"].merge(self.screen_tables["sonnet"], on=KEY,
                                                        suffixes=("_haiku", "_sonnet"), validate="one_to_one")
        self.table("screen_disagreements", disagreement.loc[disagreement.score_haiku.ne(disagreement.score_sonnet)].copy())
        pairs = pd.DataFrame(rows)
        pairs["rank"] = pd.to_numeric(pairs["rank"], errors="coerce")
        pairs = pairs.merge(human[KEY + ["grade", "unanimous"]], on=KEY, how="left", validate="many_to_one")
        for side in KEY:
            pairs[side + "_ticker"] = pairs[side].map(lambda iq: self.names[iq]["ticker"])
        self.table("pair_comparison", pairs)
        metrics = []
        for method, group in pairs.groupby("method", sort=False):
            selected = group[group.kept]
            for t in human.target.unique():
                tg = human.loc[human.target.eq(t) & human.grade.notna()]
                if method.startswith("direct_") and t not in self.direct_targets[method.removeprefix("direct_")]:
                    continue
                listed = selected.loc[selected.target.eq(t)].sort_values("rank").head(10)
                judged = listed[listed.grade.notna()]
                found = set(listed.comp)
                good = tg.grade.ge(1)
                direct = tg.grade.eq(2)
                metrics.append({"method": method, "target": t, "target_ticker": self.names[t]["ticker"],
                                "listed_top10": len(listed), "human_labeled_listed": len(judged),
                                "label_coverage": len(judged) / len(listed) if len(listed) else None,
                                "good_listed": int(judged.grade.ge(1).sum()), "nonpeers_listed": int(judged.grade.eq(0).sum()),
                                "precision_on_labeled": judged.grade.ge(1).mean() if len(judged) else None,
                                "known_good_total": int(good.sum()), "known_good_retained": int((good & tg.comp.isin(found)).sum()),
                                "known_direct_total": int(direct.sum()), "known_direct_retained": int((direct & tg.comp.isin(found)).sum())})
        self.table("method_metrics", pd.DataFrame(metrics))
        # Same-pair overlap, never pooled across different agent runs as independent data.
        assessments = []
        for value in self.config.agent_runs:
            df = self.read(value + "/verdicts.csv", optional=True)
            if df.empty:
                continue
            for r in df.to_dict("records"):
                assessments.append({**{k: r[k] for k in KEY}, "evaluator": value, "score": r["score"],
                                    "status": r["status"], "reason": r["reason"],
                                    "missing_evidence": r["missing_evidence"], "lookups": r["lookups"],
                                    "source": value + "/verdicts.csv"})
        sol = self.read(self.config.sol_gold, optional=True)
        for r in sol.to_dict("records"):
            assessments.append({**{k: r[k] for k in KEY}, "evaluator": "one_shot_sol", "score": r["score"],
                                "status": "ok" if r["score"] else "insufficient_evidence", "reason": r["reason"],
                                "missing_evidence": "", "lookups": "", "source": self.config.sol_gold})
        judges = pd.DataFrame(assessments)
        judges["score"] = pd.to_numeric(judges.score, errors="coerce")
        judges = judges.merge(human[KEY + ["grade"]], on=KEY, how="left", validate="many_to_one")
        self.table("judge_comparison", judges)
        self.table("judge_metrics", pd.DataFrame([
            {"evaluator": name, "evaluated_pairs": len(g), "human_labeled": int(g.grade.notna().sum()),
             "numeric_and_labeled": int((g.score.notna() & g.grade.notna() & g.status.eq("ok")).sum()),
             "exact_agreements": int((g.score.eq(g.grade) & g.grade.notna() & g.status.eq("ok")).sum()),
             "pairs_with_lookup": int(pd.to_numeric(g.lookups, errors="coerce").gt(0).sum())}
            for name, g in judges.groupby("evaluator", sort=False)]))

    def cases(self):
        """Observed flags locate stages to investigate; they do not prove causes."""
        human = self.frames["human_labels"]
        compared = self.frames["pair_comparison"]
        judges = self.frames["judge_comparison"]
        universe = (set(map(tuple, human[KEY].to_numpy())) | set(map(tuple, judges[KEY].to_numpy())) |
                    set(map(tuple, self.frames["screen_disagreements"][KEY].to_numpy())))
        cases = []
        b3_pairs = set(map(tuple, compared.loc[compared.method.eq("B3"), KEY].to_numpy()))
        for t, c in sorted(universe):
            h = human.loc[human.target.eq(t) & human.comp.eq(c)]
            grade = None if h.empty or pd.isna(h.iloc[0].grade) else int(h.iloc[0].grade)
            obs = compared.loc[compared.target.eq(t) & compared.comp.eq(c)]
            js = judges.loc[judges.target.eq(t) & judges.comp.eq(c)]
            flags = []
            if not h.empty and grade is None:
                flags.append("human_no_majority")
            if grade is not None:
                if grade == 0 and (t, c) in b3_pairs:
                    flags.append("retrieval_lists_human_nonpeer")
                if grade >= 1 and (t, c) not in b3_pairs:
                    flags.append("known_peer_not_in_b3_list")
                for r in obs.itertuples():
                    if r.method.startswith("screen_") and not r.kept and grade >= 1:
                        flags.append(r.method + "_removed_known_peer")
                    if r.kept and grade == 0:
                        flags.append(r.method + "_lists_human_nonpeer")
                for r in js.itertuples():
                    if r.status == "ok" and pd.notna(r.score) and r.score != grade:
                        flags.append("judge_disagrees_with_human")
            ha = self.screen_tables["haiku"]
            so = self.screen_tables["sonnet"]
            ha = ha.loc[ha.target.eq(t) & ha.comp.eq(c)]
            so = so.loc[so.target.eq(t) & so.comp.eq(c)]
            if not ha.empty and not so.empty and ha.iloc[0].score != so.iloc[0].score:
                flags.append("selector_model_disagreement")
            if grade is None and h.empty:
                flags.append("no_human_label")
            if js.missing_evidence.ne("").any():
                flags.append("judge_reports_evidence_gap")
            if not flags:
                flags.append("agreement_control")
            cases.append({"case_id": f"PAIR:{t}__{c}", "target": t, "comp": c,
                          "target_ticker": self.names[t]["ticker"], "comp_ticker": self.names[c]["ticker"],
                          "human_grade": grade, "in_b3": (t, c) in b3_pairs,
                          "flags": "; ".join(sorted(set(flags))),
                          "priority": sum(f not in {"no_human_label", "agreement_control", "judge_reports_evidence_gap"} for f in set(flags))})
        cases = self.table("case_queue", pd.DataFrame(cases).sort_values(["priority", "case_id"], ascending=[False, True]))
        packets = self.out / "cases"
        packets.mkdir()
        for row in cases.to_dict("records"):
            t, c = row["target"], row["comp"]
            refs = {}
            def ref(label, value, source):
                refs[label] = {"source": source, "data": value}
            ref("PAIR", row, "case_queue.csv (derived observed flags, not causal labels)")
            ref("HUMAN", self.human_notes.get((t, c), {}), "human_labels.csv; original reviewer scores/notes")
            ref("METHODS", compared.loc[compared.target.eq(t) & compared.comp.eq(c)].to_dict("records"), "pair_comparison.csv")
            ref("JUDGES", judges.loc[judges.target.eq(t) & judges.comp.eq(c)].to_dict("records"), "judge_comparison.csv")
            for side, iq in [("TARGET", t), ("COMP", c)]:
                for model in self.profiles:
                    profile = self.profiles[model].get(iq, {})
                    for f in fc.FACET_NAMES:
                        ref(f"{side}:{model}:{f}", {k: profile.get(k, "") for k in [f, f + "_status", f + "_source", f + "_flags"]}, getattr(self.config, model + "_facets"))
                for item in self.frames["facet_audit"].loc[self.frames["facet_audit"].company_id.eq(iq)].to_dict("records"):
                    ref(item["reference"], item, self.config.facet_labels)
                # Exact cleaned, figure-filtered passages: no crawl or new model calls.
                ref("EVIDENCE:" + side, self.website(iq), "outputs-local/website_scrape/page_text/" + iq + ".json")
            packet = {"case": row, "references": refs,
                      "limits": ["A human peer label does not label any facet as false.",
                                 "Historical facet labels apply to current text only when exact_*_text is true.",
                                 "Model disagreements are hypotheses, not factual errors.",
                                 "B3 and selector runs use Haiku profiles; Sonnet profiles are a comparison only.",
                                 "One-shot Sol versus agent Sonnet changes both inputs and model."]}
            dest = packets / f"{t}__{c}.json"
            dest.write_text(json.dumps(self.clean_json(packet), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                            encoding="utf-8")
        return cases

    @staticmethod
    def clean_json(value):
        if isinstance(value, dict):
            return {k: Analysis.clean_json(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [Analysis.clean_json(v) for v in value]
        if value is None or pd.isna(value):
            return None
        return value.item() if hasattr(value, "item") else value

    def website(self, iq):
        from types import SimpleNamespace
        from peer_evaluation import PeerEvaluation
        p = OUTPUTS_LOCAL / "website_scrape/page_text" / f"{iq}.json"
        if p.exists():
            self.register(p)
        holder = SimpleNamespace(info=self.info, config=SimpleNamespace(evidence_words=600))
        return PeerEvaluation.company_evidence(holder, iq)

    def report(self):
        h, audit = self.frames["human_labels"], self.frames["facet_audit"]
        priorities, cases = self.frames["facet_priorities"], self.frames["case_queue"]
        detailed = ["# Facet claims requiring review", "",
                    "Human labels below apply to historical text. Current text is shown for comparison, not automatically assigned that label.",
                    "Source URLs are the human reviewer's recorded evidence; they have not been fetched or reverified by this analysis.", ""]
        for f, group in audit.loc[audit.human_label.isin(["partly correct", "wrong", "outdated"])].groupby("facet", sort=False):
            detailed += [f"## {f}", ""]
            for r in group.itertuples():
                detailed += [f"### {r.ticker} — {r.human_label} ({r.reference})", "",
                             f"- Historical claim: {r.labeled_text}", f"- Reviewer note: {r.human_note or '(none supplied)'}",
                             f"- Reviewer: {r.labeler}; recorded evidence: {r.evidence_url or '(none supplied)'}",
                             f"- Current Haiku text (exact labeled text: {r.exact_haiku_text}): {r.haiku_text}",
                             f"- Current Sonnet text (exact labeled text: {r.exact_sonnet_text}): {r.sonnet_text}", ""]
        (self.out / "facet_review.md").write_text("\n".join(detailed), encoding="utf-8")
        current = audit.loc[audit.exact_haiku_text & audit.facet.ne("company_size")]
        current_problems = current.loc[current.human_label.isin(["partly correct", "wrong", "outdated"])]
        report = ["# Where company matching may be failing", "",
                  "## Findings to act on first", "",
                  f"- Only {int(audit.exact_haiku_text.sum())}/{len(audit)} historical labels match current Haiku text; just {len(current)} matches are outside company size. Most current matching facets therefore still need verification.",
                  f"- {len(current_problems)} exact-current, non-size claims carry historical problem labels. See examples below; these are direct review leads rather than inferred causes of pair errors.",
                  f"- Haiku and Sonnet disagree on {len(self.frames['screen_disagreements'])}/{len(self.b3.loc[self.b3.selected.str.lower().eq('true')])} matched B3 screen decisions. These are documented hypotheses to inspect, not proof that either model is wrong.",
                  "- On the reviewed targets, compare B3's retained peers with the screens' losses before assuming the facets are the main bottleneck. Human direct/adjacent policy matters.", "",
                  "## Scope and evidence", "",
                  f"- {len(h)} human-reviewed pairs; {int(h.grade.notna().sum())} with an exact majority across {h.target.nunique()} targets.",
                  f"- {len(audit)} historical facet labels across {audit.ticker.nunique()} companies.",
                  f"- B3: `{self.config.b3}`; profiles: Haiku versus Sonnet; snapshot: company_list_v3.",
                  "- No LLM calls, new scraping, embedding changes, or financial-table reads. This is saved-result diagnosis, not an intervention experiment.",
                  "- All rates below state their sample; the reviewed targets are not a representative accuracy benchmark.", "",
                  "## 1. Profile evidence: historical errors versus current uncertainty", ""]
        for r in priorities.itertuples():
            report.append(f"- **{r.facet}**: {r.historical_problem_claims}/{r.checkable_historical_claims} checkable historical claims partly correct, wrong or outdated; current Haiku exact-text matches {r.current_haiku_exact_checkable}, of which {r.current_haiku_exact_problem} problematic."
                          + (" Excluded from B3, so not a current similarity driver." if r.excluded_from_b3 else ""))
        report += ["", "[Detailed facet review: original claims, reviewer notes, evidence URLs and both current fills](facet_review.md).",
                   "These labels describe the original `labeled_text`. Different current text needs a new verification; a changed wording is neither a proven fix nor a proven error.",
                   "Model category/status disagreements in `profile_differences.csv` are review priorities, not accuracy labels.", "",
                   "### Exact-current facet problems identified by the historical labels", ""]
        for r in current_problems.itertuples():
            report.append(f"- **{r.ticker} / {r.facet}** ({r.reference}): {r.human_label}; reviewer note: {r.human_note}. Current claim: {r.haiku_text}. Recorded evidence: {r.evidence_url}. Recheck that source before editing the profile.")
        report += ["", "## 2. What selection adds or removes", ""]
        for r in self.frames["method_metrics"].itertuples():
            labeled = f"{r.good_listed}/{r.human_labeled_listed} labeled returned pairs are peers" if r.human_labeled_listed else "no human-labeled returned pairs (precision undefined)"
            report.append(f"- **{r.target_ticker} / {r.method}**: {labeled}; {r.listed_top10 - r.human_labeled_listed} returned pairs unlabelled; retains {r.known_good_retained}/{r.known_good_total} known peers and {r.known_direct_retained}/{r.known_direct_total} known direct peers.")
        report += ["", "Retention is within the reviewed pool, not universe-wide recall. Strict screening can remove adjacent peers even if its direct-peer precision looks good.",
                   "", "## 3. Judge reliability and comparison limits", ""]
        for r in self.frames["judge_metrics"].itertuples():
            agreement = f"{r.exact_agreements}/{r.numeric_and_labeled} exact agreements among numeric, human-labeled answers" if r.numeric_and_labeled else "no numeric answers with a human-majority label; agreement not measurable"
            report.append(f"- **{r.evaluator}**: {agreement}; {r.pairs_with_lookup}/{r.evaluated_pairs} pairs have a recorded lookup.")
        report += ["", "The older one-shot Sol and agent Sonnet comparisons change model, context and retrieval policy. Their agreement gap is not the causal effect of an agent loop.",
                   "", "## 4. Cases to investigate", ""]
        for r in cases.loc[cases.priority.gt(0)].itertuples():
            grade = str(int(r.human_grade)) if pd.notna(r.human_grade) else "unresolved or not labeled"
            report.append(f"- [{r.target_ticker} → {r.comp_ticker}](cases/{r.target}__{r.comp}.json): human grade {grade}; {r.flags}. Inspect both companies' profiles, historical label text, saved evidence and model reasons before assigning a cause.")
        report += ["", "## 5. Next experiments", "",
                   "1. Reverify the exact current claims for high-problem historical facets; distinguish buyer from end user and principal business from ancillary lines. Require sources for proposed corrections.",
                   "2. Inspect known peers dropped by screening. Compare a direct-only policy with a direct-plus-adjacent policy; report coverage and retained good peers, not just approval rate.",
                   "3. Hold profiles and candidate lists fixed when comparing models. Then hold B3 fixed when comparing Haiku and Sonnet profiles. No downstream Sonnet-profile gain is established by this report.",
                   "4. Compare one-shot and retrieval-enabled review with the same model and initial context on evidence-gap cases; retrieval frequency alone is not quality.",
                   "5. Expand human labels across targets to 200–500 unique pairs and verify 50–100 companies' exact current facet claims. Keep unseen targets for evaluation; these development labels are not a fresh final test.",
                   "", "## Missing inputs and scope limits", ""]
        report += ["- " + gap for gap in self.gaps] or ["- None recorded."]
        report += ["- This report does not merge the historical 663-pair 0–3 run into the newer 0–2 results.",
                   "- Sector/industry fills and valuation outcomes are not silently pooled with general-facet accuracy. Their downstream impact requires a separate controlled comparison.",
                   "- Pair flags identify stages to investigate; they are not counts of proven facet-caused errors.", ""]
        (self.out / "report.md").write_text("\n".join(report), encoding="utf-8")
        diagnosis = {"stage": "source_evidence | facet_fill | retrieval_scoring | selection | rubric_disagreement | undetermined",
                     "affected_facets": [], "explanation": "", "evidence_refs": [], "proposed_change": "",
                     "verification_needed": "", "status": "hypothesis"}
        (self.out / "manual_agent_instructions.md").write_text(
            "# Optional manual eval-agent review\n\nNo model calls were made. Read report.md and a cases/*.json packet. "
            "Use only the supplied references. Report observations separately from hypotheses. "
            "Cite the packet reference IDs and original file paths for every proposed failure. "
            "A valid passage ID is not proof of entailment. Old labels apply only to their exact text. "
            "Do not use model knowledge to assert current business facts. Do not invent counts, "
            "change facet values, run commands or tune a method against these labels. "
            "Identify the smallest controlled experiment or source check that could distinguish causes. "
            "When evidence is inadequate, say undetermined. Output one record per diagnosis:\n\n```json\n"
            + json.dumps(diagnosis, indent=2) + "\n```\n", encoding="utf-8")

    def build(self):
        meta_path = path(self.config.b3 + "/run.json")
        self.register(meta_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.info = self.read("universe/" + meta["universe_run"] + "/universe.csv").set_index("IQ_COMPANY_ID")
        self.names = {iq: {"ticker": r.target_ciq_ticker, "name": r.target_company_name}
                      for iq, r in self.info.iterrows()}
        self.ticker_id = {r["ticker"].upper(): iq for iq, r in self.names.items()}
        self.register(snapshot_path())  # integrity/provenance only; no financial CSV read
        self.human_labels()
        self.profiles_and_facet_audit()
        self.pair_comparison()
        self.cases()
        # Preserve useful existing diagnostics with their run version, not as causal evidence.
        for name in ["information_weights", "facet_label_check", "m2_facet_separation", "reviewed_comp_ranks"]:
            source = self.read(self.config.similarity + "/" + name + ".csv", optional=True)
            if not source.empty:
                self.table("context_" + name, source)
        self.report()
        (self.out / "manifest.json").write_text(json.dumps({
            "config": asdict(self.config), "sources": self.sources, "gaps": self.gaps,
            "model_calls": 0, "financial_tables_read": False,
            "git_commit": self.git_commit(), "created_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2) + "\n", encoding="utf-8")
        print("Saved error analysis:", self.out)
        return self

    @staticmethod
    def git_commit():
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Fresh output directory; default is a new timestamped run")
    args = parser.parse_args()
    Analysis(out=args.out).build()
