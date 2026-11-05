"""Evaluate facet changes to B3 against peer labels, without using valuation.

The existing B3 similarity, mutual-top-10 rule, training pool, and 0-2
reviewer rubric are fixed. Each variant changes one source of facet data or
one facet bundle. Human majority labels are the primary diagnostic; the
saved Sol and Haiku judgments are reported separately. Unlabeled pairs are
never treated as negatives.

Run from the repository root:
    python v1/scripts/b3_facet_add_drop.py

The local all-mpnet-base-v2 model embeds only text absent from the team's
cache. No LLM or web API is called. Results go to outputs-local/v1/facet_add_drop/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facet_eval as fe  # noqa: E402
import facet_weighting as fw  # noqa: E402
import facets as fc  # noqa: E402
import method1_candidates as mc  # noqa: E402
import sectors as sc  # noqa: E402
import similarity_eval as se  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

V1 = OUTPUTS_LOCAL / "v1"
SPLIT_RUN = "20261027T204930Z"
B3_RUN = "20261104T074915Z"
EMBED_CACHE = V1 / "embeddings" / "texts_all-mpnet-base-v2.npz"
WORK_CACHE = V1 / "facet_add_drop" / "cache" / "new_texts.npz"
LABELS = V1 / "golden_set" / "labels" / "reviewer_labels_20261028.json"
ROUND2 = V1 / "golden_set_showcase" / "labels" / "round2_filled.csv"


def read_inputs() -> tuple[pd.DataFrame, list[str], list[str], pd.DataFrame]:
    split_dir = V1 / "split" / SPLIT_RUN
    run = json.loads((split_dir / "run.json").read_text(encoding="utf-8"))
    universe = pd.read_csv(V1 / "universe" / run["universe_run"] / "universe.csv", dtype=str)
    ids = universe["IQ_COMPANY_ID"].tolist()
    split = pd.read_csv(split_dir / "split.csv", dtype=str)
    training = split.loc[split["sample"] == "training", "IQ_COMPANY_ID"].tolist()
    if set(ids) != set(split["IQ_COMPANY_ID"]) or len(ids) != len(set(ids)):
        raise ValueError("universe and saved split do not contain the same unique companies")
    sectors = sc.sector_table(universe.set_index("IQ_COMPANY_ID"))
    return universe, ids, training, sectors


def general_texts(path: Path, ids: list[str]) -> pd.DataFrame:
    filled = pd.read_csv(path, dtype=str).fillna("")
    filled = filled[(filled["prompt_version"] == fc.PROMPT_VERSION) & (filled["llm_status"] == "ok")]
    if filled["IQ_COMPANY_ID"].nunique() != len(ids):
        raise ValueError(f"general facets do not cover the universe: {path}")
    return fw.facet_texts(filled).reindex(ids)


def load_labels(training: list[str]) -> dict[str, pd.DataFrame]:
    raw = pd.DataFrame(json.loads(LABELS.read_text(encoding="utf-8"))["labels"]).fillna("")
    majority, unanimous, _ = se.reviewer_sets(raw)
    sets = {"human_majority": majority, "human_unanimous": unanimous}
    for reviewer in se.REVIEWERS:
        sets[f"human_{reviewer}"] = se.single_reviewer(raw, reviewer)
    if ROUND2.exists():
        sheet = pd.read_csv(ROUND2, dtype=str).fillna("")
        errors = se.check_reviewer_sheet(sheet, ("reviewer_a", "reviewer_b", "reviewer_c"))
        if len(errors):
            raise ValueError(f"round-2 reviewer sheet is incomplete: {len(errors)} invalid scores")
        r2, u2, _ = se.reviewer_sets(sheet, ("reviewer_a", "reviewer_b", "reviewer_c"))
        sets["human_majority"] = pd.concat([majority, r2], ignore_index=True)
        sets["human_unanimous"] = pd.concat([unanimous, u2], ignore_index=True)
    judge_path = V1 / "judge" / "tables" / "judgments.csv"
    if judge_path.exists():
        import cosine_then_llm as ctl

        j = pd.read_csv(judge_path, dtype={"target": str, "comp": str})
        j = j[(j["prompt_version"] == ctl.SAVED_PROMPT_VERSION) & j["score"].notna()]
        sets["haiku_screen_diagnostic"] = j.assign(grade=j["score"].astype(int))[
            ["target", "comp", "grade"]
        ].drop_duplicates(["target", "comp"])
    sol_path = V1 / "holdout_completion" / "graded_peer_selection" / "grades.csv"
    if sol_path.exists():
        sol, _ = se.sol_grades([sol_path])
        sets["sol_holdout_diagnostic"] = sol[["target", "comp", "grade"]]
    known = set(training)
    for name, labels in sets.items():
        if not set(labels["comp"]).issubset(known):
            raise ValueError(f"{name}: labeled comps outside the training pool")
        if labels.duplicated(["target", "comp"]).any():
            raise ValueError(f"{name}: duplicate pair labels")
    return sets


def required_texts(general: dict[str, pd.DataFrame], sector: pd.DataFrame,
                   industry: pd.DataFrame) -> set[str]:
    texts = {str(value) for table in general.values() for col in table
             for value in table[col].dropna()}
    sub = sector.loc[sector["sub_sector_status"] == "stated", "sub_sector"].dropna()
    texts.update(str(x) for x in sub if x)
    texts.update(industry.loc[industry["status"] == "stated", "value"].dropna().astype(str))
    return texts


def vectors_for(texts: set[str]) -> dict[str, np.ndarray]:
    existing = fw.load_text_cache(EMBED_CACHE)
    seed = {value: existing[fw._key(value)] for value in texts if fw._key(value) in existing}
    missing = len(texts) - len(seed)
    print(f"Embedding cache: {len(seed)} of {len(texts)} texts found; {missing} local embeddings needed")
    return fw.embed_texts(texts, WORK_CACHE, seed=seed)


def general_components(texts: pd.DataFrame, vectors: dict[str, np.ndarray]
                       ) -> tuple[dict[str, np.ndarray], pd.DataFrame, float]:
    lexical, raw, _ = fw.lexical(texts)
    info, k = fw.information(raw)
    per_facet = fw.blend(fw.embedding_cosines(texts, vectors), lexical)
    return per_facet, info, k


def sub_sector_matrix(sector: pd.DataFrame, ids: list[str], vectors: dict[str, np.ndarray]) -> np.ndarray:
    value = sector.reindex(ids)["sub_sector"].where(
        sector.reindex(ids)["sub_sector_status"] == "stated")
    texts = pd.DataFrame({"sub_sector": value})
    lex, _, _ = fw.lexical(texts)
    emb = fw.embedding_cosines(texts, vectors)
    return fw.blend(emb, lex)["sub_sector"]


def industry_matrix(industry: pd.DataFrame, ids: list[str], vectors: dict[str, np.ndarray]
                    ) -> np.ndarray:
    """One added similarity facet: B3 within each SIC2, missing across SIC2."""
    pos = {company: i for i, company in enumerate(ids)}
    out = np.full((len(ids), len(ids)), np.nan, dtype=np.float32)
    valid = industry[(industry["status"] == "stated") & industry["IQ_COMPANY_ID"].isin(pos)]
    if valid.duplicated(["IQ_COMPANY_ID", "facet"]).any():
        raise ValueError("duplicate industry-facet values")
    for sic2, group in valid.groupby("sic2"):
        members = industry.loc[industry["sic2"] == sic2, "IQ_COMPANY_ID"].drop_duplicates()
        members = [x for x in members if x in pos]
        if len(members) < 2:
            continue
        texts = group.pivot(index="IQ_COMPANY_ID", columns="facet", values="value").reindex(members)
        per, info, _ = general_components(texts, vectors)
        out[np.ix_([pos[x] for x in members], [pos[x] for x in members])] = fw.combine(per, info)
    return out


def load_facet_sources(ids: list[str]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    sector = pd.read_csv(V1 / "sector_facets_sonnet" / "tables" / "sector_facets.csv", dtype=str).fillna("")
    if sector["IQ_COMPANY_ID"].nunique() != len(ids):
        raise ValueError("Sonnet sector facets do not cover the universe")
    industry = pd.read_csv(V1 / "industry_facets_sonnet" / "tables" / "industry_facets_long.csv", dtype=str)
    general = {
        "haiku": general_texts(V1 / "facets" / "tables" / "facets.csv", ids),
        "sonnet": general_texts(V1 / "facets_sonnet" / "tables" / "facets.csv", ids),
    }
    return general, sector, industry


def addition_matrices(ids: list[str], sectors: pd.DataFrame, vectors: dict[str, np.ndarray],
                      sector: pd.DataFrame, industry: pd.DataFrame) -> dict[str, np.ndarray]:
    sf = sector.set_index("IQ_COMPANY_ID")
    cats = fe.sector_facet_matrices(sector, ids, sectors)
    out = {
        "FF49": sc.sector_similarity(sectors, ids),
        "SIC4": sc.sic_similarity(sectors, ids),
        "Fiona sub-sector": sub_sector_matrix(sf, ids, vectors),
        "Fiona categories": fe.combine(cats),
        "Barbara SIC2 facets": industry_matrix(industry, ids, vectors),
    }
    return out


def score_variant(name: str, S: np.ndarray, ids: list[str], training: list[str],
                  label_sets: dict[str, pd.DataFrame]) -> tuple[list[dict], list[dict], pd.DataFrame]:
    targets = sorted({target for labels in label_sets.values() for target in labels["target"]})
    chosen = fw.mutual_top_k(S, ids, targets, training)
    rankings = fe.rank(S, ids, targets, training)
    rows, by_target = [], []
    for source, labels in label_sets.items():
        metrics = fe.rank_metrics(rankings, labels.rename(columns={"grade": "gain"}).assign(
            gain=labels["grade"].astype(float) / (2 if labels["grade"].max() > 1 else 1)))
        listed = chosen.merge(labels, on=["target", "comp"], how="left")
        observed = listed[listed["grade"].notna()]
        good = labels["grade"] >= 1
        rows.append({
            "variant": name, "label_source": source,
            "targets": int(labels["target"].nunique()), "labeled_pairs": int(len(labels)),
            "pairwise_accuracy": metrics["pairwise accuracy"],
            "pairwise_comparisons": metrics["pairs compared"],
            "good_recall": (int((observed["grade"] >= 1).sum()) / int(good.sum())) if good.any() else np.nan,
            "direct_recall": (int((observed["grade"] == 2).sum()) / int((labels["grade"] == 2).sum()))
            if (labels["grade"] == 2).any() else np.nan,
            "labeled_bad_selected": int((observed["grade"] == 0).sum()),
            "labeled_selected": int(len(observed)),
            "selected_on_labeled_targets": int(listed[listed["target"].isin(labels["target"])].shape[0]),
        })
        if source in {"human_majority", "sol_holdout_diagnostic"}:
            for target, one in labels.groupby("target"):
                ranked_one = rankings[rankings["target"] == target]
                gained = one.rename(columns={"grade": "gain"}).assign(
                    gain=one["grade"].astype(float) / (2 if one["grade"].max() > 1 else 1))
                pairwise = fe.rank_metrics(ranked_one, gained)
                picked = observed[observed["target"] == target]
                by_target.append({
                    "variant": name, "label_source": source, "target": target,
                    "labeled_pairs": len(one), "pairwise_accuracy": pairwise["pairwise accuracy"],
                    "pairwise_comparisons": pairwise["pairs compared"],
                    "good_total": int((one["grade"] >= 1).sum()),
                    "good_selected": int((picked["grade"] >= 1).sum()),
                    "bad_selected": int((picked["grade"] == 0).sum()),
                    "selected_total": int((chosen["target"] == target).sum()),
                    "selected_labeled": len(picked),
                })
    return rows, by_target, chosen


def check_saved_baseline(S: np.ndarray, ids: list[str], training: list[str]) -> dict:
    saved = pd.read_csv(V1 / "candidates_method1" / B3_RUN / "candidates.csv",
                        dtype={"target": str, "comp": str})
    chosen = fw.mutual_top_k(S, ids, training, training)
    expected = set(zip(saved.loc[saved["selected"], "target"], saved.loc[saved["selected"], "comp"]))
    actual = set(zip(chosen["target"], chosen["comp"]))
    if expected != actual:
        raise ValueError(f"B3 does not reproduce the team's saved comp lists: "
                         f"{len(expected - actual)} missing, {len(actual - expected)} added")
    checked = saved[saved["selected"]].merge(chosen, on=["target", "comp"], validate="one_to_one",
                                             suffixes=("_saved", "_reproduced"))
    difference = float((checked["similarity_saved"] - checked["similarity_reproduced"]).abs().max())
    rank_mismatches = int((checked["rank_saved"] != checked["rank_reproduced"]).sum())
    if difference > 1e-5 or rank_mismatches:
        raise ValueError(f"B3 selected scores/ranks differ: maximum {difference}, {rank_mismatches} ranks")
    return {"saved_selected_pairs": len(expected), "reproduced_selected_pairs": len(actual),
            "max_similarity_difference": difference, "rank_mismatches": rank_mismatches}


def paired_deltas(target_metrics: pd.DataFrame) -> pd.DataFrame:
    """Target-level changes against the matching fill model's full B3.

    For the Sol diagnostic only, resample target companies, not pairs. This
    keeps large labeled pools from dominating the uncertainty interval.
    """
    rows = []
    rng = np.random.default_rng(2026)
    for source in ("human_majority", "sol_holdout_diagnostic"):
        data = target_metrics[target_metrics["label_source"] == source]
        for variant, candidate in data.groupby("variant", sort=False):
            baseline = "B3 Haiku" if variant.startswith("Haiku") or variant == "B3 Haiku" else "B3 Sonnet"
            reference = data[data["variant"] == baseline]
            pair = candidate.merge(reference, on="target", suffixes=("", "_baseline"))
            values = (pair["pairwise_accuracy"] - pair["pairwise_accuracy_baseline"]).dropna().to_numpy()
            if not len(values):
                continue
            low = high = np.nan
            if source == "sol_holdout_diagnostic" and len(values) > 1:
                draws = rng.choice(values, size=(2000, len(values)), replace=True).mean(axis=1)
                low, high = np.quantile(draws, [0.025, 0.975])
            rows.append({
                "variant": variant, "label_source": source, "baseline": baseline,
                "targets_with_pairwise_comparisons": len(values),
                "mean_target_pairwise_delta": values.mean(), "bootstrap_low": low, "bootstrap_high": high,
                "good_selected_delta": int((pair["good_selected"] - pair["good_selected_baseline"]).sum()),
                "bad_selected_delta": int((pair["bad_selected"] - pair["bad_selected_baseline"]).sum()),
            })
    return pd.DataFrame(rows)


def chart(metrics: pd.DataFrame, path: Path) -> None:
    import matplotlib.pyplot as plt

    focus = ["B3 Haiku", "B3 Sonnet", "Sonnet + Fiona sub-sector", "Sonnet + Fiona categories",
             "Sonnet + Barbara SIC2 facets", "Sonnet + FF49", "Sonnet + SIC4", "Sonnet + all additions"]
    sources = [("human_majority", "Human majority · 2 targets"),
               ("sol_holdout_diagnostic", "Sol diagnostic · 156 targets")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharex=True)
    for ax, (source, title) in zip(axes, sources):
        data = metrics[metrics["label_source"] == source].set_index("variant").reindex(focus)
        ax.barh(range(len(focus)), data["pairwise_accuracy"], color="#477ba4")
        ax.axvline(data.loc["B3 Sonnet", "pairwise_accuracy"], color="#b55f32", ls="--", lw=1)
        ax.set_xlim(0, 1)
        ax.set_title(title)
        ax.set_xlabel("Pairwise ranking accuracy on labeled pairs")
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=.2)
        ax.set_axisbelow(True)
        for i, value in enumerate(data["pairwise_accuracy"]):
            inside = value > .89
            ax.text(value - .012 if inside else value + .008, i, f"{value:.3f}",
                    ha="right" if inside else "left", va="center", fontsize=8,
                    color="white" if inside else "black")
    axes[0].set_yticks(range(len(focus)), focus)
    axes[1].set_yticks(range(len(focus)), [])
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, help="directory for results; default: a timestamped local run")
    parser.add_argument("--export-variant", help="also write this variant as a candidates run for the existing LLM selector")
    args = parser.parse_args()
    universe, ids, training, sectors = read_inputs()
    labels = load_labels(training)
    general, sector, industry = load_facet_sources(ids)
    vectors = vectors_for(required_texts(general, sector, industry))
    base_per, base_info, base_k = general_components(general["haiku"], vectors)
    base = fw.combine(base_per, base_info)
    reproduced = check_saved_baseline(base, ids, training)
    sonnet_per, sonnet_info, sonnet_k = general_components(general["sonnet"], vectors)
    additions = addition_matrices(ids, sectors, vectors, sector, industry)
    variants: dict[str, np.ndarray] = {"B3 Haiku": base, "B3 Sonnet": fw.combine(sonnet_per, sonnet_info)}
    for facet in base_per:
        variants[f"Haiku minus {fc.FACET_ID.get(facet, facet)} {facet}"] = fw.combine(
            {k: v for k, v in base_per.items() if k != facet}, base_info)
    for facet in sonnet_per:
        variants[f"Sonnet minus {fc.FACET_ID.get(facet, facet)} {facet}"] = fw.combine(
            {k: v for k, v in sonnet_per.items() if k != facet}, sonnet_info)
    for name, matrix in additions.items():
        variants[f"Sonnet + {name}"] = fw.combine({**sonnet_per, name: matrix}, sonnet_info)
    variants["Sonnet + all additions"] = fw.combine({**sonnet_per, **additions}, sonnet_info)
    if args.export_variant and args.export_variant not in variants:
        parser.error(f"unknown variant {args.export_variant!r}; choose from: {', '.join(variants)}")

    results, target_results, lists = [], [], []
    for i, (name, S) in enumerate(variants.items(), 1):
        print(f"{i}/{len(variants)} {name}", flush=True)
        rows, per_target, chosen = score_variant(name, S, ids, training, labels)
        results.extend(rows)
        target_results.extend(per_target)
        listed = chosen[chosen["target"].isin(labels["human_majority"]["target"])].copy()
        listed.insert(0, "variant", name)
        lists.append(listed)
    out = args.output or V1 / "facet_add_drop" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    metrics = pd.DataFrame(results)
    targets = pd.DataFrame(target_results)
    metrics.to_csv(out / "metrics.csv", index=False, lineterminator="\n")
    targets.to_csv(out / "target_metrics.csv", index=False, lineterminator="\n")
    paired_deltas(targets).to_csv(out / "paired_deltas.csv", index=False, lineterminator="\n")
    pd.concat(lists, ignore_index=True).to_csv(out / "human_target_lists.csv", index=False, lineterminator="\n")
    chart(metrics, out / "pairwise_accuracy.png")
    split_info = json.loads((V1 / "split" / SPLIT_RUN / "run.json").read_text(encoding="utf-8"))
    source_paths = [
        LABELS, V1 / "split" / SPLIT_RUN / "split.csv",
        V1 / "universe" / split_info["universe_run"] / "universe.csv",
        V1 / "facets" / "tables" / "facets.csv", V1 / "facets_sonnet" / "tables" / "facets.csv",
        V1 / "sector_facets_sonnet" / "tables" / "sector_facets.csv",
        V1 / "industry_facets_sonnet" / "tables" / "industry_facets_long.csv",
        V1 / "judge" / "tables" / "judgments.csv",
        V1 / "holdout_completion" / "graded_peer_selection" / "grades.csv",
    ]
    if ROUND2.exists():
        source_paths.append(ROUND2)
    manifest = {
        "split_run": SPLIT_RUN, "b3_run": B3_RUN, "model": "all-mpnet-base-v2",
        "rule": "B3 with mutual top 10, top up to 3; exactly one facet or facet bundle changed per variant",
        "facets": list(sonnet_per), "additions": list(additions), "label_counts": {k: len(v) for k, v in labels.items()},
        "saturation_k": {"haiku": base_k, "sonnet": sonnet_k}, "baseline_check": reproduced,
        "round2_included": ROUND2.exists(),
        "sources_sha256": {str(p.relative_to(V1)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in source_paths if p.exists()},
    }
    (out / "run.json").write_bytes(json.dumps(manifest, indent=2).encode("utf-8"))
    if args.export_variant:
        variant = args.export_variant
        candidate_dir = out / "selector_candidates"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        ticker = universe.set_index("IQ_COMPANY_ID")["target_ciq_ticker"]
        ranking, candidates = mc.tables_from_similarity(variants[variant], ids, training, training, ticker)
        ranking.to_csv(candidate_dir / "ranking.csv.gz", index=False)
        candidates.to_csv(candidate_dir / "candidates.csv", index=False, lineterminator="\n")
        (candidate_dir / "run.json").write_bytes(json.dumps({
            "run": out.name, "method": variant, "universe_run": split_info["universe_run"],
            "split_run": SPLIT_RUN, "facet_source": "sonnet" if variant.startswith("Sonnet") else "haiku",
            "evaluation": str(out), "targets": "training", "n_targets": len(training),
            "selected_pairs": int(candidates["selected"].sum()),
        }, indent=2).encode("utf-8"))
        print(f"Selector input: {candidate_dir} ({len(training)} targets; "
              f"{int(candidates['selected'].sum())} selected pairs)")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
