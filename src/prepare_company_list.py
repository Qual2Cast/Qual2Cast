"""
Build the corrected company-list snapshot from the raw one.

  data-local/snapshots/company_list_v1_raw.csv   as received (never edited)
      -> this script ->
  data-local/snapshots/company_list_v3_websites_fixed.csv       corrected snapshot
  data-local/snapshots/company_list_v3_websites_fixed_changes.csv  every cell changed + why

Corrections (each one reviewed; add new ones here rather than editing files):
  1. SIC codes loaded as 4-character, zero-padded strings, and the 2- and
     3-digit codes re-derived from them. Fixes BrightView Holdings (SIC 0700,
     Agricultural Services), which the spreadsheet stored as 700 and so
     grouped with hotels under SIC 70. (v2)
  2. Investor-relations hosts replaced by the company's main domain
     (ir.wingstop.com -> wingstop.com): Aziz's rule excludes IR pages. (v3)
  3. Websites missing or wrong in the source, replaced from WEBSITE_FIXES
     below; each entry records who supplied it. (v3)

All other values are copied through unchanged, as text.
(v2 = correction 1 only; its file is kept for reference.)

Usage:
  python src/prepare_company_list.py                    # build v3, print changes
  python src/prepare_company_list.py --update-manifest  # data maintainer only:
                                                        # record new checksums
"""

from __future__ import annotations

import argparse
import json
import re

import pandas as pd

from project_data import MANIFEST_PATH, REPO_ROOT, load_manifest, normalize_sic_codes, sha256

RAW = "company_list_v1_raw"
OUT = "company_list_v3"

# Correction 3: IQ_COMPANY_ID -> (website, who supplied it / why)
WEBSITE_FIXES = {
    "IQ328847166": ("www.smithdouglas.com",
                    "source had '0'; site supplied by team (M. Chen), 2026-10-17"),
}
IR_HOST = re.compile(r"^((?:https?://)?)(?:ir|investors?|investor-relations)\.", re.I)


def fix_websites(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Corrections 2 and 3. Returns the fixed table and IQ_ID -> reason."""
    df = df.copy()
    reasons = {}
    for i, site in df["target_ciq_website"].items():
        iq_id = df.at[i, "IQ_COMPANY_ID"]
        if iq_id in WEBSITE_FIXES:
            df.at[i, "target_ciq_website"], reasons[iq_id] = WEBSITE_FIXES[iq_id]
        elif IR_HOST.match(site.strip()):
            df.at[i, "target_ciq_website"] = IR_HOST.sub(r"\1", site.strip())
            reasons[iq_id] = "investor-relations host replaced by main domain"
    return df, reasons


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--update-manifest", action="store_true",
                   help="write the new snapshot's checksum into data_manifest.json")
    args = p.parse_args()

    manifest = load_manifest()
    raw_path = REPO_ROOT / manifest["snapshots"][RAW]["file"]
    out_path = REPO_ROOT / manifest["snapshots"][OUT]["file"]
    raw = pd.read_csv(raw_path, dtype=str, keep_default_na=False)
    fixed, site_reasons = fix_websites(normalize_sic_codes(raw))

    changes = []
    for col in raw.columns:
        for i in raw.index[raw[col] != fixed[col]]:
            iq_id = raw.at[i, "IQ_COMPANY_ID"]
            reason = (site_reasons[iq_id] if col == "target_ciq_website"
                      else "SIC zero-padding")
            changes.append({"IQ_COMPANY_ID": iq_id,
                            "target_company_name": raw.at[i, "target_company_name"],
                            "column": col, "old": raw.at[i, col], "new": fixed.at[i, col],
                            "reason": reason})
    # CRLF on every OS, matching the raw export and the manifest checksums
    fixed.to_csv(out_path, index=False, lineterminator="\r\n")
    changes_path = out_path.with_name(out_path.stem + "_changes.csv")
    pd.DataFrame(changes, columns=["IQ_COMPANY_ID", "target_company_name", "column",
                                   "old", "new", "reason"]).to_csv(
        changes_path, index=False, lineterminator="\r\n")

    print(f"Wrote {out_path.relative_to(REPO_ROOT)} ({len(fixed)} rows), "
          f"{len(changes)} cells changed:")
    for c in changes:
        print(f"  {c['target_company_name']}: {c['column']} {c['old']} -> {c['new']}")

    if args.update_manifest:
        for name, path in ((RAW, raw_path), (OUT, out_path)):
            manifest["snapshots"][name]["sha256"] = sha256(path)
            manifest["snapshots"][name]["rows"] = len(raw)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print("Updated checksums in data_manifest.json")
    else:
        expected = manifest["snapshots"][OUT].get("sha256")
        if expected and sha256(out_path) != expected:
            print("Warning: result doesn't match the checksum in data_manifest.json.")


if __name__ == "__main__":
    main()
