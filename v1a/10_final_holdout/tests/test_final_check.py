"""final_check.py: locked by default; B3 pool rank and agent-settings comparison (from direct_peer_pairs tests)."""
import numpy as np
import pytest

import final_check as fc


def test_parts_refuse_without_final_check(tmp_path):
    for part in (fc.direct_peers, fc.holdout):
        with pytest.raises(fc.Locked):
            part(out_root=tmp_path)
    with pytest.raises(SystemExit):
        fc.main(["holdout"])
    assert not any(tmp_path.iterdir())


def test_pool_rank_counts_only_more_similar_pool_comps():
    S = np.array([[1.0, 0.9, 0.5, 0.7],
                  [0.9, 1.0, 0.1, 0.2],
                  [0.5, 0.1, 1.0, 0.3],
                  [0.7, 0.2, 0.3, 1.0]])
    pos = {"T": 0, "A": 1, "B": 2, "H": 3}
    pool = ["T", "A", "B"]                      # H is outside the pool (a holdout comp)
    assert fc.pool_rank(S, pos, pool, "T", "H") == 2   # only A is more similar
    assert fc.pool_rank(S, pos, pool, "T", "A") == 1


def test_agent_settings_compare_facets_by_tail_only():
    ref = {k: "x" for k in fc.AGENT_SETTINGS} | {"facets": "/tmp/a/repo/outputs-local/v1/facets_sonnet/tables/facets.csv"}
    same = ref | {"facets": "C:/elsewhere/outputs-local/v1/facets_sonnet/tables/facets.csv"}
    assert fc.agent_settings_differ(ref, same) == {}
    other = same | {"prompt_version": "y", "facets": "C:/e/outputs-local/v1/facets/tables/facets.csv"}
    assert set(fc.agent_settings_differ(ref, other)) == {"prompt_version", "facets"}
