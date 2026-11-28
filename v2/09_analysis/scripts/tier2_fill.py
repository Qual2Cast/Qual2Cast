"""EXPERIMENTAL tier-2 fill of thin comp profiles (team decision 2026-11-28, Michael; EXPERIMENTAL everywhere).

A target's comp profile = tier 1 (every comp the selector keeps; it is asked for "the same business", i.e. direct
peers) + tier 2: when tier 1 has fewer than K = 3 comps, fill up to 3 with the best remaining comps that are at
least adjacent peers (rubric v3: product or customers in common, not all four questions), flagged as adjacent.
This script tries three fill rules on saved runs only (no model calls) and scores them on the rubric v3 labels.

Targets: the 67 of the v3_final cohort (311 labelled pairs, grade 2 direct / 1 adjacent / 0 not a peer).

Tier 1 (`--tier1` sources):
  baseline   progress.built_in("selector"): the pinned selector run, prompt 2026-11-04a
  repeat1/2  the two unchanged reruns (outputs-local/v2/04_selection/..._repeat{1,2}/tables/keeps.csv)

Fill pools (tier 1 removed):
  b3_list         each target's B3 list (progress._b3: 443 pairs for the 67 targets, labelled or not)
  b3_list_r11_15  the B3 list plus ranks 11-15 of B3's full ranking (the pinned ranking.csv.gz that
                  recall_audit.py reads; the target itself is never in it). Unselected rows of B3's top 10 (dropped by
                  the mutual rule) are not added.

Fill rules (first K - |tier 1| comps of the pool, in this order):
  b3_rank          B3 rank (ties by comp id)
  agent            the agent grading's verdicts (the files progress.built_in("agent_ge1") reads): agent score 2
                   first, then 1, ties by B3 rank; agent score 0 and pairs the agent never graded are skipped
  agent_then_rank  `agent`, then pairs the agent never graded in B3 rank order; agent score 0 is still skipped

Labels of a pick (label_source): v3_final (grade 0/1/2; the only source in the headline metrics); anchor (one of the
12 rubric v3 anchor pairs, scored in the pinned final.csv but left out of v3_final); judge_only (GPT-Terra in the
EXPERIMENTAL recall audit, 20261128T055935Z_EXPERIMENTAL: not reviewer labels); unlabelled. The `_all_sources`
columns pool all three label sources.

Metrics (per tier-1 source x pool x rule; `none` = tier 1 alone): targets with >= 3 comps and with 0 comps before and
after, mean profile size; tier-1 precision (direct, at least adjacent); tier-2 picks: count, label sources,
"at least adjacent" precision and direct share among labelled picks; whole-profile precision. Precision = target mean
over targets with >= 1 labelled pick (95% target bootstrap, 1,000 draws, seed 2026, progress.bootstrap_means) and
pooled. by_group.csv: the same by the target's sector group (peer_mix.GROUPS).

Outputs (outputs-local/v2/09_analysis/tier2_fill/<UTC>_EXPERIMENTAL/): summary.csv, by_group.csv, picks.csv (every
tier-2 pick), targets.csv (per target and setting: tier-1 and tier-2 comps), manifest.json (inputs and sha256).
No financial table is read: EV/EBITDA plays no part in the fill.

  uv run python v2/09_analysis/scripts/tier2_fill.py

k sweep and the llm_tier2 rule (EXPERIMENTAL, added 2026-11-28): `sweep` scores k = 2-5 for the three rules (baseline
tier 1, both pools) and, given the model's ranked picks, the llm_tier2 rule (pool b3_list_r11_15, ordered by the
model's rank; the model calls, judge labels and outputs are in tier2_llm.py). The default run above is unchanged.
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
K = 3
RULES = ["b3_rank", "agent", "agent_then_rank"]
LLM_RULE = "llm_tier2"                    # ordered by llm_rank (tier2_llm.py: one Claude call per thin target)
SWEEP_KS = (2, 3, 4, 5)
POOLS = ["b3_list", "b3_list_r11_15"]
EXTRA_RANKS = (11, 15)
LABEL = "EXPERIMENTAL"
REPEATS = {f"repeat{i}": f"outputs-local/v2/04_selection/b3_selector_candidates_2026-11-04a_claude-cli_"
                         f"claude-sonnet-5-5_repeat{i}/tables/keeps.csv" for i in (1, 2)}
RECALL_AUDIT = "outputs-local/v2/09_analysis/recall_audit/20261128T055935Z_EXPERIMENTAL"
SOURCES = ["v3_final", "anchor", "judge_only", "unlabelled"]


# ---------------------------------------------------------------- fill logic

def order_pool(pool: pd.DataFrame, rule: str) -> pd.DataFrame:
    """The pool rows a rule may use, in the rule's order (within each target). pool: target_id, comp_id, rank,
    agent_score (NaN = never graded)."""
    p = pool.copy()
    s = pd.to_numeric(p["agent_score"], errors="coerce")
    if rule == "b3_rank":
        p["_k1"] = 0
    elif rule == "agent":
        p = p[s.isin([1, 2])]
        p["_k1"] = -s[s.isin([1, 2])]
    elif rule == "agent_then_rank":
        keep = s.isin([1, 2]) | s.isna()
        p = p[keep]
        p["_k1"] = np.where(s[keep].isna(), 0, -s[keep])     # 2 -> -2, 1 -> -1, ungraded -> 0 (after both)
    elif rule == LLM_RULE:
        if "llm_rank" not in p.columns:
            raise ValueError(f"rule {LLM_RULE} needs an llm_rank column (NaN = not returned by the model)")
        r = pd.to_numeric(p["llm_rank"], errors="coerce")
        p = p[r.notna()]
        p["_k1"] = r[r.notna()]                              # the model's ranking only; B3 rank never breaks a tie
    else:
        raise ValueError(f"unknown rule {rule!r}; rules: {[*RULES, LLM_RULE]}")
    return p.sort_values(["target_id", "_k1", "rank", "comp_id"], kind="mergesort").drop(columns="_k1")


def fill(tier1: pd.DataFrame, pool: pd.DataFrame, rule: str, k: int = K,
         targets: list[str] | None = None) -> pd.DataFrame:
    """Tier-2 picks: for each target with fewer than k tier-1 comps, the first k - |tier 1| pool comps (by the rule)
    that are not in tier 1. tier1: target_id, comp_id (kept comps only). Returns the picked pool rows with fill_order
    (1..) and tier1_n."""
    targets = sorted(set(targets) if targets is not None else set(pool["target_id"]) | set(tier1["target_id"]))
    n1 = tier1.drop_duplicates(KEY).groupby("target_id").size().reindex(targets, fill_value=0)
    t1 = set(map(tuple, tier1[KEY].to_numpy()))
    p = pool[pool["target_id"].isin(targets)].drop_duplicates(KEY)
    p = p[np.array([(t, c) not in t1 and t != c for t, c in zip(p["target_id"], p["comp_id"])], dtype=bool)]
    p = order_pool(p, rule)
    p["fill_order"] = p.groupby("target_id").cumcount() + 1
    p["tier1_n"] = p["target_id"].map(n1).astype(int)
    picks = p[p["fill_order"] <= (k - p["tier1_n"]).clip(lower=0)]
    return picks.reset_index(drop=True)


# ---------------------------------------------------------------- metrics

def _prec(per: pd.DataFrame, kept: str, tp: str, prefix: str, boot: bool = True) -> dict:
    """Target-mean precision (targets with >= 1 kept) with a bootstrap interval, and pooled."""
    import progress as pr
    t = pd.DataFrame({"kept": per[kept].astype(int), "tp": per[tp].astype(int), "pos": 0})
    has = t["kept"] > 0
    mean = float((t.loc[has, "tp"] / t.loc[has, "kept"]).mean()) if has.any() else np.nan
    out = {f"{prefix}_targets": int(has.sum()), f"{prefix}_mean": mean,
           f"{prefix}_pooled": t["tp"].sum() / t["kept"].sum() if t["kept"].sum() else np.nan}
    if boot:
        b = pr.bootstrap_means(t) if len(t) else {"precision_mean_lo": np.nan, "precision_mean_hi": np.nan}
        out |= {f"{prefix}_lo": b["precision_mean_lo"], f"{prefix}_hi": b["precision_mean_hi"]}
    return out


def per_target(members: pd.DataFrame, targets: list[str]) -> pd.DataFrame:
    """members: target_id, comp_id, tier (1/2), label_source, grade (v3_final or anchor or judge score). One row per
    target with counts per tier: n, labelled (v3_final), ge1/direct among labelled, and the same over all sources."""
    m = members.copy()
    g = pd.to_numeric(m["grade"], errors="coerce")
    lab = m["label_source"].eq("v3_final")
    anyl = m["label_source"].isin(["v3_final", "anchor", "judge_only"]) & g.notna()
    cols = {"n": pd.Series(True, index=m.index), "lab": lab, "ge1": lab & g.ge(1), "dir": lab & g.eq(2),
            "anyl": anyl, "any_ge1": anyl & g.ge(1), "any_dir": anyl & g.eq(2),
            "judge": m["label_source"].eq("judge_only"), "anchor": m["label_source"].eq("anchor"),
            "unl": m["label_source"].eq("unlabelled")}
    rows = {}
    for tier in ("1", "2", "all"):
        x = m if tier == "all" else m[m["tier"].astype(str) == tier]
        for name, mask in cols.items():
            rows[f"t{tier}_{name}"] = mask.loc[x.index].groupby(x["target_id"]).sum()
    return pd.DataFrame(rows).reindex(targets).fillna(0).astype(int)


def summarize(members: pd.DataFrame, targets: list[str], k: int = K, boot: bool = True,
              extended: bool = False) -> dict:
    """One row of metrics. extended (the k sweep): also the all-sources view with intervals, the share of tier-2
    picks with any label, and whole-profile precision over all label sources."""
    t = per_target(members, targets)
    row = {"targets": len(t),
           "tier1_comps": int(t["t1_n"].sum()), "tier1_mean_size": t["t1_n"].mean(),
           "targets_ge3_before": int(t["t1_n"].ge(k).sum()), "targets_0_before": int(t["t1_n"].eq(0).sum()),
           "targets_ge3_after": int(t["tall_n"].ge(k).sum()), "targets_0_after": int(t["tall_n"].eq(0).sum()),
           "mean_size_after": t["tall_n"].mean(),
           "tier2_picks": int(t["t2_n"].sum()), "tier2_targets": int(t["t2_n"].gt(0).sum()),
           "tier2_v3_final": int(t["t2_lab"].sum()), "tier2_anchor": int(t["t2_anchor"].sum()),
           "tier2_judge_only": int(t["t2_judge"].sum()), "tier2_unlabelled": int(t["t2_unl"].sum())}
    row["tier2_labelled_share"] = row["tier2_v3_final"] / row["tier2_picks"] if row["tier2_picks"] else np.nan
    row |= _prec(t, "t1_lab", "t1_dir", "tier1_direct_prec", boot)
    row |= _prec(t, "t1_lab", "t1_ge1", "tier1_ge1_prec", boot)
    row |= _prec(t, "t2_lab", "t2_ge1", "tier2_ge1_prec", boot)
    row |= _prec(t, "t2_lab", "t2_dir", "tier2_direct_share", boot)
    row |= _prec(t, "t2_anyl", "t2_any_ge1", "tier2_ge1_prec_all_sources", False)
    row |= _prec(t, "t2_anyl", "t2_any_dir", "tier2_direct_share_all_sources", False)
    row |= _prec(t, "tall_lab", "tall_ge1", "profile_ge1_prec", boot)
    row |= _prec(t, "tall_lab", "tall_dir", "profile_direct_prec", boot)
    if extended:
        n2 = row["tier2_picks"]
        row["tier2_any_label_share"] = int(t["t2_anyl"].sum()) / n2 if n2 else np.nan
        row |= _prec(t, "t2_anyl", "t2_any_ge1", "tier2_ge1_prec_all_sources", boot)
        row |= _prec(t, "t2_anyl", "t2_any_dir", "tier2_direct_share_all_sources", boot)
        row |= _prec(t, "tall_anyl", "tall_any_ge1", "profile_ge1_prec_all_sources", boot)
        row |= _prec(t, "tall_anyl", "tall_any_dir", "profile_direct_prec_all_sources", boot)
    return row


# ---------------------------------------------------------------- inputs

def b3_ranking(cur: dict) -> pd.DataFrame:
    """B3's full pinned ranking (target_id, comp_id, rank), as recall_audit.b3_tables reads it."""
    r = pd.read_csv(v2.path(cur["retrieval"]["candidates"]) / "ranking.csv.gz", dtype={"target": str, "comp": str},
                    usecols=["target", "rank", "comp"])
    return r.rename(columns={"target": "target_id", "comp": "comp_id"}).assign(rank=lambda x: x["rank"].astype(int))


