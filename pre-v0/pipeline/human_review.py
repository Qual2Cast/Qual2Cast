"""Import explicitly completed independent reviews; blank templates approve nothing."""

import csv
import json
from datetime import date
from matching.business_gate import REQUIRED, evidence_errors
from matching.private_evidence import digest


def blank_review_row(documents, target_id, peer_id, target, peer):
    """Freeze evidence scope without copying model verdicts into human labels."""
    row = {"target": target, "target_id": target_id, "peer_id": peer_id, "peer": peer}
    for key in (
        "reviewer",
        "reviewed_on",
        "reviewed_full_scope",
        *REQUIRED,
        "grade_0_to_3",
        "source_ids",
        "target_source_id",
        "target_quote",
        "peer_source_id",
        "peer_quote",
        "scope_differences",
        "rationale",
    ):
        row[key] = ""
    for side, cid in (("target", target_id), ("peer", peer_id)):
        row[side + "_document_hashes"] = json.dumps(
            {
                sid: digest(d["text"])
                for sid, d in documents.items()
                if d["company_id"] == cid and d.get("eligible")
            },
            sort_keys=True,
        )
    return row


def load_human_reviews(path, documents):
    reviews, errors, blank = {}, [], 0
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = row["target_id"] + "|" + row["peer_id"]
            if not row.get("grade_0_to_3", "").strip():
                blank += 1
                continue
            try:
                grade = int(row["grade_0_to_3"])
                if grade not in range(4):
                    raise ValueError("Grade must be 0, 1, 2 or 3")
                for field in (
                    "reviewer",
                    "reviewed_on",
                    "rationale",
                    "scope_differences",
                ):
                    if not row.get(field, "").strip():
                        raise ValueError("Missing " + field)
                date.fromisoformat(row["reviewed_on"])
                if row.get("reviewed_full_scope", "").strip().lower() != "yes":
                    raise ValueError("Full observed company scope must be reviewed")
                decisions = {k: row[k].strip().lower() for k in REQUIRED}
                if not set(decisions.values()) <= {"yes", "no", "unknown"}:
                    raise ValueError("Criteria require yes, no or unknown")
                checks = {k: v == "yes" for k, v in decisions.items()}
                if all(checks.values()) and grade < 2:
                    raise ValueError("Grade contradicts four positive criteria")
                verdict = (
                    "eligible"
                    if all(checks.values())
                    else "incompatible"
                    if "no" in decisions.values()
                    else "insufficient_evidence"
                )
                review = {
                    "target_id": row["target_id"],
                    "peer_id": row["peer_id"],
                    "reviewer_kind": "independent_human",
                    "reviewer": row["reviewer"],
                    "reviewed_on": row["reviewed_on"],
                    "grade_0_to_3": grade,
                    "decision": verdict,
                    "checks": checks,
                    "criterion_decisions": decisions,
                    "rationale": row["rationale"],
                    "scope_differences": row["scope_differences"],
                }
                for side in ("target", "peer"):
                    hashes = json.loads(row[side + "_document_hashes"])
                    sid, quote = row[side + "_source_id"], row[side + "_quote"]
                    if sid not in hashes or not quote.strip():
                        raise ValueError("Missing source-bound " + side + " evidence")
                    review[side + "_document_hashes"] = hashes
                    review[side + "_evidence"] = [
                        {
                            "source_id": sid,
                            "source_url": documents.get(sid, {}).get("source_url"),
                            "quote": quote,
                            "text_sha256": hashes[sid],
                        }
                    ]
                problems = evidence_errors(review, documents)
                if problems:
                    raise ValueError("; ".join(problems))
                if key in reviews:
                    raise ValueError("Duplicate review pair")
                reviews[key] = review
            except (ValueError, KeyError, TypeError) as exc:
                errors.append({"pair": key, "error": str(exc)})
    return {
        "reviews": reviews,
        "errors": errors,
        "blank_rows": blank,
        "status": "requires_correction"
        if errors
        else "loaded"
        if reviews
        else "no_completed_reviews",
    }
