"""Barbara's direct-peer pairs (2026-11-17): 90 target-comp pairs she picked as
candidate direct peers for the 45 labelled targets, two per target, each marked
Yes or No ("Barbara - If Direct"). Kethan's run instructions: fill facets for the
comps outside the universe, run the agent loop on all 90 pairs, and write the
development pairs and the holdout pairs to separate outputs, with Barbara's
labels added only after the model has run.

  python v1/scripts/direct_peer_pairs.py prepare --source <Barbara's CSV>
      writes <run>/source/ (copy + sha256), manifest.csv (90 pairs, every source
      column, ids), external_companies.csv, pairs.csv (target, comp only: the
      agent never sees the labels), freeze.json (commit, B3 run, split, prompt
      and model versions). Stops if the counts differ from the instructions.
  python v1/scripts/fill_facets.py --backend claude-cli --companies <run>/external_companies.csv \
      --out <run>/facets_external
  python v1/scripts/agent_loop.py --pairs file --pair-file <run>/pairs.csv \
      --extra-companies <run>/external_companies.csv \
      --extra-facets <run>/facets_external/tables/facets.csv --facet-scores --out <run>/agent
  python v1/scripts/direct_peer_pairs.py assemble --run <run>
      writes the 359-row copy of sonnet_label.xlsx (293 + 66 development pairs)
      next to the original, and the 24 holdout pairs under
      holdout_completion/direct_peers_<stamp>/. Never overwrites.

Labels (applied in assemble only): Yes -> score_barbara 2; No -> blank, never 0
(Barbara picked these as candidates; No means "not a clean direct peer", which
is not a labelled negative). Matthew's columns stay blank. Holdout pairs are a
final check only: nothing is tuned on them.

External comps get ids EXT_<ticker>. They are not added to the universe or the
split, and they have no saved website pages: the scrape cannot run from this
environment (company sites are blocked by the network policy), so their facets
come from the facet model's first pass (name and website only) and the agent
reads them through web search. B3 has no score for any of these pairs: the
external comps are outside the universe and the holdout comps are outside B3's
comp pool (training companies only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import facets as fc  # noqa: E402  (puts src/ on the path)
from project_data import OUTPUTS_LOCAL, REPO_ROOT  # noqa: E402

V1 = OUTPUTS_LOCAL / "v1"
CANDIDATES = V1 / "candidates_method1/20261104T074915Z"          # the B3 baseline run
SPLIT = V1 / "split/20261027T204930Z/split.csv"
UNIVERSE_FACETS = V1 / "facets_sonnet/tables/facets.csv"
SCOPES = V1 / "business_structure_refinement/split_classification/refined_scopes.json"
LABEL_BOOK = V1 / "integration/sources/sonnet_label.xlsx"
HOLDOUT_OUT = V1 / "holdout_completion"
OUT = V1 / "direct_peers_barbara"

EXPECTED = {"pairs": 90, "targets": 45, "comps": 88, "yes": 62, "no": 28, "external_pairs": 66,
            "external_comps": 64, "holdout_pairs": 24, "external_yes": 43, "holdout_yes": 19}
LABEL_COL = "Barbara - If Direct"
SOURCE_COLS = ["target_ticker", "target_name", "peer_no", "peer_ticker", "peer_name", "where_peer_is",
               "why_direct", "confidence", "caveat", LABEL_COL, "Reason Yes", "Reason No"]

# Official websites of the external comps (CIQ style). Listing and exchange notes from
# Barbara's caveat column. The facet model gets the name and website only.
WEBSITES = {
    "EXPE": "www.expediagroup.com", "BKNG": "www.bookingholdings.com", "VMD": "www.viemed.com",
    "RLI": "www.rlicorp.com", "ARDX": "www.ardelyx.com", "RMTI": "www.rockwellmed.com",
    "TDY": "www.teledyne.com", "EME": "www.emcorgroup.com", "VMI": "www.valmont.com",
    "WS": "www.worthingtonsteel.com", "URI": "www.unitedrentals.com", "ARKR": "www.arkrestaurants.com",
    "BJRI": "www.bjsrestaurants.com", "ATRO": "www.astronics.com", "PRIM": "www.prim.com",
    "CW": "www.curtisswright.com", "IEX": "www.idexcorp.com", "FCN": "www.fticonsulting.com",
    "EXLS": "www.exlservice.com", "AMRZ": "www.amrize.com", "KRX": "www.kingspan.com",
    "EGHT": "www.8x8.com", "OOMA": "www.ooma.com", "ONON": "www.on.com", "CROX": "www.crocs.com",
    "LTRX": "www.lantronix.com", "INSG": "www.inseego.com", "SMP": "www.smpcorp.com",
    "MPAA": "www.motorcarparts.com", "JCAP": "www.jcap.com", "INTRUM": "www.intrum.com",
    "PEG": "www.pseg.com", "FPH": "www.fivepoint.com", "SON": "www.sonoco.com",
    "MYE": "www.myersindustries.com", "PVH": "www.pvh.com", "UMBF": "www.umb.com",
    "VLGEA": "www.villagesupermarkets.com", "WU": "www.westernunion.com", "RELY": "www.remitly.com",
    "HUBG": "www.hubgroup.com", "PRVA": "www.priviahealth.com", "SGRY": "www.surgerypartners.com",
    "LAMR": "www.lamar.com", "DEC": "www.jcdecaux.com", "SBLK": "www.starbulk.com",
    "SB": "www.safebulkers.com", "DK": "www.delekus.com", "PBF": "www.pbfenergy.com",
    "XPOF": "www.xponential.com", "LTH": "www.lifetime.life", "KW": "www.kennedywilson.com",
    "ARES": "www.aresmgmt.com", "GL9": "www.glanbia.com", "HAIN": "www.hain.com",
    "AESI": "www.atlas.energy", "ACDC": "www.profrac.com", "WINA": "www.winmarkcorporation.com",
    "TDUP": "www.thredup.com", "SPX": "www.spiraxgroup.com", "CECO": "www.cecoenviro.com",
    "GDDY": "www.godaddy.com", "HAL": "www.halliburton.com", "SLB": "www.slb.com",
}


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def universe() -> pd.DataFrame:
    meta = json.loads((CANDIDATES / "run.json").read_text(encoding="utf-8"))
    path = V1 / "universe" / meta["universe_run"] / "universe.csv"
    return pd.read_csv(path, dtype=str)


def counts(src: pd.DataFrame) -> dict:
    ext = src[src["where_peer_is"].eq("not in universe")]
    hold = src[src["where_peer_is"].eq("universe (holdout)")]
    yes = src[LABEL_COL].eq("Yes")
    return {"pairs": len(src.drop_duplicates(["target_ticker", "peer_ticker"])),
            "targets": src["target_ticker"].nunique(), "comps": src["peer_ticker"].nunique(),
            "yes": int(yes.sum()), "no": int(src[LABEL_COL].eq("No").sum()),
            "external_pairs": len(ext), "external_comps": ext["peer_ticker"].nunique(),
            "holdout_pairs": len(hold), "external_yes": int(yes[ext.index].sum()),
            "holdout_yes": int(yes[hold.index].sum())}


def build_manifest(src: pd.DataFrame, uni: pd.DataFrame, split: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One row per pair with every source column, ids and split; and the external companies."""
    ids = uni.set_index(uni["target_ciq_ticker"].str.upper())["IQ_COMPANY_ID"]
    sample = split.set_index("IQ_COMPANY_ID")["sample"]
    ext = src[src["where_peer_is"].eq("not in universe")].drop_duplicates("peer_ticker")
    missing_site = sorted(set(ext["peer_ticker"]) - set(WEBSITES))
    if missing_site:
        raise SystemExit(f"no website for external comps: {missing_site}")
    clash = set(ext["peer_ticker"]) & set(ids.index)
    if clash:
        raise SystemExit(f"'not in universe' comps found in the universe: {sorted(clash)}")
    external = pd.DataFrame({"IQ_COMPANY_ID": "EXT_" + ext["peer_ticker"].str.replace(".", "_", regex=False),
                             "target_company_name": ext["peer_name"], "target_ciq_ticker": ext["peer_ticker"],
                             "target_ciq_website": ext["peer_ticker"].map(WEBSITES)}).reset_index(drop=True)
    ext_ids = external.set_index("target_ciq_ticker")["IQ_COMPANY_ID"]

    m = src[SOURCE_COLS].copy()
    m.insert(0, "pair_id", [f"DP{i:02d}" for i in range(1, len(m) + 1)])
    m["target_id"] = m["target_ticker"].map(ids)
    m["comp_id"] = [ids.get(t) if w == "universe (holdout)" else ext_ids.get(t)
                    for t, w in zip(m["peer_ticker"], m["where_peer_is"])]
    if m[["target_id", "comp_id"]].isna().any().any():
        bad = m[m[["target_id", "comp_id"]].isna().any(axis=1)][["target_ticker", "peer_ticker"]]
        raise SystemExit(f"could not identify:\n{bad}")
    m["target_sample"] = m["target_id"].map(sample)
    m["comp_sample"] = m["comp_id"].map(sample).fillna("external (not in universe)")
    m["output"] = m["where_peer_is"].map({"not in universe": "development", "universe (holdout)": "holdout"})
    if not m["target_sample"].eq("training").all():
        raise SystemExit("a target is not in the training sample")
    if not m.loc[m["output"].eq("holdout"), "comp_sample"].eq("holdout").all():
        raise SystemExit("a 'universe (holdout)' comp is not in the holdout sample")
    ranking = pd.read_csv(CANDIDATES / "ranking.csv.gz", dtype={"target": str, "comp": str})
    m = m.merge(ranking[["target", "comp", "similarity", "rank"]].rename(
        columns={"target": "target_id", "comp": "comp_id", "similarity": "b3_similarity", "rank": "b3_rank"}),
        on=["target_id", "comp_id"], how="left")
    m["b3_status"] = ["scored" if pd.notna(s) else
                      ("comp outside the universe" if o == "development" else "comp outside B3's comp pool (holdout)")
                      for s, o in zip(m["b3_similarity"], m["output"])]
    return m, external