def agent_scores(cur: dict) -> tuple[pd.DataFrame, list[Path]]:
    """target_id, comp_id, agent_score from the agent files progress.built_in('agent_ge1') reads."""
    import progress as pr
    spec = pr.built_in("agent_ge1", cur)
    a = pd.concat([pd.read_csv(p, dtype={"target": str, "comp": str}) for p in spec["run_files"]], ignore_index=True)
    a = a.rename(columns={"target": "target_id", "comp": "comp_id"})
    a["agent_score"] = pd.to_numeric(a["score"], errors="coerce")
    chk = a.merge(spec["keeps"], on=KEY, validate="one_to_one")
    if not chk["keep"].eq(chk["agent_score"].ge(1)).all():
        raise ValueError("agent scores disagree with progress.built_in('agent_ge1') keeps")
    return a[[*KEY, "agent_score"]], [Path(p) for p in spec["run_files"]]


def tier1_sources(cur: dict, targets: list[str]) -> dict[str, tuple[pd.DataFrame, Path]]:
    """{source: (kept pairs target_id, comp_id; file)} restricted to the targets."""
    import progress as pr
    spec = pr.built_in("selector", cur)
    out = {"baseline": (spec["keeps"], Path(spec["run_file"]))}
    for name, rel in REPEATS.items():
        out[name] = (pr.read_keeps(v2.path(rel)), v2.path(rel))
    return {n: (d[d["keep"].astype(bool) & d["target_id"].isin(targets)][KEY].reset_index(drop=True), f)
            for n, (d, f) in out.items()}


