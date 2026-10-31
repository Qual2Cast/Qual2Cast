"""
Turn the team's hand-labelled facet sheet into the two inputs
verify_with_evidence.py needs, so the verifier is scored on exactly the
values the team labelled.

The sheet (Google Sheet "facet_gold_labels", tab "Labels", downloaded as
CSV) has one row per company and facet:

  ticker, company, facet_id (F1-F12), facet, what_to_check, haiku_value,
  label, evidence_url, note, labeler

The labelled haiku_value comes from an earlier fill run, not the one in
outputs-local/comps/facets (only 41 of 480 values are identical, since Haiku
words its fills differently each run). Judging the current fill against
these labels would score one set of values against another set's labels.
So this script rebuilds a fill table from haiku_value itself:

  <out>/tables/facets.csv            the labelled values, in the fill's layout
  <out>/verification/gold_labels.csv ticker, facet, verdict (+ original label)

Labels map to the verifier's verdicts:

  correct          -> supported
  partly correct   -> partly
  outdated, wrong  -> contradicted   (both count as a problem when scoring)
  can't tell       -> no_evidence    (left out of the score)

  python v0/verification/gold_from_labels.py --labels "facet_gold_labels - Labels.csv"
  python v0/verification/verify_with_evidence.py --facets outputs-local/comps/gold_labels \\
      --tickers <the tickers this script prints> \\
      --gold outputs-local/comps/gold_labels/verification/gold_labels.csv

A rerun moves the previous outputs to <out>/history/<time>/ (nothing is
overwritten).

Nothing here calls an API or the network.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import facets as fc  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402

OUT = OUTPUTS_LOCAL / "comps" / "gold_labels"
PROMPT_VERSION = "gold_labels"

LABEL_TO_VERDICT = {
    "correct": "supported",
    "partly correct": "partly",
    "outdated": "contradicted",
    "wrong": "contradicted",
    "can't tell": "no_evidence",
}
REQUIRED = ["ticker", "facet_id", "haiku_value", "label"]
STATUS_VALUES = {"unknown", "not_applicable"}
ID_TO_NAME = {v: k for k, v in fc.FACET_ID.items()}          # "F8" -> "geography_served"


def read_labels(path: Path) -> pd.DataFrame:
    """The sheet, checked and tidied: one row per ticker and facet."""
    g = pd.read_csv(path, dtype=str).fillna("")
    missing = [c for c in REQUIRED if c not in g.columns]
    if missing:
        raise SystemExit(f"{path}: missing columns {missing}")
    for c in g.columns:
        g[c] = g[c].str.strip()
    g["label"] = g["label"].str.lower().str.replace("’", "'", regex=False)
    bad = sorted(set(g.label) - set(LABEL_TO_VERDICT))
    if bad:
        raise SystemExit(f"{path}: unknown labels {bad}; expected {sorted(LABEL_TO_VERDICT)}")
    bad = sorted(set(g.facet_id) - set(ID_TO_NAME))
    if bad:
        raise SystemExit(f"{path}: unknown facet ids {bad}")
    dup = g[g.duplicated(["ticker", "facet_id"], keep=False)]
    if len(dup):
        raise SystemExit(f"{path}: {len(dup)} duplicate ticker/facet rows, e.g. "
                         f"{dup[['ticker', 'facet_id']].head(3).values.tolist()}")
    g["facet"] = g.facet_id.map(ID_TO_NAME)
    g["verdict"] = g.label.map(LABEL_TO_VERDICT)
    return g


def fill_table(g: pd.DataFrame, companies: pd.DataFrame) -> pd.DataFrame:
    """One fill row per company, in the layout of tables/facets.csv."""
    ids = companies[["IQ_COMPANY_ID", "target_ciq_ticker", "target_company_name"]].astype(str)
    ids = ids.assign(key=ids.target_ciq_ticker.str.upper())
    unknown = sorted(set(g.ticker.str.upper()) - set(ids.key))
    if unknown:
        raise SystemExit(f"tickers not in the universe: {unknown}")
    rows = []
    for ticker, x in g.groupby("ticker", sort=False):
        c = ids[ids.key == ticker.upper()].iloc[0]
        row = {"IQ_COMPANY_ID": c.IQ_COMPANY_ID, "target_company_name": c.target_company_name,
               "business_id": "B1", "business": "", "business_count": "1", "llm_status": "ok",
               "prompt_version": PROMPT_VERSION, "with_pages": ""}
        values = dict(zip(x.facet, x.haiku_value))
        for f in fc.FACETS:
            v = values.get(f.name, "")
            status = v if v in STATUS_VALUES else ("filled" if v else "unknown")
            row[f"{f.name}_status"] = status
            row[f.name] = v if status == "filled" else ""
        rows.append(row)
    return pd.DataFrame(rows)


def keep_history(out: Path) -> None:
    """Move earlier outputs to out/history/<time>/ before writing new ones."""
    old = [out / "tables", out / "verification"]
    if not any(d.exists() for d in old):
        return
    dest = out / "history" / datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    dest.mkdir(parents=True, exist_ok=True)
    for d in old:
        if d.exists():
            shutil.move(str(d), str(dest / d.name))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--labels", required=True, help="the labelled sheet, downloaded as CSV")
    p.add_argument("--out", default=str(OUT))
    args = p.parse_args()

    from universe import build_universe
    companies, _ = build_universe()
    g = read_labels(Path(args.labels))
    out = Path(args.out)
    keep_history(out)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "verification").mkdir(parents=True, exist_ok=True)

    table = fill_table(g, companies)
    table.to_csv(out / "tables" / "facets.csv", index=False)
    keep = ["ticker", "facet", "facet_id", "verdict", "label", "evidence_url", "note", "labeler"]
    g[[c for c in keep if c in g.columns]].to_csv(out / "verification" / "gold_labels.csv", index=False)

    print(f"{len(table)} companies, {len(g)} labelled facets -> {out}")
    print(g.verdict.value_counts().to_string())
    print("tickers:", " ".join(table.merge(companies[["IQ_COMPANY_ID", "target_ciq_ticker"]].astype(str),
                                           on="IQ_COMPANY_ID").target_ciq_ticker))


if __name__ == "__main__":
    main()
