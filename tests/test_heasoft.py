# -*- coding: utf-8 -*-
"""
Unit tests for HEASoft environment and command availability.

These tests verify that HEASoft is properly installed and configured.
Tests are skipped if HEASoft is not available, allowing the rest of
the test suite to run in environments without HEASoft.
"""

import os
import shutil
import subprocess

import pytest


def heasoft_available():
    """Check if HEASoft commands are available."""
    return shutil.which('uvotmaghist') is not None


def caldb_configured():
    """Check if CALDB environment is configured."""
    return (
        os.environ.get('CALDB') is not None and
        os.environ.get('CALDBCONFIG') is not None
    )


# Skip all tests in this module if HEASoft is not installed
pytestmark = pytest.mark.skipif(
    not heasoft_available(),
    reason="HEASoft not installed or not in PATH"
)


class TestHEASoftEnvironment:
    """Tests for HEASoft environment variables."""

    def test_headas_set(self):
        """HEADAS environment variable should be set."""
        headas = os.environ.get('HEADAS')
        assert headas is not None, (
            "HEADAS not set. Source headas-init.sh before running tests."
        )

    def test_headas_directory_exists(self):
        """HEADAS should point to an existing directory."""
        headas = os.environ.get('HEADAS')
        if headas:
            assert os.path.isdir(headas), f"HEADAS directory not found: {headas}"

    def test_caldb_set(self):
        """CALDB environment variable should be set."""
        caldb = os.environ.get('CALDB')
        assert caldb is not None, (
            "CALDB not set. Set CALDB=/path/to/caldb or source caldbinit.sh"
        )

    def test_caldb_directory_exists(self):
        """CALDB should point to an existing directory."""
        caldb = os.environ.get('CALDB')
        if caldb:
            assert os.path.isdir(caldb), f"CALDB directory not found: {caldb}"

    @pytest.mark.skipif(not caldb_configured(), reason="CALDB not fully configured")
    def test_caldbconfig_set(self):
        """CALDBCONFIG environment variable should be set for photometry."""
        caldbconfig = os.environ.get('CALDBCONFIG')
        assert caldbconfig is not None, (
            "CALDBCONFIG not set. Export CALDBCONFIG=$CALDB/software/tools/caldb.config"
        )

    @pytest.mark.skipif(not caldb_configured(), reason="CALDB not fully configured")
    def test_caldbconfig_file_exists(self):
        """CALDBCONFIG should point to an existing file."""
        caldbconfig = os.environ.get('CALDBCONFIG')
        if caldbconfig:
            assert os.path.isfile(caldbconfig), (
                f"CALDBCONFIG file not found: {caldbconfig}"
            )

    @pytest.mark.skipif(not caldb_configured(), reason="CALDB not fully configured")
    def test_caldbalias_set(self):
        """CALDBALIAS environment variable should be set."""
        caldbalias = os.environ.get('CALDBALIAS')
        assert caldbalias is not None, (
            "CALDBALIAS not set. Export CALDBALIAS=$CALDB/software/tools/alias_config.fits"
        )

    @pytest.mark.skipif(not caldb_configured(), reason="CALDB not fully configured")
    def test_caldbalias_file_exists(self):
        """CALDBALIAS should point to an existing file."""
        caldbalias = os.environ.get('CALDBALIAS')
        if caldbalias:
            assert os.path.isfile(caldbalias), (
                f"CALDBALIAS file not found: {caldbalias}"
            )


class TestHEASoftCommands:
    """Tests for HEASoft command availability and basic functionality."""

    @pytest.mark.parametrize("command", [
        "uvotmaghist",
        "uvotsource",
        "uvotimsum",
        "uvotdetect",
        "uvot2pha",
    ])
    def test_uvot_commands_in_path(self, command):
        """Key UVOT commands should be available in PATH."""
        path = shutil.which(command)
        assert path is not None, f"{command} not found in PATH"

    @pytest.mark.parametrize("command", [
        "fhelp",
        "fstruct",
        "ftlist",
    ])
    def test_ftools_commands_in_path(self, command):
        """Basic FTOOLS commands should be available in PATH."""
        path = shutil.which(command)
        assert path is not None, f"{command} not found in PATH"

    def test_uvotmaghist_runs(self):
        """uvotmaghist should run and show help without error."""
        result = subprocess.run(
            ["uvotmaghist", "help=yes"],
            capture_output=True,
            timeout=30
        )
        # uvotmaghist with help=yes exits 0 and prints usage
        output = result.stdout.decode() + result.stderr.decode()
        assert "uvotmaghist" in output.lower() or result.returncode == 0

    def test_uvotsource_runs(self):
        """uvotsource should run and show help without error."""
        result = subprocess.run(
            ["uvotsource", "help=yes"],
            capture_output=True,
            timeout=30
        )
        output = result.stdout.decode() + result.stderr.decode()
        assert "uvotsource" in output.lower() or result.returncode == 0

    def test_ftlist_runs(self):
        """ftlist should be runnable (just verify command exists and starts)."""
        # ftlist doesn't handle -h well in non-TTY, so just check it exists
        # The command is already tested via test_ftools_commands_in_path
        assert shutil.which("ftlist") is not None


