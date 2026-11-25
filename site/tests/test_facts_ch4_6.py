"""Facts for chapters 4-6: every fact cites existing pins, the numbers hang together, and they match the saved
outputs teammates computed them from (filter_comparison, route_common_support, the ledger).

    uv run pytest site/tests/test_facts_ch4_6.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from facts import ch4_finding as f4  # noqa: E402
from facts import ch5_judging as f5  # noqa: E402
from facts import ch6_results as f6  # noqa: E402
from facts.common import PINS, REGISTRY, Fact, pinned  # noqa: E402

MODULES = [f4, f5, f6]


def facts_of(module) -> list[Fact]:
    return [v for v in vars(module).values() if isinstance(v, Fact)]


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__)
def test_every_fact_cites_existing_pins(module):
    facts = facts_of(module)
    assert facts, f"{module.__name__} registers no facts"
    for f in facts:
        assert REGISTRY[f.name] is f
        for pin in f.source.split("+"):
            assert pin.strip() in PINS, f"{f.name} cites unknown pin {pin}"
            assert pinned(pin.strip()).is_file()
        assert str(f).strip(), f"{f.name} prints nothing"


def test_ch4_counts_hang_together():
    assert f4.b3_min_comps.value <= f4.b3_median_comps.value <= f4.b3_k.value
    assert f4.b3_pairs_topped_up.value < f4.b3_pairs.value
    assert f4.sel_kept_pairs.value <= f4.b3_pairs.value
    assert f4.sel_targets_kept.value + f4.sel_targets_no_comp.value == f4.b3_targets.value
    assert 0 <= f4.sel_keep_rate.value <= 1
    grades = f4.agent_grade0.value + f4.agent_grade1.value + f4.agent_grade2.value + f4.agent_insufficient.value
    assert grades == f4.agent_pairs.value
    assert f4.agent_ge1.value == f4.agent_grade1.value + f4.agent_grade2.value
    assert f4.agent_pairs_lookup.value <= f4.agent_pairs.value
    assert f4.sel_kept_on_agent_pairs.value <= f4.agent_pairs.value <= f4.b3_pairs.value


def test_ch4_matches_saved_numbers():
    # GRADING_REVIEW.md / filter_comparison filters.csv: B3 keep-all 293 pairs, selector 69, agent >= 1 183, agent 2 26
    filters = pd.read_csv(pinned("grading_filters"))
    b = filters[filters["reference"].eq("Barbara peer (>=1)")].set_index("filter")["kept"]
    assert b["B3 list (keep all)"] == f4.agent_pairs.value
    assert b["selector keep"] == f4.sel_kept_on_agent_pairs.value
    assert b["agent grade >= 1"] == f4.agent_ge1.value
    assert b["agent grade 2"] == f4.agent_grade2.value


def test_ch4_v0_routes_match_route_common_support():
    support = pd.read_csv(pinned("v0_route_support"))
    assert (support["common targets"] == f4.v0_common_targets.value).all()
    lo, hi = f4.v0_err_routes_range.value
    assert lo == pytest.approx(support["median APE on common targets"].min())
    assert hi == pytest.approx(support["median APE on common targets"].max())
    assert len(support) == f4.v0_routes.value
    assert f4.v0_common_targets.value <= f4.v0_holdout_targets.value
    assert f4.v0_err_no_matching.value > hi   # every route is below no matching on the common targets


def test_ch4_figures_draw():
    for fig in (f4.fig_filter_keeps(), f4.fig_agent_outcomes()):
        assert fig.axes and fig.axes[0].patches


def test_ch5_rubric_structure():
    assert f5.rubric_scored_pairs.value + f5.rubric_anchors.value == f5.rubric_pairs.value
    assert f5.rubric_questions.value == f5.rubric_score_questions.value + 1   # the overall call comes first
    assert f5.rubric_targets.value <= f5.rubric_pairs.value


def test_ch5_kappa_matches_filter_comparison():
    agree = pd.read_csv(pinned("grading_agreement")).set_index(["rater_a", "rater_b"])
    bm = agree.loc[("Barbara", "Matthew v2")]
    assert bm["pairs"] == f5.bm_pairs.value
    assert f5.bm_kappa_peer.value == pytest.approx(bm["peer_kappa"], abs=1e-12)
    assert f5.bm_kappa_grade.value == pytest.approx(bm["grade_kappa"], abs=1e-12)
    assert f5.bm_peer_agreement.value == pytest.approx(bm["peer_agreement"], abs=1e-12)


def test_ch5_agent_filter_matches_filter_comparison():
    filters = pd.read_csv(pinned("grading_filters")).set_index(["reference", "filter"])
    for ref, prefix in [("Barbara peer (>=1)", "agent_vs_barbara"), ("Matthew v2 peer (>=1)", "agent_vs_matthew")]:
        row = filters.loc[(ref, "agent grade >= 1")]
        for metric in ("precision", "recall", "kappa"):
            assert getattr(f5, f"{prefix}_{metric}").value == pytest.approx(row[metric], abs=1e-12), (prefix, metric)


def test_ch5_ranges_and_split():
    for name in ("bm_peer_agreement", "matthew_yes_product", "matthew_yes_customers", "agent_vs_barbara_precision",
                 "agent_vs_barbara_recall", "agent_vs_matthew_precision", "agent_vs_matthew_recall"):
        assert 0 <= getattr(f5, name).value <= 1, name
    for name in ("bm_kappa_peer", "bm_kappa_grade", "agent_vs_barbara_kappa", "agent_vs_matthew_kappa"):
        assert -1 <= getattr(f5, name).value <= 1, name
    assert (f5.bm_prodno_custyes_barbara0.value + f5.bm_prodno_custyes_barbara1.value
            <= f5.matthew_prodno_custyes.value <= f5.bm_pairs.value)
    t = f5.tbl_bm_crosstab()
    assert t.drop(columns=t.columns[0]).to_numpy().sum() == f5.bm_pairs.value


def test_ch6_ledger():
    for name, value in vars(f6).items():
        if name.startswith("ledger_") and name.endswith(("_precision", "_recall")):
            assert 0 <= value.value <= 1, name
    assert f6.ledger_b3_peer_recall.value == 1 and f6.ledger_b3_direct_recall.value == 1   # keep-all keeps every peer
    t = f6.tbl_ledger()
    assert len(t) >= 4 and {"B3 list, keep all", "Selector keeps (04)"} <= set(t["version"])


def test_ch6_ledger_pooled_matches_grading_review():
    # PROGRESS.md: the ledger's pooled numbers match filter_comparison (Matthew v2, agent >= 1 and selector)
    led = pd.read_csv(pinned("ledger_latest"))
    led = led[led["cohort"].eq(f6.LEDGER_COHORT)].set_index("profile")
    filters = pd.read_csv(pinned("grading_filters")).set_index(["reference", "filter"])
    for profile, filt in [("agent_ge1", "agent grade >= 1"), ("selector", "selector keep")]:
        row = filters.loc[("Matthew v2 peer (>=1)", filt)]
        assert led.loc[profile, "kept"] == row["kept"]
        assert led.loc[profile, "peer_precision_pooled"] == pytest.approx(row["precision"], abs=1e-4)
        assert led.loc[profile, "peer_recall_pooled"] == pytest.approx(row["recall"], abs=1e-4)


def test_ch6_traits():
    for trait in ("large_customers", "mission_critical"):
        for outcome in ("direct", "peer"):
            lift = getattr(f6, f"trait_{trait}_{outcome}").value
            lo, hi = getattr(f6, f"trait_{trait}_{outcome}_ci").value
            assert lo <= lift <= hi, (trait, outcome)
    assert f6.trait_r1_findings.value <= 60 and f6.trait_r2_findings.value <= 40


def test_ch6_valuation():
    assert f6.val_targets.value == f4.sel_targets_kept.value <= f6.val_training_targets.value
    for name in ("val_err_no_matching", "val_err_b3", "val_err_selector", "val_err_no_matching_all"):
        assert 0 < getattr(f6, name).value < 100, name
    lo, hi = f6.val_gain_selector_ci.value
    assert lo <= f6.val_gain_selector.value <= hi


def test_ch6_images_exist():
    for img in (f6.img_progress(), f6.img_trait_lift_r1(), f6.img_trait_lift_r2()):
        assert img.data[:8] == b"\x89PNG\r\n\x1a\n"
