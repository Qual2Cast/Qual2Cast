"""Checks for the trait X-learner (trait_uplift.py) on synthetic data; no files, models or labels are read."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
import v2paths as v2  # noqa: E402
v2.setup()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

import trait_uplift as tu  # noqa: E402


def synthetic(effect: float, seed: int = 7, targets: int = 40, comps_per_target: int = 7, unknown: float = 0.05):
    """Pairs with three B3-like covariates and the six traits answered at random; the direct outcome rises by
    `effect` when the pair matches on recurring_revenue, and does not depend on any other trait."""
    rng = np.random.default_rng(seed)
    companies = [f"T{i}" for i in range(targets)] + [f"C{i}" for i in range(120)]
    answers = {c: rng.choice(["yes", "no"], len(companies)) for c in tu.TRAITS + list(tu.TAGS)}
    traits = pd.DataFrame(answers, index=pd.Index(companies, name="IQ_COMPANY_ID"))
    for c in tu.TRAITS:
        traits.loc[rng.random(len(traits)) < unknown, c] = "unknown"
    rows = [(f"T{t}", f"C{c}") for t in range(targets) for c in rng.choice(120, comps_per_target, replace=False)]
    pairs = pd.DataFrame(rows, columns=["target", "comp"])
    for k in range(3):
        pairs[f"b3__s{k}"] = rng.normal(size=len(pairs))
    pairs = tu.add_traits(pairs, traits)
    m = np.nan_to_num(pairs["match__recurring_revenue"].to_numpy(), nan=0.0)
    p = 0.15 + effect * m + 0.05 * pairs["b3__s0"].to_numpy()
    pairs["direct"] = (rng.random(len(pairs)) < np.clip(p, 0, 1)).astype(float)
    pairs["peer"] = pairs["direct"]
    return pairs, traits


def test_match_and_unknown():
    a = pd.Series(["yes", "no", "unknown", "yes", None])
    b = pd.Series(["yes", "yes", "yes", None, "no"])
    m = tu.match(a, b)
    assert m[0] == 1 and m[1] == 0
    assert np.isnan(m[2:]).all()          # unknown or missing on either side: excluded, never a mismatch


def test_unknown_pairs_left_out_of_that_trait_only():
    pairs, _ = synthetic(0.0, unknown=0.3)
    effects, diags = tu.oof(pairs, "cyclical_demand", "direct")
    known = np.isfinite(pairs["match__cyclical_demand"]).sum()
    assert effects.treatment.isin([0, 1]).all()
    assert len(effects) <= known < len(pairs)
    assert diags.unknown_test.sum() == len(pairs) - known
    # the other traits' unknowns stay in as covariates (imputed with indicators), not dropped
    assert "match__recurring_revenue" in tu.covariates(pairs, "cyclical_demand")


def test_tag_cells_average_by_target(monkeypatch):
    monkeypatch.setattr(tu.fu, "MIN_TARGETS", 1)
    effects = pd.DataFrame({
        "target": ["A", "A", "B", "C"], "unit": ["A", "A", "B", "C"],
        "tag__offers_services": ["yes", "yes", "no", "unknown"],
        "tag__sells_to_consumers": ["no", "no", "no", "yes"],
        "uplift": [0.2, 0.4, -0.1, 0.5], "dr_pseudo_effect": [0, 0, 0, 0], "overlap": [True, True, True, True]})
    c = tu.cells(effects, folds_ok=5)
    assert c["all"]["lift"] == pytest.approx((0.3 - 0.1 + 0.5) / 3)     # each target counts once
    assert c["services_yes"]["lift"] == pytest.approx(0.3)
    assert c["services_no"]["lift"] == pytest.approx(-0.1)
    assert c["consumers_no"]["lift"] == pytest.approx((0.3 - 0.1) / 2)
    assert c["services_yes"]["targets"] == 1                              # unknown tag C is in neither cell
    assert not tu.cells(effects, folds_ok=4)["all"]["supported"]          # partial analysis: no estimate


def test_permutation_p():
    assert tu.permutation_p(0.5, [0.1, -0.2, 0.6]) == pytest.approx(0.5)
    assert tu.permutation_p(-0.5, [0.1, 0.55]) == pytest.approx(2 / 3)    # two-sided
    assert tu.permutation_p(0.9, [0.1] * 19) == pytest.approx(0.05)
    assert tu.permutation_p(0.9, [np.nan, 0.1]) == pytest.approx(0.5)     # unusable shuffles dropped
    assert np.isnan(tu.permutation_p(np.nan, [0.1]))
    assert np.isnan(tu.permutation_p(0.3, []))


def test_benjamini_hochberg():
    adj = tu.benjamini_hochberg(np.array([0.01, 0.04, 0.03, 0.2]))
    assert adj == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.2])
    assert tu.benjamini_hochberg(np.array([np.nan, 0.001]))[0] == 1       # unsupported counts as p = 1
    # all-null families of 60: BH at q = 0.10 makes any false finding in about 10% of families at most
    rng = np.random.default_rng(0)
    any_finding = np.mean([(tu.benjamini_hochberg(rng.random(60)) <= tu.Q).any() for _ in range(400)])
    assert any_finding <= 0.15


def test_known_effect_recovered():
    pairs, traits = synthetic(0.4)
    _, _, c, folds_ok = tu.analyze(pairs, "recurring_revenue", "direct")
    assert folds_ok == 5 and c["all"]["supported"]
    assert c["all"]["lift"] > 0.25
    _, _, null, _ = tu.analyze(pairs, "cyclical_demand", "direct")
    assert abs(null["all"]["lift"]) < 0.12
    shuffles = pd.DataFrame(tu._shuffle_job(pairs, traits["recurring_revenue"], "recurring_revenue", "direct",
                                            range(19)))
    s = shuffles[(shuffles.cell == "all") & shuffles.supported]
    assert tu.permutation_p(c["all"]["lift"], s.lift.to_numpy()) <= 0.05 + 1e-9
    boots = pd.DataFrame(tu._bootstrap_job(pairs, "recurring_revenue", "direct", range(8)))
    b = boots[(boots.cell == "all") & boots.supported].lift
    assert len(b) >= 6 and (b > 0.1).all()


def test_null_data_no_findings_after_bh():
    pairs, traits = synthetic(0.0, seed=11)
    summary, *_ = tu.run_all(pairs, traits, ["direct"], permutations=9, bootstrap=0, workers=1)
    assert len(summary) == len(tu.TRAITS) * len(tu.CELLS)
    assert not summary.finding.any()
    assert summary.bh_q.between(0, 1).all()