def labels(cur: dict, extra_judge: list[Path] | None = None) -> tuple[pd.DataFrame, dict[str, Path]]:
    """target_id, comp_id, label_source, grade: v3_final first, then anchors, then the recall-audit judge, then any
    extra_judge tables (columns target_id, comp_id, judge_status, judge_score; also judge-only GPT-Terra labels)."""
    import cohorts
    f = cohorts.load("v3_final")
    f = f[f["grade"].notna()].assign(label_source="v3_final")[[*KEY, "label_source", "grade"]]
    final_path = v2.path(cur["rubric_v3"]["final"]) / "final.csv"
    fa = pd.read_csv(final_path, dtype={"target_id": str, "comp_id": str}, encoding="utf-8-sig")
    anc = fa[fa["is_anchor"].astype(str).str.casefold().isin(["true", "1"]) & fa["score"].notna()]
    anc = anc.assign(label_source="anchor", grade=anc["score"])[[*KEY, "label_source", "grade"]]
    audit_path = v2.path(RECALL_AUDIT) / "pairs.csv"
    ra = pd.read_csv(audit_path, dtype={"target_id": str, "comp_id": str}, encoding="utf-8-sig")
    ra = ra[ra["judge_status"].eq("ok")].assign(grade=lambda x: pd.to_numeric(x["judge_score"], errors="coerce"))
    ra = ra[ra["grade"].notna()].assign(label_source="judge_only")[[*KEY, "label_source", "grade"]]
    extra, files = [], {}
    for i, path in enumerate(extra_judge or []):
        e = pd.read_csv(path, dtype={"target_id": str, "comp_id": str}, encoding="utf-8-sig")
        e = e[e["judge_status"].eq("ok")].assign(grade=lambda x: pd.to_numeric(x["judge_score"], errors="coerce"))
        extra.append(e[e["grade"].notna()].assign(label_source="judge_only")[[*KEY, "label_source", "grade"]])
        files[f"extra_judge_{i}"] = Path(path)
    lab = pd.concat([f, anc, ra, *extra], ignore_index=True)
    lab["grade"] = pd.to_numeric(lab["grade"]).astype(int)
    lab = lab.drop_duplicates(KEY, keep="first")       # v3_final > anchor > judge_only
    return lab.reset_index(drop=True), {"v3_final": final_path, "recall_audit_pairs": audit_path, **files}


