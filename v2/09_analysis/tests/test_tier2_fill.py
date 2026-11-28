"""tier2_fill.py (EXPERIMENTAL): fill logic and metrics on small made-up tables."""

import numpy as np
import pandas as pd
import pytest

import tier2_fill as tf

NAN = np.nan


def _pool():
    # target A: tier 1 keeps a1; B: no tier 1; C: three tier-1 comps (full)
    return pd.DataFrame({
        "target_id": ["A"] * 5 + ["B"] * 4 + ["C"] * 4,
        "comp_id": ["a1", "a2", "a3", "a4", "a5", "b1", "b2", "b3", "b4", "c1", "c2", "c3", "c4"],
        "rank": [1, 2, 3, 4, 5, 1, 2, 3, 4, 1, 2, 3, 4],
        "agent_score": [2, 0, 1, NAN, 2, 1, NAN, 0, 2, 2, 2, 2, 2],
    })


def _tier1():
    return pd.DataFrame({"target_id": ["A", "C", "C", "C"], "comp_id": ["a1", "c1", "c2", "c3"]})


def _picks(rule, k=3, tier1=None, pool=None):
    p = tf.fill(_tier1() if tier1 is None else tier1, _pool() if pool is None else pool, rule, k)
    return {t: list(x["comp_id"]) for t, x in p.groupby("target_id")}


def test_b3_rank_order_and_k():
    got = _picks("b3_rank")
    assert got == {"A": ["a2", "a3"], "B": ["b1", "b2", "b3"]}       # C is full; a1 never repeated


def test_agent_order_skips_0_and_ungraded():
    got = _picks("agent")
    assert got == {"A": ["a5", "a3"], "B": ["b4", "b1"]}             # 2 before 1; a2/b3 (0) and a4/b2 (NaN) skipped


def test_agent_then_rank():
    got = _picks("agent_then_rank")
    assert got == {"A": ["a5", "a3"], "B": ["b4", "b1", "b2"]}       # ungraded b2 fills after; agent-0 b3 never


def test_never_exceeds_k_never_repeats_tier1():
    pool, t1 = _pool(), _tier1()
    for rule in tf.RULES:
        for k in (1, 2, 3, 5):
            p = tf.fill(t1, pool, rule, k)
            n1 = t1.groupby("target_id").size()
            for t, x in p.groupby("target_id"):
                assert len(x) + n1.get(t, 0) <= k
            assert not set(map(tuple, p[["target_id", "comp_id"]].to_numpy())) & set(map(tuple, t1.to_numpy()))
            assert not p.duplicated(["target_id", "comp_id"]).any()


def test_ties_by_rank_then_comp_and_no_self():
    pool = pd.DataFrame({"target_id": ["A", "A", "A", "A"], "comp_id": ["z", "y", "A", "x"],
                         "rank": [2, 2, 1, 3], "agent_score": [1, 1, 2, 1]})
    p = tf.fill(pd.DataFrame(columns=["target_id", "comp_id"]), pool, "agent", 2)
    assert list(p["comp_id"]) == ["y", "z"] and list(p["fill_order"]) == [1, 2]


def test_target_without_pool_or_with_empty_pool():
    p = tf.fill(_tier1(), _pool().iloc[0:0], "b3_rank", 3, targets=["A", "B", "D"])
    assert p.empty


def test_unknown_rule():
    with pytest.raises(ValueError):
        tf.fill(_tier1(), _pool(), "random", 3)


def test_summarize_counts_and_precision():
    members = pd.DataFrame({
        "target_id": ["A", "A", "A", "B", "B", "B", "C"],
        "comp_id": ["a1", "a2", "a3", "b1", "b2", "b3", "c1"],
        "tier": [1, 2, 2, 2, 2, 2, 1],
        "label_source": ["v3_final", "v3_final", "unlabelled", "v3_final", "judge_only", "v3_final", "v3_final"],
        "grade": [2, 1, NAN, 0, 2, 2, 0],
    })
    s = tf.summarize(members, ["A", "B", "C", "D"], k=3, boot=False)
    assert s["targets_ge3_before"] == 0 and s["targets_0_before"] == 2
    assert s["targets_ge3_after"] == 2 and s["targets_0_after"] == 1
    assert s["tier2_picks"] == 5 and s["tier2_v3_final"] == 3 and s["tier2_judge_only"] == 1
    assert s["tier2_unlabelled"] == 1 and s["tier2_labelled_share"] == pytest.approx(0.6)
    assert s["tier2_ge1_prec_mean"] == pytest.approx((1 + 0.5) / 2)       # A: a2 1/1; B: b1 0, b3 2 -> 1/2
    assert s["tier2_ge1_prec_pooled"] == pytest.approx(2 / 3)
    assert s["tier2_direct_share_pooled"] == pytest.approx(1 / 3)
    assert s["tier2_ge1_prec_all_sources_pooled"] == pytest.approx(3 / 4)   # judge-only b2 counts only here
    assert s["tier1_direct_prec_mean"] == pytest.approx(0.5)                # A 1/1, C 0/1
    assert s["profile_ge1_prec_pooled"] == pytest.approx(3 / 5)


