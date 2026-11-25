"""Facts for Describing a company (describing.qmd). Pattern: see ch2_data.py.

Sources: the 12 general facets (v2/current.toml [profiles] general, Sonnet, prompt 2026-10-25k) and their definitions
in v2/02_profiles/scripts/facets.py; the tags and traits (v2/current.toml [traits] and [traits_r2] tables), their
questions in traits.py, and the 30-company double-fill check (stability.csv per round, keep rule in
trait_stability.py). Code files are parsed with ast, never imported: facets.py and trait_stability.py import the v2
path setup and pydantic, which the site's light environment doesn't have.
"""

from __future__ import annotations

import ast

import matplotlib.pyplot as plt
import pandas as pd

from facts.common import fact, pinned


def _module(pin: str) -> ast.Module:
    return ast.parse(pinned(pin).read_text(encoding="utf-8"))


def _assigned(tree: ast.Module, name: str) -> ast.expr:
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(getattr(t, "id", None) == name for t in targets):
            return node.value
    raise ValueError(f"{name} not found")


def _calls(tree: ast.Module, name: str, fields: list[str]) -> list[dict]:
    """`NAME = [Cls(a, b, ..., key=value), ...]` as dicts: positional arguments named by `fields`, plus keywords."""
    out = []
    for call in _assigned(tree, name).elts:
        row = dict(zip(fields, (ast.literal_eval(a) for a in call.args)))
        row.update({k.arg: ast.literal_eval(k.value) for k in call.keywords})
        out.append(row)
    return out


def _n(name: str, value, source: str):
    return fact(name, int(value), f"{int(value):,}", source=source)


def _pct(name: str, value: float, source: str, digits: int = 1):
    return fact(name, float(value), f"{100 * float(value):.{digits}f}%", source=source)


# ---- the 12 general facets
_facet_defs = _calls(_module("facets_code"), "FACETS", ["name", "label", "captures", "examples"])
for _i, _f in enumerate(_facet_defs, start=1):
    _f["id"] = f"F{_i}"                                       # as facets.FACET_ID
_general = pd.read_csv(pinned("facets_general"), dtype=str).fillna("")
_names = [f["name"] for f in _facet_defs]

n_facets = _n("n_facets", len(_facet_defs), "facets_code")
facet_names = fact("facet_names", [f["label"] for f in _facet_defs],
                   ", ".join(f["label"] for f in _facet_defs), source="facets_code")

# where each value comes from (v2/02_profiles/profiles.ipynb 3.2, cell 10): model knowledge, or website lines it cites
_src = pd.DataFrame({n: _general[f"{n}_source"] for n in _names})
_kind = _src.apply(lambda col: col.map(
    lambda s: "website" if "http" in s else ("model knowledge" if "model knowledge" in s else "none")))
facet_share_model = _pct("facet_share_model",
                         (_kind == "model knowledge").sum().sum() / (_kind != "none").sum().sum(), "facets_general")
n_facet_values_web = _n("n_facet_values_web", (_kind == "website").sum().sum(), "facets_general")
n_facet_web_companies = _n("n_facet_web_companies", (_kind == "website").any(axis=1).sum(), "facets_general")
n_facet_unknown = _n("n_facet_unknown",
                     sum(_general[f"{n}_status"].eq("unknown").sum() for n in _names), "facets_general")

# ---- tags T1-T4 and traits E1-E10
_traits_tree = _module("traits_code")
_questions = (_calls(_traits_tree, "QUESTIONS", ["id", "name", "kind", "question", "yes", "no"])
              + _calls(_traits_tree, "ROUND_2", ["id", "name", "kind", "question", "yes", "no"]))
_t1 = pd.read_csv(pinned("traits_r1"), dtype=str)
_t2 = pd.read_csv(pinned("traits_r2"), dtype=str)
_answers = _t1.set_index("IQ_COMPANY_ID").join(
    _t2.set_index("IQ_COMPANY_ID")[[q["name"] for q in _questions if q["name"] in _t2.columns]])
_stab = pd.concat([pd.read_csv(pinned("traits_test_r1")), pd.read_csv(pinned("traits_test_r2"))], ignore_index=True)
_keep = _module("traits_stability_code")

n_tags = _n("n_tags", sum(q["kind"] == "tag" for q in _questions), "traits_code")
n_traits = _n("n_traits", sum(q["kind"] == "trait" for q in _questions), "traits_code")
n_traits_filled = _n("n_traits_filled",
                     min(_t1["llm_status"].eq("ok").sum(), _t2["llm_status"].eq("ok").sum()), "traits_r1+traits_r2")


