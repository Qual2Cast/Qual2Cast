"""Freeze and align the shared v1 inputs without changing their originals."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/sources"


def digest(path: Path) -> dict:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
            "sha256": h.hexdigest()}


def correct_sonnet() -> dict:
    path = V1 / "facets_sonnet/tables/facets.csv"
    source = pd.read_csv(path, dtype=str).fillna("")
    if source["IQ_COMPANY_ID"].duplicated().any() or len(source) != 533:
        raise ValueError("Expected one Sonnet profile per eligible company")
    updated = source.set_index("IQ_COMPANY_ID").copy()
    changes = pd.read_csv(OUT / "yiming_corrections.csv", dtype=str).fillna("")
    applied = changes[changes["applied"] == "True"]
    for row in applied.itertuples(index=False):
        if row.IQ_COMPANY_ID not in updated.index or row.facet not in updated:
            raise ValueError(f"Missing correction target: {row.IQ_COMPANY_ID} {row.facet}")
        if updated.at[row.IQ_COMPANY_ID, row.facet] != row.old:
            raise ValueError(f"Correction source differs: {row.IQ_COMPANY_ID} {row.facet}")
        updated.at[row.IQ_COMPANY_ID, row.facet] = row.new
    changed = set(applied["IQ_COMPANY_ID"])
    updated["divestiture_corrected"] = updated.index.isin(changed)
    updated.reset_index().to_csv(OUT / "facets_sonnet_corrected.csv", index=False)
    return {"companies": len(updated), "corrected_companies": len(changed),
            "corrected_values": len(applied), "review_rows": len(pd.read_csv(OUT / "yiming_review_list.csv"))}


def barbara_crosswalk() -> dict:
    with gzip.open(V1 / "barbara_catalog_probe.json.gz", "rt", encoding="utf-8") as stream:
        catalog = json.load(stream)
    with gzip.open(V1 / "barbara_comparison_probe.json.gz", "rt", encoding="utf-8") as stream:
        targets = json.load(stream)
    companies = pd.DataFrame(catalog["companies"])
    if companies["key"].duplicated().any():
        raise ValueError("Duplicate economic group keys")
    if len(targets) != 560:
        raise ValueError("Unexpected Barbara comparison-target count")
    split = pd.read_csv(V1 / "split/20261027T204930Z/split.csv", dtype=str)
    baseline = set(split["IQ_COMPANY_ID"])
    rows = []
    for entry in catalog["companies"]:
        for original_id in entry.get("original_target_ids", []):
            rows.append({"IQ_COMPANY_ID": original_id, "group_key": entry["key"],
                         "name": entry["name"], "listing_status": entry["listing_status"],
                         "profile_shard": catalog["groups"].get(entry["key"], "")})
    crosswalk = pd.DataFrame(rows)
    crosswalk["in_baseline"] = crosswalk["IQ_COMPANY_ID"].isin(baseline)
    crosswalk.to_csv(OUT / "barbara_crosswalk.csv", index=False)
    status = companies["listing_status"].value_counts().to_dict()
    eligible = companies["listing_status"] != "LISTING_OR_LEGAL_ENTITY_MAPPING_REQUIRES_REVIEW"
    return {"catalog_groups": len(companies), "eligible_groups": int(eligible.sum()),
            "status_counts": status, "comparison_targets": len(targets),
            "crosswalk_rows": len(crosswalk), "crosswalk_unique_targets": crosswalk["IQ_COMPANY_ID"].nunique(),
            "baseline_ids_mapped": len(baseline & set(crosswalk["IQ_COMPANY_ID"])),
            "duplicate_original_ids": int(crosswalk["IQ_COMPANY_ID"].duplicated().sum()),
            "profile_shards": len(set(catalog["groups"].values()))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if args.out.resolve() != OUT.resolve():
        raise ValueError("This run uses the fixed local source directory")
    OUT.mkdir(parents=True, exist_ok=True)
    corrected = correct_sonnet()
    crosswalk = barbara_crosswalk()
    files = [
        ROOT / "data-local/snapshots/company_list_v3_websites_fixed.csv",
        V1 / "split/20261027T204930Z/split.csv",
        V1 / "universe/20261025T060358Z/financials.csv",
        V1 / "facets_sonnet/tables/facets.csv",
        V1 / "sector_facets_sonnet/tables/sector_facets.csv",
        V1 / "industry_facets_sonnet/tables/industry_facets_long.csv",
        V1 / "golden_set/labels/reviewer_labels_20261028.json",
        OUT / "sonnet_label.xlsx",
        V1 / "barbara_catalog_probe.json.gz", V1 / "barbara_comparison_probe.json.gz",
        OUT / "barbara_site_20261030.html",
        *(OUT / f"yiming_{name}.csv" for name in ("checks", "exits", "corrections", "review_list")),
    ]
    record = {"sonnet_corrections": corrected, "barbara_catalog": crosswalk,
              "inputs": [digest(path) for path in files]}
    (OUT / "manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({"sonnet_corrections": corrected, "barbara_catalog": crosswalk}, indent=2))


if __name__ == "__main__":
    main()
