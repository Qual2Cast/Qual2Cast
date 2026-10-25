"""A blank template or stale source cannot become an independent approval."""

import csv
import json
import pytest
from matching.business_gate import REQUIRED
from matching.private_evidence import digest
from pipeline.human_review import load_human_reviews


def review_file(tmp_path, change=None):
    documents = {
        cid + ":P1": {
            "company_id": cid,
            "text": "Electrical installation.",
            "eligible": True,
        }
        for cid in ("T", "P")
    }
    row = dict(
        target_id="T",
        peer_id="P",
        reviewer="Independent reviewer",
        reviewed_on="2026-10-19",
        rationale="Both install electrical systems.",
        scope_differences="No other activity in this synthetic fixture.",
        reviewed_full_scope="yes",
        grade_0_to_3="3",
        **dict.fromkeys(REQUIRED, "yes"),
    )
    for side, cid in [("target", "T"), ("peer", "P")]:
        sid = cid + ":P1"
        row[side + "_source_id"] = sid
        row[side + "_quote"] = documents[sid]["text"]
        row[side + "_document_hashes"] = json.dumps(
            {sid: digest(documents[sid]["text"])}
        )
    row.update(change or {})
    path = tmp_path / "reviews.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=row)
        writer.writeheader()
        writer.writerow(row)
    return path, documents


@pytest.mark.parametrize("reviewer", ["", "Reviewer who found insufficient evidence"])
def test_blank_template_approves_nothing(tmp_path, reviewer):
    path, documents = review_file(tmp_path, {"reviewer": reviewer, "grade_0_to_3": ""})
    result = load_human_reviews(path, documents)
    assert result["status"] == "no_completed_reviews" and result["reviews"] == {}


def test_completed_review_is_source_bound(tmp_path):
    path, documents = review_file(tmp_path)
    result = load_human_reviews(path, documents)
    assert result["reviews"]["T|P"]["reviewer_kind"] == "independent_human"
    documents["T:P2"] = {
        "company_id": "T",
        "text": "We also manufacture machinery.",
        "eligible": True,
    }
    result = load_human_reviews(path, documents)
    assert result["status"] == "requires_correction" and not result["reviews"]


@pytest.mark.parametrize(
    "changes",
    [
        {"peer_quote": "Invented quotation"},
        {
            "business_function": "no",
            "grade_0_to_3": "0",
            "peer_quote": "Invented quotation",
        },
        {"reviewed_on": "not a date"},
        {"reviewed_full_scope": "no"},
    ],
)
def test_unverifiable_review_is_rejected_even_for_negative_verdict(tmp_path, changes):
    path, documents = review_file(tmp_path, changes)
    result = load_human_reviews(path, documents)
    assert result["status"] == "requires_correction" and not result["reviews"]
