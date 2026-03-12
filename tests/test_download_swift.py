# -*- coding: utf-8 -*-
"""Unit tests for download_swift.py helpers (is_number, parse_coord)."""

import importlib.util
from pathlib import Path

import pytest

astroquery = pytest.importorskip("astroquery", reason="astroquery not installed")


def _load_download_swift():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "bin" / "download_swift.py"
    spec = importlib.util.spec_from_file_location("download_swift", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def dl_module():
    return _load_download_swift()


class TestIsNumber:
    def test_int(self, dl_module):
        assert dl_module.is_number(42) is True
        assert dl_module.is_number("42") is True

    def test_float(self, dl_module):
        assert dl_module.is_number(3.14) is True
        assert dl_module.is_number("3.14") is True

    def test_non_number(self, dl_module):
        assert dl_module.is_number("12:30:00") is False
        assert dl_module.is_number("nope") is False


class TestParseCoord:
    def test_degrees(self, dl_module):
        coord = dl_module.parse_coord(229.5927, 21.9832)
        assert coord is not None
        assert abs(coord.ra.deg - 229.5927) < 0.01
        assert abs(coord.dec.deg - 21.9832) < 0.01

    def test_sexagesimal(self, dl_module):
        coord = dl_module.parse_coord("15:03:49.97", "+42:06:50.52")
        assert coord is not None
        assert abs(coord.ra.deg - 225.96) < 0.5

    def test_invalid_returns_none(self, dl_module):
        assert dl_module.parse_coord("not", "valid") is None
