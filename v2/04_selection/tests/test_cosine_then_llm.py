"""Tests for the LLM good/bad step (cosine_then_llm.py). No model is called."""

import pandas as pd

import facets as fc
import cosine_then_llm as jc


def company_tables():
    info = pd.DataFrame({"target_company_name": ["Target Co", "Zeta Inc", "Alpha LLC"],
                         "target_ciq_website": ["t.com", "z.com", "a.com"],
                         "target_ciq_ticker": ["TGT", "ZET", "ALP"]}, index=["T", "Z", "A"])
    rows = {}
    for iq in info.index:
        r = {}
        for f in fc.FACETS:
            r[f.name], r[f"{f.name}_status"] = f"{iq} {f.name}", "filled"
        rows[iq] = r
    rows["Z"]["primary_products_status"] = "not_applicable"
    rows["A"]["end_markets_status"] = "unknown"
    return info, pd.DataFrame.from_dict(rows, orient="index")


def test_prompt_lists_candidates_alphabetically_without_ranks_or_tickers():
    info, facets = company_tables()
    prompt, labels = jc.build_prompt("T", ["Z", "A"], info, facets)
    assert labels == {"C1": "A", "C2": "Z"}                    # Alpha before Zeta, whatever the input order
    assert prompt.index("C1: Alpha LLC") < prompt.index("C2: Zeta Inc")
    assert "Target: Target Co (t.com)" in prompt
    assert "TGT" not in prompt and "ZET" not in prompt
    assert "similarity" not in prompt.lower() and "rank" not in prompt.lower()
    assert "- Primary products: none" in prompt               # Zeta: not applicable
    assert "- End markets: unknown" in prompt                 # Alpha: unknown


def test_check_answer_scores_and_issues():
    labels = {"C1": "A", "C2": "Z", "C3": "Q"}
    raw = {"comps": [{"label": "C1", "good": True, "reason": "same business"},
                     {"label": "C1", "good": False, "reason": "again"},
                     {"label": "C2", "good": False, "reason": "different"},
                     {"label": "C9", "good": True, "reason": "?"}]}
    rows, issues = jc.check_answer(raw, labels)
    assert [(r["comp"], r["score"]) for r in rows] == [("A", 1), ("Z", 0), ("Q", None)]
    assert set(issues) == {"duplicate_label:C1", "unknown_label:C9", "not_answered:C3"}


def test_schema_limits_labels():
    schema = jc.answer_schema(["C1", "C2"])
    item = schema["properties"]["comps"]["items"]
    assert item["properties"]["label"]["enum"] == ["C1", "C2"]
    assert item["properties"]["good"]["type"] == "boolean"


def test_fingerprint_changes_with_model_and_prompt():
    assert jc.fingerprint("p", "m1") != jc.fingerprint("p", "m2")
    assert jc.fingerprint("p", "m1") != jc.fingerprint("q", "m1")


def test_prompt_versions_differ_only_in_company_size():
    # see v2/04_selection/PROMPT_VERSIONS.md: the saved version lists all twelve facets, the current one leaves out F9
    info, facets = company_tables()
    new, _ = jc.build_prompt("T", ["Z", "A"], info, facets)
    saved, _ = jc.build_prompt("T", ["Z", "A"], info, facets, jc.SAVED_PROMPT_VERSION)
    assert jc.PROMPT_VERSION != jc.SAVED_PROMPT_VERSION
    assert "- Company size:" not in new and "- Company size:" in saved
    assert [l for l in saved.splitlines() if not l.startswith("- Company size:")] == new.splitlines()


def test_write_tables_refuses_to_empty_a_table_of_another_version(tmp_path):
    import json
    import pytest
    out = jc.output_paths(tmp_path)
    out.judgments.mkdir(parents=True)
    (out.judgments / "T.json").write_text(json.dumps({
        "target": "T", "llm_status": "ok", "prompt_version": jc.SAVED_PROMPT_VERSION, "model": "m", "comps": [],
        "issues": [], "candidates_run": "r", "judged_at": "t"}), encoding="utf-8")
    info, _ = company_tables()
    pairs = pd.DataFrame(columns=["target", "comp", "rank", "similarity", "z"])
    with pytest.raises(SystemExit, match="Pass --prompt-version"):
        jc.write_tables(out, pairs, info)                          # the default (current) version
    assert jc.write_tables(out, pairs, info, jc.SAVED_PROMPT_VERSION).exists()