def test_summarize_bootstrap_interval_contains_mean():
    members = pd.DataFrame({"target_id": list("ABCD"), "comp_id": list("abcd"), "tier": [2] * 4,
                            "label_source": ["v3_final"] * 4, "grade": [2, 1, 0, 1]})
    s = tf.summarize(members, list("ABCD"), k=3)
    assert s["tier2_ge1_prec_lo"] <= s["tier2_ge1_prec_mean"] <= s["tier2_ge1_prec_hi"]


# ---------------------------------------------------------------- k sweep and llm_tier2 (EXPERIMENTAL, 2026-11-28)

import json  # noqa: E402

import tier2_llm as tl  # noqa: E402


def _llm_pool():
    # the model ranked a4 first, then a2 (and tier-1 a1, which must never be repeated); B: b3, b1, b2
    p = _pool()
    p["llm_rank"] = [3, 2, NAN, 1, NAN, 2, 3, 1, NAN, NAN, NAN, NAN, NAN]
    return p


def test_llm_rule_order_and_k_truncation():
    got = {k: _picks("llm_tier2", k=k, pool=_llm_pool()) for k in (1, 2, 3, 5)}
    assert got[1] == {"B": ["b3"]}                                   # A already has 1 tier-1 comp
    assert got[2] == {"A": ["a4"], "B": ["b3", "b1"]}
    assert got[3] == {"A": ["a4", "a2"], "B": ["b3", "b1", "b2"]}
    assert got[5] == {"A": ["a4", "a2"], "B": ["b3", "b1", "b2"]}   # fewer ranked than needed: no B3-rank top-up


def test_llm_rule_never_exceeds_k_or_repeats_tier1():
    pool, t1 = _llm_pool(), _tier1()
    for k in range(1, 7):
        p = tf.fill(t1, pool, "llm_tier2", k)
        n1 = t1.groupby("target_id").size()
        for t, x in p.groupby("target_id"):
            assert len(x) + n1.get(t, 0) <= k
            assert x["llm_rank"].is_monotonic_increasing
        assert not set(map(tuple, p[["target_id", "comp_id"]].to_numpy())) & set(map(tuple, t1.to_numpy()))
        assert p["llm_rank"].notna().all() and not p.duplicated(["target_id", "comp_id"]).any()


def test_llm_rule_needs_rank_column():
    with pytest.raises(ValueError):
        tf.fill(_tier1(), _pool(), "llm_tier2", 3)


def test_parse_answer_none_unknown_duplicate_and_cap():
    labels = {f"C{i}": f"x{i}" for i in range(1, 9)}
    raw = {"comps": [{"label": "C3", "reason": " r3 "}, {"label": "none", "reason": ""}, {"label": "C99", "reason": ""},
                     {"label": "C3", "reason": "again"}, {"label": "C1", "reason": "r1"}, {"label": "C2", "reason": ""},
                     {"label": "C4", "reason": ""}, {"label": "C5", "reason": ""}, {"label": "C6", "reason": ""}],
           "note": " n "}
    picks, issues, note = tl.parse_answer(raw, labels)
    assert [p["comp_id"] for p in picks] == ["x3", "x1", "x2", "x4", "x5"]
    assert [p["llm_rank"] for p in picks] == [1, 2, 3, 4, 5]
    assert picks[0]["llm_reason"] == "r3" and note == "n"
    assert "none_label" in issues and "unknown_label:C99" in issues and "duplicate_label:C3" in issues
    assert "over_max:6" in issues


def test_parse_answer_empty_and_bad():
    assert tl.parse_answer({"comps": [], "note": "none qualify"}, {"C1": "x"}) == ([], [], "none qualify")
    picks, issues, _ = tl.parse_answer({"comps": [{"label": "None", "reason": ""}], "note": ""}, {"C1": "x"})
    assert picks == [] and issues == ["none_label"]
    with pytest.raises(ValueError):
        tl.parse_answer(["C1"], {"C1": "x"})


def test_candidates_exclude_tier1_and_target():
    pool = pd.concat([_pool(), pd.DataFrame({"target_id": ["A"], "comp_id": ["A"], "rank": [0], "agent_score": [2]})])
    c = tl.candidates_for(pool, _tier1(), ["A", "B", "C"])
    assert c == {"A": ["a2", "a3", "a4", "a5"], "B": ["b1", "b2", "b3", "b4"], "C": ["c4"]}


