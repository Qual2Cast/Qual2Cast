"""The locked final check: the current method on the holdout. Nothing runs without --final-check.

Two parts, both kept out of every development decision (01-09 never read them):

  direct-peers  Barbara's 24 direct-peer pairs whose comp is in the universe (all 24 comps are holdout companies;
                cohort final_holdout_24). Puts them through the same steps as the 293 reviewed pairs: B3 similarity
                of the current variant (checked against the 293 pairs' saved scores), the rank the comp would have
                in the target's list if it were in the pool, a check that the agent loop ran with the 293 run's
                settings, and C/S/E and the final order (agent_ranking.py), alone and pooled with the 293.
                v1: direct_peer_pairs.py standardize (2026-11-18), minus the X-learner inputs (deleted: these pairs
                are not used for analysis). Yes = grade 2; No is not a 0.
  holdout       the current B3 lists of the 160 holdout targets (comp pool = the 373 training firms) and their
                valuation against "no matching". The selector on the holdout needs an LLM run (04, approval first).

  uv run python v2/10_final_holdout/scripts/final_check.py direct-peers --final-check
  uv run python v2/10_final_holdout/scripts/final_check.py holdout --final-check
Writes outputs-local/v2/10_final_holdout/final_check/<part>_<stamp>/ (never overwrites).
"""
from __future__ import annotations

import sys as _sys  # v2: shared paths (common/paths.py) put every component's scripts on the path
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "common"))
import paths as v2  # noqa: E402
v2.setup()

import argparse  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DIRECT = v2.src("10_final_holdout", "direct_peers_24")
OUT = v2.out("10_final_holdout") / "final_check"
AGENT_SETTINGS = ["backend", "model", "effort", "search", "search_model", "max_steps", "facet_scores",
                  "industry_facets", "activate", "prompt_version", "start_words"]
IDS = {"target": str, "comp": str}


class Locked(PermissionError):
    pass


def require(final_check: bool) -> None:
    if not final_check:
        raise Locked("the holdout is the locked final check; pass --final-check (final_check=True) to run it")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(v2.ROOT).as_posix()


def pool_rank(S, pos: dict[str, int], pool: list[str], target: str, comp: str) -> int:
    """Rank the comp would have in the target's B3 list if it were in the pool (1 = most similar)."""
    others = [pos[x] for x in pool if x not in (target, comp)]
    return int((S[pos[target], others] > S[pos[target], pos[comp]]).sum()) + 1


def agent_settings_differ(reference: dict, mine: dict) -> dict:
    diff = {k: (reference.get(k), mine.get(k)) for k in AGENT_SETTINGS if reference.get(k) != mine.get(k)}
    # facets paths were absolute on the machine that ran them; compare the part under outputs-local/
    tail = [Path(str(c.get("facets", ""))).parts[-4:] for c in (reference, mine)]
    if tail[0] != tail[1]:
        diff["facets"] = (reference.get("facets"), mine.get("facets"))
    return diff


def b3_matrix() -> tuple[np.ndarray, list[str], list[str], list[str]]:
    """Current B3 similarity over all 533 companies, the id order, training and holdout ids."""
    import method1_candidates as m1
    cur = v2.current()
    ids = pd.read_csv(v2.path(cur["universe"]["universe"]), dtype=str)["IQ_COMPANY_ID"].tolist()
    split = pd.read_csv(v2.path(cur["universe"]["split"]), dtype=str)
    S, _ = m1.similarity(ids, cur)
    return (S, ids, split.loc[split["sample"] == "training", "IQ_COMPANY_ID"].tolist(),
            split.loc[split["sample"] == "holdout", "IQ_COMPANY_ID"].tolist())