class TestCaldbInfo:
    """Tests for CALDB functionality using caldbinfo."""

    @pytest.mark.skipif(not caldb_configured(), reason="CALDB not fully configured")
    def test_caldbinfo_command_exists(self):
        """caldbinfo command should be available."""
        assert shutil.which('caldbinfo') is not None, "caldbinfo not in PATH"

    @pytest.mark.skipif(not caldb_configured(), reason="CALDB not fully configured")
    def test_caldbinfo_swift_uvota(self):
        """CALDB should have Swift UVOTA calibration data."""
        result = subprocess.run(
            ["caldbinfo", "INST", "SWIFT", "UVOTA"],
            capture_output=True,
            timeout=30
        )
        output = result.stdout.decode() + result.stderr.decode()
        # Should either succeed or at least recognize the instrument
        # A properly configured CALDB will show calibration file info
        assert result.returncode == 0 or "UVOTA" in output.upper(), (
            f"CALDB query for Swift UVOTA failed: {output}"
        )


class TestCheckHeasoftEnvironmentFunction:
    """Tests for the check_heasoft_environment function from batch script."""

    def test_check_function_importable(self):
        """The check function should be importable from the batch script."""
        import importlib.util
        import sys

        script_path = os.path.join(
            os.path.dirname(__file__), "..", "bin", "Swift_batch_photom.py"
        )
        script_path = os.path.abspath(script_path)

        if not os.path.exists(script_path):
            pytest.skip("Swift_batch_photom.py not found")

        spec = importlib.util.spec_from_file_location("batch_photom", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["batch_photom"] = module
        spec.loader.exec_module(module)

        assert hasattr(module, 'check_heasoft_environment')

    def test_check_function_returns_tuple(self):
        """check_heasoft_environment should return (bool, list) tuple."""
        import importlib.util
        import sys

        script_path = os.path.join(
            os.path.dirname(__file__), "..", "bin", "Swift_batch_photom.py"
        )
        script_path = os.path.abspath(script_path)

        if not os.path.exists(script_path):
            pytest.skip("Swift_batch_photom.py not found")

        spec = importlib.util.spec_from_file_location("batch_photom_test", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["batch_photom_test"] = module
        spec.loader.exec_module(module)

        result = module.check_heasoft_environment()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

    def test_check_function_detects_heasoft(self):
        """If HEASoft is available, check should return True with no issues."""
        import importlib.util
        import sys

        script_path = os.path.join(
            os.path.dirname(__file__), "..", "bin", "Swift_batch_photom.py"
        )
        script_path = os.path.abspath(script_path)

        if not os.path.exists(script_path):
            pytest.skip("Swift_batch_photom.py not found")

        spec = importlib.util.spec_from_file_location("batch_photom_detect", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["batch_photom_detect"] = module
        spec.loader.exec_module(module)

        ok, issues = module.check_heasoft_environment()

        # If all env vars are set properly, should return True
        headas = os.environ.get('HEADAS')
        caldb = os.environ.get('CALDB')
        caldbconfig = os.environ.get('CALDBCONFIG')

        if headas and caldb and caldbconfig:
            assert ok is True, f"Expected True but got issues: {issues}"
        else:
            # If not fully configured, should return False with issues
            assert ok is False
            assert len(issues) > 0


class TestHEASoftIntegration:
    """Integration tests that require full HEASoft + CALDB setup."""

    @pytest.mark.skipif(not caldb_configured(), reason="CALDB not fully configured")
    def test_uvotmaghist_caldb_access(self, tmp_path):
        """uvotmaghist should be able to access CALDB (basic sanity check)."""
        # Create a minimal test - just verify CALDB access doesn't fail
        # We can't run full photometry without real data, but we can check
        # that the command starts and recognizes CALDB
        result = subprocess.run(
            ["uvotmaghist", "infile=none", "help=no"],
            capture_output=True,
            timeout=10,
            cwd=str(tmp_path)
        )
        output = result.stderr.decode()
        # Should NOT see "CALDBCONFIG environment variable not set"
        assert "CALDBCONFIG environment variable not set" not in output, (
            "CALDB not properly configured - CALDBCONFIG not set"
        )
