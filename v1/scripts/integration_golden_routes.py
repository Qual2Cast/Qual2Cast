"""Evaluate the four existing peer-selection routes on the reviewed training pairs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

import pandas as pd

import b3_facet_add_drop as b3
import cosine_then_llm as judge
import direct_llm as suggest
import facets as fc
import holdout_llm_routes as calls
from integration_reviewed_ranks import mutual_from_top10, score_cohort


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
BASE = V1 / "integration"
OUT = BASE / "golden_routes"
GENERAL = V1 / "facets_codex_gpt61sol/tables/facets.csv"
MODEL = "gpt-6.1-sol"


def inputs():
    _, ids, training, _ = b3.read_inputs()
    labels = {name: frame for name, frame in b3.load_labels(training).items()
              if name.startswith("human_")}
    targets = sorted(set(labels["human_majority"]["target"]))
    if len(targets) != 2 or not set(targets) <= set(training):
        raise ValueError("Expected the two reviewed training targets")
    _, info, _, _ = suggest.load_inputs(calls.BASE_RUN)
    facets = pd.read_csv(GENERAL, dtype=str).fillna("")
    facets = facets[(facets["prompt_version"] == fc.PROMPT_VERSION) &
                    (facets["llm_status"] == "ok") & (facets["business_id"] == "B1")]
    if len(facets) != len(ids) or facets["IQ_COMPANY_ID"].duplicated().any():
        raise ValueError("Incomplete GPT general facets")
    return training, targets, labels, info, facets.set_index("IQ_COMPANY_ID")


def main() -> None:
    training, targets, cohorts, info, facets = inputs()
    routes = sorted(path for path in (BASE / "gpt_candidates").iterdir()
                    if path.is_dir() and (path / "all_targets_top10.csv").exists())
    if len(routes) != 12:
        raise ValueError("Expected twelve GPT facet conditions")
    selections = {}
    for route in routes:
        top = pd.read_csv(route / "all_targets_top10.csv", dtype={"target": str, "comp": str})
        selected = mutual_from_top10(top, set(targets))
        selections[route.name] = (top[top["target"].isin(targets)], selected)
    union = {target: sorted(set().union(*(set(selected.loc[selected["target"].eq(target), "comp"])
                                            for _, selected in selections.values()))) for target in targets}
    OUT.mkdir(parents=True, exist_ok=True)

    def judge_one(target: str) -> list[dict]:
        prompt, mapping = judge.build_prompt(target, union[target], info, facets, judge.PROMPT_VERSION)
        raw = calls.checked_call(prompt, judge.answer_schema(list(mapping)),
                                 OUT / "calls/judge" / target, MODEL)
        answers, issues = judge.check_answer(raw, mapping)
        if issues or len(answers) != len(union[target]) or any(row["score"] is None for row in answers):
            raise ValueError(f"Incomplete judge answer for {target}: {issues}")
        return [dict(target=target, **row) for row in answers]

    def direct_one(target: str) -> list[dict]:
        pool = [company for company in training if company != target]
        system, mapping = suggest.build_system(pool, info, facets)
        prompt = suggest.build_prompt(system, target, info, facets, suggest.PROMPT_VERSION)
        raw = calls.checked_call(prompt, suggest.ANSWER_SCHEMA,
                                 OUT / "calls/direct" / target, MODEL, system)
        answers, issues = suggest.check_answer(raw, mapping, target)
        if issues:
            raise ValueError(f"Invalid direct answer for {target}: {issues}")
        return [dict(target=target, **row) for row in answers]

    judged, direct = [], []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(judge_one, target): ("judge", target) for target in targets}
        futures.update({pool.submit(direct_one, target): ("direct", target) for target in targets})
        for future in as_completed(futures):
            kind, target = futures[future]
            rows = future.result()
            (judged if kind == "judge" else direct).extend(rows)
            print(f"{kind} {target}: {len(rows)}", flush=True)
    judged = pd.DataFrame(judged).sort_values(["target", "comp"])
    direct = pd.DataFrame(direct).sort_values(["target", "rank"])
    judged.to_csv(OUT / "judge.csv", index=False)
    direct.to_csv(OUT / "direct.csv", index=False)
    positive = judged[judged["score"].eq(1)][["target", "comp"]]
    direct_pairs = direct[["target", "comp"]]
    rows = []
    for name, (top, selected) in selections.items():
        kept = selected.merge(positive, on=["target", "comp"], how="inner", validate="one_to_one")
        for route, peers in (("B3 selected", selected), ("B3 then LLM", kept),
                             ("Direct LLM", direct_pairs), ("LLM then B3", direct_pairs)):
            for cohort_name, cohort in cohorts.items():
                result, _ = score_cohort(name, route, top, peers, cohort_name, cohort)
                if route in ("Direct LLM", "LLM then B3"):
                    result["pairwise_top10_accuracy"] = float("nan")
                    result["pairwise_comparisons"] = 0
                rows.append(result)
    result = pd.DataFrame(rows)
    if len(result) != 12 * 4 * 5 or result.duplicated(["facet_source", "method", "label_source"]).any():
        raise ValueError("Incomplete four-route golden comparison")
    result.to_csv(OUT / "metrics.csv", index=False)
    (OUT / "run.json").write_text(json.dumps({
        "model": MODEL, "targets": targets, "training_pool_per_target": len(training)-1,
        "facet_conditions": len(routes), "selection_routes": 4,
        "judge_protocol": "One union of B3 shortlisted peers per target, then reuse each binary verdict across conditions",
        "direct_protocol": "One direct selection per target from the other 372 training firms",
        "direct_and_reverse_hybrid_membership_equal": True,
        "general_sha256": hashlib.sha256(GENERAL.read_bytes()).hexdigest(),
        "gold_label_sha256": hashlib.sha256(b3.LABELS.read_bytes()).hexdigest(),
        "caveat": "Two historical training targets; retrieval rank metric is only defined for B3 routes. No independent holdout conclusion.",
    }, indent=2), encoding="utf-8")
    print(result[result["label_source"].eq("human_majority")][
        ["facet_source", "method", "good_selected", "good_total", "bad_selected"]].to_string(index=False))


if __name__ == "__main__":
    main()
