"""Evidence extraction and direct/staged business review with one LLM API.

Models cite sentence IDs; software supplies the exact source text and hashes.
Valid IDs prove traceability, not semantic correctness or human approval.
"""

import re
from pipeline.llm import object_schema, enum_schema
from matching.private_evidence import digest
from matching.business_gate import validate_pair, REQUIRED

STR = {"type": "string"}
IDS = {"type": "array", "items": STR, "maxItems": 4}
PROFILE_SCHEMA = object_schema(
    {
        "activities": {
            "type": "array",
            "items": object_schema(
                {"description": STR, "role": STR, "customers": STR, "sentence_ids": IDS}
            ),
        },
        "scope_uncertainties": STR,
    }
)
REVIEW_SCHEMA = object_schema(
    {
        "checks": object_schema(
            {key: enum_schema(["yes", "no", "unknown"]) for key in REQUIRED}
        ),
        "target_sentence_id": STR,
        "peer_sentence_id": STR,
        "scope_differences": STR,
        "rationale": STR,
    }
)


def sentence_cards(documents, company_id):
    cards = []
    for sid, doc in sorted(documents.items()):
        if doc["company_id"] != company_id or not doc.get("eligible"):
            continue
        # No removal of secondary business lines; all retained blocks included.
        parts = [
            s.strip()
            for s in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z])", doc["text"])
            if s.strip()
        ]
        for i, text in enumerate(parts):
            cards.append(
                {
                    "sentence_id": sid + ":S" + str(i),
                    "text": text,
                    "source_id": sid,
                    "source_url": doc["source_url"],
                    "text_sha256": digest(doc["text"]),
                }
            )
    return cards


def compact_cards(cards, prefix):
    """Collapse exact duplicate sentences only; keep every distinct observed line."""
    seen, result = set(), []
    for card in cards:
        if card["text"] not in seen:
            seen.add(card["text"])
            result.append({**card, "sentence_id": prefix + str(len(result))})
    return result


