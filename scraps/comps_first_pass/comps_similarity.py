"""
SCRAPS: first matching pass, set aside on 2026-10-18 (the real matching method
is being designed separately). Kept runnable for reference; see scraps/README.md.

Find comparable companies from website text alone.

Ported from Riya's proof of concept (similarities/comps_similarity_PCTY.ipynb on
branch riya/wip), reading this repository's website scrape instead of her
scrape. Treat a company as if it were private, then rank the other companies
by how similar their website text is.

Two text sources, so they can be compared on the same checks:
  pages      the cleaned page text from website_scrape/, with the company's
             own name removed
  profiles   the fixed-format matching_summary built from verified Codex
             profile items (scraps/codex_profiles, final_tables/matching_inputs.csv)

Method (as in the notebook):
  1. split into sentences; drop leftover boilerplate and any sentence found on
     3+ companies' sites (shared templates, cookie text)
  2. represent each company three ways: TF-IDF (1-2 word phrases), LSA (SVD of
     TF-IDF) and, if sentence-transformers is installed, mean-pooled sentence
     embeddings over ~200-word chunks
  3. cosine similarity to the target per method; z-score each method's scores
     and average them into an ensemble
  4. explain each match with the TF-IDF terms that contribute most

Checks (validate):
  - peer_labels.csv: graded peers per target (2 = direct competitor,
    1 = adjacent), written BEFORE looking at results; NDCG@10/20 and
    recall@10/25 per method, against 200 random orderings
  - universe-wide: how often a company's top-5 neighbours share its SIC4 code,
    compared with chance (SIC is never used in the score)
  - agreement between methods and correlation with text length

SIC codes are read through project_data.normalize_sic_codes (BrightView is
0700). Financial fields are never read. Every run writes its inputs, settings
and results to outputs-local/scraps/comps_first_pass/<source>/.

Usage (from this folder):
  python comps_similarity.py --source pages --target PCTY
  python comps_similarity.py --source pages --validate
  python comps_similarity.py --source profiles --validate     # after a full Codex run
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.preprocessing import normalize

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "website_scrape"))
sys.path.insert(0, str(REPO / "scraps" / "codex_profiles"))
from fetch_and_clean import find_input, load_companies  # noqa: E402  (also adds src/)
from project_data import OUTPUTS_LOCAL  # noqa: E402
from scrape_websites import DEFAULT_OUT as SCRAPE_OUT, output_paths  # noqa: E402
from step2_extract_profiles import DEFAULT_OUT as CODEX_OUT  # noqa: E402
from step2_extract_profiles import build_prompt, mask, name_variants  # noqa: E402
from step2_extract_profiles import output_paths as codex_paths  # noqa: E402

OUT_ROOT = OUTPUTS_LOCAL / "scraps" / "comps_first_pass"
PEER_LABELS = Path(__file__).with_name("peer_labels.csv")

TOP_K = 25                   # size of a reported comps list
MIN_WORDS = {"pages": 100, "profiles": 20}   # minimum cleaned words to be matchable
LSA_DIMS = 150
EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
CHUNK_WORDS = 200
SHARED_SENTENCE_SITES = 3    # a sentence on this many sites is a template
RANDOM_ORDERINGS = 200
SEED = 0

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\s*\|\s*|\s{2,}|\n+")
# Leftover site text. Word boundaries throughout (the notebook's "quarter"
# matched "headquarters"); public-company language is already removed by the
# scrape's filters, so "investor" and "stock" are not here (they describe the
# business of asset managers and brokers).
BOILERPLATE = re.compile(
    r"\b(?:cookies?|privacy (?:policy|notice|statement)|enable javascript|opens in a new tab"
    r"|all rights reserved|copyright|terms of (?:use|service)|subscribe|newsletter|sign up"
    r"|log ?in|click (?:here|on)|learn more|read more|contact us|webcast|press release)\b",
    re.I,
)
# Generic words that say nothing about what a company does. The marketing
# words in the second group were partly picked while reading PCTY results
# (notebook known issue #3): keep them frozen and validate on new targets.
EXTRA_STOP = {
    "company", "companies", "inc", "llc", "solutions", "solution", "services", "service", "new",
    "help", "helps", "world", "leading", "leader", "people", "team", "work", "today", "year",
    "years", "way", "make", "including", "provide", "provides", "providing", "us", "our", "we",
    "s", "multiple",
    "smarter", "stronger", "seamless", "seamlessly", "simplify", "simplified", "simple", "save",
    "excel", "strive", "best", "innovation", "innovative", "step", "need", "needs", "right",
    "real", "depend", "steer", "future", "together", "forward", "trusted", "success", "journey",
    "proud", "excellence",
    # words the profile template itself repeats for every company
    "stated", "website", "products", "customers", "markets", "channels", "streams", "role",
    "operating", "end", "sales", "revenue", "types",
}


# ---------------------------------------------------------------- inputs

def company_table() -> pd.DataFrame:
    """Identifiers and SIC codes only (no financial columns)."""
    return load_companies(find_input(None))[
        ["IQ_COMPANY_ID", "target_company_name", "target_ciq_ticker", "target_ciq_website",
         "target_sic4_code", "target_primary_sic_industry"]]


def page_texts(scrape_out: Path = SCRAPE_OUT) -> pd.DataFrame:
    """The scraped page text, with the company's name removed."""
    rows = []
    for path in sorted(output_paths(scrape_out).page_text.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        text = "\n".join(build_prompt(rec)[1].values()) if rec["pages"] else ""
        text, _ = mask(text, name_variants(rec["company_name"], rec["website"]), [])
        rows.append({"IQ_COMPANY_ID": rec["IQ_COMPANY_ID"], "status": rec["status"],
                     "method": rec["method"], "raw_text": text})
    return pd.DataFrame(rows)


def profile_texts(codex_out: Path = CODEX_OUT) -> pd.DataFrame:
    """matching_summary from the verified Codex profiles."""
    path = codex_paths(codex_out).tables / "matching_inputs.csv"
    t = pd.read_csv(path, dtype=str).fillna("")
    status = np.where(t["llm_status"] != "ok", "profile: " + t["llm_status"],
                      np.where(t["evidence_quality"] == "insufficient", "insufficient evidence", "ok"))
    return pd.DataFrame({"IQ_COMPANY_ID": t["IQ_COMPANY_ID"], "status": status,
                         "method": "profile", "raw_text": t["matching_summary"]})


def to_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text.replace("the Company", " "))
            if len(s.split()) >= 4]


