# -*- coding: utf-8 -*-
"""Unit tests for Swift_setup.py (add_sci_tmpl, mk_swift_reduction_files)."""

import importlib.util
from pathlib import Path

import pytest
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy import units as u

astroquery = pytest.importorskip("astroquery", reason="astroquery not installed")


def _load_swift_setup():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "bin" / "Swift_setup.py"
    spec = importlib.util.spec_from_file_location("swift_setup", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def setup_module():
    return _load_swift_setup()


class TestAddSciTmpl:
    def test_adds_tag_column(self, setup_module):
        table = Table({
            "REL_DATE": [0.0, 50.0, 100.0, 250.0],
        })
        out = setup_module.add_sci_tmpl(table, max_date=200.0)
        assert "TAG" in out.columns
        tags = list(out["TAG"])
        assert "science" in tags
        assert "template" in tags
        # REL_DATE in (0, 200) -> science, else template
        assert out[out["REL_DATE"] == 50.0]["TAG"][0] == "science"
        assert out[out["REL_DATE"] == 250.0]["TAG"][0] == "template"

    def test_no_rel_date_returns_unchanged(self, setup_module):
        table = Table({"X": [1, 2]})
        out = setup_module.add_sci_tmpl(table)
        assert out is table
        assert "TAG" not in out.columns


class TestMkSwiftReductionFiles:
    def test_creates_reg_and_dat_files(self, setup_module, tmp_path_cwd):
        coord = SkyCoord(229.5927, 21.9832, unit=u.deg)
        table = Table({
            "TAG": ["science", "template"],
            "FILENAME": ["raw/sw001a_sk.img.gz", "raw/sw002b_sk.img.gz"],
        })
        setup_module.mk_swift_reduction_files(table, coord, radius=5*u.arcsec)
        assert (tmp_path_cwd / "sn.reg").exists()
        assert (tmp_path_cwd / "bkg.reg").exists()
        assert (tmp_path_cwd / "sci.dat").exists()
        assert (tmp_path_cwd / "tmpl.dat").exists()
        assert "circle" in (tmp_path_cwd / "sn.reg").read_text()
        assert "annulus" in (tmp_path_cwd / "bkg.reg").read_text()