def attach_labels(d: pd.DataFrame, lab: pd.DataFrame) -> pd.DataFrame:
    d = d.merge(lab, on=KEY, how="left", validate="many_to_one")
    d["label_source"] = d["label_source"].fillna("unlabelled")
    return d


def pools(cur: dict, targets: list[str], agent: pd.DataFrame) -> dict[str, pd.DataFrame]:
    import progress as pr
    b3 = pr._b3(cur)
    b3 = b3[b3["target_id"].isin(targets)].assign(in_b3_list=True)
    r = b3_ranking(cur)
    lo, hi = EXTRA_RANKS
    extra = r[r["target_id"].isin(targets) & r["rank"].between(lo, hi)]
    extra = extra.merge(b3[KEY], on=KEY, how="left", indicator=True)
    extra = extra[extra["_merge"] == "left_only"].drop(columns="_merge").assign(in_b3_list=False)
    out = {"b3_list": b3, "b3_list_r11_15": pd.concat([b3, extra], ignore_index=True)}
    return {n: p.merge(agent, on=KEY, how="left", validate="one_to_one")[[*KEY, "rank", "in_b3_list", "agent_score"]]
            for n, p in out.items()}


# ---------------------------------------------------------------- build

def build(cur: dict | None = None, boot: bool = True, k: int = K) -> tuple[dict[str, pd.DataFrame], dict]:
    import cohorts
    import peer_mix as pm
    import progress as pr
    cur = cur or v2.current()
    coh = cohorts.load("v3_final")
    targets = sorted(coh["target_id"].unique())
    tick = cohorts._tickers()
    group = pm.industry(targets)["group"]
    agent, agent_files = agent_scores(cur)
    lab, lab_files = labels(cur)
    pl = pools(cur, targets, agent)
    t1s = tier1_sources(cur, targets)
    b3 = pl["b3_list"]
    for name, (t1, _) in t1s.items():
        miss = t1.merge(b3[KEY], on=KEY, how="left", indicator=True)["_merge"].ne("both").sum()
        if miss:
            raise ValueError(f"tier 1 {name}: {miss} kept pairs not in the B3 list")

    settings = [(s, "-", "none") for s in t1s] + [(s, p, r) for s in t1s for p in POOLS for r in RULES]
    summary, by_group, picks_all, tgt_rows = [], [], [], []
    for src, pool_name, rule in settings:
        t1 = t1s[src][0].merge(b3, on=KEY, how="left")
        picks = (fill(t1, pl[pool_name], rule, k, targets) if rule != "none"
                 else pd.DataFrame(columns=[*KEY, "rank", "in_b3_list", "agent_score", "fill_order", "tier1_n"]))
        members = pd.concat([x for x in (t1.assign(tier=1), picks.assign(tier=2)) if len(x)], ignore_index=True)
        members = attach_labels(members, lab)
        setting = {"label": LABEL, "tier1_source": src, "pool": pool_name, "rule": rule}
        summary.append({**setting, **summarize(members, targets, k, boot)})
        for gname, ids in [("all", targets), *[(g, sorted(group.index[group == g])) for g in sorted(group.unique())]]:
            sub = members[members["target_id"].isin(ids)]
            by_group.append({**setting, "group": gname, **summarize(sub, ids, k, boot)})
        if rule != "none":
            p = attach_labels(picks, lab)
            picks_all.append(p.assign(**setting))
        for t in targets:
            m = members[members["target_id"] == t]
            fmt = lambda x: " ".join(f"{tick.get(c, c)}({g})" for c, g in zip(  # noqa: E731
                x["comp_id"], [_g(s, v) for s, v in zip(x["label_source"], x["grade"])]))
            tgt_rows.append({**setting, "target_id": t, "target_ticker": tick.get(t, t), "group": group[t],
                             "tier1_n": int(m["tier"].eq(1).sum()), "tier2_n": int(m["tier"].eq(2).sum()),
                             "tier1": fmt(m[m["tier"] == 1]), "tier2": fmt(m[m["tier"] == 2])})

    picks = pd.concat(picks_all, ignore_index=True)
    picks["target_ticker"] = picks["target_id"].map(tick)
    picks["comp_ticker"] = picks["comp_id"].map(tick)
    picks["group"] = picks["target_id"].map(group)
    picks = picks.rename(columns={"rank": "b3_rank"})[[
        "label", "tier1_source", "pool", "rule", "target_id", "target_ticker", "comp_id", "comp_ticker", "group",
        "tier1_n", "fill_order", "b3_rank", "in_b3_list", "agent_score", "label_source", "grade"]]
    tables = {"summary": pd.DataFrame(summary), "by_group": pd.DataFrame(by_group), "picks": picks,
              "targets": pd.DataFrame(tgt_rows)}
    inputs = {"current_toml": v2.V2 / "current.toml",
              "b3_candidates": v2.path(cur["retrieval"]["candidates"]) / "candidates.csv",
              "b3_ranking": v2.path(cur["retrieval"]["candidates"]) / "ranking.csv.gz",
              "universe": v2.path(cur["universe"]["universe"]),
              **{f"tier1_{n}": f for n, (_, f) in t1s.items()},
              **{f"agent_{i}": p for i, p in enumerate(agent_files)}, **lab_files}
    return tables, {"inputs": inputs, "targets": len(targets)}


