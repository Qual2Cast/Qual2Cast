"""direct_peer_pairs.py counts and labels, and agent_loop's --pairs file."""

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_loop as al  # noqa: E402
import direct_peer_pairs as dp  # noqa: E402


def source() -> pd.DataFrame:
    rows = [("AAA", "A", "1", "X", "X Co", "not in universe", "Yes"),
            ("AAA", "A", "2", "Y", "Y Co", "universe (holdout)", "No"),
            ("BBB", "B", "1", "X", "X Co", "not in universe", "No")]
    df = pd.DataFrame(rows, columns=["target_ticker", "target_name", "peer_no", "peer_ticker", "peer_name",
                                     "where_peer_is", dp.LABEL_COL])
    for col in dp.SOURCE_COLS:
        df[col] = df.get(col, "")
    return df


def test_counts():
    c = dp.counts(source())
    assert c == {"pairs": 3, "targets": 2, "comps": 2, "yes": 1, "no": 2, "external_pairs": 2,
                 "external_comps": 1, "holdout_pairs": 1, "external_yes": 1, "holdout_yes": 0}


def test_load_pairs_file(tmp_path):
    f = tmp_path / "pairs.csv"
    pd.DataFrame({"target": ["IQ1", "IQ1"], "comp": ["EXT_X", "IQ2"]}).to_csv(f, index=False)
    pairs = al.load_pairs("file", pair_file=f)
    assert len(pairs) == 2 and set(pairs.columns) == {"target", "comp", "similarity", "rank"}
    assert pairs["similarity"].isna().all()
