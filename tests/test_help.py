# -*- coding: utf-8 -*-
"""Unit tests for SwiftPhotom.help (CLI help strings)."""

import pytest

import SwiftPhotom.help as SH


class TestHelpModule:
    """Help module exposes expected attributes for argparse."""

    def test_description_exists(self):
        assert hasattr(SH, 'description')
        assert 'Swift' in SH.description or 'photometry' in SH.description.lower()

    def test_infile_help_exists(self):
        assert hasattr(SH, 'infile_help')
        assert len(SH.infile_help) > 0

    def test_sn_reg_exists(self):
        assert hasattr(SH, 'sn_reg')
        assert 'region' in SH.sn_reg.lower() or 'circle' in SH.sn_reg.lower()

    def test_bg_reg_exists(self):
        assert hasattr(SH, 'bg_reg')
        assert 'background' in SH.bg_reg.lower() or 'region' in SH.bg_reg.lower()

    def test_det_limit_exists(self):
        assert hasattr(SH, 'det_limit')
        assert 'detection' in SH.det_limit.lower() or 'signal' in SH.det_limit.lower()

    def test_ab_mag_exists(self):
        assert hasattr(SH, 'ab_mag')
        assert 'AB' in SH.ab_mag or 'Vega' in SH.ab_mag

    def test_filter_help_exists(self):
        assert hasattr(SH, 'filter')
        assert 'filter' in SH.filter.lower() or 'V' in SH.filter or 'ALL' in SH.filter

    def test_no_combine_exists(self):
        assert hasattr(SH, 'no_combine')
        assert 'combine' in SH.no_combine.lower() or 'extension' in SH.no_combine.lower()

    def test_obj_exists(self):
        assert hasattr(SH, 'obj')
        assert 'object' in SH.obj.lower() or 'name' in SH.obj.lower()