def test_b3_flag_picks_the_baseline_lists_not_the_z_shortlist():
    import pytest
    pairs = pd.DataFrame({"target": "T", "comp": ["A", "B", "C"], "z": [2.5, 1.0, 2.1],
                          "selected": [True, True, False]})
    assert jc.pick_pairs(pairs, 2.0)["comp"].tolist() == ["A", "C"]                 # v0: z >= 2
    assert jc.pick_pairs(pairs, 2.0, "selected")["comp"].tolist() == ["A", "B"]     # --b3: the baseline list
    as_text = pairs.assign(selected=pairs["selected"].astype(str))                  # read back from CSV
    assert jc.pick_pairs(as_text, 2.0, "selected")["comp"].tolist() == ["A", "B"]
    with pytest.raises(SystemExit, match="method1_candidates"):
        jc.pick_pairs(pairs.drop(columns="selected"), 2.0, "selected")


# ---------------------------------------------------------------- 2026-11-28 versions: trait lines (data only)

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

TRAIT_LINE = re.compile(r"^- (Recurring revenue|Big-ticket sales): (yes|no|unknown)$")
# sha256 of the 2026-11-04a prompt for company_tables(), rendered by the code before the 11-28 versions were added
PROMPT_1104A_SHA256 = "65116b504b7ae54666732f80f75b7fb64e624703d3551ee7dc49581ff2f10607"
FINANCIAL_WORDS = ["ebitda", "ev/", "multiple", "valuation", "price", "revenue", "margin", "profit", "earnings",
                   "income", "cash", "debt", "market cap", "$", "%", "financial"]


def trait_table():
    # the reasons hold financial words on purpose: they must never reach the prompt
    return pd.DataFrame({"IQ_COMPANY_ID": ["T", "Z", "A"], "llm_status": ["ok", "ok", "error"],
                         "recurring_revenue": ["yes", "no", "yes"], "big_ticket": ["no", "unknown", "yes"],
                         "recurring_revenue_reason": ["EBITDA margin 20%"] * 3,
                         "big_ticket_reason": ["price $5m"] * 3})


def loaded_traits(tmp_path):
    path = tmp_path / "traits.csv"
    trait_table().to_csv(path, index=False)
    return jc.load_traits(path)


def without_trait_lines(prompt):
    return [line for line in prompt.splitlines() if not TRAIT_LINE.match(line)]


def test_1104a_prompt_is_byte_identical_to_before_the_trait_versions():
    info, facets = company_tables()
    prompt, _ = jc.build_prompt("T", ["Z", "A"], info, facets, "2026-11-04a")
    assert hashlib.sha256(prompt.encode("utf-8")).hexdigest() == PROMPT_1104A_SHA256
    assert jc.PROMPT_VERSION == "2026-11-04a"                       # the default is still the pinned version
    assert jc.build_prompt("T", ["Z", "A"], info, facets)[0] == prompt


def test_28a_adds_one_recurring_revenue_line_for_target_and_every_candidate(tmp_path):
    info, facets = company_tables()
    traits = loaded_traits(tmp_path)
    new, labels = jc.build_prompt("T", ["Z", "A"], info, facets, "2026-11-28a", traits)
    old, old_labels = jc.build_prompt("T", ["Z", "A"], info, facets, "2026-11-04a")
    assert labels == old_labels
    blocks = new.split("\n\n")
    target = next(b for b in blocks if b.startswith("Target: Target Co"))
    alpha = next(b for b in blocks if b.startswith("C1: Alpha LLC"))
    zeta = next(b for b in blocks if b.startswith("C2: Zeta Inc"))
    assert target.splitlines()[-1] == "- Recurring revenue: yes"
    assert zeta.splitlines()[-1] == "- Recurring revenue: no"
    assert alpha.splitlines()[-1] == "- Recurring revenue: unknown"          # its fill failed: shown as unknown
    assert sum(bool(TRAIT_LINE.match(line)) for line in new.splitlines()) == 3
    assert "Big-ticket" not in new
    assert without_trait_lines(new) == old.splitlines()                      # data only: nothing else changes
    assert jc.INSTRUCTIONS in new


