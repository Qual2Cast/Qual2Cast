"""Reproducible common-input stage comparisons and factorial experiment."""

from pathlib import Path
import json
import numpy as np
import pandas as pd
from pipeline.team import TeamPipeline, ExperimentRunner
from pipeline.stages import PipelineConfig
from pipeline.config import FACTOR_SETS, AGGREGATORS
from pipeline.private_inputs import sponsor_simulation
from pipeline.company import _json_safe
from pipeline.evaluation_stage import event_metrics
from growth_signals.stage import GrowthStage
from valuation.measurement import accuracy_summary
from matching.private_evidence import digest

TARGETS = ["PCTY", "BV", "ROAD", "FIX", "BRO", "ADUS", "LOPE", "ODFL", "WING", "DXPE"]
METHOD_FIELDS = [
    "matching_method",
    "business_review_method",
    "factor_method",
    "valuation_method",
]


def paired_comparisons(frame, base):
    """Compare errors only on jointly scored targets; retain each arm's coverage."""
    reference = frame
    for field in METHOD_FIELDS:
        reference = reference[reference[field].eq(getattr(base, field))]
    reference = reference.set_index("company")
    results = []
    for names, group in frame.groupby(METHOD_FIELDS):
        paired = group.set_index("company")[["estimate", "observed_multiple"]].join(
            reference.estimate.rename("reference_estimate"), how="inner"
        )
        valid = np.isfinite(paired).all(axis=1) & paired.gt(0).all(axis=1)
        common = paired.loc[valid]
        error = 100 * (common.estimate / common.observed_multiple - 1).abs()
        ref_error = (
            100 * (common.reference_estimate / common.observed_multiple - 1).abs()
        )
        results.append(
            {
                **dict(zip(METHOD_FIELDS, names)),
                "common_scored": len(common),
                "common_companies": ", ".join(common.index),
                "method_coverage": float(group.estimate.notna().mean()),
                "reference_coverage": float(reference.estimate.notna().mean()),
                "common_median_ape": float(error.median()) if len(common) else None,
                "reference_common_median_ape": float(ref_error.median())
                if len(common)
                else None,
                "mean_paired_ape_change_pp": float((error - ref_error).mean())
                if len(common)
                else None,
            }
        )
    return pd.DataFrame(results)


