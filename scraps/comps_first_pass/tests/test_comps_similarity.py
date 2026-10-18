"""
Tests for the comps model's checks and text handling (comps_similarity.py).

Run from scraps/comps_first_pass/:  python -m pytest tests -q
"""

import pandas as pd

import comps_similarity as cs


def test_ndcg_and_recall():
    labels = {"A": 2, "B": 1}
    assert cs.ndcg_at_k(["A", "B", "C"], labels, 10) == 1.0
    assert cs.ndcg_at_k(["C", "D", "E"], labels, 10) == 0.0
    assert 0 < cs.ndcg_at_k(["B", "A"], labels, 10) < 1           # adjacent above direct
    assert cs.recall_at_k(["C", "A"], labels, 1) == 0.0
    assert cs.recall_at_k(["C", "A"], labels, 2) == 0.5


def test_boilerplate_needs_whole_words():
    # the notebook's "quarter" rule dropped every "headquarters" sentence
    assert not cs.BOILERPLATE.search("Our headquarters team builds payroll software for employers.")
    assert not cs.BOILERPLATE.search("We protect customer data with privacy-preserving analytics.")
    assert cs.BOILERPLATE.search("Read our privacy policy and terms of use.")


def companies(n):
    return pd.DataFrame({
        "IQ_COMPANY_ID": [f"IQ{i}" for i in range(n)],
        "target_company_name": [f"Co {i}" for i in range(n)],
        "target_ciq_ticker": [f"T{i}" for i in range(n)],
        "target_ciq_website": [f"co{i}.com" for i in range(n)],
        "target_sic4_code": ["0700"] + ["7372"] * (n - 1),
        "target_primary_sic_industry": ["x"] * n,
    })


def test_universe_drops_shared_templates_and_gives_exclusion_reasons():
    template = "We use cookies to improve your browsing experience on this site."
    shared = "This exact sentence appears on several different company websites."
    def body(c):   # each company's own text
        return " ".join(f"Company {c} payroll software module {k} for employers." for k in range(30))
    texts = pd.DataFrame({
        "IQ_COMPANY_ID": ["IQ0", "IQ1", "IQ2", "IQ3"],
        "status": ["ok", "ok", "ok", "robots_disallowed"],
        "method": ["html"] * 4,
        "raw_text": [f"{body(c)} {template} {shared}" for c in "ABC"] + [""],
    })
    universe, excluded = cs.build_universe(texts, companies(5), "pages")
    assert len(universe) == 3
    assert not universe["clean_text"].str.contains("cookies|exact sentence").any()
    reasons = dict(zip(excluded.IQ_COMPANY_ID, excluded.excluded_because))
    assert reasons == {"IQ3": "status: robots_disallowed", "IQ4": "status: not collected"}
    assert universe["target_sic4_code"].iloc[0] == "0700"           # zero-padded SIC kept


def test_embedding_cache_name_depends_on_the_texts(tmp_path, monkeypatch):
    saved = []
    monkeypatch.setattr(cs.np, "save", lambda path, arr: saved.append(path.name))

    class Fake:
        def __init__(self, name):
            pass

        def encode(self, chunks, normalize_embeddings):
            return cs.np.ones((len(chunks), 3))

    import sentence_transformers
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", Fake)
    cs.embed_texts(["alpha beta"], tmp_path)
    cs.embed_texts(["alpha gamma"], tmp_path)
    assert len(set(saved)) == 2 and all("all-mpnet-base-v2" in s for s in saved)