def prepare(args) -> None:
    source = Path(args.source)
    src = pd.read_csv(source, dtype=str).fillna("")
    found = counts(src)
    if found != EXPECTED:
        raise SystemExit(f"counts differ from the instructions:\n found    {found}\n expected {EXPECTED}")
    out = Path(args.out) if args.out else OUT / stamp()
    if (out / "manifest.csv").exists():
        raise SystemExit(f"{out} is already prepared (never overwritten)")
    (out / "source").mkdir(parents=True, exist_ok=True)
    copy = out / "source" / source.name
    shutil.copy2(source, copy)
    digest = sha256(copy)
    (out / "source" / "sha256.txt").write_text(f"{digest}  {source.name}\n", encoding="utf-8")

    split = pd.read_csv(SPLIT, dtype=str)
    manifest, external = build_manifest(src, universe(), split)
    manifest.to_csv(out / "manifest.csv", index=False)
    external.to_csv(out / "external_companies.csv", index=False)
    manifest[["target_id", "comp_id"]].rename(columns={"target_id": "target", "comp_id": "comp"}).to_csv(
        out / "pairs.csv", index=False)       # what the agent loop reads: no labels, no notes

    import agent_loop  # noqa: E402  (its PROMPT_VERSION)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    freeze = {"created": stamp(), "git_commit": commit, "source_file": source.name, "source_sha256": digest,
              "counts": found, "b3_baseline": str(CANDIDATES.relative_to(REPO_ROOT)),
              "b3_scored_pairs": int(manifest["b3_status"].eq("scored").sum()),
              "split": str(SPLIT.relative_to(REPO_ROOT)), "universe_facets": str(UNIVERSE_FACETS.relative_to(REPO_ROOT)),
              "facet_prompt_version": fc.PROMPT_VERSION, "facet_model": "claude-cli claude-sonnet-5-5",
              "agent_prompt_version": agent_loop.PROMPT_VERSION, "agent_model": "claude-cli sonnet, search sonnet",
              "external_pages": "none: company websites are blocked from this environment, so no scrape; "
                                "facets from the first pass only, agent evidence from web search"}
    (out / "freeze.json").write_text(json.dumps(freeze, indent=1), encoding="utf-8")
    print(json.dumps(found))
    print(f"prepared {len(manifest)} pairs, {len(external)} external companies -> {out}")


