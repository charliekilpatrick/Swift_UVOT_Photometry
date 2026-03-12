# -*- coding: utf-8 -*-
"""Unit tests for Swift_batch_photom.py FOV checking and helpers."""

import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.io import fits
import astropy.units as u

astroquery = pytest.importorskip("astroquery", reason="astroquery not installed")


def _load_batch_photom():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "bin" / "Swift_batch_photom.py"
    spec = importlib.util.spec_from_file_location("batch_photom", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def batch_module():
    return _load_batch_photom()


class TestCheckFov:
    """Tests for the check_fov function (pointing-based pre-filter)."""

    def test_source_at_pointing_center(self, batch_module):
        """Source at pointing center should be in FOV."""
        coord = SkyCoord(ra=180.0, dec=45.0, unit=u.deg)
        in_fov, sep = batch_module.check_fov(coord, 180.0, 45.0)
        assert in_fov is True
        assert sep < 0.1  # Should be essentially zero

    def test_source_near_pointing(self, batch_module):
        """Source within 8.5 arcmin should be in FOV."""
        coord = SkyCoord(ra=180.0, dec=45.0, unit=u.deg)
        # 5 arcmin offset in Dec
        in_fov, sep = batch_module.check_fov(coord, 180.0, 45.0 + 5.0/60.0)
        assert in_fov is True
        assert 4.9 < sep < 5.1

    def test_source_far_from_pointing(self, batch_module):
        """Source > 8.5 arcmin from pointing should be out of FOV."""
        coord = SkyCoord(ra=180.0, dec=45.0, unit=u.deg)
        # 15 arcmin offset in Dec (well outside FOV)
        in_fov, sep = batch_module.check_fov(coord, 180.0, 45.0 + 15.0/60.0)
        assert in_fov is False
        assert 14.9 < sep < 15.1

    def test_sn2018bff_example(self, batch_module):
        """Real example: SN2018bff vs observation 00034405013."""
        coord = batch_module.parse_coord('13:45:25.21', '+26:25:27.2')
        # Pointing from observation
        pointing_ra = 206.474416983874
        pointing_dec = 26.8258244139923
        in_fov, sep = batch_module.check_fov(coord, pointing_ra, pointing_dec)
        assert in_fov is False
        assert 24.0 < sep < 26.0  # ~24.9 arcmin


class TestCheckCoordInImage:
    """Tests for WCS-based FOV checking."""

    @pytest.fixture
    def uvot_fits_with_wcs(self, tmp_path):
        """Create a minimal FITS file with valid WCS."""
        path = tmp_path / "test_uvot_sk.img.gz"
        
        # Create primary HDU
        primary = fits.PrimaryHDU()
        primary.header['FILTER'] = 'UVW2'
        primary.header['OBS_ID'] = '00012345'
        
        # Create image extension with WCS
        data = np.zeros((1000, 1000), dtype=np.float32)
        img = fits.ImageHDU(data=data)
        
        # Set up WCS for image centered at RA=180, Dec=45
        img.header['CTYPE1'] = 'RA---TAN'
        img.header['CTYPE2'] = 'DEC--TAN'
        img.header['CRPIX1'] = 500.0
        img.header['CRPIX2'] = 500.0
        img.header['CRVAL1'] = 180.0
        img.header['CRVAL2'] = 45.0
        img.header['CDELT1'] = -0.0001389  # ~0.5 arcsec/pixel
        img.header['CDELT2'] = 0.0001389
        img.header['NAXIS1'] = 1000
        img.header['NAXIS2'] = 1000
        
        hdul = fits.HDUList([primary, img])
        hdul.writeto(path, overwrite=True)
        return str(path)

    def test_source_in_image(self, batch_module, uvot_fits_with_wcs):
        """Source near image center should be in FOV."""
        coord = SkyCoord(ra=180.0, dec=45.0, unit=u.deg)
        in_fov, details = batch_module.check_coord_in_image(coord, uvot_fits_with_wcs)
        assert in_fov is True
        assert details['in_fov'] is True
        assert details['filter'] == 'UVW2'

    def test_source_outside_image(self, batch_module, uvot_fits_with_wcs):
        """Source far from image center should be out of FOV."""
        # 1 degree away - well outside
        coord = SkyCoord(ra=181.0, dec=45.0, unit=u.deg)
        in_fov, details = batch_module.check_coord_in_image(coord, uvot_fits_with_wcs)
        assert in_fov is False
        assert 'outside bounds' in details.get('reason', '')

    def test_unsupported_filter(self, batch_module, tmp_path):
        """Images with unsupported filters should be excluded."""
        path = tmp_path / "test_white_sk.img.gz"
        primary = fits.PrimaryHDU()
        primary.header['FILTER'] = 'BLOCKED'
        hdul = fits.HDUList([primary])
        hdul.writeto(path, overwrite=True)
        
        coord = SkyCoord(ra=180.0, dec=45.0, unit=u.deg)
        in_fov, details = batch_module.check_coord_in_image(coord, str(path))
        assert in_fov is False
        assert 'unsupported filter' in details.get('reason', '')


class TestParseCoord:
    """Tests for coordinate parsing."""

    def test_decimal_degrees(self, batch_module):
        coord = batch_module.parse_coord(180.0, 45.0)
        assert coord is not None
        assert abs(coord.ra.deg - 180.0) < 0.001
        assert abs(coord.dec.deg - 45.0) < 0.001

    def test_sexagesimal(self, batch_module):
        coord = batch_module.parse_coord('13:45:25.21', '+26:25:27.2')
        assert coord is not None
        assert abs(coord.ra.deg - 206.355) < 0.01
        assert abs(coord.dec.deg - 26.424) < 0.01

    def test_invalid_returns_none(self, batch_module):
        coord = batch_module.parse_coord('invalid', 'coords')
        assert coord is None


class TestDownloadArchive:
    """Tests for archive directory and symlink functionality."""

    def test_download_returns_stats_dict(self, batch_module):
        """download_swift_data should return a stats dictionary."""
        from astropy.table import Table, Column
        
        # Create empty table with required columns
        table = Table()
        table['OBSID'] = Column(['00012345'])
        table['OBS_TYPE'] = Column(['excluded'])  # Will be skipped
        table['START_TIME'] = Column([58000.0])
        table['SEP_ARCMIN'] = Column([5.0])
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = batch_module.download_swift_data(table, tmpdir, archive_dir=None)
            assert isinstance(stats, dict)
            assert 'n_downloaded' in stats
            assert 'n_linked' in stats
            assert 'n_skipped_fov' in stats
            assert 'n_skipped_time' in stats
            # With obs_type='excluded', should be skipped
            assert stats['n_skipped_time'] == 1
            assert stats['n_downloaded'] == 0

    def test_archive_creates_symlinks(self, batch_module, tmp_path):
        """When archive exists, should create symlinks instead of downloading."""
        from astropy.table import Table, Column
        
        # Create archive with fake obsid directory
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        obsid_dir = archive_dir / "00012345"
        obsid_dir.mkdir()
        (obsid_dir / "uvot").mkdir()
        (obsid_dir / "uvot" / "test.txt").write_text("test data")
        
        # Create output directory
        outdir = tmp_path / "object1"
        outdir.mkdir()
        
        # Create table with science observation
        table = Table()
        table['OBSID'] = Column(['00012345'])
        table['OBS_TYPE'] = Column(['science'])
        table['START_TIME'] = Column([58000.0])
        table['SEP_ARCMIN'] = Column([5.0])
        table['IN_FOV'] = Column([True])
        
        stats = batch_module.download_swift_data(
            table, str(outdir), 
            archive_dir=str(archive_dir)
        )
        
        # Should have linked, not downloaded
        assert stats['n_linked'] == 1
        assert stats['n_downloaded'] == 0
        
        # Check symlink exists
        link_path = outdir / "00012345"
        assert link_path.is_symlink()
        assert link_path.resolve() == obsid_dir
        
        # Check we can access data through symlink
        assert (link_path / "uvot" / "test.txt").read_text() == "test data"

    def test_no_archive_downloads_directly(self, batch_module):
        """With archive_dir=None, should return stats without linking."""
        from astropy.table import Table, Column
        
        # Create table with out_of_fov observation (will be skipped, avoiding actual download)
        table = Table()
        table['OBSID'] = Column(['00012345'])
        table['OBS_TYPE'] = Column(['out_of_fov'])
        table['START_TIME'] = Column([58000.0])
        table['SEP_ARCMIN'] = Column([25.0])
        table['IN_FOV'] = Column([False])
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = batch_module.download_swift_data(table, tmpdir, archive_dir=None)
            assert stats['n_linked'] == 0  # No archive = no linking
            assert stats['n_skipped_fov'] == 1