def test_28b_and_28c_lines(tmp_path):
    info, facets = company_tables()
    traits = loaded_traits(tmp_path)
    old = jc.build_prompt("T", ["Z", "A"], info, facets, "2026-11-04a")[0]
    b, _ = jc.build_prompt("T", ["Z", "A"], info, facets, "2026-11-28b", traits)
    c, _ = jc.build_prompt("T", ["Z", "A"], info, facets, "2026-11-28c", traits)
    assert "- Big-ticket sales: no" in b and "Recurring revenue" not in b
    assert "- Big-ticket sales: unknown" in b                       # Zeta answered unknown
    target_c = next(x for x in c.split("\n\n") if x.startswith("Target:")).splitlines()
    assert target_c[-2:] == ["- Recurring revenue: yes", "- Big-ticket sales: no"]
    assert sum(bool(TRAIT_LINE.match(line)) for line in c.splitlines()) == 6
    assert without_trait_lines(b) == without_trait_lines(c) == old.splitlines()


def test_trait_versions_add_no_financial_words_beyond_the_trait_label(tmp_path):
    info, facets = company_tables()
    traits = loaded_traits(tmp_path)
    old = jc.build_prompt("T", ["Z", "A"], info, facets, "2026-11-04a")[0].lower()
    for version in ("2026-11-28a", "2026-11-28b", "2026-11-28c"):
        new = jc.build_prompt("T", ["Z", "A"], info, facets, version, traits)[0].lower()
        revenue_labels = 3 if "recurring_revenue" in jc.PROMPT_TRAITS[version] else 0
        for word in FINANCIAL_WORDS:
            extra = revenue_labels if word == "revenue" else 0        # the "Recurring revenue" label itself
            assert new.count(word) == old.count(word) + extra, (version, word)
        assert "ebitda margin" not in new and "$5m" not in new        # reasons are never shown


def test_trait_versions_need_the_trait_table():
    info, facets = company_tables()
    with pytest.raises(ValueError, match="trait table"):
        jc.build_prompt("T", ["Z", "A"], info, facets, "2026-11-28a")


def test_trait_labels_are_the_names_in_traits_py():
    import traits as tr
    doc = " ".join(tr.__doc__.lower().split())
    for name, label in jc.TRAIT_LABELS.items():
        if name in jc.ROUND_2_TRAITS:
            continue                                                  # round 2: test_round_2_labels_are_the_names_in_traits_py
        assert name in tr.TRAITS and label.lower() in doc


def test_1104a_rebuilds_a_saved_prompt_of_the_pinned_run():
    run = Path(jc.v2.path(jc.CUR["selection"]["judgments"])).parents[1]
    saved = run / "judgments" / "IQ100918.json"
    if not saved.exists():
        pytest.skip("pinned selector run not on disk")
    j = json.loads(saved.read_text(encoding="utf-8"))
    pairs, info, facets = jc.load_inputs(jc.CURRENT_B3, 2.0, "selected")
    comps = pairs.loc[pairs["target"] == "IQ100918", "comp"].tolist()
    prompt, labels = jc.build_prompt("IQ100918", comps, info, facets, "2026-11-04a")
    assert labels == j["labels"]
    assert prompt == (run / j["run_dir"].replace("\\", "/") / "prompt.txt").read_text(encoding="utf-8")


def test_judge_one_28a_with_a_mocked_model(tmp_path, monkeypatch):
    import cli_models
    info, facets = company_tables()
    traits = loaded_traits(tmp_path)
    seen = {}

    def fake_call_cli(prompt, run_dir, schema, backend, model=None, effort=None, timeout=600, instructions_len=0):
        seen["prompt"] = prompt
        labels = schema["properties"]["comps"]["items"]["properties"]["label"]["enum"]
        answer = {"comps": [{"label": lab, "good": lab == "C1", "reason": "r"} for lab in labels]}
        return {"llm_status": "ok", "text": json.dumps(answer), "usage": {}, "seconds": 0.1}

    monkeypatch.setattr(cli_models, "call_cli", fake_call_cli)
    out = jc.output_paths(tmp_path / "run")
    for d in (out.runs, out.judgments, out.logs):
        d.mkdir(parents=True)
    args = SimpleNamespace(prompt_version="2026-11-28a", backend="claude-cli", model="m", effort=None, refresh=False,
                           b3=True, z=2.0, candidates=tmp_path / "cands", traits_table=traits, traits_sha256="abc")
    assert jc.judge_one("T", ["Z", "A"], info, facets, out, args)["status"] == "ok"
    assert sum(bool(TRAIT_LINE.match(line)) for line in seen["prompt"].splitlines()) == 3
    j = json.loads((out.judgments / "T.json").read_text(encoding="utf-8"))
    assert j["prompt_version"] == "2026-11-28a" and j["traits_sha256"] == "abc"
    assert [(c["comp"], c["score"]) for c in j["comps"]] == [("A", 1), ("Z", 0)]
    assert jc.judge_one("T", ["Z", "A"], info, facets, out, args)["status"] == "current"   # a rerun resumes


