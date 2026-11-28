"""Direct vs adjacent peers on the rubric v3 headline labels, by industry group. Descriptive only.

Reads the v3_final cohort (311 pairs, 67 targets; grade 2 direct, 1 adjacent, 0 not a peer), the judge run's
per-question answers (Matthew, Barbara, GPT-Terra; rubric_v3.scores on filled_with_terra.csv), B3's candidate
lists (rank) and the saved keeps of three pipeline profiles (selector, agent_ge1, agent_2). The labelled pairs
are B3's candidates, and not every candidate of every target was labelled: every count is "of the labelled B3
candidates", not of the universe.

Industry group: the sector group of the target's 4-digit SIC code (03_retrieval/scripts/sectors.py: SIC4 ->
Fama-French 49 -> sector, the sector B3's "Fiona sub-sector" facets hang off), with the small sectors merged so
every group has at least 5 targets (GROUPS below). Table 1 is also written by the unmerged sector and by SIC
division. Groups with fewer than MIN_TARGETS targets are flagged (small_group).

Tables (outputs-local/v2/09_analysis/peer_mix/<UTC>/):
  t1_mix_by_group.csv, t1_mix_by_sector.csv, t1_mix_by_sic_division.csv
      targets, labelled pairs, per-target mean count and share of direct / adjacent / not; share of targets with
      at least one direct, with no direct but at least one adjacent, with neither.
  t2_adjacent_patterns.csv   for grade-1 pairs, which questions fail, by answer source and group
  t2_question_no_rates.csv   per final grade, the share of pairs each source answers no to each question
  t2_same_industry.csv       per final grade, the share of pairs whose comp shares the target's SIC2 / FF49 / sector
  t3_b3_rank.csv             B3 rank of direct vs adjacent vs not, by group
  t4_overall_call.csv        final overall-call yes-rate by final grade, by group
  t5_keep_rates.csv          keep rates of selector / agent_ge1 / agent_2 by final grade, by group
  targets.csv, pairs.csv     the per-target and per-pair tables behind them
  manifest.json              input paths and sha256, script sha256

Reads saved runs only: no model calls. No financial fields are read.

  uv run python v2/09_analysis/scripts/peer_mix.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

KEY = ["target_id", "comp_id"]
QUESTIONS = ["same_product", "same_customers", "same_revenue_model", "same_chain_step"]
GRADES = {2: "direct", 1: "adjacent", 0: "not"}
PROFILES = ["selector", "agent_ge1", "agent_2"]
MIN_TARGETS = 5
ALL = "all"

# sector (sectors.SECTOR_GROUPS) -> coarse group; small sectors merged so each group has >= 5 of the 67 targets
GROUPS = {
    "financials": "financials",
    "manufacturing": "manufacturing",
    "construction_real_estate": "construction_real_estate",
    "consumer_products": "consumer",
    "consumer_venues": "consumer",
    "business_services": "business_services",
    "software": "software",
    "healthcare": "healthcare",
    "energy_resources": "energy_transport_telecom",
    "distribution_transport": "energy_transport_telecom",
    "media_telecom": "energy_transport_telecom",
    "other": "other",
}

SIC_DIVISIONS = [  # (first SIC2, last SIC2, division)
    (1, 9, "A agriculture"), (10, 14, "B mining"), (15, 17, "C construction"), (20, 39, "D manufacturing"),
    (40, 49, "E transport, communications, utilities"), (50, 51, "F wholesale"), (52, 59, "G retail"),
    (60, 67, "H finance, insurance, real estate"), (70, 89, "I services"), (91, 99, "J public administration"),
]

# which questions fail on an adjacent pair
PATTERNS = ["product no, customers yes", "product yes, customers no", "product+customers yes, revenue model no",
            "product+customers yes, chain step no", "product+customers yes, revenue model and chain step no"]


def sic_division(sic4: str) -> str:
    s2 = int(str(sic4)[:2])
    for lo, hi, name in SIC_DIVISIONS:
        if lo <= s2 <= hi:
            return name
    return "other"


def industry(ids: pd.Series | list) -> pd.DataFrame:
    """Per company id: sic4 (4-char, zero-padded), sic2, sic_division, ff49, sector, group."""
    import sectors
    from project_data import normalize_sic_codes
    uni = pd.read_csv(v2.path(v2.current()["universe"]["universe"]), dtype=str)
    uni = normalize_sic_codes(uni).set_index("IQ_COMPANY_ID")
    st = sectors.sector_table(uni)
    out = pd.DataFrame({"sic4": st["sic4"], "sic2": st["sic4"].str[:2], "ff49": st["ff49"], "sector": st["sector"]})
    out["sic_division"] = out["sic4"].map(sic_division)
    out["group"] = out["sector"].map(GROUPS)
    out = out.reindex(pd.Index(pd.Series(ids).astype(str).unique(), name="id"))
    if out["sector"].isna().any():
        raise ValueError(f"no SIC code for {list(out.index[out['sector'].isna()])}")
    return out


def pattern(product, customers, revenue, chain) -> str | None:
    """Which questions fail, for answers that score 1 (adjacent); None if the answers don't score 1."""
    if None in (product, customers, revenue, chain) or any(pd.isna(x) for x in (product, customers, revenue, chain)):
        return None
    p, c, r, s = (bool(x) for x in (product, customers, revenue, chain))
    if p and c and r and s:
        return None          # direct
    if not p and not c:
        return None          # not a peer
    if not p:
        return PATTERNS[0]
    if not c:
        return PATTERNS[1]
    if not r and not s:
        return PATTERNS[4]
    return PATTERNS[2] if not r else PATTERNS[3]


