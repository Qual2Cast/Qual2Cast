"""Evidence-bound business eligibility before any financial reranking.

Source review judgments are distinct from independent human validation. No
unreviewed pair, high cosine or favorable financial ratio can bypass this gate.
"""

from matching.private_evidence import digest

REQUIRED = ("business_function", "operating_role", "customer_use", "whole_scope")


def evidence_errors(review, documents):
    """Check source ownership, quotations and complete scope for any verdict."""
    errors = []
    for side in ("target", "peer"):
        claims = review.get(side + "_evidence", [])
        if not claims:
            errors.append("missing_" + side + "_evidence")
        for claim in claims:
            doc = documents.get(claim.get("source_id"))
            if (
                not doc
                or doc["company_id"] != review.get(side + "_id")
                or not doc.get("eligible")
            ):
                errors.append("invalid_" + side + "_source")
                continue
            if claim.get("text_sha256") != digest(doc["text"]):
                errors.append("stale_" + side + "_evidence")
            if not claim.get("quote") or claim["quote"] not in doc["text"]:
                errors.append("unsupported_" + side + "_quote")
        # Binding the entire reviewed website corpus prevents reusing approval
        # when an unquoted page adds a new business line or changes materially.
        expected = {
            k: digest(v["text"])
            for k, v in documents.items()
            if v["company_id"] == review.get(side + "_id") and v.get("eligible")
        }
        if not expected or review.get(side + "_document_hashes") != expected:
            errors.append("incomplete_or_changed_" + side + "_scope")
    return errors


def validate_pair(review, documents):
    if not review:
        return {
            "eligible": False,
            "status": "unreviewed",
            "errors": ["missing_business_review"],
        }
    if review.get("decision") != "eligible":
        return {
            "eligible": False,
            "status": review.get("decision", "unreviewed"),
            "errors": [],
            "rationale": review.get("rationale", ""),
        }
    errors = evidence_errors(review, documents)
    if any(review.get("checks", {}).get(k) is not True for k in REQUIRED):
        errors.append("business_criteria_not_met")
    if review.get("reviewer_kind") not in (
        "source_based_assessment",
        "independent_human",
    ):
        errors.append("unknown_review_provenance")
    if not review.get("scope_differences") or not review.get("rationale"):
        errors.append("missing_scope_explanation")
    return {
        "eligible": not errors,
        "status": "source_review_pass" if not errors else "invalid_review",
        "errors": errors,
        "rationale": review.get("rationale", ""),
        "scope_differences": review.get("scope_differences", ""),
        "independent_human": review.get("reviewer_kind") == "independent_human",
    }


def eligible_pool(target_id, company_ids, reviews, documents):
    rows = []
    for peer_id in company_ids:
        if peer_id == target_id:
            continue
        result = validate_pair(reviews.get(target_id + "|" + peer_id), documents)
        rows.append({"peer_id": peer_id, **result})
    return rows