def _ge_k(row: dict) -> dict:
    """summarize's targets_ge3_* keys hold "at least k"; in the sweep they are named for k."""
    return {(c.replace("targets_ge3_", "targets_ge_k_") if c.startswith("targets_ge3_") else c): v
            for c, v in row.items()}


def sweep(cur: dict | None = None, ks: tuple[int, ...] = SWEEP_KS, llm: pd.DataFrame | None = None,
          extra_judge: list[Path] | None = None, boot: bool = True) -> tuple[dict[str, pd.DataFrame], dict]:
    """The k sweep (EXPERIMENTAL): tier 1 = the baseline selector; for each k in ks, the three no-model rules on
    both pools and, when `llm` is given (target_id, comp_id, llm_rank[, llm_reason]: the model's ranked tier-2
    picks), llm_tier2 on the b3_list_r11_15 pool (the pool its prompt showed). Metrics as in build, plus the
    all-sources view (extra_judge: more judge-only label tables, see labels)."""
    import cohorts
    import peer_mix as pm
    import progress as pr
    cur = cur or v2.current()
    coh = cohorts.load("v3_final")
    targets = sorted(coh["target_id"].unique())
    tick = cohorts._tickers()
    group = pm.industry(targets)["group"]
    agent, agent_files = agent_scores(cur)
    lab, lab_files = labels(cur, extra_judge)
    pl = pools(cur, targets, agent)
    spec = pr.built_in("selector", cur)
    t1 = spec["keeps"]
    t1 = t1[t1["keep"].astype(bool) & t1["target_id"].isin(targets)][KEY].merge(pl["b3_list"], on=KEY, how="left")
    settings = [(p, r) for p in POOLS for r in RULES]
    if llm is not None:
        lp = pl["b3_list_r11_15"].merge(llm, on=KEY, how="left", validate="one_to_one")
        outside = llm.merge(pl["b3_list_r11_15"][KEY], on=KEY, how="left", indicator=True)["_merge"].ne("both")
        if outside.any():
            raise ValueError(f"{int(outside.sum())} llm picks are not in the b3_list_r11_15 pool")
        pl = {**pl, "llm": lp}
        settings.append(("b3_list_r11_15", LLM_RULE))
    groups = [("all", targets), *[(g, sorted(group.index[group == g])) for g in sorted(group.unique())]]
    summary, by_group, picks_all, tgt_rows = [], [], [], []
    for k in ks:
        for pool_name, rule in [("-", "none"), *settings]:
            pool = pl["llm"] if rule == LLM_RULE else pl.get(pool_name)
            picks = (fill(t1, pool, rule, k, targets) if rule != "none"
                     else pd.DataFrame(columns=[*KEY, "rank", "in_b3_list", "agent_score", "fill_order", "tier1_n"]))
            members = pd.concat([x for x in (t1.assign(tier=1), picks.assign(tier=2)) if len(x)], ignore_index=True)
            members = attach_labels(members, lab)
            setting = {"label": LABEL, "k": k, "tier1_source": "baseline", "pool": pool_name, "rule": rule}
            summary.append({**setting, **_ge_k(summarize(members, targets, k, boot, extended=True))})
            for gname, ids in groups:
                sub = members[members["target_id"].isin(ids)]
                by_group.append({**setting, "group": gname, **_ge_k(summarize(sub, ids, k, boot, extended=True))})
            if rule != "none":
                picks_all.append(attach_labels(picks, lab).assign(**setting))
            for t in targets:
                m = members[members["target_id"] == t]
                fmt = lambda x: " ".join(f"{tick.get(c, c)}({g})" for c, g in zip(  # noqa: E731
                    x["comp_id"], [_g(s, v) for s, v in zip(x["label_source"], x["grade"])]))
                tgt_rows.append({**setting, "target_id": t, "target_ticker": tick.get(t, t), "group": group[t],
                                 "tier1_n": int(m["tier"].eq(1).sum()), "tier2_n": int(m["tier"].eq(2).sum()),
                                 "tier1": fmt(m[m["tier"] == 1]), "tier2": fmt(m[m["tier"] == 2])})
    picks = pd.concat(picks_all, ignore_index=True)
    picks["target_ticker"] = picks["target_id"].map(tick)
    picks["comp_ticker"] = picks["comp_id"].map(tick)
    picks["group"] = picks["target_id"].map(group)
    extra_cols = [c for c in ("llm_rank", "llm_reason") if c in picks.columns]
    picks = picks.rename(columns={"rank": "b3_rank"})[[
        "label", "k", "tier1_source", "pool", "rule", "target_id", "target_ticker", "comp_id", "comp_ticker", "group",
        "tier1_n", "fill_order", "b3_rank", "in_b3_list", "agent_score", *extra_cols, "label_source", "grade"]]
    tables = {"summary": pd.DataFrame(summary), "by_group": pd.DataFrame(by_group), "picks": picks,
              "targets": pd.DataFrame(tgt_rows)}
    inputs = {"current_toml": v2.V2 / "current.toml",
              "b3_candidates": v2.path(cur["retrieval"]["candidates"]) / "candidates.csv",
              "b3_ranking": v2.path(cur["retrieval"]["candidates"]) / "ranking.csv.gz",
              "universe": v2.path(cur["universe"]["universe"]), "tier1_baseline": Path(spec["run_file"]),
              **{f"agent_{i}": p for i, p in enumerate(agent_files)}, **lab_files}
    return tables, {"inputs": inputs, "targets": len(targets), "labels": lab}


