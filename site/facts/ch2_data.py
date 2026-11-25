"""Facts for Data (data.qmd).

Pattern for every chapter module: read only pinned files (pinned("<pin name>")), compute the number with code, and
register it with fact(name, value, text, source=<pin name(s), joined with "+">). The chapter's text then prints it
inline with `{python} f.<name>`.

Sources: the universe and split runs named in v2/current.toml [universe] (outputs-local/v1a/01_universe/, read in
place) and the website scrape log (outputs-local/website_scrape/scrape_log.csv). No financial value is read here:
companies.csv carries only the 3-30 filter's outcome (kept_multiple, drop_reason), never the multiple itself.
"""

from __future__ import annotations

import ast
import json

import matplotlib.pyplot as plt
import pandas as pd

from facts.common import fact, pinned

_companies = pd.read_csv(pinned("companies"), dtype=str)        # the companies supplied, one flag per filter
_universe = pd.read_csv(pinned("universe"), dtype=str)          # the companies kept
_universe_run = json.loads(pinned("universe_run").read_text(encoding="utf-8"))
_split = pd.read_csv(pinned("split"), dtype=str)
_split_run = json.loads(pinned("split_run").read_text(encoding="utf-8"))
_scrape = pd.read_csv(pinned("scrape_log"), dtype=str)

# SIC codes are strings, zero-padded (AGENTS.md): the 2-digit major group keeps its leading zero (e.g. "07").
for _df in (_companies, _universe, _split):
    _df["target_sic2_code"] = _df["target_sic2_code"].str.zfill(2)


def _flag(col: str) -> pd.Series:
    return _companies[col].eq("True")


def _n(name: str, value: int, source: str):
    return fact(name, int(value), f"{int(value):,}", source=source)


# ---- from the list supplied to the universe (recipe steps 1-2)
n_supplied = _n("n_supplied", len(_companies), "companies")
n_us_hq = _n("n_us_hq", _flag("us_hq").sum(), "companies")

_lo, _hi = _universe_run["ev_to_ebitda_range"]
ev_ebitda_min = fact("ev_ebitda_min", _lo, f"{_lo:g}", source="universe_run")
ev_ebitda_max = fact("ev_ebitda_max", _hi, f"{_hi:g}", source="universe_run")

_dropped = _companies[_flag("candidate") & ~_flag("kept_multiple")]
n_dropped_multiple = _n("n_dropped_multiple", len(_dropped), "companies")
n_dropped_above = _n("n_dropped_above", _dropped["drop_reason"].str.startswith("above").sum(), "companies")
n_dropped_below = _n("n_dropped_below", _dropped["drop_reason"].str.startswith("below").sum(), "companies")

n_universe = fact("n_universe", len(_universe), f"{len(_universe):,}", source="universe")
n_sic2 = _n("n_sic2", _universe["target_sic2_code"].nunique(), "universe")

# ---- the training / holdout split
_sample = _split["sample"].value_counts()
n_training = _n("n_training", _sample.get("training", 0), "split")
n_holdout = _n("n_holdout", _sample.get("holdout", 0), "split")
train_share = fact("train_share", _split_run["train_share"], f"{_split_run['train_share']:.0%}", source="split_run")
n_strata = _n("n_strata", _split["stratum"].nunique(), "split")
min_stratum = _n("min_stratum", _split_run["min_stratum"], "split_run")
n_split_forced = _n("n_split_forced", _split["showcase"].eq("True").sum(), "split")

# ---- website text (the scrape covers every company supplied; counted here for the companies kept)
_web = _scrape[_scrape["IQ_COMPANY_ID"].isin(_universe["IQ_COMPANY_ID"])].assign(
    words=lambda d: d["word_count"].astype(int), pages=lambda d: d["pages"].astype(int))
n_web_text = _n("n_web_text", (_web["words"] > 0).sum(), "scrape_log+universe")
n_web_no_text = _n("n_web_no_text", (_web["words"] == 0).sum(), "scrape_log+universe")
web_max_pages = _n("web_max_pages", _web["pages"].max(), "scrape_log")
_median_words = float(_web.loc[_web["words"] > 0, "words"].median())
web_words_median = fact("web_words_median", _median_words, f"{_median_words:,.0f}", source="scrape_log+universe")


# ---- tables and figures

def funnel_table() -> pd.DataFrame:
    """Companies left after each filter.

    Ported from v2/01_universe/universe.ipynb, section 3.1 (cell 7), nearly verbatim. The notebook rebuilds
    `companies` with universe.build_universe() from the snapshot (data-local/, not in git); here it is the saved
    companies.csv of the same run. The 3-30 label is built from the run's range instead of typed.
    """
    companies = _companies.copy()
    for col in ("us_hq", "sic2_in_target_list", "candidate", "kept_multiple", "in_universe"):
        companies[col] = companies[col].eq("True")
    funnel = pd.Series({
        "companies in the snapshot": len(companies),
        "HQ in the US": int(companies["us_hq"].sum()),
        "SIC2 in the target list": int(companies["sic2_in_target_list"].sum()),
        "candidates (both)": int(companies["candidate"].sum()),
        f"EV/EBITDA within {_lo:g}-{_hi:g}": int(companies["kept_multiple"].sum()),
        "in the universe": int(companies["in_universe"].sum()),
    })
    return funnel.to_frame("companies")


def _divisions() -> list[tuple[int, int, str]]:
    """SIC divisions (first and last 2-digit group, letter and name) from DIVISIONS in v2/01_universe/scripts/split.py.

    Parsed, not imported: split.py imports the v2 path setup, which the site's light environment doesn't have.
    """
    tree = ast.parse(pinned("split_code").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "DIVISIONS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("DIVISIONS not found in split.py")


def sic_division(sic2: str) -> str:
    """As split.sic_division."""
    return next((name for lo, hi, name in _divisions() if lo <= int(sic2) <= hi), "unknown")


def companies_by_division() -> pd.DataFrame:
    """Companies kept per SIC division, training and holdout, largest division first."""
    div = _split["target_sic2_code"].map(sic_division)
    t = pd.crosstab(div, _split["sample"]).reindex(columns=["training", "holdout"], fill_value=0)
    t["companies"] = t.sum(axis=1)
    return t.sort_values("companies", ascending=False)


def division_figure():
    """Horizontal stacked bars: companies per SIC division, training then holdout. New code (the 01 notebook has
    tables only, no figure); colours are slots 1-2 of the dataviz reference palette."""
    t = companies_by_division().iloc[::-1]          # largest at the top
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(t) + 1.2))
    left = pd.Series(0, index=t.index)
    for col, color in (("training", "#2a78d6"), ("holdout", "#eb6834")):
        ax.barh(t.index, t[col], left=left, color=color, edgecolor="white", linewidth=1.5, height=0.7, label=col)
        left = left + t[col]
    for y, total in enumerate(t["companies"]):
        ax.text(total + 2, y, f"{total:,}", va="center", fontsize=9, color="#52514e")
    ax.set_xlim(0, t["companies"].max() * 1.1)
    ax.set_xlabel("companies", color="#52514e", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#b0afa8")
    ax.tick_params(colors="#52514e", labelsize=9)
    ax.xaxis.grid(True, color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    fig.tight_layout()
    return fig
