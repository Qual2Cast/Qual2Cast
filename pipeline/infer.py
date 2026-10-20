"""Run bounded, resumable local inference for the registered experiment arms."""

from pathlib import Path
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pipeline.team import TeamPipeline
from pipeline.stages import PipelineConfig
from pipeline.compare import TARGETS
from growth_signals.stage import GrowthStage


def run_inference(
    bundle,
    output,
    config=None,
    phases=("business", "fewshot", "rag", "growth", "private_growth"),
    workers=1,
):
    config = config or PipelineConfig(shortlist=5)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    pipeline = TeamPipeline.from_bundle(bundle, live_llm=True)
    reviewer, llm = pipeline._reviewer(config)
    if workers > 1 and config.llm_provider == "local":
        raise ValueError("Local model inference uses one worker only")
    if not 1 <= workers <= 2:
        raise ValueError("Use one or two hosted request workers")
    root = Path(__file__).resolve().parents[1] / "growth_signals/eval/2026-10-19"
    try:
        for phase in phases:
            rows = []
            if phase in ("growth", "private_growth"):
                records = (
                    {
                        path.stem: json.loads(path.read_text(encoding="utf-8"))
                        for path in sorted((root / "records/holdout_c").glob("*.json"))
                    }
                    if phase == "growth"
                    else {
                        pipeline.workflow.ticker[t]: pipeline.growth_records.get(
                            pipeline.workflow.ticker[t]
                        )
                        for t in TARGETS
                    }
                )
                for cid, record in records.items():
                    result = (
                        GrowthStage(llm).run(
                            record,
                            "llm",
                            target_mode="public_benchmark",
                            require_capture_by_cutoff=False,
                        )
                        if phase == "growth"
                        else GrowthStage(llm).run(record, "llm", config.cutoff)
                    )
                    (output / (phase + "_" + cid + ".json")).write_text(
                        json.dumps(result, ensure_ascii=False), encoding="utf-8"
                    )
                    print(
                        json.dumps(
                            {
                                "phase": phase,
                                "company_id": cid,
                                "status": result["status"],
                            }
                        ),
                        flush=True,
                    )
                continue
            methods = {
                "business": ["llm_direct", "llm_staged"],
                "fewshot": ["llm_fewshot"],
                "rag": ["llm_rag"],
            }[phase]
            retrievers = (
                list(pipeline.matching.methods) if phase == "business" else ["rrf"]
            )
            jobs = []
            for ticker in TARGETS:
                cid = pipeline.workflow.ticker[ticker]
                peers = []
                for name in retrievers:
                    peers.extend(
                        pipeline.matching.run(
                            name, company_id=cid, limit=config.shortlist
                        ).peer_id
                    )
                for peer in dict.fromkeys(peers):
                    for method in methods:
                        jobs.append((ticker, cid, peer, method))
            # Complete unique profiles first, avoiding duplicated hosted requests.
            profile_ids = sorted(
                {cid for _, cid, _, _ in jobs} | {peer for _, _, peer, _ in jobs}
            )
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(reviewer.profile, cid): cid for cid in profile_ids
                }
                for future in as_completed(futures):
                    result = future.result()
                    print(
                        json.dumps(
                            {
                                "phase": "profile",
                                "company_id": futures[future],
                                "status": result["status"],
                            }
                        ),
                        flush=True,
                    )

            def run_job(job):
                ticker, cid, peer, method = job
                start = time.perf_counter()
                result = reviewer.run(cid, peer, method)
                return {
                    "target": ticker,
                    "target_id": cid,
                    "peer_id": peer,
                    "method": method,
                    "wall_seconds": round(time.perf_counter() - start, 2),
                    **result,
                }

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(run_job, job) for job in jobs]
                for future in as_completed(futures):
                    row = future.result()
                    rows.append(row)
                    (output / "progress.json").write_text(
                        json.dumps(
                            {
                                "phase": phase,
                                "completed": len(rows),
                                "expected": len(jobs),
                                "target": row["target"],
                                "last_status": row["status"],
                            }
                        ),
                        encoding="utf-8",
                    )
                    print(
                        json.dumps(
                            {
                                k: row[k]
                                for k in (
                                    "target",
                                    "peer_id",
                                    "method",
                                    "status",
                                    "wall_seconds",
                                )
                            }
                        ),
                        flush=True,
                    )
                    if len(rows) % 10 == 0:
                        (output / (phase + "_partial.json")).write_text(
                            json.dumps(rows, ensure_ascii=False), encoding="utf-8"
                        )
            (output / (phase + "_results.json")).write_text(
                json.dumps(rows, ensure_ascii=False), encoding="utf-8"
            )
    finally:
        pipeline.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--provider", default="local", choices=["local", "cli", "openai"]
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--phases",
        nargs="+",
        default=["business", "fewshot", "rag", "growth", "private_growth"],
        choices=["business", "fewshot", "rag", "growth", "private_growth"],
    )
    args = parser.parse_args()
    config = PipelineConfig(shortlist=5)
    if args.provider != "local":
        from dataclasses import replace

        if not args.model:
            parser.error("--model is required for a hosted provider")
        config = replace(
            config, llm_provider=args.provider, llm_model=args.model, llm_revision=None
        )
    run_inference(
        args.bundle,
        args.output,
        config=config,
        phases=args.phases,
        workers=args.workers,
    )
