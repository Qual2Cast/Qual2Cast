"""round4_sheet.py: the tie-break sample and the profile-pair selection, on small made-up tables."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import round4_sheet as r4  # noqa: E402
import rubric_v3 as r3  # noqa: E402


def _final():
    rows = []
    for i in range(20):
        src_d = "tiebreak:terra" if i < 4 else "agreed"
        src_p = "tiebreak:terra" if 2 <= i < 12 else "agreed"
        rows.append({"target_id": f"T{i % 5}", "comp_id": f"C{i}", "is_anchor": i == 19,
                     "direct_source": src_d, "peer_source": src_p})
    return pd.DataFrame(rows)


def test_tiebreak_sample_stratified_seeded_no_anchors():
    f = _final()
    s = r4.tiebreak_sample(f, n=6, seed=1)
    assert len(s) == 6 and not s.duplicated(["target_id", "comp_id"]).any()
    # strata sizes: both 2 (i=2,3), direct_only 2 (i=0,1), peer_only 8 (i=4..11) -> 6 * (2,2,8)/12 = 1,1,4
    assert s["stratum"].value_counts().to_dict() == {"peer_only": 4, "both": 1, "direct_only": 1}
    assert s.equals(r4.tiebreak_sample(f, n=6, seed=1))
    assert "C19" not in set(s["comp_id"])
    assert set(s["part"]) == {"c_tiebreak_check"}


def test_profile_pairs_only_unlabelled_and_given_targets():
    keeps = pd.DataFrame({"target_id": ["A", "A", "B", "Z"], "comp_id": ["a1", "a2", "b1", "z1"],
                          "keep": [True, False, True, True]})
    picks = pd.DataFrame({"target_id": ["A", "B"], "comp_id": ["a3", "b1"]})
    labelled = {("B", "b1")}
    out = r4.profile_pairs(keeps, picks, labelled, {"A", "B"})
    assert set(zip(out["target_id"], out["comp_id"])) == {("A", "a1"), ("A", "a3")}
    assert dict(zip(out["comp_id"], out["part"])) == {"a1": "a_tier1_unlabelled", "a3": "a_tier2_unlabelled"}


def test_round4_key_uses_1127_wording_and_old_key_unchanged():
    new = {r[0]: r[1] for r in r3.KEY_ROWS_1127}
    old = {r[0]: r[1] for r in r3.KEY_ROWS}
    assert new["same_customers_<you>"].startswith("Do the same buyers, in the same role")
    assert old["same_customers_<you>"].startswith("Would the target's own customers")
    assert "MAIN business" in r3.KEY_ROWS_1127[1][2]
    assert [r[0] for r in r3.KEY_ROWS_1127] == [r[0] for r in r3.KEY_ROWS]
