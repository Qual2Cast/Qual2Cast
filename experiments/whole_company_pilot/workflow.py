"""Offline tutorial API over the frozen experiment's original analysis cells.

The numeric/model implementation remains in src/modular_validation and scripts.
This adapter reuses the original checks and calculations; it does not refit models.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile


class Pilot:
    """Run named, ordered analysis steps and expose their tables as attributes."""

    def __init__(self, payload_base64: str, payload_sha256: str):
        from IPython.utils.capture import capture_output

        packed = base64.b64decode(payload_base64, validate=True)
        if hashlib.sha256(packed).hexdigest() != payload_sha256:
            raise ValueError("Embedded payload checksum mismatch")
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            self._stages = json.loads(archive.read("tutorial/replay_stages.json"))
            self.method_catalogue_records = json.loads(archive.read("tutorial/method_catalogue.json"))
        self._capture = capture_output
        self._namespace = {"PAYLOAD_BASE64": payload_base64, "PAYLOAD_SHA256": payload_sha256}
        self._done = set()
        self._audit = {}

    def run(self, stage: str):
        """Replay through a named step once; retain detailed audit output on demand."""
        if stage not in self._stages:
            raise KeyError(stage)
        for name, sources in self._stages.items():
            if name not in self._done:
                with self._capture() as captured:
                    for source in sources:
                        exec(compile(source, f"frozen-analysis/{name}", "exec"), self._namespace)
                self._audit[name] = captured
                self._done.add(name)
            if name == stage:
                break
        return self

    def __getattr__(self, name):
        try:
            return self._namespace[name]
        except KeyError as exc:
            raise AttributeError(f"Run the relevant tutorial step before accessing {name!r}") from exc

    def show_audit(self, stage: str):
        """Show the original, verbose tables and diagnostics for just this step."""
        self.run(stage)
        self._audit[stage].show()

    def top_peers(self, ticker: str, method="team_mpnet_cosine", k=5):
        """Return observed ranked candidates, without claiming human approval."""
        self.run("rankings")
        ids = self.F.index[self.F.target_ciq_ticker.eq(ticker)].tolist()
        if len(ids) != 1:
            raise ValueError("Ticker must resolve to exactly one supplied company")
        rows = self.rankings.loc[
            self.rankings.target_id.eq(ids[0]) & self.rankings.method.eq(method)
            & self.rankings.available
        ].sort_values("rank").head(k)
        result = rows[["rank", "candidate_id", "score"]].copy()
        result["ticker"] = result.candidate_id.map(self.F.target_ciq_ticker)
        result["company"] = result.candidate_id.map(self.F.target_company_name)
        return result[["rank", "ticker", "company", "candidate_id", "score"]].reset_index(drop=True)

    def case_review(self, target_ticker: str, candidate_ticker: str):
        """Return the saved AI review and exact company-source evidence."""
        self.run("cases")
        for (target_id, candidate_id), pair in self.ic_reviews.items():
            if (self.F.loc[target_id, "target_ciq_ticker"] == target_ticker
                    and self.F.loc[candidate_id, "target_ciq_ticker"] == candidate_ticker):
                return {
                    "overlap": [r["claim"] for r in pair["overlap_claims"]],
                    "differences": [r["claim"] for r in pair["material_mismatches"]],
                    "assessment": pair["committee_rationale"],
                    "human_approved": False,
                    "evidence": [{**r, "company_id": cid} for cid in (target_id, candidate_id)
                                 for r in self.ic_companies[cid]["source_records"]],
                }
        for pair in self.new_candidate_reviews:
            if pair["target_ticker"] == target_ticker and pair["candidate_ticker"] == candidate_ticker:
                return {"overlap": pair.get("supported_overlap", []),
                        "differences": pair.get("material_differences", []),
                        "assessment": pair.get("verdict_text", ""), "human_approved": False,
                        "evidence": pair["source_evidence"]}
        raise KeyError("No saved source review for this pair; inspect the source pages directly")

    def export_workspace(self, directory):
        """Explicit opt-in: create a fresh source/data workspace for full inference."""
        self.run("export")
        return self._namespace["export_workspace"](directory)