def shown_companies(uni: pd.DataFrame, external: pd.DataFrame, facets: pd.DataFrame) -> pd.DataFrame:
    """What the label sheet shows per company: name, SIC industry, website, offering, customers."""
    info = pd.concat([uni, external.reindex(columns=uni.columns)]).set_index("IQ_COMPANY_ID")
    b1 = facets[(facets["business_id"] == "B1") & (facets["llm_status"] == "ok")].set_index("IQ_COMPANY_ID")
    return pd.DataFrame({"ticker": info["target_ciq_ticker"], "company": info["target_company_name"],
                         "sic_industry": info["target_primary_sic_industry"].fillna(""),
                         "website": info["target_ciq_website"],
                         "offering": b1["offering_description"].reindex(info.index).fillna(""),
                         "customers": b1["customer_segment"].reindex(info.index).fillna("")})


def assemble(args) -> None:
    run = Path(args.run).resolve()
    manifest = pd.read_csv(run / "manifest.csv", dtype=str).fillna("")
    external = pd.read_csv(run / "external_companies.csv", dtype=str)
    agent = pd.read_csv(run / "agent" / "verdicts.csv", dtype={"target": str, "comp": str})
    facets = pd.concat([pd.read_csv(UNIVERSE_FACETS, dtype=str),
                        pd.read_csv(run / "facets_external/tables/facets.csv", dtype=str)]).fillna("")
    shown = shown_companies(universe(), external, facets)
    scopes = json.loads(SCOPES.read_text(encoding="utf-8"))

    rows = manifest.merge(agent.rename(columns={"target": "target_id", "comp": "comp_id"}),
                          on=["target_id", "comp_id"], how="left", suffixes=("", "_agent"))
    if len(rows) != len(manifest):
        raise SystemExit("agent verdicts repeat a pair")
    rows["status"] = rows["status"].fillna("not run")
    t, c = shown.loc[rows["target_id"]].reset_index(drop=True), shown.loc[rows["comp_id"]].reset_index(drop=True)
    yes = rows[LABEL_COL].eq("Yes")
    sheet = pd.DataFrame({
        "pair": rows["target_ticker"] + "-" + rows["pair_id"],
        "target_ticker": rows["target_ticker"], "target_company": t["company"],
        "target_sic_industry": t["sic_industry"], "target_website": t["website"],
        "target_offering": t["offering"], "target_customers": t["customers"],
        "target_business_scope": [scopes.get(x, {}).get("scope_note", "").removeprefix("Current company scope: ")
                                  for x in rows["target_ticker"]],
        "comp_ticker": rows["peer_ticker"], "comp_company": c["company"], "comp_sic_industry": c["sic_industry"],
        "comp_website": c["website"], "comp_offering": c["offering"], "comp_customers": c["customers"],
        "score_matthew": None, "reason_if_0_matthew": None, "notes_matthew": None,
        "score_barbara": [2 if y else None for y in yes],          # No stays blank, never 0
        "reason_if_0_barbara": None,
        "notes_barbara": [ry if y else rn for y, ry, rn in zip(yes, rows["Reason Yes"], rows["Reason No"])],
        "rank": rows["b3_rank"].replace("", None), "similarity": rows["b3_similarity"].replace("", None),
        "agent_score": rows["score"], "agent_verdict": rows["verdict"], "agent_reason": rows["reason"],
        "target_id": rows["target_id"], "comp_id": rows["comp_id"],
        # provenance, traceable to Barbara's CSV
        "batch": "barbara_direct_peers_20261117", "source_pair_id": rows["pair_id"],
        "src_where_peer_is": rows["where_peer_is"], "src_barbara_if_direct": rows[LABEL_COL],
        "src_why_direct": rows["why_direct"], "src_confidence": rows["confidence"], "src_caveat": rows["caveat"],
        "src_reason_yes": rows["Reason Yes"], "src_reason_no": rows["Reason No"],
        "b3_status": rows["b3_status"], "agent_status": rows["status"],
        "agent_lookups": rows.get("lookups"), "agent_web_searches": rows.get("web_searches"),
        "agent_error": rows.get("error"),
    })
    facet_cols = [col for col in rows.columns if col.startswith("facet_")]
    sheet = pd.concat([sheet, rows[facet_cols].add_prefix("agent_")], axis=1)
    dev, hold = sheet[rows["output"].eq("development")], sheet[rows["output"].eq("holdout")]

    when = stamp()
    book = pd.read_excel(LABEL_BOOK)
    book_out = LABEL_BOOK.with_name(f"sonnet_label_direct_peers_{when}.xlsx")
    combined = pd.concat([book.assign(batch="rounds 1-3 (original 293)"), dev], ignore_index=True)
    with pd.ExcelWriter(book_out) as xl:
        combined.to_excel(xl, sheet_name="pairs", index=False)
    hold_dir = HOLDOUT_OUT / f"direct_peers_{when}"
    hold_dir.mkdir(parents=True)
    hold.to_csv(hold_dir / "pairs.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(hold_dir / "pairs.xlsx") as xl:
        hold.to_excel(xl, sheet_name="pairs", index=False)
    shutil.copy2(run / "manifest.csv", hold_dir / "manifest.csv")

    labels = sheet["score_barbara"]
    summary = {
        "run": str(run.relative_to(REPO_ROOT)), "workbook": str(book_out.relative_to(REPO_ROOT)),
        "holdout": str(hold_dir.relative_to(REPO_ROOT)),
        "pairs_attempted": len(sheet), "development_pairs": len(dev), "holdout_pairs": len(hold),
        "workbook_rows": len(combined), "original_rows": len(book),
        "agent_status": sheet["agent_status"].value_counts().to_dict(),
        "agent_score_by_label": pd.crosstab(sheet["src_barbara_if_direct"],
                                            sheet["agent_score"].fillna(-1).astype(int)).to_dict(),
        "barbara_scores": {"2": int(labels.eq(2).sum()), "blank": int(labels.isna().sum()),
                           "0": int(labels.eq(0).sum())},
        "b3_status": sheet["b3_status"].value_counts().to_dict(),
    }
    (run / "assemble_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (hold_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--source", required=True, help="Barbara's direct_peer_candidates CSV")
    p.add_argument("--out", help="run folder (default direct_peers_barbara/<time>)")
    a = sub.add_parser("assemble")
    a.add_argument("--run", required=True)
    args = ap.parse_args(argv)
    {"prepare": prepare, "assemble": assemble}[args.cmd](args)


if __name__ == "__main__":
    main()
