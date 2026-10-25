"""Continue down a full candidate ranking; preserve reviewed and unreviewed rows."""

import argparse
import json
from pathlib import Path
import pandas as pd
from pipeline.team import TeamPipeline
from pipeline.stages import PipelineConfig
from pipeline.private_inputs import sponsor_simulation
from pipeline.reporting import company_html
from pipeline.human_review import blank_review_row


def run(
    bundle, output, targets, review_limit=50, live=False, simulate_financials=False
):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    pipeline = TeamPipeline.from_bundle(bundle, live_llm=live)
    config = PipelineConfig(
        profile_method="llm",
        peer_search_policy="progressive",
        review_limit=review_limit,
        shortlist=len(pipeline.workflow.ids) - 1,
        peers=10,
        min_peers=3,
        business_review_method="llm_staged",
        llm_provider="cli",
        llm_model="gpt-6.1-sol",
        llm_revision=None,
    )
    reviewer, _ = pipeline._reviewer(config)
    original = reviewer.run
    examined = []

    def observed_review(cid, peer, method):
        result = original(cid, peer, method)
        examined.append({"target_id": cid, "peer_id": peer, "status": result["status"]})
        (output / "progress.json").write_text(
            json.dumps(examined, indent=1), encoding="utf-8"
        )
        print(json.dumps(examined[-1]), flush=True)
        return result

    reviewer.run = observed_review
    try:
        for target in targets:
            inputs = (
                sponsor_simulation(pipeline.workflow, pipeline.workflow.ticker[target])
                if simulate_financials
                else None
            )
            report = pipeline.run(target, config, inputs)
            search = report["stages"]["candidate_search"]["result"]
            (output / (target + "_Company_Report.json")).write_text(
                json.dumps(report, indent=1), encoding="utf-8"
            )
            (output / (target + "_Company_Report.html")).write_text(
                company_html(report), encoding="utf-8"
            )
            pd.DataFrame(search["ranked_candidates"]).to_csv(
                output / (target + "_ranked_candidates.csv"), index=False
            )
            cid = report["identity"]["IQ_COMPANY_ID"]
            pd.DataFrame(
                [
                    blank_review_row(
                        pipeline.documents, cid, row["peer_id"], target, row["peer"]
                    )
                    for row in search["ranked_candidates"]
                    if row["review_status"] != "not_reviewed"
                ]
            ).sort_values("peer_id").to_csv(output / (target + "_independent_human_review.csv"), index=False)
            pd.DataFrame(
                [
                    {k: v for k, v in p.items() if k != "business_review"}
                    for p in report["peers"]
                ]
            ).to_csv(output / (target + "_selected_peers.csv"), index=False)
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in search.items()
                        if k not in ("ranked_candidates", "reviews")
                    }
                ),
                flush=True,
            )
    finally:
        pipeline.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--targets", nargs="+", default=["PCTY"])
    parser.add_argument(
        "--review-limit",
        type=int,
        default=50,
        help="Cumulative candidate review budget; zero scans until ten qualify or the pool is exhausted",
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--simulate-financials", action="store_true")
    args = parser.parse_args()
    run(
        args.bundle,
        args.output,
        args.targets,
        args.review_limit or None,
        args.live,
        args.simulate_financials,
    )