def direct_peers(final_check: bool = False, out_root: Path = OUT) -> Path:
    require(final_check)
    import agent_ranking as ar
    import cohorts
    cur = v2.current()
    ref_run = v2.path(cur["agent_grading"]["run"])
    diff = agent_settings_differ(json.loads((ref_run / "config.json").read_text(encoding="utf-8")),
                                 json.loads((DIRECT / "agent_config.json").read_text(encoding="utf-8")))
    if diff:
        raise SystemExit(f"agent loop settings differ from the 293 pairs' run {ref_run.name}: {diff}")
    manifest = pd.read_csv(DIRECT / "manifest.csv", dtype=str).fillna("")
    inside = manifest[~manifest["comp_id"].str.startswith("EXT_")]
    labels = cohorts.load("final_holdout_24", final_check=True)
    if len(inside) != len(labels):
        raise SystemExit("manifest and the final_holdout_24 cohort disagree")
    ref_v = pd.read_csv(ref_run / "verdicts.csv", dtype=IDS)
    keys = labels.rename(columns={"target_id": "target", "comp_id": "comp"})[["target", "comp"]]
    mine = keys.merge(pd.read_csv(DIRECT / "agent_verdicts.csv", dtype=IDS), on=["target", "comp"],
                      how="left", validate="one_to_one")
    if mine["status"].isna().any():
        raise SystemExit("agent verdicts missing for some of the 24 pairs")

    S, ids, training, _ = b3_matrix()
    pos = {x: i for i, x in enumerate(ids)}
    recomputed = np.array([S[pos[t], pos[c]] for t, c in zip(ref_v["target"], ref_v["comp"])])
    ranks = np.array([pool_rank(S, pos, training, t, c) for t, c in zip(ref_v["target"], ref_v["comp"])])
    reproduction = {"pairs": len(ref_v),
                    "max_abs_difference_vs_saved_similarity": float(np.abs(recomputed - ref_v["similarity"]).max()),
                    "rank_mismatches": int((ranks != ref_v["rank"]).sum())}
    if reproduction["max_abs_difference_vs_saved_similarity"] > 1e-5 or reproduction["rank_mismatches"]:
        raise SystemExit(f"current B3 does not reproduce the 293 pairs' saved scores: {reproduction}")

    mine["similarity"] = [float(S[pos[t], pos[c]]) for t, c in zip(mine["target"], mine["comp"])]
    mine["rank"] = [pool_rank(S, pos, training, t, c) for t, c in zip(mine["target"], mine["comp"])]
    ok = mine["status"].eq("ok")
    alone = ar.rank(mine[ok])
    pooled = ar.rank(pd.concat([ref_v.assign(batch="b3_list_293"), mine[ok].assign(batch="barbara_direct_peers")],
                               ignore_index=True))
    pooled = pooled.rename(columns={"final_rank": "pooled_final_rank", "e_rank": "pooled_e_rank"})

    pairs = labels[["target_id", "comp_id", "target_ticker", "comp_ticker", "grade"]].reset_index(drop=True)
    cols = {"similarity": "b3_similarity", "rank": "b3_rank_if_in_pool", "status": "agent_status",
            "score": "agent_score", "verdict": "agent_verdict", "reason": "agent_reason",
            "lookups": "agent_lookups", "web_searches": "agent_web_searches"}
    pairs = pd.concat([pairs, mine[list(cols)].rename(columns=cols).reset_index(drop=True)], axis=1)
    cse = ["coverage", "observed_similarity", "evidence_points", "upper_bound", "observed_facets", "final_rank"]
    pairs = pairs.merge(alone[["target", "comp", *cse]].rename(columns={
        "target": "target_id", "comp": "comp_id", "final_rank": "final_rank_within_direct_pairs"}),
        on=["target_id", "comp_id"], how="left")
    pairs = pairs.merge(pooled.loc[pooled["batch"].eq("barbara_direct_peers"),
                                   ["target", "comp", "pooled_final_rank", "pooled_e_rank"]].rename(
        columns={"target": "target_id", "comp": "comp_id"}), on=["target_id", "comp_id"], how="left")
    pairs = pairs.merge(pooled.groupby("target")["comp"].size().rename("pooled_list_size"),
                        left_on="target_id", right_index=True, how="left")

    out = out_root / f"direct_peers_{stamp()}"
    out.mkdir(parents=True, exist_ok=False)
    pairs.to_csv(out / "pairs.csv", index=False)
    pooled.to_csv(out / "pooled_ranking.csv", index=False)
    report = {"created": out.name, "pairs": len(pairs), "external_pairs_left_out": len(manifest) - len(inside),
              "barbara": pairs["grade"].map({2: "Yes"}).fillna("No").value_counts().to_dict(),
              "agent_score_by_label": pd.crosstab(pairs["grade"].fillna(-1).astype(int),
                                                  pairs["agent_score"].fillna(-1).astype(int)).to_dict(),
              "b3_variant": cur["retrieval"]["variant"], "b3_reproduction_on_293": reproduction,
              "reference_run": rel(ref_run),
              "sources_sha256": {rel(p): sha256(p) for p in [DIRECT / "manifest.csv", DIRECT / "agent_verdicts.csv",
                                                             ref_run / "verdicts.csv"]}}
    (out / "run.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return out


def holdout(final_check: bool = False, out_root: Path = OUT) -> Path:
    require(final_check)
    import method1_candidates as m1
    import agent_valuation as av
    import valuation as vl
    _, top, run, _, _ = m1.build("all")
    cur = v2.current()
    split = pd.read_csv(v2.path(cur["universe"]["split"]), dtype=str)
    hold = split.loc[split["sample"] == "holdout", "IQ_COMPANY_ID"].tolist()
    training = split.loc[split["sample"] == "training", "IQ_COMPANY_ID"].tolist()
    lists = top[top["selected"] & top["target"].isin(hold)]
    if lists["comp"].isin(hold).any():
        raise SystemExit("a holdout company is in a comp list")
    m = av.multiples()
    results = {"no matching": vl.no_matching(hold, training, m),
               "B3 (median)": vl.estimate(lists, m, how="median"),
               "B3 (similarity-weighted mean)": vl.estimate(lists, m, weight="similarity")}
    out = out_root / f"holdout_{stamp()}"
    out.mkdir(parents=True, exist_ok=False)
    lists.to_csv(out / "b3_lists.csv", index=False)
    vl.bootstrap(results, m[hold], "no matching").to_csv(out / "valuation.csv")
    vl.summary(results, m[hold], "no matching").to_csv(out / "summary.csv")
    (out / "run.json").write_text(json.dumps({"created": out.name, "targets": len(hold), "pairs": len(lists),
                                              "b3": {k: run[k] for k in ("variant", "split_run", "facets_version")},
                                              "selector": "not run on the holdout yet"}, indent=1), encoding="utf-8")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("part", choices=["direct-peers", "holdout"])
    ap.add_argument("--final-check", action="store_true", help="required: this is the locked final check")
    args = ap.parse_args(argv)
    try:
        out = {"direct-peers": direct_peers, "holdout": holdout}[args.part](args.final_check)
    except Locked as e:
        ap.error(str(e))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