def test_manifest_records_the_trait_table_and_its_sha256(tmp_path):
    path = tmp_path / "traits.csv"
    trait_table().to_csv(path, index=False)
    out = jc.output_paths(tmp_path / "run")
    out.runs.mkdir(parents=True)
    args = SimpleNamespace(prompt_version="2026-11-28a", model="m", backend="claude-cli", effort=None,
                           candidates=tmp_path / "cands", b3=True, z=2.0, traits=path,
                           traits_table=jc.load_traits(path), traits_sha256=jc.file_sha256(path), targets_file=None)
    groups = pd.Series({"T": ["Z", "A"]})
    m = json.loads(jc.write_manifest(out, args, groups).read_text(encoding="utf-8"))
    assert m["traits"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert m["traits"]["lines"] == ["Recurring revenue"] and m["n_pairs"] == 2
    jc.write_manifest(out, args, groups)                                # unchanged: kept as is
    assert not (out.runs.parent / "manifest_history").exists()
    args.model = "m2"                                                   # changed: the old one goes to history
    jc.write_manifest(out, args, groups)
    assert len(list((out.runs.parent / "manifest_history").glob("manifest_*.json"))) == 1


def test_read_target_ids(tmp_path):
    a = tmp_path / "ids.txt"
    a.write_text("# comment\nIQ2\nIQ1  # note\n\n", encoding="utf-8")
    b = tmp_path / "ids.csv"
    pd.DataFrame({"target_id": ["IQ2", "IQ1", "IQ1"], "comp_id": ["x", "y", "z"]}).to_csv(b, index=False)
    assert jc.read_target_ids(a) == jc.read_target_ids(b) == ["IQ1", "IQ2"]


# ---------------------------------------------------------------- 2026-11-28d to k: one more trait line each (data only)

# sha256 of each older prompt for company_tables() and trait_table(), rendered before 11-28d to k were added
GOLDEN_SHA256 = {
    "2026-10-25a": "4a19140b40a167ae8c40c6fdcf3e023aa457d54d1978595534db7aea91eb8a42",
    "2026-11-04a": PROMPT_1104A_SHA256,
    "2026-11-28a": "9b8fffd8c8693c7d594e83dd7faafc9ff9f3f6d898b702ba96c499d09ccc4874",
    "2026-11-28b": "a4b4d77eea40f1bf6d1e598bd57a855ae4900d4e5eb0b22ed298039dc79cf970",
    "2026-11-28c": "467cf10b608d4f8768582e41f80324d0003141d310aa0bb25194811851666b19",
}
ONE_TRAIT = {"2026-11-28d": ("cyclical_demand", "Cyclical demand"), "2026-11-28e": ("people_delivered", "People-delivered"),
             "2026-11-28f": ("large_customers", "Large customers"), "2026-11-28g": ("asset_heavy", "Asset-heavy"),
             "2026-11-28h": ("maintenance_led", "Maintenance-led"), "2026-11-28i": ("publicly_funded", "Publicly funded"),
             "2026-11-28j": ("serial_acquirer", "Serial acquirer"), "2026-11-28k": ("mission_critical", "Mission-critical")}
ANY_TRAIT_LINE = re.compile(r"^- (" + "|".join(re.escape(l) for l in jc.TRAIT_LABELS.values()) + r"): (yes|no|unknown)$")
ROUND_1_EXTRA = {"cyclical_demand": ["yes", "no", "no"], "people_delivered": ["no", "yes", "no"],
                 "large_customers": ["unknown", "yes", "no"], "asset_heavy": ["yes", "yes", "yes"]}
ROUND_2 = {"maintenance_led": ["no", "yes", "yes"], "publicly_funded": ["yes", "no", "no"],
           "serial_acquirer": ["unknown", "no", "yes"], "mission_critical": ["yes", "yes", "no"]}


def full_traits(tmp_path):
    """Round-1 table with all six traits (the 28a-c columns as in trait_table) and a round-2 table, joined."""
    r1 = trait_table().assign(**ROUND_1_EXTRA, **{f"{n}_reason": "EBITDA margin 20%" for n in ROUND_1_EXTRA})
    r2 = pd.DataFrame({"IQ_COMPANY_ID": ["T", "Z", "A"], "llm_status": ["ok", "error", "ok"], **ROUND_2,
                       **{f"{n}_reason": "price $5m" for n in ROUND_2}})
    p1, p2 = tmp_path / "traits.csv", tmp_path / "traits_r2.csv"
    r1.to_csv(p1, index=False)
    r2.to_csv(p2, index=False)
    return p1, p2, pd.concat([jc.load_traits(p1), jc.load_traits(p2)], axis=1)


def test_older_versions_render_byte_identically(tmp_path):
    info, facets = company_tables()
    small = loaded_traits(tmp_path)
    full = full_traits(tmp_path)[2]                                   # extra columns in the table change nothing
    for version, sha in GOLDEN_SHA256.items():
        for traits in (small, full):
            prompt = jc.build_prompt("T", ["Z", "A"], info, facets, version,
                                     traits if version in jc.PROMPT_TRAITS else None)[0]
            assert hashlib.sha256(prompt.encode("utf-8")).hexdigest() == sha, version


def test_28d_to_28k_add_one_trait_line_each(tmp_path):
    info, facets = company_tables()
    traits = full_traits(tmp_path)[2]
    old = jc.build_prompt("T", ["Z", "A"], info, facets, "2026-11-04a")[0]
    for version, (name, label) in ONE_TRAIT.items():
        assert jc.PROMPT_TRAITS[version] == (name,) and jc.TRAIT_LABELS[name] == label
        assert jc.PROMPT_EXCLUDES[version] == jc.PROMPT_EXCLUDES["2026-11-04a"]
        new, labels = jc.build_prompt("T", ["Z", "A"], info, facets, version, traits)
        assert labels == {"C1": "A", "C2": "Z"}
        lines = [l for l in new.splitlines() if ANY_TRAIT_LINE.match(l)]
        assert len(lines) == 3 and all(l.startswith(f"- {label}: ") for l in lines), version
        last = {b.split(" ")[0]: b.splitlines()[-1] for b in new.split("\n\n") if b.startswith(("Target:", "C1:", "C2:"))}
        values = (ROUND_2 if name in ROUND_2 else ROUND_1_EXTRA)[name]                     # rows T, Z, A
        failed = {"Z"} if name in ROUND_2 else {"A"}                                       # the row whose fill failed
        show = {iq: ("unknown" if iq in failed else v) for iq, v in zip("TZA", values)}
        assert last == {"Target:": f"- {label}: {show['T']}", "C1:": f"- {label}: {show['A']}",
                        "C2:": f"- {label}: {show['Z']}"}, version
        assert [l for l in new.splitlines() if not ANY_TRAIT_LINE.match(l)] == old.splitlines()   # data only
        low, old_low = new.lower(), old.lower()
        for word in FINANCIAL_WORDS:
            assert low.count(word) == old_low.count(word), (version, word)
        assert "ebitda margin" not in low and "$5m" not in low                         # reasons are never shown


def test_version_traits_split_the_two_tables():
    assert jc.version_traits("2026-11-04a") == ((), ())
    assert jc.version_traits("2026-11-28c") == (("recurring_revenue", "big_ticket"), ())
    assert jc.version_traits("2026-11-28g") == (("asset_heavy",), ())
    assert jc.version_traits("2026-11-28h") == ((), ("maintenance_led",))
    assert set(jc.ROUND_2_TRAITS) == {n for v in "hijk" for n in jc.PROMPT_TRAITS[f"2026-11-28{v}"]}


def test_round_2_labels_are_the_names_in_traits_py():
    import traits as tr
    assert list(jc.ROUND_2_TRAITS) == tr.ROUND_2_NAMES
    assert set(jc.TRAIT_LABELS) == set(tr.TRAITS) | set(tr.ROUND_2_NAMES)
    for name in tr.ROUND_2_NAMES:
        assert jc.TRAIT_LABELS[name].lower().replace("-", "_").replace(" ", "_") == name


def test_manifest_records_the_round_2_table(tmp_path):
    p1, p2, traits = full_traits(tmp_path)
    out = jc.output_paths(tmp_path / "run")
    out.runs.mkdir(parents=True)
    groups = pd.Series({"T": ["Z", "A"]})
    args = SimpleNamespace(prompt_version="2026-11-28h", model="m", backend="claude-cli", effort=None,
                           candidates=tmp_path / "cands", b3=True, z=2.0, traits=None, traits_r2=p2,
                           traits_table=traits, traits_sha256=None, traits_r2_sha256=jc.file_sha256(p2),
                           targets_file=None)
    m = json.loads(jc.write_manifest(out, args, groups).read_text(encoding="utf-8"))
    assert m["traits"] is None
    assert m["traits_r2"] == {"path": "traits_r2.csv", "sha256": hashlib.sha256(p2.read_bytes()).hexdigest(),
                              "lines": ["Maintenance-led"]}
    out2 = jc.output_paths(tmp_path / "run2")                          # a round-1 version: no traits_r2 key
    out2.runs.mkdir(parents=True)
    args.prompt_version, args.traits, args.traits_sha256, args.traits_r2_sha256 = "2026-11-28d", p1, "abc", None
    m = json.loads(jc.write_manifest(out2, args, groups).read_text(encoding="utf-8"))
    assert m["traits"]["lines"] == ["Cyclical demand"] and "traits_r2" not in m


def test_judge_one_28k_records_the_round_2_sha256(tmp_path, monkeypatch):
    import cli_models
    info, facets = company_tables()
    traits = full_traits(tmp_path)[2]

    def fake_call_cli(prompt, run_dir, schema, backend, model=None, effort=None, timeout=600, instructions_len=0):
        labels = schema["properties"]["comps"]["items"]["properties"]["label"]["enum"]
        return {"llm_status": "ok", "text": json.dumps({"comps": [{"label": l, "good": True, "reason": "r"}
                                                                  for l in labels]}), "usage": {}, "seconds": 0.1}

    monkeypatch.setattr(cli_models, "call_cli", fake_call_cli)
    out = jc.output_paths(tmp_path / "run")
    for d in (out.runs, out.judgments, out.logs):
        d.mkdir(parents=True)
    args = SimpleNamespace(prompt_version="2026-11-28k", backend="claude-cli", model="m", effort=None, refresh=False,
                           b3=True, z=2.0, candidates=tmp_path / "cands", traits_table=traits, traits_sha256=None,
                           traits_r2_sha256="def")
    assert jc.judge_one("T", ["Z", "A"], info, facets, out, args)["status"] == "ok"
    j = json.loads((out.judgments / "T.json").read_text(encoding="utf-8"))
    assert j["traits_r2_sha256"] == "def" and "traits_sha256" not in j


@pytest.mark.parametrize("version", ["2026-11-28a", "2026-11-28b"])
def test_saved_trait_prompts_of_the_real_runs_rebuild_byte_identically(version):
    run = jc.DEFAULT_OUT_ROOT / f"b3_selector_candidates_{version}_claude-cli_claude-sonnet-5-5"
    if not (run / "manifest.json").exists():
        pytest.skip("run not on disk")
    m = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if jc.file_sha256(jc.v2.ROOT / m["traits"]["path"]) != m["traits"]["sha256"]:
        pytest.skip("trait table changed since the run")
    pairs, info, facets = jc.load_inputs(jc.v2.ROOT / m["candidates"], 2.0, "selected")
    traits = jc.load_traits(jc.v2.ROOT / m["traits"]["path"])
    for target in m["targets"]["ids"][:5]:
        j = json.loads((run / "judgments" / f"{target}.json").read_text(encoding="utf-8"))
        comps = pairs.loc[pairs["target"] == target, "comp"].tolist()
        prompt, labels = jc.build_prompt(target, comps, info, facets, version, traits)
        assert labels == j["labels"]
        assert prompt == (run / j["run_dir"].replace("\\", "/") / "prompt.txt").read_text(encoding="utf-8")