def _rates() -> pd.DataFrame:
    """yes / no / unknown share per question over the full fill (both rounds), in the order of traits.py."""
    rows = []
    for q in _questions:
        a = _answers[q["name"]]
        rows.append({"id": q["id"], "name": q["name"], "kind": q["kind"],
                     **{v: float((a == v).mean()) for v in ("yes", "no", "unknown")}})
    return pd.DataFrame(rows)


_r = _rates()
trait_unknown_max = _pct("trait_unknown_max", _r.loc[_r["kind"] == "trait", "unknown"].max(), "traits_r1+traits_r2")
n_trait_known = _n("n_trait_known", _t1["knows_company"].eq("True").sum(), "traits_r1")
n_trait_pages = _n("n_trait_pages", _t1["had_pages"].eq("True").sum(), "traits_r1")

# the 30-company double fill: flips between the two runs, unknowns, and the keep rule
trait_test_n = _n("trait_test_n", _stab["companies"].max(), "traits_test_r1+traits_test_r2")
trait_flips_max = _n("trait_flips_max", _stab["flips"].max(), "traits_test_r1+traits_test_r2")
trait_flip_share = _pct("trait_flip_share", _stab["flips"].sum() / _stab["answered_both"].sum(),
                        "traits_test_r1+traits_test_r2")
trait_test_unknown_max = _n("trait_test_unknown_max", round((_stab["unknown_rate_max"] * _stab["companies"]).max()),
                            "traits_test_r1+traits_test_r2")
trait_keep_flip_max = _pct("trait_keep_flip_max", ast.literal_eval(_assigned(_keep, "MAX_FLIP")),
                           "traits_stability_code", digits=0)
trait_keep_unknown_max = _pct("trait_keep_unknown_max", ast.literal_eval(_assigned(_keep, "MAX_UNKNOWN")),
                              "traits_stability_code", digits=0)


# ---- tables and figures

def facets_table() -> pd.DataFrame:
    """The twelve facets. Ported from v2/02_profiles/profiles.ipynb 3.1 (cell 7, itself from v1
    comp_universe_and_facets.ipynb 3.1) nearly verbatim; the definitions are parsed from facets.py instead of
    imported, so `f.kind` is recomputed as in facets.Facet.kind."""
    def kind(f: dict) -> str:
        return "text" if not f.get("categories") else ("any of" if f.get("several") else "one of")
    return pd.DataFrame([{"ID": f["id"], "Facet": f["label"], "What it captures": f["captures"],
                          "Example values": f["examples"],
                          "Categories": f"{kind(f)}: {', '.join(f['categories'])}" if f.get("categories") else ""}
                         for f in _facet_defs])


def traits_table() -> pd.DataFrame:
    """Every tag and trait: the question the model reads (traits.py), the full fill's answers (533 companies) and the
    30-company double fill (flips between the two runs, of companies answered yes/no both times)."""
    s = _stab.set_index("id")
    t = _r.assign(question=[q["question"] for q in _questions])
    return pd.DataFrame({
        "ID": t["id"], "kind": t["kind"], "question": t["question"],
        **{v: t[v].map(lambda x: f"{100 * x:.1f}%") for v in ("yes", "no", "unknown")},
        "test flips": [f"{s.at[i, 'flips']}/{s.at[i, 'answered_both']}" for i in t["id"]],
    })


def trait_label(name: str) -> str:
    q = next(q for q in _questions if q["name"] == name)
    return f"{q['id']} {name.replace('_', ' ')}"


def trait_rates_figure():
    """Stacked bars, one per trait E1-E10: share yes, no and unknown over the full fill. New code (no teammate figure
    of the yes rates exists); colours: slot 1 of the dataviz reference palette for yes, slot 2 for unknown, grey no."""
    t = _r[_r["kind"] == "trait"].iloc[::-1]             # E1 at the top
    labels = [trait_label(n) for n in t["name"]]
    fig, ax = plt.subplots(figsize=(8, 0.4 * len(t) + 1.2))
    left = pd.Series(0.0, index=t.index)
    for col, color in (("yes", "#2a78d6"), ("unknown", "#eb6834"), ("no", "#d9d8d3")):
        ax.barh(labels, t[col] * 100, left=left * 100, color=color, edgecolor="white", linewidth=1.5, height=0.7,
                label=col)
        left = left + t[col]
    for y, (v, u) in enumerate(zip(t["yes"], t["unknown"])):       # label after the yes and unknown segments
        ax.text((v + u) * 100 + 1, y, f"{100 * v:.1f}%", va="center", fontsize=9, color="#0b0b0b")
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of companies", color="#52514e", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#b0afa8")
    ax.tick_params(colors="#52514e", labelsize=9)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=9)
    fig.tight_layout()
    return fig

