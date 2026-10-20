"""Method-level procedures, citations and interpretation limits."""

from pipeline.research import SOURCES

REFERENCES = {
    "rag": {
        "title": "Lewis et al. (2020), Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "url": "https://arxiv.org/abs/2005.11401",
    },
    "lora": {
        "title": "Hu et al. (2021), LoRA: Low-Rank Adaptation of Large Language Models",
        "url": "https://arxiv.org/abs/2106.09685",
    },
    "enterprise_rag": {
        "title": "Google Cloud: RAG and grounding on Vertex AI",
        "url": "https://cloud.google.com/blog/products/ai-machine-learning/rag-and-grounding-on-vertex-ai",
    },
    **{key: {"title": value[0], "url": value[1]} for key, value in SOURCES.items()},
    "text": {
        "title": "Manning, Raghavan and Schuetze, Introduction to Information Retrieval",
        "url": "https://nlp.stanford.edu/IR-book/",
    },
    "lsa": {
        "title": "scikit-learn: TruncatedSVD and latent semantic analysis",
        "url": "https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html",
    },
    "cluster": {
        "title": "scikit-learn: hierarchical clustering",
        "url": "https://scikit-learn.org/stable/modules/clustering.html#hierarchical-clustering",
    },
    "hdbscan": {
        "title": "McInnes, Healy and Astels (2017), hdbscan",
        "url": "https://joss.theoj.org/papers/10.21105/joss.00205",
    },
    "qwen": {
        "title": "Qwen2.5-3B-Instruct model card",
        "url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct",
    },
    "structured": {
        "title": "OpenAI: Structured Outputs",
        "url": "https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses",
    },
    "team_matching": {
        "title": "Team matching implementation, Michael branch 14d7d95",
        "url": "https://github.com/Qual2Cast/Qual2Cast/tree/14d7d95749104100335f7a52152b39da265cbd58",
    },
    "team_growth": {
        "title": "Team growth implementation and evaluation, 793cf63",
        "url": "https://github.com/Qual2Cast/Qual2Cast/tree/793cf63787f5abb459eff71fde26e7b0c1611eff/growth_signals",
    },
    "team_scrape": {
        "title": "Team website collection implementation",
        "url": "https://github.com/Qual2Cast/Qual2Cast/tree/4d24050a6eeedad5581ec91a8bf32b2821d0fbe3/website_scrape",
    },
}


