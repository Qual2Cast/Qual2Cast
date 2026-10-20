import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

from score_rules import score_set  # noqa: E402


def test_score_set_counts_pairs_and_ignores_borderline(tmp_path):
    records = tmp_path / "records"
    records.mkdir()
    page = {"category": "article", "published_date": "2026-09-22",
            "published_date_precision": "day", "fetched_at": "2026-09-23T12:00:00Z",
            "raw_title": "", "raw_meta": ""}
    record = {"IQ_COMPANY_ID": "IQ1", "company_name": "Example Co.", "pages": [
        {**page, "page_id": "P1", "source_url": "https://example.com/news/a",
         "raw_blocks": ["Example Co. opened a new plant in Ohio."]},
        {**page, "page_id": "P2", "source_url": "https://example.com/news/b",
         "raw_blocks": ["Example Co. launched a new payroll platform."]},
        {**page, "page_id": "P3", "source_url": "https://example.com/news/c",
         "raw_blocks": ["Example Co. signed a contract with a hospital network."]},
    ]}
    (records / "IQ1.json").write_text(json.dumps(record))
    labels = {"IQ1": {"truth": {"P1": ["market_expansion"], "P3": ["hiring"]},
                      "borderline": [["P2", "product_launch"]]}}
    rows = score_set(labels, records)["rows"]
    assert rows["ALL"] == {"predicted": 2, "true": 2, "correct": 1}
    assert rows["market_expansion"] == {"predicted": 1, "true": 1, "correct": 1}
