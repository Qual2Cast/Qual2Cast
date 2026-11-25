"""Checks for the facts of chapters 1-3 (index.qmd, data.qmd, describing.qmd).

    uv run pytest site/tests/test_facts_ch1_3.py -q

Every fact cites pins that exist and still match their hash, and the numbers agree with each other and with the
runs' own metadata (run.json, the saved balance tables, the prompt versions in the code that made the fills).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))

from facts import ch1_intro, ch2_data, ch3_describing  # noqa: E402
from facts.common import PINS, Fact, pinned  # noqa: E402

MODULES = (ch1_intro, ch2_data, ch3_describing)


def facts_of(module) -> dict[str, Fact]:
    return {k: v for k, v in vars(module).items() if isinstance(v, Fact)}


def _constant(pin: str, name: str):
    tree = ast.parse(pinned(pin).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


# ---------------------------------------------------------------- every fact

@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__)
def test_facts_cite_pins_that_match(module):
    facts = facts_of(module)
    assert facts, f"{module.__name__} registers no facts"
    for name, f in facts.items():
        assert name == f.name, f"attribute {name} holds fact {f.name}"
        for pin in f.source.split("+"):
            assert pin.strip() in PINS, f"{f.name} cites unknown pin {pin}"
            pinned(pin.strip())                      # raises if missing or changed


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__)
def test_counts_print_with_separators(module):
    for f in facts_of(module).values():
        if isinstance(f.value, int) and not isinstance(f.value, bool):
            assert str(f) == f"{f.value:,}", f.name


# ---------------------------------------------------------------- chapter 1

def test_ch1_reexports_are_the_same_facts():
    assert ch1_intro.n_universe is ch2_data.n_universe
    assert ch1_intro.n_supplied is ch2_data.n_supplied
    assert ch1_intro.n_training is ch2_data.n_training
    assert ch1_intro.n_holdout is ch2_data.n_holdout
    assert ch1_intro.n_facets is ch3_describing.n_facets
    assert ch1_intro.n_traits is ch3_describing.n_traits


def test_ch1_labels():
    assert 0 < ch1_intro.n_labelled_twice.value <= ch1_intro.n_labelled_pairs.value
    assert 0 < ch1_intro.n_labelled_targets.value <= ch1_intro.n_labelled_pairs.value
    assert ch1_intro.n_reviewers.value >= 2
    # the ledger leaves out comps outside the universe: every labelled pair is inside it
    pairs = pd.read_csv(pinned("labels_ledger_pairs"), dtype=str)
    human = pairs[pairs["n_judged_human_review"].astype(int) > 0]
    ids = set(pd.read_csv(pinned("universe"), dtype=str)["IQ_COMPANY_ID"])
    assert set(human["target_id"]) <= ids and set(human["comp_id"]) <= ids


# ---------------------------------------------------------------- chapter 2

def test_ch2_universe_matches_its_run():
    run = json.loads(pinned("universe_run").read_text(encoding="utf-8"))
    companies = pd.read_csv(pinned("companies"), dtype=str)
    assert ch2_data.n_supplied.value == run["companies"] == len(companies)
    assert ch2_data.n_universe.value == run["in_universe"] == companies["in_universe"].eq("True").sum()
    assert ch2_data.n_dropped_above.value == run["dropped"]["above_30"]
    assert ch2_data.n_dropped_below.value == run["dropped"]["below_3"]
    assert ch2_data.n_dropped_above.value + ch2_data.n_dropped_below.value == ch2_data.n_dropped_multiple.value
    assert ch2_data.n_us_hq.value <= ch2_data.n_supplied.value
    assert ch2_data.n_supplied.value - ch2_data.n_dropped_multiple.value >= ch2_data.n_universe.value
    assert ch2_data.ev_ebitda_min.value < ch2_data.ev_ebitda_max.value


def test_ch2_split():
    universe = pd.read_csv(pinned("universe"), dtype=str)
    split = pd.read_csv(pinned("split"), dtype=str)
    run = json.loads(pinned("split_run").read_text(encoding="utf-8"))
    assert set(split["IQ_COMPANY_ID"]) == set(universe["IQ_COMPANY_ID"])
    assert ch2_data.n_training.value + ch2_data.n_holdout.value == ch2_data.n_universe.value
    assert ch2_data.n_training.value == round(run["train_share"] * ch2_data.n_universe.value)
    assert ch2_data.n_strata.value == len(run["counts"])
    by_stratum = pd.crosstab(split["stratum"], split["sample"])
    for stratum, c in run["counts"].items():
        assert by_stratum.at[stratum, "training"] == c["training"] and by_stratum.at[stratum, "holdout"] == c["holdout"]
    assert ch2_data.n_split_forced.value == len(run["showcase_in_training"])
    assert split.loc[split["showcase"].eq("True"), "sample"].eq("training").all()
    assert ch2_data.n_sic2.value >= ch2_data.n_strata.value - 1


def test_ch2_divisions_match_saved_balance():
    """The figure's counts reproduce the split's own balance table (shares of each sample, in %)."""
    t = ch2_data.companies_by_division()
    balance = pd.read_csv(pinned("split_balance_sector"), index_col=0)
    assert set(balance.index) == set(t.index)
    for sample in ("training", "holdout"):
        n = t[sample].sum()
        assert (t[sample] * 100 / n).reindex(balance.index).round(6).equals(balance[sample].round(6))
    assert t["companies"].sum() == ch2_data.n_universe.value


def test_ch2_sic_codes_keep_leading_zeros():
    universe = ch2_data._universe
    assert universe["target_sic2_code"].str.len().eq(2).all()
    assert "unknown" not in set(ch2_data.companies_by_division().index)


def test_ch2_website():
    assert ch2_data.n_web_text.value + ch2_data.n_web_no_text.value == ch2_data.n_universe.value
    assert ch2_data.web_max_pages.value >= 1


def test_ch2_outputs_build():
    assert list(ch2_data.funnel_table()["companies"])[-1] == ch2_data.n_universe.value
    plt.close(ch2_data.division_figure())


# ---------------------------------------------------------------- chapter 3

def test_ch3_facets_match_the_fill():
    general = pd.read_csv(pinned("facets_general"), dtype=str)
    status_cols = [c for c in general.columns if c.endswith("_status") and c != "llm_status"]
    assert ch3_describing.n_facets.value == len(status_cols) == len(ch3_describing.facet_names.value)
    assert set(general["prompt_version"]) == {_constant("facets_code", "PROMPT_VERSION")}
    assert general["IQ_COMPANY_ID"].nunique() == ch2_data.n_universe.value
    assert 0.5 < ch3_describing.facet_share_model.value <= 1
    assert ch3_describing.n_facet_web_companies.value <= ch3_describing.n_facet_values_web.value


def test_ch3_traits_match_the_fill_and_the_test():
    t1 = pd.read_csv(pinned("traits_r1"), dtype=str)
    t2 = pd.read_csv(pinned("traits_r2"), dtype=str)
    assert set(t1["prompt_version"]) == {_constant("traits_code", "PROMPT_VERSION")}
    assert set(t2["prompt_version"]) == {_constant("traits_code", "PROMPT_VERSION_R2")}
    universe = set(pd.read_csv(pinned("universe"), dtype=str)["IQ_COMPANY_ID"])
    assert set(t1["IQ_COMPANY_ID"]) == set(t2["IQ_COMPANY_ID"]) == universe
    assert ch3_describing.n_traits_filled.value == ch2_data.n_universe.value
    stab = pd.concat([pd.read_csv(pinned("traits_test_r1")), pd.read_csv(pinned("traits_test_r2"))])
    assert len(stab) == ch3_describing.n_tags.value + ch3_describing.n_traits.value
    assert list(stab["id"]) == list(ch3_describing.traits_table()["ID"])
    assert stab["verdict"].eq("keep").all()
    assert ch3_describing.trait_flips_max.value / ch3_describing.trait_test_n.value <= ch3_describing.trait_keep_flip_max.value
    unknowns = stab["unknown_rate_max"] * stab["companies"]
    assert (unknowns - unknowns.round()).abs().max() < 0.05          # the rounded rates come from whole counts


def test_ch3_pages_cover_the_scraped_text():
    """Every company with cleaned website text had page text in its trait prompt; a page title alone also counts
    there, so the trait count can be higher than the scrape's."""
    t1 = pd.read_csv(pinned("traits_r1"), dtype=str).set_index("IQ_COMPANY_ID")
    log = pd.read_csv(pinned("scrape_log"), dtype=str).set_index("IQ_COMPANY_ID")
    with_text = log.index[log["word_count"].astype(int) > 0].intersection(t1.index)
    assert t1.loc[with_text, "had_pages"].eq("True").all()
    assert ch2_data.n_web_text.value <= ch3_describing.n_trait_pages.value <= ch2_data.n_universe.value


def test_ch3_outputs_build():
    assert len(ch3_describing.facets_table()) == ch3_describing.n_facets.value
    rates = ch3_describing.traits_table()
    assert len(rates) == ch3_describing.n_tags.value + ch3_describing.n_traits.value
    plt.close(ch3_describing.trait_rates_figure())
