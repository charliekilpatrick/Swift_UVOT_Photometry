# -*- coding: utf-8 -*-
"""Unit tests for Swift_photom_csv helpers (parse_coord, write_regions)."""

import importlib.util
from pathlib import Path

import pytest

# Load bin script as module to test its functions
def _load_photom_csv():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "bin" / "Swift_photom_csv.py"
    spec = importlib.util.spec_from_file_location("swift_photom_csv", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def csv_module():
    return _load_photom_csv()


class TestParseCoord:
    def test_degrees(self, csv_module):
        coord = csv_module.parse_coord(229.5927, 21.9832)
        assert abs(coord.ra.deg - 229.5927) < 0.01
        assert abs(coord.dec.deg - 21.9832) < 0.01

    def test_sexagesimal(self, csv_module):
        coord = csv_module.parse_coord("15:03:49.97", "+42:06:50.52")
        assert abs(coord.ra.deg - 225.9582) < 0.1
        assert abs(coord.dec.deg - 42.114) < 0.1

    def test_string_degrees(self, csv_module):
        coord = csv_module.parse_coord("0", "0")
        assert coord.ra.deg == 0
        assert coord.dec.deg == 0


class TestWriteRegions:
    def test_writes_sn_and_bg(self, csv_module, tmp_path):
        coord = csv_module.parse_coord(229.5927, 21.9832)
        sn = tmp_path / "sn.reg"
        bg = tmp_path / "bg.reg"
        csv_module.write_regions(coord, str(sn), str(bg), ap_arcsec=3, bkg_inner=100, bkg_outer=200)
        assert sn.read_text().startswith("fk5;circle(")
        assert "3\"" in sn.read_text()
        assert bg.read_text().startswith("fk5;annulus(")
        assert "100\"" in bg.read_text() and "200\"" in bg.read_text()
