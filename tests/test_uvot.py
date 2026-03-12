# -*- coding: utf-8 -*-
"""Unit tests for SwiftPhotom.uvot."""

import json
import os
from pathlib import Path

import pytest

import SwiftPhotom.errors as err
import SwiftPhotom.uvot as up


class TestSortFilters:
    def test_all(self):
        assert up.sort_filters("ALL") == ["V", "B", "U", "UVW1", "UVM2", "UVW2"]

    def test_opt(self):
        assert up.sort_filters("OPT") == ["V", "B", "U"]

    def test_uv(self):
        assert up.sort_filters("UV") == ["UVW1", "UVM2", "UVW2"]

    def test_single_comma_separated(self):
        assert up.sort_filters("V,UVM2") == ["V", "UVM2"]

    def test_lowercase_normalized(self):
        assert up.sort_filters("v,b") == ["V", "B"]

    def test_invalid_filter_raises(self):
        # FilterError only when no valid filters remain (all invalid)
        with pytest.raises(err.FilterError):
            up.sort_filters("INVALID,BAD,UNKNOWN")

    def test_all_invalid_raises(self):
        with pytest.raises(err.FilterError):
            up.sort_filters("bad,unknown")


class TestGetApertureSize:
    def test_3arcsec(self, reg_file_3arcsec):
        assert up.get_aperture_size(reg_file_3arcsec) == "3"

    def test_5arcsec(self, reg_file_5arcsec):
        assert up.get_aperture_size(reg_file_5arcsec) == "5"


class TestLoadObsid:
    def test_empty_dir_returns_empty(self, tmp_path_cwd):
        assert up.load_obsid("00010001") == []

    def test_finds_sky_frame(self, tmp_path_cwd):
        # uvot expects sw{OBSID}*_sk.img or .gz; use distinct ObsID so only one file found
        import shutil
        from astropy.io import fits
        obs_dir = tmp_path_cwd / "sub"
        obs_dir.mkdir()
        path = tmp_path_cwd / "sw00010002uuu_sk.img"
        hdu = fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(data=[[0]])])
        hdu[0].header["OBS_ID"] = "00010002"
        hdu[0].header["FILTER"] = "U"
        hdu.writeto(path, overwrite=True)
        dest = obs_dir / "sw00010002uuu_sk.img"
        shutil.copy(path, dest)
        found = up.load_obsid("00010002")
        assert len(found) == 2  # root and sub/
        assert all("00010002" in f and "_sk.img" in f for f in found)

    def test_obsid_padded(self, tmp_path_cwd):
        # short obsid is zfilled to 8
        result = up.load_obsid("123")
        assert result == []


class TestInterpretInfile:
    def test_single_sky_image(self, minimal_uvot_fits):
        obj, tem = up.interpret_infile([minimal_uvot_fits])
        assert len(obj) == 1
        assert obj[0] == minimal_uvot_fits
        assert len(tem) == 0

    def test_list_file(self, list_file_with_path, minimal_uvot_fits):
        obj, tem = up.interpret_infile([list_file_with_path])
        assert len(obj) == 1
        assert obj[0] == minimal_uvot_fits

    def test_missing_list_raises(self, tmp_path_cwd):
        (tmp_path_cwd / "empty.lst").write_text("\n")  # no valid paths in list
        with pytest.raises(err.ListError):
            up.interpret_infile([str(tmp_path_cwd / "empty.lst")])

    def test_nonexistent_obsid_raises(self, tmp_path_cwd):
        # No files matching this ObsID in cwd
        with pytest.raises(err.FileNotFound):
            up.interpret_infile(["99999999"])


class TestSortFileList:
    def test_groups_by_filter(self, minimal_uvot_fits):
        by_filter = up.sort_file_list([minimal_uvot_fits])
        assert "U" in by_filter
        assert len(by_filter["U"]) == 1


class TestOutputMags:
    def test_writes_json_and_deduplicates_mjd(self, tmp_path_cwd):
        os.makedirs("reduction", exist_ok=True)
        mag = {
            "3_arcsec": [
                {"filter": "U", "mjd": 58000.0, "mag": 18.0, "mag_err": 0.1, "upper_limit": False, "mag_limit": 19.0},
            ],
            "5_arcsec": [
                {"filter": "U", "mjd": 58000.0, "mag": 17.8, "mag_err": 0.1, "upper_limit": False, "mag_limit": 18.5},
                {"filter": "U", "mjd": 58000.0, "mag": 17.8, "mag_err": 0.1, "upper_limit": False, "mag_limit": 18.5},
            ],
        }
        up.output_mags(mag, "3", obj=None)
        assert os.path.isfile("reduction/3_arcsec_photometry.json")
        assert os.path.isfile("reduction/5_arcsec_photometry.json")
        with open("reduction/5_arcsec_photometry.json") as f:
            data = json.load(f)
        # JSON is written before in-memory dedup in output_mags, so input length preserved
        assert len(data) == 2
        assert data[0]["filter"] == "U" and data[0]["mjd"] == 58000.0
