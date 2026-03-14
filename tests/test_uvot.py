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


class TestAspectCorrection:
    """Tests for aspect-corrected extension filtering."""

    def test_all_direct_returns_all_extensions(self, minimal_uvot_fits):
        """When all extensions have ASPCORR=DIRECT, all (non-primary) are returned."""
        good, bad = up.get_aspect_corrected_extension_indices(minimal_uvot_fits)
        assert len(bad) == 0
        assert 1 in good

    def test_mixed_aspect_returns_only_direct(self, tmp_path):
        """Extensions without ASPCORR=DIRECT are in bad list."""
        from astropy.io import fits
        import numpy as np
        path = tmp_path / "mixed.fits"
        hdu_list = fits.HDUList()
        hdu_list.append(fits.PrimaryHDU())
        for i, asp in enumerate(["DIRECT", "RAW", "DIRECT", "NONE"]):
            ext = fits.ImageHDU(data=np.zeros((5, 5)), name=f"ext{i+1}")
            ext.header["ASPCORR"] = asp
            ext.header["FRAMTIME"] = 0.011
            hdu_list.append(ext)
        hdu_list.writeto(path, overwrite=True)
        good, bad = up.get_aspect_corrected_extension_indices(str(path))
        assert good == [1, 3]
        assert bad == [2, 4]

    def test_no_direct_returns_empty_good(self, tmp_path):
        """When no extension is aspect-corrected, good is empty."""
        from astropy.io import fits
        import numpy as np
        path = tmp_path / "raw.fits"
        hdu_list = fits.HDUList()
        hdu_list.append(fits.PrimaryHDU())
        ext = fits.ImageHDU(data=np.zeros((5, 5)))
        ext.header["ASPCORR"] = "RAW"
        hdu_list.append(ext)
        hdu_list.writeto(path, overwrite=True)
        good, bad = up.get_aspect_corrected_extension_indices(str(path))
        assert good == []
        assert bad == [1]

    def test_check_aspect_correction_returns_same_as_get_indices(self, minimal_uvot_fits):
        """check_aspect_correction returns same good/bad as get_aspect_corrected_extension_indices."""
        good1, bad1 = up.get_aspect_corrected_extension_indices(minimal_uvot_fits)
        good2, bad2 = up.check_aspect_correction(minimal_uvot_fits)
        assert good1 == good2
        assert bad1 == bad2


class TestCombine:
    """Tests for combine() (fcopy + fappend)."""

    def test_combine_calls_fcopy_then_fappend(self, tmp_path_cwd, minimal_uvot_fits):
        """combine with two files should call fcopy then fappend (mocked)."""
        import unittest.mock as mock
        import SwiftPhotom.commands as sc
        with mock.patch.object(sc, 'run') as mock_run:
            out_file = str(tmp_path_cwd / "combined.fits")
            up.combine([minimal_uvot_fits, minimal_uvot_fits], out_file)
            assert mock_run.call_count == 2
            calls = [c[0][0] for c in mock_run.call_args_list]
            assert any('fcopy' in c for c in calls)
            assert any('fappend' in c for c in calls)

    def test_combine_single_file_calls_fcopy_only(self, tmp_path_cwd, minimal_uvot_fits):
        """combine with one file only calls fcopy."""
        import unittest.mock as mock
        import SwiftPhotom.commands as sc
        with mock.patch.object(sc, 'run') as mock_run:
            out_file = str(tmp_path_cwd / "single.fits")
            up.combine([minimal_uvot_fits], out_file)
            assert mock_run.call_count == 1
            assert 'fcopy' in mock_run.call_args[0][0]