def mix_table(pairs: pd.DataFrame, by: str) -> pd.DataFrame:
    """Per group (and all): targets, pairs, per-target mean count and pooled share of direct / adjacent / not,
    share of targets with >= 1 direct, with 0 direct but >= 1 adjacent, with neither."""
    g = pairs.assign(**{n: pairs["grade"].eq(k) for k, n in GRADES.items()})
    per_t = g.groupby(["target_id", by])[list(GRADES.values())].sum().reset_index()
    rows = []
    for name, t in [*per_t.groupby(by), (ALL, per_t)]:
        p = g[g[by] == name] if name != ALL else g
        n = len(p)
        row = {by: name, "targets": len(t), "small_group": len(t) < MIN_TARGETS, "labelled_pairs": n,
               "pairs_per_target": n / len(t)}
        for k in GRADES.values():
            row[f"{k}_per_target"] = t[k].mean()
        for k in GRADES.values():
            row[f"{k}_share"] = t[k].sum() / n
        row["adjacent_per_direct"] = t["adjacent"].sum() / t["direct"].sum() if t["direct"].sum() else np.nan
        row["targets_ge1_direct"] = (t["direct"] >= 1).mean()
        row["targets_0_direct_ge1_adjacent"] = ((t["direct"] == 0) & (t["adjacent"] >= 1)).mean()
        row["targets_no_peer"] = ((t["direct"] == 0) & (t["adjacent"] == 0)).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def _groups(d: pd.DataFrame, by: str = "group"):
    yield ALL, d
    for name, x in d.groupby(by):
        yield name, x


def _size(pairs: pd.DataFrame, name: str, by: str = "group") -> dict:
    """The group's target count (all its labelled targets, not only those in the row) and the small-group flag."""
    n = pairs["target_id"].nunique() if name == ALL else pairs.loc[pairs[by] == name, "target_id"].nunique()
    return {"group_targets": n, "small_group": n < MIN_TARGETS}


def adjacent_patterns(pairs: pd.DataFrame, answers: pd.DataFrame) -> pd.DataFrame:
    """For final grade-1 pairs, the count and share of each failing-question pattern, per source:
    terra (the judge, all grade-1 pairs), matthew / barbara (the pairs both humans score 1) and humans_same (those
    pairs where both humans fail the same way). Pairs whose source answers don't score 1 are 'source not adjacent'."""
    a = pairs[pairs["grade"].eq(1)].merge(answers, on=KEY, how="left", validate="one_to_one")
    both = a["score_matthew"].eq(1) & a["score_barbara"].eq(1)
    for r in ("matthew", "barbara", "terra"):
        a[f"pattern_{r}"] = [pattern(*row) for row in a[[f"{q}_{r}" for q in QUESTIONS]].itertuples(index=False)]
    a["pattern_humans_same"] = np.where(a["pattern_matthew"].eq(a["pattern_barbara"]), a["pattern_matthew"], None)
    sources = {"terra": a, "matthew": a[both], "barbara": a[both], "humans_same": a[both]}
    rows = []
    for src, d in sources.items():
        for name, x in _groups(d):
            col = x[f"pattern_{'humans_same' if src == 'humans_same' else src}"]
            label = col.fillna("humans differ" if src == "humans_same" else "source not adjacent")
            counts = label.value_counts()
            for pat in [*PATTERNS, "humans differ" if src == "humans_same" else "source not adjacent"]:
                rows.append({"source": src, "group": name, **_size(pairs, name), "pairs": len(x),
                             "targets": x["target_id"].nunique(), "pattern": pat, "count": int(counts.get(pat, 0)),
                             "share": counts.get(pat, 0) / len(x) if len(x) else np.nan})
    return pd.DataFrame(rows)


