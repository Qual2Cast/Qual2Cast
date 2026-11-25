"""Facts for Results (results.qmd). Pattern: see ch2_data.py.

1. Improvement ledger (v2/09_analysis/PROGRESS.md): latest.csv, one row per profile, label set and split. The facts
   read the rows for LEDGER_COHORT and LEDGER_SPLIT: change these two lines (and re-pin) when the rubric v3 consensus
   rows and the checking-half split are recorded. Precision and recall are target means (the ledger's headline).
2. Trait X-learner (v2/09_analysis/PREREG_TRAITS.md, PREREG_TRAITS_R2.md): the pinned runs in v2/current.toml
   [analysis.trait_uplift] (round 1) and [analysis.trait_uplift_r2] (round 2); lift on all pairs with its 95% refit-
   bootstrap interval; a "finding" passes Benjamini-Hochberg at q = 0.10 within its round.
3. Valuation, once, as context (v2/08_valuation/valuation.ipynb section 3.2): on the training targets where the
   selector kept a comp, median absolute % error of the median comp EV/EBITDA vs the actual multiple, with "no
   matching" (median of every other training firm) as the reference. Functions below are copied from
   v2/08_valuation/scripts/valuation.py (which imports the v2 path setup, so it is not imported here).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from IPython.display import Image

from facts.common import fact, pinned


def _n(x) -> str:
    return f"{int(x):,}"


def _pct(x: float, digits: int = 0) -> str:
    return f"{100 * x:.{digits}f}%"


def _signed(x: float, digits: int = 1) -> str:
    return f"{x:+.{digits}f}".replace("-", "−")


# ---------------------------------------------------------------- 1. improvement ledger
LEDGER_COHORT = "matthew_v2_262"   # v2/current.toml [analysis.progress] cohort; switch to the rubric v3 consensus
LEDGER_SPLIT = "all"               # all labelled targets; switch to the checking half when it is recorded
LEDGER_PROFILES = {"b3_all": "B3 list, keep all", "b3_top7": "B3 top 7", "selector": "Selector keeps (04)",
                   "agent_ge1": "Agent grade >= 1 (05)", "agent_2": "Agent grade 2 (05)"}   # analysis.ipynb 3.3

_led_all = pd.read_csv(pinned("ledger_latest"), dtype={"split": str})
_led_all["split"] = _led_all["split"].fillna("all")
_led = _led_all[_led_all["cohort"].eq(LEDGER_COHORT) & _led_all["split"].eq(LEDGER_SPLIT)]
assert not _led["profile"].duplicated().any(), "latest.csv should hold one row per profile, label set and split"
_led = _led.set_index("profile")

ledger_cohort = fact("ledger_cohort", LEDGER_COHORT, LEDGER_COHORT, source="ledger_latest")
ledger_pairs = fact("ledger_pairs", int(_led["labelled_pairs"].iloc[0]), _n(_led["labelled_pairs"].iloc[0]),
                    source="ledger_latest")
ledger_targets = fact("ledger_targets", int(_led["targets"].iloc[0]), _n(_led["targets"].iloc[0]),
                      source="ledger_latest")

_LEDGER_FACTS = {}
for _profile, _short in [("b3_all", "b3"), ("selector", "selector"), ("agent_ge1", "agent_ge1"), ("agent_2", "agent_2")]:
    _row = _led.loc[_profile]
    for _outcome in ("peer", "direct"):
        for _metric in ("precision", "recall"):
            _name = f"ledger_{_short}_{_outcome}_{_metric}"
            _x = float(_row[f"{_outcome}_{_metric}_mean"])
            _LEDGER_FACTS[_name] = fact(_name, _x, _pct(_x), source="ledger_latest")
globals().update(_LEDGER_FACTS)


def tbl_ledger() -> pd.DataFrame:
    """The ledger table of v2/09_analysis/analysis.ipynb section 3.3, nearly verbatim, on latest.csv for the label
    set and split above."""
    led = _led.reset_index()

    def ci(m, lo, hi):
        return f"{m:.0%}" if pd.isna(lo) or lo == hi else f"{m:.0%}  [{lo:.0%}, {hi:.0%}]"

    show = pd.DataFrame({
        "date": led.entry_utc.str[:10], "version": led.profile.map(LEDGER_PROFILES).fillna(led.profile),
        "kept": led.kept,
        "any peer: precision": [ci(*r) for r in led[["peer_precision_mean", "peer_precision_mean_lo", "peer_precision_mean_hi"]].to_numpy()],
        "any peer: recall": [ci(*r) for r in led[["peer_recall_mean", "peer_recall_mean_lo", "peer_recall_mean_hi"]].to_numpy()],
        "direct: precision": [ci(*r) for r in led[["direct_precision_mean", "direct_precision_mean_lo", "direct_precision_mean_hi"]].to_numpy()],
        "direct: recall": [ci(*r) for r in led[["direct_recall_mean", "direct_recall_mean_lo", "direct_recall_mean_hi"]].to_numpy()],
    })
    return show


def img_progress() -> Image:
    """progress.png as exported by v2/09_analysis/scripts/progress.py show."""
    return Image(filename=str(pinned("ledger_png")))


# ---------------------------------------------------------------- 2. trait X-learner
_r1 = pd.read_csv(pinned("trait_r1_summary"))
_r2 = pd.read_csv(pinned("trait_r2_summary"))


def _cell(s: pd.DataFrame, trait: str, outcome: str) -> pd.Series:
    r = s[s["trait"].eq(trait) & s["outcome"].eq(outcome) & s["cell"].eq("all")]
    assert len(r) == 1
    return r.iloc[0]


_TRAIT_FACTS = {}
for _s, _trait, _src in [(_r1, "large_customers", "trait_r1_summary"), (_r2, "mission_critical", "trait_r2_summary")]:
    for _outcome in ("direct", "peer"):
        _r = _cell(_s, _trait, _outcome)
        _base = f"trait_{_trait}_{_outcome}"
        _TRAIT_FACTS[_base] = fact(_base, float(_r["lift"]), f"{_signed(100 * _r['lift'])} pp", source=_src)
        _TRAIT_FACTS[_base + "_ci"] = fact(
            _base + "_ci", (float(_r["ci_low"]), float(_r["ci_high"])),
            f"{_signed(100 * _r['ci_low'])} to {_signed(100 * _r['ci_high'])} pp", source=_src)
    _f = _s[_s["trait"].eq(_trait)]
    _TRAIT_FACTS[f"trait_{_trait}_findings"] = fact(f"trait_{_trait}_findings", int(_f["finding"].sum()),
                                                    f"{int(_f['finding'].sum())} of {len(_f)}", source=_src)
globals().update(_TRAIT_FACTS)

trait_r1_findings = fact("trait_r1_findings", int(_r1["finding"].sum()), f"{int(_r1['finding'].sum())} of {len(_r1)}",
                         source="trait_r1_summary")
trait_r2_findings = fact("trait_r2_findings", int(_r2["finding"].sum()), f"{int(_r2['finding'].sum())} of {len(_r2)}",
                         source="trait_r2_summary")
_unsup = sorted(_r2.loc[_r2["cell"].eq("all") & _r2["status"].ne("supported"), "trait"].unique())
trait_r2_unsupported = fact("trait_r2_unsupported", len(_unsup), str(len(_unsup)), source="trait_r2_summary")


def img_trait_lift_r1() -> Image:
    """Round 1 lift with intervals, as exported by v2/09_analysis/analysis.ipynb section 3.1."""
    return Image(filename=str(pinned("trait_r1_png")))


def img_trait_lift_r2() -> Image:
    """Round 2 lift with intervals, as exported by v2/09_analysis/analysis.ipynb section 3.2."""
    return Image(filename=str(pinned("trait_r2_png")))


# ---------------------------------------------------------------- 3. valuation, once (training targets)
# --- copied from v2/08_valuation/scripts/valuation.py (estimate, no_matching, errors, bootstrap) ---
def _estimate(pairs: pd.DataFrame, multiples: pd.Series, how: str = "median") -> pd.DataFrame:
    d = pairs.assign(multiple=pairs["comp"].map(multiples)).dropna(subset=["multiple"])
    g = d.groupby("target")
    assert how == "median"
    return pd.DataFrame({"estimate": g["multiple"].median(), "comps": g.size()})


def _no_matching(targets, pool, multiples: pd.Series) -> pd.DataFrame:
    m = multiples.reindex(list(pool)).dropna()
    rows = {t: (m.drop(t, errors="ignore").median(), len(m.drop(t, errors="ignore"))) for t in targets}
    return pd.DataFrame.from_dict(rows, orient="index", columns=["estimate", "comps"])


def _errors(result: pd.DataFrame, actual: pd.Series) -> pd.DataFrame:
    out = result.join(actual.rename("actual"), how="left")
    out["error %"] = 100 * (out["estimate"] - out["actual"]) / out["actual"]
    return out


def _bootstrap(results: dict[str, pd.DataFrame], actual: pd.Series, baseline: str,
               n_boot: int = 2000, seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = _errors(results[baseline], actual)["error %"].abs()
    rows = []
    for name, result in results.items():
        ape = _errors(result, actual)["error %"].abs().dropna()
        pick = rng.integers(0, len(ape), (n_boot, len(ape)))
        lo, hi = np.percentile(np.median(ape.to_numpy()[pick], axis=1), [2.5, 97.5])
        row = {"comp rule": name, "targets": len(ape), "median abs % error": ape.median(),
               "error 2.5%": lo, "error 97.5%": hi, "gain on baseline": np.nan, "gain 2.5%": np.nan, "gain 97.5%": np.nan}
        both = ape.index.intersection(base.dropna().index)
        if name != baseline and len(both):
            a, b = ape[both].to_numpy(), base[both].to_numpy()
            pick = rng.integers(0, len(both), (n_boot, len(both)))
            gain = np.median(b[pick], axis=1) - np.median(a[pick], axis=1)
            row.update({"gain on baseline": np.median(b) - np.median(a),
                        "gain 2.5%": np.percentile(gain, 2.5), "gain 97.5%": np.percentile(gain, 97.5)})
        rows.append(row)
    return pd.DataFrame(rows).set_index("comp rule")
# --- end of copy ---


_fin = pd.read_csv(pinned("val_financials"), dtype={"IQ_COMPANY_ID": str})
_mult = _fin.set_index("IQ_COMPANY_ID")["target_ev_to_ebitda"].astype(float)
_split = pd.read_csv(pinned("val_split"), dtype={"IQ_COMPANY_ID": str})
_training = _split.loc[_split["sample"].eq("training"), "IQ_COMPANY_ID"].tolist()
_top = pd.read_csv(pinned("b3_candidates"), dtype={"target": str, "comp": str})
_b3 = _top[_top["selected"]]
_j = pd.read_csv(pinned("sel_judgments"), dtype={"target": str, "comp": str})
_kept = _b3.merge(_j.loc[_j["score"] == 1, ["target", "comp"]], on=["target", "comp"])
assert set(_b3["target"]) <= set(_training), "every valued target is a training target"

# valuation.ipynb section 3.2: same targets for every rule (the dict order fixes the bootstrap draws)
_common = sorted(_kept["target"].unique())
_same = {"no matching": _no_matching(_common, _training, _mult),
         "B3 (median)": _estimate(_b3[_b3.target.isin(_common)], _mult, how="median"),
         "selector kept (median)": _estimate(_kept, _mult, how="median")}
_val = _bootstrap(_same, _mult[_common], "no matching")
# valuation.ipynb section 3.1: no matching on all training targets (its first row; the bootstrap draws for it come
# first, so they do not depend on the other rules)
_all = _bootstrap({"no matching": _no_matching(_training, _training, _mult)}, _mult[_training], "no matching")

_vsrc = "val_financials+val_split+b3_candidates+sel_judgments"
val_targets = fact("val_targets", int(_val.loc["selector kept (median)", "targets"]),
                   _n(_val.loc["selector kept (median)", "targets"]), source=_vsrc)
val_err_no_matching = fact("val_err_no_matching", float(_val.loc["no matching", "median abs % error"]),
                           f"{_val.loc['no matching', 'median abs % error']:.1f}%", source=_vsrc)
val_err_b3 = fact("val_err_b3", float(_val.loc["B3 (median)", "median abs % error"]),
                  f"{_val.loc['B3 (median)', 'median abs % error']:.1f}%", source=_vsrc)
val_err_selector = fact("val_err_selector", float(_val.loc["selector kept (median)", "median abs % error"]),
                        f"{_val.loc['selector kept (median)', 'median abs % error']:.1f}%", source=_vsrc)
_g = _val.loc["selector kept (median)"]
val_gain_selector = fact("val_gain_selector", float(_g["gain on baseline"]), f"{_signed(_g['gain on baseline'])} pp",
                         source=_vsrc)
val_gain_selector_ci = fact("val_gain_selector_ci", (float(_g["gain 2.5%"]), float(_g["gain 97.5%"])),
                            f"{_signed(_g['gain 2.5%'])} to {_signed(_g['gain 97.5%'])} pp", source=_vsrc)
val_training_targets = fact("val_training_targets", len(_training), _n(len(_training)), source="val_split")
val_err_no_matching_all = fact("val_err_no_matching_all", float(_all.loc["no matching", "median abs % error"]),
                               f"{_all.loc['no matching', 'median abs % error']:.1f}%",
                               source="val_financials+val_split")
