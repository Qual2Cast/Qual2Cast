"""site/facts/common.py: pinned files, hashes and named facts. Uses temporary folders, never the real pins.

    uv run pytest site/tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))

from facts import common  # noqa: E402


@pytest.fixture
def fake_pins(tmp_path, monkeypatch):
    """A repo root in tmp_path with one pinned file, data.csv, pinned as "data" at its current hash."""
    (tmp_path / "data.csv").write_bytes(b"a,b\n1,2\n")
    pins = {
        "data": {
            "path": "data.csv",
            "sha256": common.sha256(tmp_path / "data.csv"),
            "pinned": "2026-11-24",
            "file": "test.toml",
        }
    }
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "PINS", pins)
    monkeypatch.setattr(common, "REGISTRY", {})
    return tmp_path


def test_pinned_returns_the_file_while_it_matches(fake_pins):
    assert common.pinned("data") == fake_pins / "data.csv"


def test_pin_mismatch_raises(fake_pins):
    (fake_pins / "data.csv").write_bytes(b"a,b\n1,3\n")
    with pytest.raises(common.PinError, match="changed since it was pinned"):
        common.pinned("data")


def test_missing_pinned_file_raises(fake_pins):
    (fake_pins / "data.csv").unlink()
    with pytest.raises(common.PinError, match="missing"):
        common.pinned("data")


def test_crlf_and_lf_copies_hash_equal(tmp_path):
    lf, crlf, other = tmp_path / "lf.csv", tmp_path / "crlf.csv", tmp_path / "other.csv"
    lf.write_bytes(b"name,n\nalpha,1\nbeta,2\n")
    crlf.write_bytes(b"name,n\r\nalpha,1\r\nbeta,2\r\n")
    other.write_bytes(b"name,n\nalpha,1\nbeta,3\n")
    assert common.sha256(lf) == common.sha256(crlf)
    assert common.sha256(lf) != common.sha256(other)


def test_duplicate_fact_name_raises(fake_pins):
    common.fact("n_rows", 1, source="data")
    with pytest.raises(ValueError, match="defined twice"):
        common.fact("n_rows", 2, source="data")


def test_fact_citing_unknown_pin_raises(fake_pins):
    with pytest.raises(common.PinError, match="unknown pin 'nope'"):
        common.fact("n_rows", 1, source="data+nope")
    assert "n_rows" not in common.REGISTRY


def test_fact_prints_its_text_and_keeps_its_value(fake_pins):
    f = common.fact("n_rows", 1234, f"{1234:,}", source="data")
    assert f"{f}" == "1,234" and f.value == 1234 and f.source == "data"