class BusinessReview:
    METHODS = (
        "source_review",
        "human_only",
        "llm_direct",
        "llm_staged",
        "llm_fewshot",
        "llm_rag",
        "hybrid",
    )

    def __init__(self, documents, reviews=None, llm=None):
        self.documents, self.reviews, self.llm = documents, reviews or {}, llm
        self.profiles = {}
        self.pair_cache = {}

    def profile(self, company_id):
        if company_id in self.profiles:
            return self.profiles[company_id]
        cards = compact_cards(sentence_cards(self.documents, company_id), "S")
        if self.llm is None:
            return {"status": "not_configured", "activities": []}
        answer = self.llm.complete(
            "business_profile_v3",
            {c["sentence_id"]: c["text"] for c in cards},
            PROFILE_SCHEMA,
            "List every materially distinct business activity visible in the evidence, including secondary lines. "
            "Distinguish the company from customers, suppliers and partners. Cite sentence_ids for each activity; "
            "role and customers are unknown unless supported. No invented segment shares or revenue models. "
            "Use concise descriptions and cite 1-4 decisive sentence IDs per activity; do not list every sentence.",
        )
        lookup = {c["sentence_id"]: c for c in cards}
        activities = (answer.get("data") or {}).get("activities", [])
        valid = [
            a
            for a in activities
            if a["sentence_ids"] and all(s in lookup for s in a["sentence_ids"])
        ]
        result = {
            "status": answer["status"],
            "activities": valid,
            "rejected_activities": len(activities) - len(valid),
            "scope_uncertainties": (answer.get("data") or {}).get(
                "scope_uncertainties", ""
            ),
            "request_id": answer.get("request_id"),
            "independent_human": False,
        }
        self.profiles[company_id] = result
        return result

    def run(self, target_id, peer_id, method="llm_staged"):
        key = (target_id, peer_id, method)
        if key not in self.pair_cache:
            self.pair_cache[key] = self._run(target_id, peer_id, method)
        return self.pair_cache[key]

    def _run(self, target_id, peer_id, method):
        if method not in self.METHODS:
            raise ValueError("Unknown business review method: " + method)
        stored = self.reviews.get(target_id + "|" + peer_id)
        if method in ("source_review", "human_only") or (method == "hybrid" and stored):
            if (
                method == "human_only"
                and (stored or {}).get("reviewer_kind") != "independent_human"
            ):
                return {
                    "peer_id": peer_id,
                    "eligible": False,
                    "status": "independent_review_missing",
                }
            return {
                "peer_id": peer_id,
                "review": stored,
                **validate_pair(stored, self.documents),
            }
        if method == "hybrid":
            method = "llm_staged"
        if self.llm is None:
            return {
                "peer_id": peer_id,
                "eligible": False,
                "status": "llm_not_configured",
            }
        target = compact_cards(sentence_cards(self.documents, target_id), "T")
        peer = compact_cards(sentence_cards(self.documents, peer_id), "P")
        if not target or not peer:
            return {
                "peer_id": peer_id,
                "eligible": False,
                "status": "business_evidence_missing",
            }
        full_target, full_peer = target, peer
        if method == "llm_rag":
            target, peer = (
                retrieve_passages(target, peer),
                retrieve_passages(full_peer, full_target),
            )
        payload = {
            "target": {c["sentence_id"]: c["text"] for c in target},
            "peer": {c["sentence_id"]: c["text"] for c in peer},
        }
        if method in ("llm_staged", "llm_fewshot", "llm_rag", "hybrid"):
            payload["target_profile"] = self.profile(target_id)
            payload["peer_profile"] = self.profile(peer_id)
        examples = (
            " Synthetic calibration examples (not company observations): "
            "A sells payroll, HR and expense-management software; B sells payroll and HR software. "
            "Their functions, software-vendor role and organizational customer use match; a product-feature gap alone "
            "does not make whole-scope comparability false. Record the gap, but all four checks can be yes. "
            "A installs and maintains HVAC systems; B manufactures HVAC equipment. Same end market, different "
            "function and role: no. A brokers insurance and advises on employee benefits; B brokers insurance "
            "and offers HR consulting. The additional related advisory service does not itself negate brokerage "
            "comparability. A carries insurance risk as an insurer and B brokers policies: operating_role no. "
            "Apply these distinctions to the supplied evidence; do not copy an example verdict blindly."
            if method == "llm_fewshot"
            else ""
        )
        answer = self.llm.complete(
            "business_pair_" + method + "_v5",
            payload,
            REVIEW_SCHEMA,
            "Judge comparability of the whole observed companies. business_function means the same actual service/product, "
            "not a broad sector. Equivalent functions count even when brands or marketing wording differ. "
            "operating_role distinguishes manufacturer, distributor, contractor, broker, insurer, "
            "software vendor/platform provider and asset owner. customer_use requires comparable customer needs. whole_scope requires that "
            "material secondary business lines do not make a one-line overlap misleading. Comparable does not mean identical: "
            "different product features, automation claims, company sizes or breadth within the same core business "
            "are scope differences, not automatic rejection or unknown. Do not require exact segment revenue weights "
            "when both observed companies perform the same coherent business function and role. "
            "Use unknown only for a genuinely missing decision-critical fact. Read all sentences; profiles "
            "are unverified aids. Return no for a substantive mismatch and unknown for insufficient evidence. "
            "Do not force a match or let common words outweigh different operating roles. Explain scope differences "
            "even for accepted peers. Each target_sentence_id and peer_sentence_id must be ONE decisive sentence ID "
            "(such as T3 and P5), not a list or a range. Consider ALL evidence before selecting those supporting citations. "
            "Keep rationale and scope_differences each below 60 words. No financial information is provided."
            + examples,
        )
        data = answer.get("data")
        if data is None:
            return {
                "peer_id": peer_id,
                "eligible": False,
                "status": answer["status"],
                "request_id": answer.get("request_id"),
            }
        checks = {k: data["checks"][k] == "yes" for k in REQUIRED}
        decision = (
            "eligible"
            if all(checks.values())
            else (
                "incompatible"
                if "no" in data["checks"].values()
                else "insufficient_evidence"
            )
        )
        review = {
            "target_id": target_id,
            "peer_id": peer_id,
            "decision": decision,
            "checks": checks,
            "criterion_decisions": dict(data["checks"]),
            "reviewer_kind": "source_based_assessment",
            "method": method,
            "model": self.llm.model,
            "request_id": answer["request_id"],
            "rationale": data["rationale"],
            "scope_differences": data["scope_differences"],
        }
        invalid_ids = False
        for side, cards in [("target", target), ("peer", peer)]:
            lookup = {c["sentence_id"]: c for c in cards}
            selected = [data[side + "_sentence_id"]]
            invalid_ids |= not selected or any(s not in lookup for s in selected)
            review[side + "_evidence"] = [
                {
                    "source_id": lookup[s]["source_id"],
                    "source_url": lookup[s]["source_url"],
                    "text_sha256": lookup[s]["text_sha256"],
                    "quote": lookup[s]["text"],
                }
                for s in selected
                if s in lookup
            ]
            review[side + "_document_hashes"] = {
                sid: digest(d["text"])
                for sid, d in self.documents.items()
                if d["company_id"] == (target_id if side == "target" else peer_id)
                and d.get("eligible")
            }
        if invalid_ids:
            review["decision"] = "invalid_citations"
        result = {
            "peer_id": peer_id,
            "review": review,
            **validate_pair(review, self.documents),
        }
        if method == "llm_rag":
            # Retrieved snippets may omit an unrelated business. Every positive
            # decision therefore also needs the all-evidence staged decision.
            full_scope = self.run(target_id, peer_id, "llm_staged")
            result["rag_audit"] = {
                "target_sentences": len(target),
                "peer_sentences": len(peer),
                "target_total_sentences": len(full_target),
                "peer_total_sentences": len(full_peer),
                "full_scope_review_status": full_scope["status"],
                "full_scope_request_id": full_scope.get("review", {}).get("request_id"),
            }
            if result["eligible"] and not full_scope["eligible"]:
                result.update(eligible=False, status="full_scope_review_not_passed")
        return result


def retrieve_passages(cards, counterpart, limit=12):
    """TF-IDF passage retrieval with per-document coverage; no financial inputs."""
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    if len(cards) <= limit:
        return cards
    texts = [c["text"] for c in cards]
    query = " ".join(c["text"] for c in counterpart)
    try:
        vectors = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit_transform(
            texts + [query]
        )
        scores = (vectors[:-1] @ vectors[-1].T).toarray().ravel()
    except ValueError:
        scores = np.zeros(len(cards))
    selected = set(np.argsort(-scores, kind="stable")[:limit].tolist())
    # Include the leading statement of every captured document as context.
    seen = set()
    for i, c in enumerate(cards):
        if c["source_id"] not in seen:
            selected.add(i)
            seen.add(c["source_id"])
    return [cards[i] for i in sorted(selected)]
