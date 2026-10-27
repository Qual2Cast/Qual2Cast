"""Sectors (sectors.py), sector-specific facets (sector_facets.py) and the
facet add/drop and sub-model evaluation (facet_eval.py)."""

import numpy as np
import pandas as pd
import pytest

import facet_eval as fe
import sector_facets as sf
import sectors as sc


# ---------------------------------------------------------------- sectors

def test_every_ff49_industry_is_in_exactly_one_group():
    shorts = set(sc.ff49_table()["ff49_short"]) | {sc.OTHER}
    grouped = [ff for members in sc.SECTOR_GROUPS.values() for ff in members]
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == shorts


@pytest.mark.parametrize("sic,ff", [("3585", "Mach"), ("7372", "Softw"), ("0700", "Agric"),
                                    ("6411", "Insur"), ("8062", "Hlth"), ("5812", "Meals"), ("9999", "Other")])
def test_ff49_of(sic, ff):
    assert sc.ff49_of(sic) == ff


def test_missing_sic_is_other():
    assert sc.ff49_of(None) == sc.OTHER and sc.ff49_of("") == sc.OTHER


def test_sector_table_and_similarity():
    info = pd.DataFrame({"target_sic4_code": ["3585", "3560", "2821", "7372"]}, index=["A", "B", "C", "D"])
    t = sc.sector_table(info)
    assert list(t["ff49"]) == ["Mach", "Mach", "Chems", "Softw"]
    assert list(t["sector"]) == ["manufacturing"] * 3 + ["software"]
    S = sc.sector_similarity(t, ["A", "B", "C", "D"])
    assert S[0, 1] == 1.0 and S[0, 2] == 0.5 and S[0, 3] == 0.0 and S[3, 3] == 1.0


def test_sector_groups_on_the_company_list():
    from project_data import snapshot_path
    info = pd.read_csv(snapshot_path(), dtype=str)
    t = sc.sector_table(info)
    assert t["sector"].notna().all()
    assert (t["sector"] == "other").mean() < 0.05


# ---------------------------------------------------------------- sector facets

def test_every_group_has_facets_defined():
    assert set(sf.SECTOR_FACETS) == set(sc.SECTOR_GROUPS)
    for group, fs in sf.SECTOR_FACETS.items():
        names = [f.name for f in fs]
        assert len(names) == len(set(names)), group
        assert all(f.categories for f in fs), group     # all category facets: compared value for value


def test_prompt_has_no_provenance_notes_and_lists_categories():
    p = sf.build_prompt({"company_name": "AAON, Inc.", "website": "www.aaon.com", "sector": "manufacturing"})
    assert "Barbara" not in p and "(ours" not in p
    assert "make-to-order" in p and "sub_sector" in p


def test_schema_matches_the_sector():
    s = sf.answer_schema("software")
    assert "deployment_model" in s["properties"] and "manufacturing_type" not in s["properties"]
    assert s["properties"]["sub_sector"]["required"] == ["status", "value", "cites"]


def test_evidence_text_groups_lines_by_source():
    t = sf.evidence_text({"P1.1": "a", "P1.2": "b", "S2.1": "c"})
    assert t.count("<source") == 2 and '<source id="P1">' in t and "[S2.1] c" in t


def test_check_answer_keeps_valid_categories_and_flags_problems():
    labels = {"P1.1", "P1.2"}
    raw = {"knows_company": True, "notes": "",
           "sub_sector": {"status": "stated", "value": "commercial HVAC equipment", "cites": ["[P1.1]"]},
           "manufacturing_type": {"status": "stated", "categories": ["discrete", "assembly", "made up"],
                                  "detail": "", "cites": ["P1.2", "X9.9"]},
           "production_model": {"status": "stated", "categories": ["make-to-order", "both"], "detail": "x",
                                "cites": ["P1.1"]},
           "product_complexity": {"status": "stated", "categories": [], "detail": "", "cites": []},
           "production_role": {"status": "stated", "categories": ["final manufacturer / OEM"],
                               "detail": "sells $40 million a year", "cites": []},
           "end_market_exposure": {"status": "unknown", "categories": ["industrial"], "detail": "x", "cites": ["P1.1"]}}
    out, issues = sf.check_answer(raw, "manufacturing", labels)
    assert out["sub_sector"]["source"] == "evidence" and out["sub_sector"]["cites"] == ["P1.1"]
    assert out["manufacturing_type"]["categories"] == ["discrete", "assembly"]
    assert out["manufacturing_type"]["cites"] == ["P1.2"] and "unknown_cite:manufacturing_type" in issues
    assert out["production_model"]["categories"] == ["make-to-order"]
    assert "several_categories:production_model" in issues
    assert out["product_complexity"]["status"] == "unknown" and "no_category:product_complexity" in issues
    assert out["production_role"]["source"] == "model knowledge" and "from_memory:production_role" in issues
    assert "figure_in_value:production_role" in issues
    assert out["end_market_exposure"] == {"status": "unknown", "cites": [], "source": "", "categories": [], "detail": ""}
    row = sf.table_row(out)
    assert row["manufacturing_type_categories"] == "discrete|assembly"
    assert row["sub_sector"] == "commercial HVAC equipment"
    assert row["production_role_source"] == "model knowledge"


