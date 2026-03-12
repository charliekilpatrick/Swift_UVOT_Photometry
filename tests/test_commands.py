# -*- coding: utf-8 -*-
"""Unit tests for SwiftPhotom.commands (mocked to avoid requiring HEASoft)."""

import SwiftPhotom.commands as sc


class TestRun:
    def test_run_echo_returns_stdout(self):
        out = sc.run("echo hello")
        assert out is not None
        text = out.decode() if isinstance(out, bytes) else out
        assert "hello" in text
