"""
Retrieval step (the "R" in RAG) for verifying facet fills.

verify_with_evidence.py's tiers P, PW and PWS put every evidence line of a
company in one prompt, so the model has to find the few lines that bear on
each facet among all of them. Tier R puts a retrieval step first: for each
facet it picks the k evidence lines most related to that facet, and the
prompt shows them grouped under the facet. Same evidence, same labels, same
rules afterwards; only the selection and grouping change, so R against PWS
measures what retrieval adds.

The query for a facet is its label and what it captures, the value the fill
wrote, and a short list of words that tend to settle that facet (FACET_TERMS).
The words for core offering, products and specialization include the deal
words (sold, divested, acquired, spin-off), since out-of-date businesses are
a main error the check has to catch.

Two retrievers:
- "bm25" (default): keyword ranking, no extra packages, the same result
  on every run.
- "hybrid": BM25 averaged with embedding similarity, using the model
  candidates.py already uses (all-mpnet-base-v2; needs sentence-transformers).

Ties go to the better-ranked source type (company site, press release, news,
reference, database), so the result doesn't depend on line order.

Look at what it retrieves, without any API call (evidence must be collected
first; evidence.py --no-search needs no key):

  python v0/verification/retrieve.py --facets outputs-local/comps/gold_labels --tickers ADUS
"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import facets as fc  # noqa: E402
import evidence as evm  # noqa: E402

RETRIEVAL_VERSION = "2026-10-27a"
DEFAULT_K = 8
RETRIEVERS = ("bm25", "hybrid")

CHANGE_TERMS = ("sold sale divested divestiture acquired acquisition spin-off spun exited discontinued "
                "merged completed transaction")
FACET_TERMS = {
    "offering_description": f"provides offers makes designs manufactures customers {CHANGE_TERMS}",
    "primary_products": f"products product line manufactures makes equipment systems brands {CHANGE_TERMS}",
    "primary_services": "services provides installation maintenance repair consulting support management",
    "customer_segment": "customers clients serves businesses consumers patients government agencies",
    "end_markets": "industries markets serves sectors applications customers",
    "revenue_model": "subscription fees contracts sales recurring licensing pricing pay per",
    "value_chain_position": "manufacturer distributor retailer supplier operator platform provider brand",
    "geography_served": "locations states countries international global offices headquarters "
                        "nationwide regions facilities operations united states",
    "company_size": "largest leading leader one of the largest locations sites network nationwide",
    "specialization": f"segments divisions businesses lines portfolio specialty focused {CHANGE_TERMS}",
    "distribution_channels": "sold through distributors dealers retailers online direct sales "
                             "resellers partners agents brokers stores e-commerce",
    "regulatory_exposure": "regulated regulation license licensed approval fda epa compliance "
                           "regulatory federal state rules certified medicare",
}

STOPWORDS = set("""a an and are as at be by for from has have in is it its of on or our that the
their this to was we were what which who will with you your all also any can more most other
such than these they into over about us""".split())

# BM25 parameters (the usual values).
K1, B = 1.5, 0.75


def tokens(text: str) -> list[str]:
    """Lower-case words without stopwords, with a light plural strip
    ("dealers" and "dealer" match). "US" and "U.S." become "united states";
    the pronoun "us" is a stopword."""
    text = re.sub(r"\bU\.?S\.?(?:A\.?)?(?![A-Za-z])", " united states ", text or "")
    out = []
    for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()):
        if w in STOPWORDS or len(w) < 2:
            continue
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def facet_query(f: fc.Facet, value: str) -> str:
    v = value if value and value not in ("unknown", "not_applicable") else ""
    return " ".join([f.label, f.captures, v, FACET_TERMS.get(f.name, "")])


def bm25_scores(query: str, docs: list[list[str]]) -> list[float]:
    n = len(docs)
    if not n:
        return []
    avg = sum(len(d) for d in docs) / n or 1.0
    df = Counter(t for d in docs for t in set(d))
    q = set(tokens(query))
    out = []
    for d in docs:
        tf = Counter(d)
        s = 0.0
        for t in q:
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * len(d) / avg))
        out.append(s)
    return out


def _scaled(xs: list[float]) -> list[float]:
    lo, hi = min(xs), max(xs)
    return [0.0] * len(xs) if hi <= lo else [(x - lo) / (hi - lo) for x in xs]


def retrieve(ev: evm.Evidence, values: dict[str, str], *, kinds: str = "PWS", k: int = DEFAULT_K,
             method: str = "bm25", embedder=None) -> dict[str, list[str]]:
    """Facet name -> the labels of the k evidence lines most related to it,
    best first. values: facet name -> the value the fill wrote. embedder(texts)
    -> unit vectors (hybrid only; default candidates.embed)."""
    if method not in RETRIEVERS:
        raise ValueError(f"method must be one of {RETRIEVERS}")
    labels = [lab for lab in ev.lines if lab[0] in kinds]
    if not labels:
        return {f.name: [] for f in fc.FACETS}
    docs = [tokens(ev.lines[lab]) for lab in labels]
    rank = [evm.SOURCE_RANK.get(ev.sources.get(lab.split(".")[0], {}).get("type", ""), 9) for lab in labels]
    queries = [facet_query(f, values.get(f.name, "")) for f in fc.FACETS]

    sims = None
    if method == "hybrid":
        if embedder is None:
            from candidates import embed as embedder
        import numpy as np
        lv = np.asarray(embedder([ev.lines[lab] for lab in labels]))
        qv = np.asarray(embedder(queries))
        sims = (qv @ lv.T).tolist()

    out = {}
    for i, (f, q) in enumerate(zip(fc.FACETS, queries)):
        s = bm25_scores(q, docs)
        if sims is not None:
            s = [(a + b) / 2 for a, b in zip(_scaled(s), _scaled(sims[i]))]
        order = sorted(range(len(labels)), key=lambda j: (-s[j], rank[j], j))
        out[f.name] = [labels[j] for j in order[:k] if s[j] > 0]
    return out


def evidence_block(ev: evm.Evidence, picked: dict[str, list[str]], values: dict[str, str]) -> str:
    """The prompt's evidence, grouped by facet; each line shows its source
    type (and date, for search results). A line picked for several facets is
    written out the first time only, then referred to by its label, so the
    prompt doesn't grow with the overlap."""
    parts, first = [], {}
    for f in fc.FACETS:
        fid = fc.FACET_ID[f.name]
        head = f"{fid} {f.name} ({f.label}): {values.get(f.name) or 'unknown'}"
        body = []
        for lab in picked.get(f.name, []):
            if lab in first:
                body.append(f"  [{lab}] (shown under {first[lab]})")
                continue
            first[lab] = fid
            src = ev.sources.get(lab.split(".")[0], {})
            tag = src.get("type", "") + (f', {src["date"]}' if src.get("date") else "")
            body.append(f"  [{lab}] ({tag}) {ev.lines[lab]}")
        parts.append("\n".join([head, *(body or ["  (no related evidence found)"])]))
    return "\n\n".join(parts)


