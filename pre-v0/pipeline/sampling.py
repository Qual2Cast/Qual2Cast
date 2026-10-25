"""Declare the target sample before inspecting method outcomes."""

import numpy as np

TEAM_PILOT = (
    "PCTY",
    "BV",
    "ROAD",
    "FIX",
    "BRO",
    "ADUS",
    "LOPE",
    "ODFL",
    "WING",
    "DXPE",
)


class SampleStage:
    METHODS = ("team_pilot", "seeded_random")

    def run(self, method, workflow, n=10, seed=4511, exclude_ids=()):
        if method == "team_pilot":
            ids = [workflow.ticker[t] for t in TEAM_PILOT]
            description = (
                "Purposive team development cases; not a random or independent holdout."
            )
        elif method == "seeded_random":
            pool = sorted(set(workflow.ids) - set(exclude_ids))
            if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= len(pool):
                raise ValueError(
                    "Sample size must be a positive integer within the eligible pool"
                )
            ids = np.random.default_rng(seed).choice(pool, n, replace=False).tolist()
            description = "Uniform sample without replacement from eligible website records; outcome availability is not a sampling filter."
        else:
            raise ValueError("Unknown sampling method: " + method)
        rows = workflow.data.set_index("IQ_COMPANY_ID").loc[ids].reset_index()
        return {
            "method": method,
            "company_ids": ids,
            "tickers": rows.target_ciq_ticker.tolist(),
            "seed": seed if method == "seeded_random" else None,
            "sampling_frame": len(set(workflow.ids) - set(exclude_ids))
            if method == "seeded_random"
            else len(workflow.ids),
            "interpretation": description,
        }
