# -*- coding: utf-8 -*-
"""Unit tests for SwiftPhotom.commands (mocked to avoid requiring HEASoft)."""

import SwiftPhotom.commands as sc


class TestRun:
    def test_run_echo_returns_stdout(self):
        out = sc.run("echo hello")
        assert out is not None
        text = out.decode() if isinstance(out, bytes) else out
        assert "hello" in text


class TestUvotimsum:
    def test_uvotimsum_command_default(self):
        import unittest.mock as mock
        with mock.patch.object(sc, 'run') as m:
            sc.uvotimsum('in.fits', 'out.fits')
            m.assert_called_once()
            call = m.call_args[0][0]
            assert 'uvotimsum' in call
            assert 'in.fits' in call and 'out.fits' in call
            assert 'ignoreframetime=no' in call

    def test_uvotimsum_ignoreframetime_yes(self):
        import unittest.mock as mock
        with mock.patch.object(sc, 'run') as m:
            sc.uvotimsum('a.fits', 'b.fits', ignoreframetime=True)
            call = m.call_args[0][0]
            assert 'ignoreframetime=yes' in call


class TestFcopyFappend:
    def test_fcopy_calls_run_with_fcopy(self):
        import unittest.mock as mock
        with mock.patch.object(sc, 'run') as m:
            sc.fcopy('src.fits', 'dest.fits')
            m.assert_called_once()
            assert 'fcopy' in m.call_args[0][0]
            assert 'src.fits' in m.call_args[0][0] and 'dest.fits' in m.call_args[0][0]

    def test_fappend_calls_run_with_fappend(self):
        import unittest.mock as mock
        with mock.patch.object(sc, 'run') as m:
            sc.fappend('extra.fits', 'existing.fits')
            m.assert_called_once()
            assert 'fappend' in m.call_args[0][0]