def test_judge_order_priority_skips_labelled_and_caps():
    llm = pd.DataFrame({"target_id": ["A", "A", "B", "B"], "comp_id": ["a4", "a2", "b3", "b1"],
                        "llm_rank": [1, 2, 1, 2], "tier1_n": [1, 1, 0, 0]})
    other = pd.DataFrame({"target_id": ["B", "A", "B"], "comp_id": ["b1", "a5", "b2"],
                          "rule": ["b3_rank", "agent_then_rank", "b3_rank"], "fill_order": [1, 1, 2]})
    d = tl.judge_order(llm, other, labelled={("B", "b3")}, cap=10)
    # entry k: A a4 = 1 + 1 = 2, B b1 = 0 + 2 = 2, A a2 = 3; b3 labelled; then agent_then_rank, then b3_rank
    assert list(zip(d["target_id"], d["comp_id"])) == [("A", "a4"), ("B", "b1"), ("A", "a2"), ("A", "a5"), ("B", "b2")]
    assert d["source"].tolist() == ["llm_tier2"] * 3 + ["agent_then_rank", "b3_rank"]
    assert d["priority"].tolist() == [1, 2, 3, 4, 5]
    assert len(tl.judge_order(llm, other, set(), cap=2)) == 2


def test_shortfall_counts():
    status = pd.DataFrame({"target_id": ["A", "B", "C"], "llm_status": ["ok", "ok", "cli_error"],
                           "n_picks": [1, 0, 0]})
    n1 = pd.Series({"A": 1, "B": 0, "C": 2, "D": 6})
    s = tl.shortfall(status, n1, ks=(2, 3)).set_index("k")
    assert s.at[2, "targets_needing_tier2"] == 2 and s.at[2, "fewer_than_needed"] == 1   # A needs 1, has 1; B 0
    assert s.at[3, "targets_needing_tier2"] == 3 and s.at[3, "not_answered"] == 1
    assert s.at[3, "fewer_than_needed"] == 2 and s.at[3, "none_returned"] == 1
    assert s.at[3, "slots_needed"] == 2 + 3 + 1 and s.at[3, "slots_filled"] == 1


def test_summarize_extended_all_sources():
    members = pd.DataFrame({"target_id": ["A", "A", "B"], "comp_id": ["a1", "a2", "b1"], "tier": [1, 2, 2],
                            "label_source": ["v3_final", "judge_only", "unlabelled"], "grade": [2, 0, NAN]})
    base = tf.summarize(members, ["A", "B"], k=2, boot=False)
    ext = tf.summarize(members, ["A", "B"], k=2, boot=False, extended=True)
    assert all(ext[k] == v or (pd.isna(ext[k]) and pd.isna(v)) for k, v in base.items())
    assert ext["tier2_any_label_share"] == pytest.approx(0.5)
    assert ext["tier2_ge1_prec_all_sources_pooled"] == 0
    assert ext["profile_ge1_prec_all_sources_pooled"] == pytest.approx(0.5)


def test_run_with_mocked_model(tmp_path, monkeypatch):
    out = tmp_path / "d"
    llm = out / "llm_tier2"
    tl.save(out, "manifest.json", {"commands": []})
    tl.save(llm, "manifest.json", {"instructions_sha256": tl.sha_text(tl.INSTRUCTIONS),
                                   "prompt_version": tl.PROMPT_VERSION, "sessions": []})
    labels = {"T1": {"C1": "x", "C2": "y"}, "T2": {"C1": "z"}}

    def fake_prompt(t, comps, info, facets):
        return tl.INSTRUCTIONS + f"\nTarget: {t} " + " ".join(comps), labels[t]

    cand = pd.DataFrame([{"target_id": t, "comp_id": c, "label": lab, "b3_rank": i, "tier1_n": 0,
                          "prompt_sha256": tl.sha_text(fake_prompt(t, list(m.values()), None, None)[0])}
                         for t, m in labels.items() for i, (lab, c) in enumerate(m.items(), 1)])
    tl.save(llm, "inputs/candidates.csv", cand)
    info = pd.DataFrame({"target_ciq_ticker": ["T1", "T2"]}, index=["T1", "T2"])
    monkeypatch.setattr(tl, "selector_inputs", lambda: (None, info, None))
    monkeypatch.setattr(tl, "build_prompt", fake_prompt)
    calls = []

    def fake_call(prompt, run_dir, schema, backend, model=None, effort=None, instructions_len=0):
        calls.append(prompt)
        ans = ({"comps": [{"label": "C2", "reason": "same buyers"}, {"label": "none", "reason": ""}], "note": "n"}
               if "T1" in prompt else {"comps": [], "note": "none qualify"})
        return {"llm_status": "ok", "text": json.dumps(ans), "seconds": 0.1, "usage": {}}

    c = tl.run(out, "test", call=fake_call)
    assert c["ok"] == 2 and len(calls) == 2
    picks = tl.read_csv(llm / "picks.csv")
    assert picks[["target_id", "comp_id"]].values.tolist() == [["T1", "y"]] and picks["llm_rank"].tolist() == [1]
    status = tl.read_csv(llm / "status.csv").set_index("target_id")
    assert int(status.at["T2", "n_picks"]) == 0 and status.at["T1", "issues"] == "none_label"
    c = tl.run(out, "test again", call=fake_call)                    # resumes: nothing is called again
    assert c["skipped_done"] == 2 and len(calls) == 2