def shown(picked: dict[str, list[str]]) -> list[str]:
    """Every label shown in the prompt, once."""
    return list(dict.fromkeys(lab for labs in picked.values() for lab in labs))


def main() -> None:
    import argparse
    import pandas as pd
    from verify_with_evidence import facet_values, load_evidence

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--facets", required=True, help="a fill output folder (has tables/facets.csv)")
    p.add_argument("--tickers", nargs="+", required=True)
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--retriever", choices=RETRIEVERS, default="bm25")
    args = p.parse_args()

    from universe import build_universe
    companies, _ = build_universe()
    table = pd.read_csv(Path(args.facets) / "tables" / "facets.csv", dtype=str).fillna("")
    table = table.merge(companies[["IQ_COMPANY_ID", "target_ciq_ticker"]], on="IQ_COMPANY_ID")
    table = table[table.target_ciq_ticker.str.upper().isin({t.upper() for t in args.tickers})]
    for _, row in table.iterrows():
        ev = load_evidence(row.IQ_COMPANY_ID)
        if ev is None:
            print(f"{row.target_ciq_ticker}: no evidence yet; run evidence.py first")
            continue
        values = facet_values(row)
        picked = retrieve(ev, values, k=args.k, method=args.retriever)
        print(f"===== {row.target_ciq_ticker}  ({len(ev.lines)} evidence lines, "
              f"{len(shown(picked))} shown)\n")
        print(evidence_block(ev, picked, values), "\n")


if __name__ == "__main__":
    main()