def summarize(frame, grouping):
    rows = []
    for keys, g in frame.groupby(grouping, dropna=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        values = accuracy_summary(
            g.observed_multiple.to_numpy(float), g.estimate.to_numpy(float)
        )
        rows.append({**dict(zip(grouping, keys)), **values})
    return pd.DataFrame(rows)


def compare_growth(pipeline, root, out, config=None):
    labels = json.loads((root / "labels_holdout_c.json").read_text(encoding="utf-8"))
    records = {
        cid: json.loads(
            (root / "records/holdout_c" / (cid + ".json")).read_text(encoding="utf-8")
        )
        for cid in labels
        if not cid.startswith("_")
    }
    _, llm = pipeline._reviewer(config or PipelineConfig())
    rows, results = [], {}
    for method in GrowthStage.METHODS:
        results[method] = {
            cid: GrowthStage(llm).run(
                record,
                method,
                target_mode="public_benchmark",
                require_capture_by_cutoff=False,
            )
            for cid, record in records.items()
        }
        metrics = event_metrics(results[method], labels, records)
        rows.append(
            {
                "method": method,
                **{
                    k: v
                    for k, v in metrics.items()
                    if k not in ("false_positives", "false_negatives")
                },
            }
        )
        results[method + "_evaluation"] = metrics
    (out / "growth_stage_results.json").write_text(
        json.dumps(_json_safe(results), ensure_ascii=False), encoding="utf-8"
    )
    pd.DataFrame(rows).to_csv(out / "growth_evaluation.csv", index=False)
    return rows


def run_comparison(bundle, output, growth_root=None, config=None):
    pipeline = TeamPipeline.from_bundle(bundle)
    runner = ExperimentRunner(pipeline)
    inputs = {
        t: sponsor_simulation(pipeline.workflow, pipeline.workflow.ticker[t])
        for t in TARGETS
    }
    base = config or PipelineConfig(
        shortlist=5, peers=3, profile_method="llm", business_review_method="llm_staged"
    )
    configs = runner.configurations(
        base,
        matching_method=list(pipeline.matching.methods),
        business_review_method=["llm_direct", "llm_staged"],
        factor_method=list(FACTOR_SETS),
        valuation_method=list(AGGREGATORS),
    )
    configs += runner.configurations(
        base,
        business_review_method=["llm_rag", "llm_fewshot", "source_review"],
        factor_method=list(FACTOR_SETS),
        valuation_method=list(AGGREGATORS),
    )
    _, rows = runner.run(TARGETS, configs, inputs, output_dir=output, compact=True)
    out = runner.last_output
    summary = summarize(
        rows,
        [
            "matching_method",
            "business_review_method",
            "factor_method",
            "valuation_method",
        ],
    )
    summary.to_csv(out / "combination_evaluation.csv", index=False)
    paired_comparisons(rows, base).to_csv(
        out / "paired_method_evaluation.csv", index=False
    )
    # One-factor-at-a-time summaries use a declared fixed route, not pooled repeated cases.
    for stage, fixed in {
        "matching_method": {
            "factor_method": "business_only",
            "valuation_method": "median",
        },
        "factor_method": {"matching_method": "rrf", "valuation_method": "median"},
        "valuation_method": {
            "matching_method": "rrf",
            "factor_method": "business_only",
        },
    }.items():
        selected = rows.copy()
        for field, value in fixed.items():
            selected = selected[selected[field].eq(value)]
        summarize(selected, [stage, "business_review_method"]).to_csv(
            out / (stage + "_evaluation.csv"), index=False
        )
    reviewer, llm = pipeline._reviewer(base)
    pairs, retrieval, queue, profiles = [], [], [], []
    for t in TARGETS:
        cid = pipeline.workflow.ticker[t]
        profiles.append({"company": t, "company_id": cid, **reviewer.profile(cid)})
        union = set()
        for method in pipeline.matching.methods:
            frame = pipeline.matching.run(method, company_id=cid, limit=5)
            for row in frame.to_dict("records"):
                retrieval.append(
                    {"company": t, "target_id": cid, "method": method, **row}
                )
                union.add(row["peer_id"])
        for peer in sorted(union):
            for method in reviewer.METHODS:
                if method in ("llm_rag", "llm_fewshot") and peer not in set(
                    pipeline.matching.run("rrf", company_id=cid, limit=5).peer_id
                ):
                    continue
                # The hybrid arm reuses the same staged request when no ledger exists.
                result = reviewer.run(cid, peer, method)
                pairs.append(
                    {
                        "company": t,
                        "target_id": cid,
                        "peer_id": peer,
                        "method": method,
                        **result,
                    }
                )
            queue.append(
                {
                    "target": t,
                    "target_id": cid,
                    "peer_id": peer,
                    "peer": pipeline.workflow.data.iloc[
                        pipeline.workflow.index[peer]
                    ].target_ciq_ticker,
                    "reviewer": "",
                    "reviewed_on": "",
                    "reviewed_full_scope": "",
                    "business_function": "",
                    "operating_role": "",
                    "customer_use": "",
                    "whole_scope": "",
                    "grade_0_to_3": "",
                    "source_ids": "",
                    "target_source_id": "",
                    "target_quote": "",
                    "peer_source_id": "",
                    "peer_quote": "",
                    "scope_differences": "",
                    "target_document_hashes": json.dumps(
                        {
                            sid: digest(d["text"])
                            for sid, d in pipeline.documents.items()
                            if d["company_id"] == cid and d.get("eligible")
                        },
                        sort_keys=True,
                    ),
                    "peer_document_hashes": json.dumps(
                        {
                            sid: digest(d["text"])
                            for sid, d in pipeline.documents.items()
                            if d["company_id"] == peer and d.get("eligible")
                        },
                        sort_keys=True,
                    ),
                    "rationale": "",
                }
            )
    pd.DataFrame(retrieval).to_csv(out / "matching_stage_results.csv", index=False)
    pd.DataFrame(queue).to_csv(out / "independent_human_review.csv", index=False)
    (out / "business_stage_results.json").write_text(
        json.dumps(pairs, ensure_ascii=False), encoding="utf-8"
    )
    (out / "profile_stage_results.json").write_text(
        json.dumps(profiles, ensure_ascii=False), encoding="utf-8"
    )
    pair_frame = pd.DataFrame(pairs)
    pair_frame.groupby(["method", "status"]).size().rename(
        "pairs"
    ).reset_index().to_csv(out / "business_evaluation.csv", index=False)
    # Unreviewed retrieval and no-matching median are diagnostic controls only.
    controls = []
    for t in TARGETS:
        cid = pipeline.workflow.ticker[t]
        for name in ["no_matching"] + list(pipeline.matching.methods):
            ids = (
                [i for i in pipeline.workflow.ids if i != cid]
                if name == "no_matching"
                else pipeline.matching.run(
                    name, company_id=cid, limit=base.peers
                ).peer_id.tolist()
            )
            v = pipeline.valuation.run(
                "median",
                values=pipeline.peer_multiples.reindex(ids).tolist(),
                min_peers=3,
            )
            controls.append(
                {
                    "company": t,
                    "method": name,
                    "estimate": v["multiple"],
                    "observed_multiple": pipeline.peer_multiples.loc[cid],
                    "status": v["status"],
                    "business_approved": False,
                }
            )
    control_frame = pd.DataFrame(controls)
    control_frame.to_csv(out / "unreviewed_controls.csv", index=False)
    summarize(control_frame, ["method"]).to_csv(
        out / "control_evaluation.csv", index=False
    )
    if growth_root:
        compare_growth(pipeline, Path(growth_root), out, base)
    reports = {t: pipeline.run(t, base, inputs[t]) for t in TARGETS}
    for t, r in reports.items():
        observed = float(pipeline.peer_multiples.loc[pipeline.workflow.ticker[t]])
        estimate = r["stages"]["valuation"]["result"]["multiple"]
        r["development_evaluation"] = {
            "observed_snapshot_multiple": observed,
            "evaluation_timing": "Outcome read after the company report was returned",
            **accuracy_summary([observed], [estimate]),
        }
        (out / (t + "_Company_Report.json")).write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    (out / "comparison_scope.json").write_text(
        json.dumps(
            {
                "targets": TARGETS,
                "candidate_population": len(pipeline.workflow.ids),
                "shortlist": 5,
                "selected_peers": base.peers,
                "peer_count_design": "Retrieve up to five candidates and select three eligible peers, so factor reranking can alter the selected set. Fixed before the complete hosted valuation comparison.",
                "distinct_target_peer_pairs": len(queue),
                "configurations": len(configs),
                "company_config_runs": len(rows),
                "business_labels": "No independent labels; human-only and saved-review arms correctly abstain.",
                "growth_labels": "Team holdout C is reused as development data for the new prompt; not a fresh holdout.",
                "financial_inputs": "Explicit public-as-private simulation; dates, currencies and definitions unverified.",
                "interpretation": "No universal winner or validated private-company fair value is claimed.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pipeline.close()
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--growth-root", type=Path)
    parser.add_argument(
        "--provider", default="local", choices=["local", "cli", "openai"]
    )
    parser.add_argument("--model")
    args = parser.parse_args()
    base = PipelineConfig(
        shortlist=5, peers=3, profile_method="llm", business_review_method="llm_staged"
    )
    if args.provider != "local":
        from dataclasses import replace

        if not args.model:
            parser.error("--model is required for hosted inference")
        base = replace(
            base, llm_provider=args.provider, llm_model=args.model, llm_revision=None
        )
    print(run_comparison(args.bundle, args.output, args.growth_root, base))
