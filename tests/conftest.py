# -*- coding: utf-8 -*-
"""Pytest fixtures for Swift UVOT Photometry tests."""

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits


@pytest.fixture
def tmp_path_cwd(tmp_path, monkeypatch):
    """Change cwd to a temporary directory for the test."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def reg_file_3arcsec(tmp_path):
    """A DS9 region file with 3\" circle (matches get_aperture_size parsing)."""
    p = tmp_path / "sn.reg"
    p.write_text('fk5;circle(15:03:49.97,+42:06:50.52,3")')
    return str(p)


@pytest.fixture
def reg_file_5arcsec(tmp_path):
    """A DS9 region file with 5\" circle."""
    p = tmp_path / "sn5.reg"
    p.write_text('fk5;circle(15:03:49.97,+42:06:50.52,5")')
    return str(p)


@pytest.fixture
def minimal_uvot_fits(tmp_path):
    """Minimal FITS file with FILTER in primary (for sort_file_list / load_obsid)."""
    path = tmp_path / "sw00010001uuu_sk.img"
    hdu_list = fits.HDUList()
    primary = fits.PrimaryHDU()
    primary.header["OBS_ID"] = "00010001"
    primary.header["FILTER"] = "U"
    hdu_list.append(primary)
    # Extension with FILTER (minimal image)
    data = np.zeros((10, 10), dtype=np.float32)
    ext = fits.ImageHDU(data=data)
    ext.header["FILTER"] = "U"
    ext.header["ASPCORR"] = "DIRECT"
    ext.header["FRAMTIME"] = 0.011
    hdu_list.append(ext)
    hdu_list.writeto(path, overwrite=True)
    return str(path)


@pytest.fixture
def list_file_with_path(tmp_path, minimal_uvot_fits):
    """A list file pointing to the minimal FITS (same path)."""
    list_path = tmp_path / "obj.lst"
    list_path.write_text(minimal_uvot_fits + "\n")
    return str(list_path)
