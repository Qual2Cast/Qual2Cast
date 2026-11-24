"""Add a batch of agent-graded pairs to a copy of the Sonnet label workbook, for a reviewer to grade by hand.

The new rows use the layout of Fiona's direct-peer rows (direct_peer_pairs.py assemble): what the sheet shows per
company (name, SIC industry, website, Sonnet offering and customers, business scope), blank reviewer columns, B3
rank and similarity, the agent's grade, reason and facet scores, and provenance. The reviewer columns stay blank:
a blank grade is not judged, never 0. Never overwrites: writes <book stem>_<batch>_<stamp>.xlsx next to the book.

  uv run python v2/06_labels/scripts/extend_label_book.py \\
      --pairs outputs-local/v1a/05_agent_grading/b3_kept_30/pairs.csv \\
      --agent outputs-local/v1a/05_agent_grading/b3_kept_30/agent --batch b3_kept_30
--pairs: target, comp (ids), rank, similarity (the current B3 list). --agent: an agent_loop.py run folder.
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

import pandas as pd  # noqa: E402

BOOK = v2.src("06_labels", "barbara_293", "sonnet_label.xlsx")
IDS = {"target": str, "comp": str}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows_for(pairs: pd.DataFrame, verdicts: pd.DataFrame, batch: str) -> pd.DataFrame:
    import direct_peer_pairs as dp
    cur = v2.current()
    split = pd.read_csv(v2.path(cur["universe"]["split"]), dtype=str).set_index("IQ_COMPANY_ID")["sample"]
    if not (pairs["target"].map(split).eq("training").all() and pairs["comp"].map(split).eq("training").all()):
        raise SystemExit("a pair touches a holdout company; holdout pairs go to 10_final_holdout only")
    facets = pd.read_csv(v2.path(cur["profiles"]["general"]), dtype=str).fillna("")
    shown = dp.shown_companies(dp.universe(), pd.DataFrame(columns=["IQ_COMPANY_ID"]), facets)
    scopes = json.loads(dp.SCOPES.read_text(encoding="utf-8"))
    r = pairs.merge(verdicts, on=["target", "comp"], how="left", validate="one_to_one", suffixes=("", "_agent"))
    r["status"] = r["status"].fillna("not run")
    t, c = shown.loc[r["target"]].reset_index(drop=True), shown.loc[r["comp"]].reset_index(drop=True)
    sheet = pd.DataFrame({
        "pair": t["ticker"] + "-" + c["ticker"], "target_ticker": t["ticker"], "target_company": t["company"],
        "target_sic_industry": t["sic_industry"], "target_website": t["website"], "target_offering": t["offering"],
        "target_customers": t["customers"],
        "target_business_scope": [scopes.get(x, {}).get("scope_note", "").removeprefix("Current company scope: ")
                                  for x in t["ticker"]],
        "comp_ticker": c["ticker"], "comp_company": c["company"], "comp_sic_industry": c["sic_industry"],
        "comp_website": c["website"], "comp_offering": c["offering"], "comp_customers": c["customers"],
        "score_matthew": None, "reason_if_0_matthew": None, "notes_matthew": None,
        "score_barbara": None, "reason_if_0_barbara": None, "notes_barbara": None,
        "rank": r["rank"], "similarity": r["similarity"],
        "agent_score": r["score"], "agent_verdict": r["verdict"], "agent_reason": r["reason"],
        "target_id": r["target"], "comp_id": r["comp"], "batch": batch,
        "source_pair_id": r.get("request_no"), "agent_status": r["status"],
        "agent_lookups": r.get("lookups"), "agent_web_searches": r.get("web_searches"), "agent_error": r.get("error"),
    })
    facet_cols = [col for col in r.columns if col.startswith("facet_")]
    return pd.concat([sheet, r[facet_cols].add_prefix("agent_").reset_index(drop=True)], axis=1)


def main(argv=None) -> Path:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pairs", type=Path, required=True)
    ap.add_argument("--agent", type=Path, required=True, help="agent_loop.py run folder (verdicts.csv, config.json)")
    ap.add_argument("--batch", required=True)
    ap.add_argument("--book", type=Path, default=BOOK)
    args = ap.parse_args(argv)
    args.pairs, args.agent, args.book = args.pairs.resolve(), args.agent.resolve(), args.book.resolve()
    pairs = pd.read_csv(args.pairs, dtype=IDS)
    verdicts = pd.read_csv(args.agent / "verdicts.csv", dtype=IDS)
    book = pd.read_excel(args.book, dtype={"target_id": str, "comp_id": str})
    if "batch" not in book:
        book["batch"] = "rounds 1-3 (original 293)"
    clash = set(zip(pairs["target"], pairs["comp"])) & set(zip(book["target_id"], book["comp_id"]))
    if clash:
        raise SystemExit(f"{len(clash)} pairs are already in the workbook")
    new = rows_for(pairs, verdicts, args.batch)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = v2.out("06_labels") / "barbara_293" / f"{args.book.stem}_{args.batch}_{stamp}.xlsx"   # v2: new books in v2
    out.parent.mkdir(parents=True, exist_ok=True)
    combined = pd.concat([book, new], ignore_index=True)
    with pd.ExcelWriter(out) as xl:
        combined.to_excel(xl, sheet_name="pairs", index=False)
    config = json.loads((args.agent / "config.json").read_text(encoding="utf-8"))
    summary = {"workbook": out.relative_to(v2.ROOT).as_posix(), "original_rows": len(book), "added_rows": len(new),
               "batch": args.batch, "agent_status": new["agent_status"].value_counts().to_dict(),
               "agent_score": new["agent_score"].fillna(-1).astype(int).value_counts().sort_index().to_dict(),
               "agent_settings": {k: config.get(k) for k in ("backend", "model", "search", "search_model",
                                                              "max_steps", "facet_scores", "prompt_version")},
               "sources_sha256": {p.relative_to(v2.ROOT).as_posix(): sha256(p)
                                  for p in [args.book, args.pairs, args.agent / "verdicts.csv"]}}
    out.with_suffix(".json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return out


if __name__ == "__main__":
    main()