def test_unknown_company_keeps_only_cited_facets():
    raw = {"knows_company": False, "notes": "",
           "sub_sector": {"status": "stated", "value": "guess", "cites": []},
           "software_category": {"status": "stated", "categories": ["HR and payroll"], "detail": "",
                                 "cites": ["P1.1"]}}
    out, issues = sf.check_answer(raw, "software", {"P1.1"})
    assert out["sub_sector"]["status"] == "unknown" and "unsupported:sub_sector" in issues
    assert "company_not_known" in issues
    assert out["software_category"]["status"] == "stated" and out["software_category"]["source"] == "evidence"


# ---------------------------------------------------------------- evaluation

def test_combine_skips_missing_facets():
    A = np.array([[1, 0.2], [0.2, 1]])
    B = np.array([[1, np.nan], [np.nan, 1]])
    S = fe.combine({"a": A, "b": B}, {"a": 1, "b": 3})
    assert S[0, 1] == pytest.approx(0.2)        # b unknown for the pair: a alone
    assert S[0, 0] == pytest.approx(1.0)


def test_category_similarity_only_within_a_group():
    cats = pd.Series(["a|b", "a", "a", None])
    group = pd.Series(["g1", "g1", "g2", "g1"])
    M = fe.category_similarity(cats, group)
    assert M[0, 1] == pytest.approx(0.5)
    assert np.isnan(M[0, 2]) and np.isnan(M[0, 3])


def test_restrict_to_sector_needs_a_big_enough_pool():
    ids = ["t", "s1", "s2", "x1", "x2"]
    sectors = pd.DataFrame({"sector": ["g", "g", "g", "h", "h"]}, index=ids)
    S = np.ones((5, 5))
    R = fe.restrict_to_sector(S, ids, sectors, ids, min_pool=2)
    assert np.isnan(R[0, 3]) and R[0, 1] == 1
    R = fe.restrict_to_sector(S, ids, sectors, ids, min_pool=3)    # only two others in g: whole pool
    assert R[0, 3] == 1


def test_rank_metrics():
    ranking = pd.DataFrame({"target": "t", "comp": ["a", "b", "c", "d"], "rank": [1, 2, 3, 4]})
    labels = pd.DataFrame({"target": "t", "comp": ["a", "c", "d", "z"], "gain": [1.0, 0.0, 0.5, 1.0]})
    m = fe.rank_metrics(ranking, labels, k=2)
    # pairs (better ranked above worse): a>c ok, a>d ok, d>c wrong, z(unranked, last)>c wrong, z>d wrong
    assert m["pairwise accuracy"] == pytest.approx(2 / 5)
    assert m["recall@2 of best comps"] == pytest.approx(0.5)     # a in top 2, z not
    assert m["MRR of best comps"] == pytest.approx(1.0)
    assert m["top-2 label mean"] == pytest.approx(1.0) and m["top-2 labeled share"] == pytest.approx(0.5)


def test_load_labels_scales_rubric_scores(tmp_path):
    p = tmp_path / "gold.csv"
    pd.DataFrame({"Target_Ticker": ["PCTY", "PCTY", "XXX"], "Comp_Ticker": ["PAYC", "ADP", "PAYC"],
                  "Score": [2, 1, 0]}).to_csv(p, index=False)
    labels = fe.load_labels(p, {"PCTY": "IQ1", "PAYC": "IQ2", "ADP": "IQ3"})
    assert list(labels["gain"]) == [1.0, 0.5]
    kept, dropped = fe.training_only(labels, {"IQ1", "IQ2"})
    assert len(kept) == 1 and dropped == 1


def test_variants_and_evaluate_end_to_end():
    rng = np.random.default_rng(0)
    ids = [f"c{i}" for i in range(12)]
    sectors = pd.DataFrame({"sector": ["g"] * 6 + ["h"] * 6, "ff49": ["A"] * 3 + ["B"] * 3 + ["C"] * 6}, index=ids)
    general = {}
    for name in ["offering_description", "end_markets"]:
        M = rng.uniform(0, 1, (12, 12))
        general[name] = (M + M.T) / 2
    extra = {"sector": sc.sector_similarity(sectors, ids)}
    defs = fe.variants(general, extra)
    assert fe.GENERIC in defs and "generic + sector (FF49)" in defs
    assert any(k.startswith("generic minus") for k in defs)
    # labels: same-FF49 comps are the good ones, so adding sector must not hurt
    labels = pd.DataFrame([{"target": "c0", "comp": c, "gain": 1.0 if c in ("c1", "c2") else 0.0}
                           for c in ids[1:]])
    table, tops = fe.evaluate(defs, ids, ids, sectors, {"gold": labels}, k=3)
    acc = table.set_index("variant")["pairwise accuracy"]
    assert acc["generic + sector (FF49)"] >= acc[fe.GENERIC]
    assert set(tops) == set(defs)