def question_no_rates(pairs: pd.DataFrame, answers: pd.DataFrame) -> pd.DataFrame:
    """Per source and final grade: the share of pairs the source answers no to each question."""
    a = pairs.merge(answers, on=KEY, how="left", validate="one_to_one")
    rows = []
    for r in ("matthew", "barbara", "terra"):
        for g, x in a.groupby("grade"):
            row = {"source": r, "grade": int(g), "label": GRADES[int(g)], "pairs": len(x)}
            for q in QUESTIONS:
                v = x[f"{q}_{r}"].dropna().astype(bool)
                row[f"{q}_no"] = (~v).mean() if len(v) else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def same_industry(pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, x in _groups(pairs):
        for g, y in x.groupby("grade"):
            rows.append({"group": name, **_size(pairs, name), "grade": int(g), "label": GRADES[int(g)],
                         "pairs": len(y), "same_sic2": (y["sic2"] == y["comp_sic2"]).mean(),
                         "same_ff49": (y["ff49"] == y["comp_ff49"]).mean(),
                         "same_sector": (y["sector"] == y["comp_sector"]).mean()})
    return pd.DataFrame(rows)


def rank_table(pairs: pd.DataFrame) -> pd.DataFrame:
    """B3 rank by final grade and group: mean and median rank, share in B3's top 3, mean position among the
    target's B3 list as a fraction of its length (b3_position / b3_list_len)."""
    rows = []
    for name, x in _groups(pairs):
        for g, y in x.groupby("grade"):
            rows.append({"group": name, **_size(pairs, name), "grade": int(g), "label": GRADES[int(g)],
                         "pairs": len(y), "targets": y["target_id"].nunique(), "rank_mean": y["rank"].mean(), "rank_median": y["rank"].median(),
                         "share_rank_le3": y["rank"].le(3).mean(),
                         "position_frac_mean": (y["b3_position"] / y["b3_list_len"]).mean()})
    return pd.DataFrame(rows)


def rate_table(pairs: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Per group and final grade: n and the yes-rate of each 0/1 column."""
    rows = []
    for name, x in _groups(pairs):
        for g, y in x.groupby("grade"):
            row = {"group": name, **_size(pairs, name), "grade": int(g), "label": GRADES[int(g)], "pairs": len(y),
                   "targets": y["target_id"].nunique()}
            for c in cols:
                v = y[c].dropna().astype(float)
                row[f"{c}_n"], row[f"{c}_rate"] = len(v), v.mean() if len(v) else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def load_answers(cur: dict) -> tuple[pd.DataFrame, Path]:
    import rubric_v3 as rv3
    path = v2.path(cur["rubric_v3"]["judge"]) / "filled_with_terra.csv"
    s = rv3.scores(rv3._read(path), ["matthew", "barbara", "terra"])
    s = s[~s["is_anchor"]]
    cols = [f"{q}_{r}" for r in ("matthew", "barbara", "terra") for q in QUESTIONS]
    return s[[*KEY, *cols, "score_matthew", "score_barbara", "score_terra"]].reset_index(drop=True), path


def build(cur: dict | None = None) -> tuple[dict[str, pd.DataFrame], dict]:
    import cohorts
    import progress as pr
    cur = cur or v2.current()
    f = cohorts.load("v3_final")
    f = f[f["grade"].notna()]
    pairs = f[[*KEY, "target_ticker", "comp_ticker", "grade", "overall_call", "tie_broken_direct",
               "tie_broken_peer"]].copy()
    pairs["grade"] = pairs["grade"].astype(int)
    pairs["overall_call"] = pairs["overall_call"].map(lambda v: np.nan if pd.isna(v) else float(bool(v)))
    ind = industry(pd.concat([pairs["target_id"], pairs["comp_id"]]))
    tcols = ["sic4", "sic2", "sic_division", "ff49", "sector", "group"]
    pairs = pairs.join(ind[tcols], on="target_id").join(
        ind[["sic2", "ff49", "sector"]].add_prefix("comp_"), on="comp_id")
    b3 = pr._b3(cur)
    b3 = b3.assign(b3_position=b3.groupby("target_id")["rank"].rank(method="first").astype(int),
                   b3_list_len=b3.groupby("target_id")["rank"].transform("size"))
    pairs = pairs.merge(b3, on=KEY, how="left", validate="one_to_one")
    if pairs["rank"].isna().any():
        raise ValueError("labelled pairs missing from B3's candidate list")
    runs = {}
    for p in PROFILES:
        spec = pr.built_in(p, cur)
        runs[p] = spec["run"]
        k = spec["keeps"].rename(columns={"keep": f"keep_{p}"})
        pairs = pairs.merge(k.assign(**{f"keep_{p}": k[f"keep_{p}"].astype(float)}), on=KEY, how="left",
                            validate="one_to_one")
    answers, answers_path = load_answers(cur)

    targets = pairs.groupby("target_id").agg(
        target_ticker=("target_ticker", "first"), **{c: (c, "first") for c in tcols},
        labelled_pairs=("comp_id", "size"), b3_list_len=("b3_list_len", "first"),
        direct=("grade", lambda g: int((g == 2).sum())), adjacent=("grade", lambda g: int((g == 1).sum())),
        not_peer=("grade", lambda g: int((g == 0).sum()))).reset_index()

    keep_cols = [f"keep_{p}" for p in PROFILES]
    tables = {
        "t1_mix_by_group": mix_table(pairs, "group"),
        "t1_mix_by_sector": mix_table(pairs, "sector"),
        "t1_mix_by_sic_division": mix_table(pairs, "sic_division"),
        "t2_adjacent_patterns": adjacent_patterns(pairs, answers),
        "t2_question_no_rates": question_no_rates(pairs, answers),
        "t2_same_industry": same_industry(pairs),
        "t3_b3_rank": rank_table(pairs),
        "t4_overall_call": rate_table(pairs, ["overall_call"]),
        "t5_keep_rates": rate_table(pairs, keep_cols),
        "targets": targets,
        "pairs": pairs,
    }
    inputs = {"v3_final": v2.path(cur["rubric_v3"]["final"]) / "final.csv",
              "judge_answers": answers_path,
              "universe": v2.path(cur["universe"]["universe"]),
              "b3_candidates": v2.path(cur["retrieval"]["candidates"]) / "candidates.csv",
              "selector": v2.path(cur["selection"]["judgments"])}
    for i, p in enumerate(pr.built_in("agent_ge1", cur)["run_files"]):
        inputs[f"agent_{i}"] = Path(p)
    return tables, {"inputs": inputs, "profiles": runs}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    tables, meta = build()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or v2.out("09_analysis") / "peer_mix" / stamp
    out.mkdir(parents=True, exist_ok=True)
    for name, t in tables.items():
        t.to_csv(out / f"{name}.csv", index=False)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
    rel = lambda p: Path(p).resolve().relative_to(v2.ROOT.resolve()).as_posix()  # noqa: E731
    manifest = {
        "created_at": stamp, "script": "v2/09_analysis/scripts/peer_mix.py", "script_sha256": sha(__file__),
        "cohort": "v3_final", "industry_group": "sector of the target's SIC4 (sectors.py, via FF49), small sectors "
        f"merged: {GROUPS}", "min_targets_flag": MIN_TARGETS, "profiles": meta["profiles"],
        "inputs": {k: {"path": rel(p), "sha256": sha(p)} for k, p in meta["inputs"].items()},
        "outputs": sorted(f"{n}.csv" for n in tables),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    with pd.option_context("display.width", 250, "display.max_columns", 40, "display.max_rows", 300,
                           "display.float_format", "{:.2f}".format):
        for name, t in tables.items():
            if name not in ("targets", "pairs"):
                print(f"\n== {name}\n{t.to_string(index=False)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
