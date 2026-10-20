"""Use the existing website collector through a common, replaceable interface."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys
import uuid
from matching.private_evidence import source_document


class EvidenceStage:
    METHODS = ("cached", "live_http")

    def run(
        self,
        method="cached",
        *,
        record=None,
        company_name=None,
        website=None,
        output_dir=None,
        user_agent=None,
        max_pages=3,
    ):
        if method == "cached":
            if record is None:
                return {"status": "capture_required", "documents": []}
        elif method == "live_http":
            if not all((company_name, website, output_dir, user_agent)):
                raise ValueError(
                    "Live collection requires name, website, output directory and contact User-Agent"
                )
            module_dir = Path(__file__).resolve().parents[1] / "website_scrape"
            if str(module_dir) not in sys.path:
                sys.path.insert(0, str(module_dir))
            from scrape_websites import collect
            from fetch_and_clean import Fetcher

            folder = Path(output_dir) / (
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                + "-"
                + uuid.uuid4().hex[:6]
            )
            folder.mkdir(parents=True)
            result = collect(
                [Fetcher(user_agent)], website, max_pages, folder / "raw_html"
            )
            record = {
                "IQ_COMPANY_ID": "PRIVATE_"
                + hashlib.sha256(website.encode()).hexdigest()[:16],
                "company_name": company_name,
                "website": website,
                **result,
            }
            (folder / "capture.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        else:
            raise ValueError("Unknown collection method: " + method)
        documents = [
            source_document(record["IQ_COMPANY_ID"], p) for p in record.get("pages", [])
        ]
        return {
            "status": record.get("status", "captured"),
            "record": record,
            "documents": documents,
            "method": method,
            "evaluation": {
                "captured_pages": len(documents),
                "eligible_pages": sum(d["eligible"] for d in documents),
                "coverage_complete": False,
            },
        }