def build_universe(texts: pd.DataFrame, companies: pd.DataFrame, source: str
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(matchable companies with cleaned text, excluded companies with a reason)."""
    meta = companies.merge(texts, on="IQ_COMPANY_ID", how="left")
    meta["status"] = meta["status"].fillna("not collected")
    meta["raw_text"] = meta["raw_text"].fillna("")
    meta["sents"] = meta["raw_text"].map(to_sentences)
    doc_freq = collections.Counter(s.lower() for ss in meta["sents"] for s in set(ss))
    # profile summaries share template sentences by design; only page text has site templates
    shared = (lambda s: doc_freq[s.lower()] >= SHARED_SENTENCE_SITES) if source == "pages" \
        else (lambda s: False)
    meta["clean_sents"] = meta["sents"].map(
        lambda ss: [s for s in ss if not BOILERPLATE.search(s) and not shared(s)])
    meta["clean_text"] = meta["clean_sents"].map(" ".join)
    meta["clean_words"] = meta["clean_text"].str.split().str.len()

    def reason(r):
        if r.status not in ("ok", "thin_content"):
            return f"status: {r.status}"
        if r.clean_words < MIN_WORDS[source]:
            return f"too little text after cleaning ({r.clean_words} words)"
        return ""
    meta["excluded_because"] = meta.apply(reason, axis=1)
    universe = meta[meta.excluded_because == ""].reset_index(drop=True)
    excluded = meta[meta.excluded_because != ""][
        ["IQ_COMPANY_ID", "target_ciq_ticker", "target_company_name", "excluded_because"]]
    return universe, excluded


# ---------------------------------------------------------------- representations

class Model:
    """TF-IDF, LSA and (optionally) embedding vectors for one universe."""

    def __init__(self, universe: pd.DataFrame, embed: bool, cache_dir: Path,
                 weights: dict[str, float] | None = None):
        self.U = universe
        self.tfidf = TfidfVectorizer(
            stop_words=list(ENGLISH_STOP_WORDS | EXTRA_STOP), ngram_range=(1, 2),
            min_df=2, max_df=0.4, sublinear_tf=True,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+(?:-[a-zA-Z]+)*\b")
        self.X_tfidf = self.tfidf.fit_transform(universe["clean_text"])   # rows L2-normalised
        self.vocab = np.array(self.tfidf.get_feature_names_out())
        dims = min(LSA_DIMS, self.X_tfidf.shape[0] - 1, self.X_tfidf.shape[1] - 1)
        svd = TruncatedSVD(n_components=dims, random_state=SEED)
        self.X_lsa = normalize(svd.fit_transform(self.X_tfidf))
        self.reps = {"tfidf": self.X_tfidf, "lsa": self.X_lsa}
        if embed:
            self.reps["embed"] = embed_texts(universe["clean_text"].tolist(), cache_dir)
        self.weights = weights or {m: 1.0 for m in self.reps}
        self.index = {t: i for i, t in enumerate(universe["target_ciq_ticker"])}

    def similarities(self, idx: int) -> pd.DataFrame:
        """Cosine similarity of every company to company idx, per method, plus
        the ensemble (weighted mean of z-scores; self excluded from the stats)."""
        sims = {}
        for name, M in self.reps.items():
            s = M @ M[idx].T
            sims[name] = np.asarray(s.todense()).ravel() if hasattr(s, "todense") else np.ravel(s)
        S = pd.DataFrame(sims)
        others = np.arange(len(S)) != idx
        z = {m: (S[m] - S[m][others].mean()) / S[m][others].std() for m in self.reps}
        total = sum(self.weights[m] for m in self.reps)
        S["ensemble"] = sum(self.weights[m] * z[m] for m in self.reps) / total
        return S

    def ranking(self, idx: int, method: str = "ensemble") -> list[str]:
        S = self.similarities(idx)
        return [self.U.target_ciq_ticker[i] for i in S[method].sort_values(ascending=False).index
                if i != idx]

    def shared_terms(self, i: int, j: int, n: int = 6) -> str:
        """Terms contributing most to the TF-IDF similarity of i and j."""
        contrib = self.X_tfidf[i].multiply(self.X_tfidf[j]).toarray().ravel()
        return ", ".join(self.vocab[k] for k in contrib.argsort()[::-1][:n] if contrib[k] > 0)

    def find_comps(self, ticker: str, k: int = TOP_K) -> pd.DataFrame:
        idx = self.index[ticker]
        S = self.similarities(idx)
        order = [i for i in S["ensemble"].sort_values(ascending=False).index if i != idx][:k]
        U = self.U
        out = pd.DataFrame({
            "rank": range(1, len(order) + 1),
            "ticker": U.target_ciq_ticker[order].values,
            "company": U.target_company_name[order].values,
            "sic4": U.target_sic4_code[order].values,
            "sic_industry": U.target_primary_sic_industry[order].values,
            "text_start": U.clean_text[order].str.slice(0, 300).values,
        })
        for m in S.columns:
            out[f"score_{m}"] = S.loc[order, m].round(3).values
            out[f"rank_{m}"] = S[m].drop(idx).rank(ascending=False).loc[order].astype(int).values
        out["same_sic4_as_target"] = out["sic4"].values == U.target_sic4_code[idx]
        out["why_similar"] = [self.shared_terms(idx, j) for j in order]
        return out


def embed_texts(texts: list[str], cache_dir: Path) -> np.ndarray:
    """Mean-pooled, L2-normalised sentence embeddings over ~200-word chunks.
    Cached under a name that includes the model and a hash of the texts, so a
    change to either never reuses stale vectors (notebook known issue #2)."""
    digest = hashlib.sha256("\x00".join(texts).encode("utf-8")).hexdigest()[:16]
    cache = cache_dir / f"embed_{EMBED_MODEL.split('/')[-1]}_{CHUNK_WORDS}w_{digest}.npy"
    if cache.exists():
        return np.load(cache)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBED_MODEL)
    vectors = []
    for t in texts:
        w = t.split()
        chunks = [" ".join(w[i:i + CHUNK_WORDS]) for i in range(0, len(w), CHUNK_WORDS)] or [""]
        v = model.encode(chunks, normalize_embeddings=True).mean(axis=0)
        vectors.append(v / np.linalg.norm(v))
    E = np.vstack(vectors)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(cache, E)
    return E


def embeddings_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------- checks

def ndcg_at_k(order: list[str], labels: dict[str, int], k: int) -> float:
    gains = [labels.get(t, 0) for t in order[:k]]
    dcg = sum((2 ** g - 1) / np.log2(r + 2) for r, g in enumerate(gains))
    ideal = sorted(labels.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / np.log2(r + 2) for r, g in enumerate(ideal))
    return dcg / idcg if idcg else float("nan")


def recall_at_k(order: list[str], labels: dict[str, int], k: int) -> float:
    return len(set(order[:k]) & set(labels)) / len(labels)


def metrics(order: list[str], labels: dict[str, int]) -> dict[str, float]:
    return {"NDCG@10": ndcg_at_k(order, labels, 10), "NDCG@20": ndcg_at_k(order, labels, 20),
            "Recall@10": recall_at_k(order, labels, 10), "Recall@25": recall_at_k(order, labels, 25)}


def load_peer_labels(path: Path = PEER_LABELS) -> dict[str, dict[str, int]]:
    t = pd.read_csv(path, dtype=str, comment="#")
    return {target: dict(zip(g.peer, g.grade.astype(int))) for target, g in t.groupby("target")}


def peer_validation(model: Model, labels: dict[str, dict[str, int]]) -> pd.DataFrame:
    """Per target and method: NDCG / recall against the peer labels, and the
    mean over random orderings. Labeled peers outside the universe count as misses."""
    rng = np.random.default_rng(SEED)
    rows = []
    for target, peers in labels.items():
        if target not in model.index:
            rows.append({"target": target, "method": "(target not matchable)"})
            continue
        idx = model.index[target]
        S = model.similarities(idx)
        for method in S.columns:
            order = [model.U.target_ciq_ticker[i] for i in S[method].sort_values(ascending=False).index
                     if i != idx]
            rows.append({"target": target, "method": method, **metrics(order, peers)})
        others = [t for t in model.U.target_ciq_ticker if t != target]
        random_runs = pd.DataFrame([metrics(list(rng.permutation(others)), peers)
                                    for _ in range(RANDOM_ORDERINGS)])
        rows.append({"target": target, "method": "random", **random_runs.mean().to_dict()})
        rows[-1]["peers_not_matchable"] = ", ".join(sorted(set(peers) - set(model.index)))
    return pd.DataFrame(rows)


def sic_check(model: Model, k: int = 5) -> pd.DataFrame:
    """Share of each company's top-k neighbours with the same SIC4, against chance."""
    sic = model.U["target_sic4_code"].values
    chance = np.mean([(sic == s).sum() - 1 for s in sic]) / (len(sic) - 1)
    rows = []
    for name, M in model.reps.items():
        S = M @ M.T
        S = S.toarray() if hasattr(S, "toarray") else np.array(S)
        np.fill_diagonal(S, -np.inf)
        top = np.argsort(-S, axis=1)[:, :k]
        rate = (sic[top] == sic[:, None]).mean()
        rows.append({"method": name, f"same_sic4_at_{k}": rate, "chance": chance,
                     "lift": rate / chance})
    return pd.DataFrame(rows)


def target_diagnostics(model: Model, ticker: str) -> dict:
    """Agreement between methods' top-20 lists, and how much text length
    alone drives similarity to the target (Spearman)."""
    idx = model.index[ticker]
    S = model.similarities(idx).drop(idx)
    tops = {m: set(S[m].nlargest(20).index) for m in S.columns}
    lengths = model.U["clean_words"].drop(idx)
    return {
        "top20_overlap": {f"{a} vs {b}": len(tops[a] & tops[b]) / 20
                          for a in tops for b in tops if a < b},
        "spearman_with_length": {m: round(S[m].corr(lengths, method="spearman"), 3)
                                 for m in S.columns},
    }


# ---------------------------------------------------------------- run

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--source", choices=["pages", "profiles"], default="pages")
    p.add_argument("--target", nargs="*", default=[], help="tickers to find comps for")
    p.add_argument("--validate", action="store_true",
                   help="score against peer_labels.csv and the SIC4 check")
    p.add_argument("--no-embed", action="store_true", help="TF-IDF and LSA only")
    p.add_argument("--scrape-out", default=str(SCRAPE_OUT))
    p.add_argument("--codex-out", default=str(CODEX_OUT))
    args = p.parse_args()

    out_dir = OUT_ROOT / args.source
    out_dir.mkdir(parents=True, exist_ok=True)
    texts = (page_texts(Path(args.scrape_out)) if args.source == "pages"
             else profile_texts(Path(args.codex_out)))
    universe, excluded = build_universe(texts, company_table(), args.source)
    excluded.to_csv(out_dir / "excluded_companies.csv", index=False)
    universe[["IQ_COMPANY_ID", "target_ciq_ticker", "status", "method", "clean_words",
              "clean_text"]].to_csv(out_dir / "universe_text.csv", index=False)
    print(f"{args.source}: {len(universe)} matchable companies, {len(excluded)} excluded "
          f"(reasons in excluded_companies.csv)")

    embed = not args.no_embed and embeddings_available()
    if not args.no_embed and not embed:
        print("sentence-transformers isn't installed; using TF-IDF and LSA only.")
    model = Model(universe, embed, OUT_ROOT / "cache")

    info = {"run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": args.source, "matchable": len(universe), "excluded": len(excluded),
            "methods": list(model.reps), "weights": model.weights,
            "embed_model": EMBED_MODEL if embed else None, "lsa_dims": model.X_lsa.shape[1],
            "tfidf_terms": model.X_tfidf.shape[1], "targets": {}}
    for ticker in args.target:
        ticker = ticker.upper()
        if ticker not in model.index:
            print(f"{ticker}: not matchable ({'excluded' if ticker in set(excluded.target_ciq_ticker) else 'not in list'})")
            continue
        comps = model.find_comps(ticker)
        comps.to_csv(out_dir / f"comps_{ticker}.csv", index=False)
        info["targets"][ticker] = target_diagnostics(model, ticker)
        print(f"\nTop comps for {ticker}:")
        print(comps[["rank", "ticker", "company", "sic4", "score_ensemble", "why_similar"]]
              .head(10).to_string(index=False))
    if args.validate:
        val = peer_validation(model, load_peer_labels())
        val.to_csv(out_dir / "peer_validation.csv", index=False)
        sic = sic_check(model)
        sic.to_csv(out_dir / "sic_check.csv", index=False)
        print("\nPeer labels (peer_labels.csv):")
        print(val.round(3).to_string(index=False))
        print("\nSame-SIC4 share of top-5 neighbours, all companies:")
        print(sic.round(3).to_string(index=False))
    (out_dir / "run_info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    main()