def _g(source: str, grade) -> str:
    if source == "unlabelled" or pd.isna(grade):
        return "?"
    g = str(int(grade))
    return {"v3_final": g, "anchor": f"a{g}", "judge_only": f"j{g}"}[source]


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--k", type=int, default=K, help=f"profile size to fill to (default {K}; the k sweep and the "
                                                      "llm_tier2 rule: tier2_llm.py)")
    args = ap.parse_args(argv)
    print(f"*** {LABEL}: tier-2 fill of thin comp profiles (k = {args.k}); saved runs only, no model calls ***")
    tables, meta = build(k=args.k)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or v2.out("09_analysis") / "tier2_fill" / f"{stamp}_{LABEL}"
    out.mkdir(parents=True, exist_ok=True)
    for name, t in tables.items():
        t.to_csv(out / f"{name}.csv", index=False)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
    rel = lambda p: Path(p).resolve().relative_to(v2.ROOT.resolve()).as_posix()  # noqa: E731
    manifest = {
        "label": LABEL,
        "status": f"{LABEL} tier-2 fill (team decision 2026-11-28, Michael); not a pipeline input; no model calls",
        "created_at": stamp, "script": "v2/09_analysis/scripts/tier2_fill.py", "script_sha256": sha(__file__),
        "design": {"k": args.k, "targets": f"v3_final cohort ({meta['targets']} targets)",
                   "tier1": {"baseline": "progress.built_in('selector'), prompt 2026-11-04a",
                             **{n: rel(v2.path(p)) for n, p in REPEATS.items()}},
                   "pools": {"b3_list": "progress._b3 (B3 selected lists)",
                             "b3_list_r11_15": f"B3 list + ranks {EXTRA_RANKS[0]}-{EXTRA_RANKS[1]} of B3's ranking"},
                   "rules": {"b3_rank": "B3 rank order",
                             "agent": "agent score 2 then 1, ties by B3 rank; agent 0 and ungraded skipped",
                             "agent_then_rank": "agent rule, then ungraded pairs in B3 rank order; agent 0 skipped"},
                   "label_sources": {"v3_final": "headline labels (metrics)",
                                     "anchor": "rubric v3 anchor pairs, pinned final.csv score, outside v3_final",
                                     "judge_only": f"GPT-Terra, {RECALL_AUDIT} (not reviewer labels)",
                                     "unlabelled": "no label"},
                   "bootstrap": "targets, 1,000 draws, seed 2026 (progress.bootstrap_means)",
                   "groups": "peer_mix.GROUPS (sector of the target's SIC4)"},
        "inputs": {k: {"path": rel(p), "sha256": sha(p)} for k, p in meta["inputs"].items()},
        "outputs": sorted(f"{n}.csv" for n in tables),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    s = tables["summary"]
    cols = ["tier1_source", "pool", "rule", "targets_ge3_before", "targets_ge3_after", "targets_0_after",
            "mean_size_after", "tier1_direct_prec_mean", "tier2_picks", "tier2_labelled_share", "tier2_ge1_prec_mean",
            "tier2_ge1_prec_lo", "tier2_ge1_prec_hi", "tier2_ge1_prec_pooled", "tier2_direct_share_mean",
            "tier2_direct_share_pooled", "profile_ge1_prec_mean", "profile_ge1_prec_pooled"]
    with pd.option_context("display.width", 300, "display.max_columns", 40, "display.float_format", "{:.2f}".format):
        print(s[cols].to_string(index=False))
    print(f"[{LABEL}] wrote {out}")


if __name__ == "__main__":
    main()
