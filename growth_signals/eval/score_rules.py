"""Score the rule extractor against a hand-labeled evaluation set.

python eval/score_rules.py                       # all sets in eval/2026-10-19
python eval/score_rules.py --set holdout_c       # one set

Labels (labels_<set>.json) were written by reading each article BEFORE
running the extractor. Scores count (article, event type) pairs. A pair listed
as "borderline" is neither rewarded nor penalized. Pages not listed under
"truth" have no true event.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from extract_events import extract_record  # noqa: E402

DEFAULT_DIR = HERE / "2026-10-19"
SETS = ["pilot", "holdout_a", "holdout_b", "holdout_c"]


def score_set(labels: dict, records_dir: Path) -> dict:
    """Return truth, predictions, borderline pairs and per-type counts for one set."""
    truth, border, predicted = set(), set(), {}
    for company_id, label in labels.items():
        if company_id.startswith("_"):
            continue
        record = json.loads((records_dir / f"{company_id}.json").read_text(encoding="utf-8"))
        page_of = {page["source_url"]: page["page_id"] for page in record["pages"]}
        truth |= {(company_id, page, kind) for page, kinds in label["truth"].items()
                  for kind in kinds}
        border |= {(company_id, page, kind) for page, kind in label.get("borderline", [])}
        events, _ = extract_record(record)
        for event in events:
            predicted[(company_id, page_of[event.source_url], event.event_type)] = event
    scored = set(predicted) - border
    rows = {}
    for kind in sorted({k[2] for k in truth | scored}) + ["ALL"]:
        p = {k for k in scored if kind in ("ALL", k[2])}
        t = {k for k in truth if kind in ("ALL", k[2])}
        rows[kind] = {"predicted": len(p), "true": len(t), "correct": len(p & t)}
    return {"truth": truth, "predicted": predicted, "scored": scored, "rows": rows}


def _pct(a: int, b: int) -> str:
    return f"{a / b:.0%}" if b else "-"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--set", choices=SETS, action="append")
    parser.add_argument("--errors", action="store_true", help="list false positives/negatives")
    args = parser.parse_args()
    for name in args.set or SETS:
        labels = json.loads((args.dir / f"labels_{name}.json").read_text(encoding="utf-8"))
        result = score_set(labels, args.dir / "records" / name)
        print(f"\n{name}")
        print(f"{'type':18}{'pred':>6}{'correct':>9}{'true':>6}{'precision':>11}{'recall':>8}")
        for kind, r in result["rows"].items():
            print(f"{kind:18}{r['predicted']:>6}{r['correct']:>9}{r['true']:>6}"
                  f"{_pct(r['correct'], r['predicted']):>11}{_pct(r['correct'], r['true']):>8}")
        if args.errors:
            for key in sorted(result["scored"] - result["truth"]):
                print("  FP", key, "|", result["predicted"][key].source_text[:120])
            for key in sorted(result["truth"] - set(result["predicted"])):
                print("  FN", key)


if __name__ == "__main__":
    main()