def method_catalog():
    rows = []

    def add(stage, method, procedure, sources, limitation):
        rows.append(
            dict(
                stage=stage,
                method=method,
                procedure=procedure,
                sources=sources,
                limitation=limitation,
            )
        )

    add(
        "sample",
        "team_pilot",
        "Use the ten declared team development targets without relabeling them as random.",
        ["selection"],
        "Purposive diagnostic cases; no independent population inference.",
    )
    add(
        "sample",
        "seeded_random",
        "Sample without replacement from eligible website records with a fixed seed and explicit exclusions.",
        ["selection"],
        "Random selection alone does not create a valid held-out test after repeated method tuning.",
    )
    add(
        "business_review",
        "llm_fewshot",
        "Add synthetic role/scope calibration examples to direct source-bounded pair review.",
        ["llm_peers", "qwen"],
        "Prompt-development arm, not trained weights; examples were added after inspecting development failures.",
    )
    add(
        "evidence",
        "cached",
        "Reuse versioned website captures; retain URLs, dates, text hashes and a removal ledger.",
        ["team_scrape"],
        "Captured pages do not establish complete business coverage.",
    )
    add(
        "evidence",
        "live_http",
        "Run the existing robots-aware HTTP collector and save a new capture before transformation.",
        ["team_scrape"],
        "Not rerun in the common-input experiment; dynamic or blocked pages may be unavailable.",
    )
    add(
        "profile",
        "sentence_evidence",
        "Retain all permitted source sentences without inferred facets.",
        ["rbics"],
        "A source-evidence baseline, not an RBICS reconstruction.",
    )
    add(
        "profile",
        "llm",
        "Extract all observed activities, operating roles and customers; validate cited sentence IDs.",
        ["llm_peers", "qwen"],
        "Source traceability does not establish factual or scope completeness.",
    )
    for name, procedure, refs in [
        (
            "mpnet",
            "Mean normalized MPNet embeddings of 200-word chunks; cosine ordering.",
            ["sbert"],
        ),
        (
            "tfidf",
            "Word unigrams/bigrams, sublinear term frequency and cosine ordering.",
            ["text"],
        ),
        (
            "lsa",
            "96-component truncated SVD of TF-IDF, normalized before cosine ordering.",
            ["lsa"],
        ),
        ("rrf", "Fuse the three complete rankings with sum 1/(60 + rank).", ["rrf"]),
        (
            "z2",
            "Retain MPNet similarities at least two within-target standard deviations above their mean.",
            ["team_matching"],
        ),
        (
            "mutual20",
            "Require reciprocal membership in the 20-nearest-neighbor lists.",
            ["team_matching"],
        ),
        (
            "cluster_eom",
            "Use the team UMAP/HDBSCAN EOM membership selector, then order within the eligible group.",
            ["team_matching", "hdbscan"],
        ),
        (
            "tree_complete",
            "Complete-linkage hierarchy; select the smallest enclosing group with at least five peers.",
            ["team_matching", "cluster"],
        ),
        (
            "tree_ward",
            "Ward hierarchy on normalized embeddings; select the smallest enclosing group with at least five peers.",
            ["team_matching", "cluster"],
        ),
    ]:
        add(
            "matching",
            name,
            procedure,
            refs,
            "Retrieval is a candidate proposal, not proof of comparable economics.",
        )
    for name, procedure in [
        (
            "llm_direct",
            "Judge function, operating role, customer use and whole observed scope in one evidence-bounded request.",
        ),
        (
            "llm_staged",
            "Extract company profiles, then judge the pair using profiles and all retained source sentences.",
        ),
        (
            "source_review",
            "Apply a saved, source-bound review ledger; invalidate approval if any eligible document changes.",
        ),
        (
            "human_only",
            "Require an independent human ledger entry with exact evidence and four positive criteria.",
        ),
        (
            "hybrid",
            "Use a saved source review where available; otherwise use staged LLM review.",
        ),
    ]:
        add(
            "business_review",
            name,
            procedure,
            ["llm_peers", "ranking"],
            "All four criteria must pass. This custom gate is not validated by the cited papers; automated decisions remain reviewable.",
        )
    add(
        "business_review",
        "llm_rag",
        "Retrieve TF-IDF evidence sentences, retain full-company profiles, and require the all-evidence staged gate before accepting a pair.",
        ["rag", "enterprise_rag"],
        "A retrieval-plus-generation adaptation, not a reproduction of jointly trained RAG. Evaluated on RRF candidates only; no claimed superiority.",
    )
    add(
        "adaptation",
        "fine_tuning",
        "Future supervised or LoRA adaptation on independently reviewed training pairs/events; evaluate on company-disjoint held-out labels.",
        ["lora", "selection"],
        "Not trained: no adequate independent training/evaluation labels. An API fine-tuned model can use the existing model-name configuration once available.",
    )
    from pipeline.config import FACTOR_SETS

    for name, fields in FACTOR_SETS.items():
        add(
            "factors",
            name,
            (
                "Preserve business retrieval order."
                if not fields
                else "Equal-weight mean absolute percentile distance on "
                + ", ".join(fields)
                + " among business-eligible peers."
            ),
            ["sard", "ipev", "selection"],
            "Private inputs must be explicitly supplied. Our factors differ from SARD; no optimal weights are claimed.",
        )
    for name, procedure in [
        (
            "rules",
            "Run the integrated 13-event-type team rules on eligible news, press and careers pages.",
        ),
        (
            "llm",
            "Extract article events with supported sentence IDs, status and duration; retain publication-date provenance.",
        ),
        (
            "hybrid",
            "Retain only article/type predictions on which rules and the LLM agree.",
        ),
    ]:
        add(
            "growth",
            name,
            procedure,
            ["team_growth", "qwen"],
            "Hybrid intersection is a conservative design choice. Events are not a validated growth forecast or valuation premium.",
        )
    for name, procedure in [
        ("provided", "Use only explicitly supplied EBITDA with source metadata."),
        (
            "net_income_bridge",
            "Add signed interest, tax, depreciation and amortization to net income.",
        ),
        (
            "four_quarters",
            "Sum four nonoverlapping discrete quarters after entity, basis, units and chronology checks.",
        ),
        (
            "fy_plus_ytd",
            "Compute fiscal year + current YTD - corresponding prior YTD, with aligned dates and definitions.",
        ),
        (
            "reviewed_adjustments",
            "Apply only source-backed, accepted adjustments; retain all rejected or pending items.",
        ),
    ]:
        add(
            "measurement",
            name,
            procedure,
            ["sec_ebitda", "ipev"],
            "Arithmetic and metadata checks do not establish maintainable earnings. No unavailable financial components are invented.",
        )
    for name, procedure, refs in [
        (
            "median",
            "Median of positive, business-eligible public-peer EV/EBITDA multiples.",
            ["ipev"],
        ),
        (
            "harmonic",
            "Number of valid peers divided by the sum of reciprocal multiples.",
            ["baker", "multiples"],
        ),
        ("geometric", "Exponential of the mean log positive multiple.", ["ipev"]),
        (
            "rank_weighted",
            "Arithmetic mean weighted by reciprocal selection rank.",
            ["rrf"],
        ),
    ]:
        add(
            "valuation",
            name,
            procedure,
            refs,
            "Minimum three valid peers. Rank weighting is a heuristic; citations do not validate these weights. Unaligned financial bases permit a development proxy only.",
        )
    for name, procedure, refs in [
        (
            "valuation_accuracy",
            "Coverage, percentage/log errors and all-target error-threshold success rates.",
            ["accuracy", "selection"],
        ),
        (
            "business_ranking",
            "Precision@k and nDCG against independently graded pooled candidates.",
            ["ndcg"],
        ),
        (
            "event_extraction",
            "Article/type precision, recall, F1, false positives and false negatives; borderline labels excluded.",
            ["team_growth"],
        ),
    ]:
        add(
            "evaluation",
            name,
            procedure,
            refs,
            "Missing labels remain missing; post-hoc development comparisons are not independent validation.",
        )
    return rows


def citation_text(keys):
    return "; ".join(
        "[" + REFERENCES[k]["title"] + "](" + REFERENCES[k]["url"] + ")" for k in keys
    )
