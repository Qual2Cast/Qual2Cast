"""
SCRAPS: set aside on 2026-10-18 (Codex extraction was started before the
matching method was settled). Kept runnable for reference; see scraps/README.md.

Human audit of the Codex profiles: measures whether the extracted values are
correct readings of the company's website, which automated checks can't do.
(Pydantic validation shows a value is well-formed and backed by a real quote;
it can't show the quote actually supports the value.)

  python step3_audit_profiles.py sample            # 30 random companies -> audit sheet
  python step3_audit_profiles.py sample -n 20 --seed 7
  python step3_audit_profiles.py score outputs-local/scraps/codex_profiles/step3_audit/audit_sheet_....csv
  python step3_audit_profiles.py carry outputs-local/scraps/codex_profiles/step3_audit/audit_sheet.csv
                         (after the profiles were redone: same companies,
                         earlier judgments reused where the item is unchanged)

The sheet (CSV, opens in Excel) has one row per item to judge:
  stated items     value + the quote supporting it + source page link
  unknown fields   "(unknown)": checks the website really doesn't say it

The auditor fills in `judgment` for every row, opening the source link when
needed:
  yes      the website supports this value (for unknown rows: the website
           really doesn't say this)
  partly   partly supported, or vaguer/broader than the website says
  no       not supported, wrong, or (for unknown rows) the website does say it
and may add a `comment`. `score` then reports accuracy per column.

Only current profiles (current prompt version and page text) are sampled. Output goes to
outputs-local/scraps/codex_profiles/step3_audit/ (sheets are never overwritten).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import profile_schema as pm
from step2_extract_profiles import (DEFAULT_OUT, PROMPT_VERSION, is_current, load_page_text, mask,
                                    name_variants, output_paths)

JUDGMENTS = ["yes", "partly", "no"]


def field_rows(rec: dict) -> dict[str, list[dict]]:
    """Every row that could be judged for one company profile, per field:
    one per verified item, or one "(unknown)" row."""
    urls = {p["page_id"]: p["url"] for p in rec["pages"]}
    profile = rec["profile"]
    base = {"IQ_COMPANY_ID": rec["IQ_COMPANY_ID"], "company_name": rec["company_name"],
            "website": rec["website"]}
    out = {}
    for field in pm.FIELDS:
        record = profile[field]
        if record["status"] == "unknown":
            out[field] = [{**base, "field": field, "kind": "unknown", "value": "(unknown)",
                           "quote": "", "source_url": " | ".join(urls.values())}]
            continue
        if "items" in record:
            parts = [(i["value"], i["quote"], i["found_on"]) for i in record["items"]
                     if i["verified"]]
        else:
            ev = [e for e in record["evidence"] if e["verified"]]
            parts = [(record["value"], " … ".join(e["quote"] for e in ev),
                      [p for e in ev for p in e["found_on"]])] if ev else []
        out[field] = [{**base, "field": field, "kind": "stated", "value": value,
                       "quote": quote,
                       "source_url": " | ".join(dict.fromkeys(urls[p] for p in found_on
                                                              if p in urls))}
                      for value, quote, found_on in parts]
    # No row for matching_summary: it is assembled in code from the items
    # above, so auditing the items audits the summary.
    return out


def field_cap(field: str, max_items: int) -> int:
    return 1 if field == "brands" else max_items   # brands can run to dozens


def sheet_rows(rec: dict, rng: random.Random, max_items: int) -> list[dict]:
    """Rows to judge for one company profile: up to max_items randomly chosen
    items per field (1 for brands), so the sheet stays a size someone will
    actually check carefully."""
    rows = []
    for field, candidates in field_rows(rec).items():
        cap = field_cap(field, max_items)
        rows += rng.sample(candidates, cap) if len(candidates) > cap else candidates
    return rows


def current_profiles(out_dir: Path) -> dict[str, dict]:
    """Profiles made with the current prompt version from the current page text."""
    found = {}
    for path in sorted(output_paths(out_dir).profiles.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("llm_status") == "ok" and is_current(rec, load_page_text(out_dir, rec["IQ_COMPANY_ID"])):
            found[rec["IQ_COMPANY_ID"]] = rec
    return found


def sample(args) -> None:
    out_dir = Path(args.out)
    profiles = list(current_profiles(out_dir).values())
    if not profiles:
        sys.exit("No current profiles to sample; run step2_extract_profiles.py first.")
    rng = random.Random(args.seed)
    chosen = rng.sample(profiles, min(args.n, len(profiles)))
    rows = [r for rec in chosen for r in sheet_rows(rec, rng, args.max_items)]
    sheet = pd.DataFrame(rows)
    sheet.insert(0, "audit_id", range(1, len(sheet) + 1))
    sheet["judgment"] = ""
    sheet["comment"] = ""
    sheet["auditor"] = ""
    path = write_sheet(out_dir, sheet, f"seed{args.seed}")
    print(f"Wrote {path}: {len(chosen)} companies, {len(sheet)} rows to judge "
          f"(seed {args.seed}, prompt version {PROMPT_VERSION}).")
    print("Fill in 'judgment' (yes / partly / no) for every row; see the top of "
          "step3_audit_profiles.py for what each means.")


def write_sheet(out_dir: Path, sheet: pd.DataFrame, label: str) -> Path:
    audit_dir = output_paths(out_dir).audit
    audit_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = audit_dir / f"audit_sheet_{stamp}_{label}.csv"
    sheet.to_csv(path, index=False, encoding="utf-8-sig")   # BOM: Excel shows ™ etc.
    return path


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def carry(args) -> None:
    """A new sheet for the companies of an earlier (judged) sheet, built from
    their current profiles, reusing the earlier judgments:
      same value and quote as a judged row   judgment, comment and auditor
                                             copied (carried_from = its audit_id)
      same value, different quote            judgment left blank; the earlier
                                             judgment and quote shown in
                                             previous_judgment / previous_quote
                                             for a quick confirmation
      new item                               blank, judged from scratch
    Items matching earlier rows are picked first, then others at random up to
    --max-items per field, so the sheet stays the same size."""
    out_dir = Path(args.out)
    old = pd.read_csv(args.sheet, dtype=str, encoding="utf-8-sig").fillna("")
    judged = old[old["judgment"].str.strip() != ""]
    # Quotes are compared with the company's name masked on both sides: since
    # prompt version e the model reads "the Company" where the page has the name.
    names = {r.IQ_COMPANY_ID: name_variants(r.company_name, r.website)
             for r in old.drop_duplicates("IQ_COMPANY_ID").itertuples()}

    def quote_key(iq_id: str, quote: str) -> str:
        return _norm(mask(quote, names[iq_id], [])[0])
    by_quote = {(r.IQ_COMPANY_ID, r.field, r.kind, _norm(r.value),
                 quote_key(r.IQ_COMPANY_ID, r.quote)): r for r in judged.itertuples()}
    by_value = {(r.IQ_COMPANY_ID, r.field, r.kind, _norm(r.value)): r
                for r in judged.itertuples()}
    profiles = current_profiles(out_dir)
    rng = random.Random(args.seed)
    rows, missing = [], []
    for iq_id in dict.fromkeys(old["IQ_COMPANY_ID"]):
        if iq_id not in profiles:
            missing.append(iq_id)   # not re-profiled yet: run step 2 first
            continue
        for field, candidates in field_rows(profiles[iq_id]).items():
            for row in candidates:
                key = (iq_id, field, row["kind"], _norm(row["value"]))
                same = by_quote.get(key + (quote_key(iq_id, row["quote"]),))
                if same is not None:
                    row.update(judgment=same.judgment, comment=same.comment,
                               auditor=same.auditor, carried_from=same.audit_id)
                elif key in by_value:
                    prev = by_value[key]
                    row.update(previous_judgment=prev.judgment, previous_quote=prev.quote,
                               carried_from=prev.audit_id)
            exact = [r for r in candidates if r.get("judgment")]
            similar = [r for r in candidates if "previous_judgment" in r]
            rest = [r for r in candidates if "carried_from" not in r]
            room = max(0, field_cap(field, args.max_items) - len(exact) - len(similar))
            rows += exact + similar + (rng.sample(rest, room) if len(rest) > room else rest)
    if missing:
        sys.exit(f"{len(missing)} companies have no current profile yet "
                 f"({', '.join(missing)}); run step2_extract_profiles.py for them first.")
    columns = ["IQ_COMPANY_ID", "company_name", "website", "field", "kind", "value", "quote",
               "judgment", "comment", "auditor", "source_url", "carried_from",
               "previous_judgment", "previous_quote"]
    sheet = pd.DataFrame(rows).reindex(columns=columns).fillna("")
    sheet.insert(0, "audit_id", range(1, len(sheet) + 1))
    path = write_sheet(out_dir, sheet, "carried")
    carried = (sheet["judgment"] != "").sum()
    confirm = (sheet["previous_judgment"] != "").sum()
    print(f"Wrote {path}: {sheet['IQ_COMPANY_ID'].nunique()} companies, {len(sheet)} rows.")
    print(f"  {carried} judgments carried over (same value and quote)")
    print(f"  {confirm} to confirm (same value, new quote; earlier judgment shown)")
    print(f"  {len(sheet) - carried - confirm} new rows to judge")


def score(args) -> None:
    sheet = pd.read_csv(args.sheet, dtype=str, encoding="utf-8-sig").fillna("")
    sheet["judgment"] = sheet["judgment"].str.strip().str.lower()
    bad = sheet[~sheet["judgment"].isin(JUDGMENTS + [""])]
    if not bad.empty:
        sys.exit(f"Unrecognized judgments in rows {bad['audit_id'].tolist()}: use "
                 f"{', '.join(JUDGMENTS)}.")
    judged = sheet[sheet["judgment"] != ""]
    print(f"{len(judged)} of {len(sheet)} rows judged, "
          f"{judged['IQ_COMPANY_ID'].nunique()} companies.")
    if judged.empty:
        return
    rows = []
    for (field, kind), grp in judged.groupby(["field", "kind"], sort=False):
        counts = grp["judgment"].value_counts()
        n = len(grp)
        rows.append({"field": field, "rows": kind, "judged": n,
                     **{j: int(counts.get(j, 0)) for j in JUDGMENTS},
                     "accuracy (yes)": round(counts.get("yes", 0) / n, 3),
                     "yes + partly": round((counts.get("yes", 0) + counts.get("partly", 0)) / n, 3)})
    result = pd.DataFrame(rows).sort_values(["rows", "field"])
    out = Path(args.sheet).with_name(Path(args.sheet).stem + "_scores.csv")
    result.to_csv(out, index=False)
    print("\n'stated' rows: is the value supported by the website?  'unknown' rows: is it "
          "really not on the website?\n")
    print(result.to_string(index=False))
    print(f"\nSaved {out}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sample", help="write an audit sheet for random companies")
    s.add_argument("-n", type=int, default=30, help="companies to sample (default 30)")
    s.add_argument("--max-items", type=int, default=2,
                   help="items judged per field per company (brands: 1)")
    s.add_argument("--seed", type=int, default=2026, help="random seed, for a reproducible sample")
    s.add_argument("--out", default=str(DEFAULT_OUT))
    c = sub.add_parser("score", help="score a filled-in audit sheet")
    c.add_argument("sheet")
    k = sub.add_parser("carry", help="new sheet for the same companies after their profiles "
                                     "were redone, reusing earlier judgments")
    k.add_argument("sheet", help="the earlier, judged sheet")
    k.add_argument("--max-items", type=int, default=2,
                   help="items per field per company (brands: 1)")
    k.add_argument("--seed", type=int, default=2026)
    k.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args()
    {"sample": sample, "score": score, "carry": carry}[args.command](args)


if __name__ == "__main__":
    main()
