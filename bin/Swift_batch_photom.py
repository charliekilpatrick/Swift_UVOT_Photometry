#!/usr/bin/env python
"""
Run Swift UVOT photometry for multiple sources from an input file.

Input file format (CSV or whitespace-separated):
    name, ra, dec, tpeak
    
Where tpeak is JD - 2458000 (i.e., days relative to JD 2458000).

Time constraints:
    - Science data: tpeak - 60 days to tpeak + 365 days
    - Template data: before tpeak - 60 days

Output is saved to: <base_dir>/<name>/
"""

import argparse
import csv
import json
import os
import shutil
import sys
import time

from astroquery.heasarc import Heasarc
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.time import Time, TimeDelta
from astropy.table import unique, Column
from astropy.io import fits
from astropy import wcs
import warnings

import SwiftPhotom.uvot as up

warnings.filterwarnings('ignore')

# JD zero point for tpeak conversion
JD_OFFSET = 2458000.0


def is_number(num):
    """Return True if the value can be converted to float.

    Parameters
    ----------
    num : any
        Value to test.

    Returns
    -------
    bool
        True if float(num) succeeds.
    """
    try:
        float(num)
        return True
    except (ValueError, TypeError):
        return False


def parse_coord(ra, dec):
    """Parse RA and Dec (degrees or sexagesimal) to an ICRS SkyCoord.

    Parameters
    ----------
    ra : str or float
        Right ascension.
    dec : str or float
        Declination.

    Returns
    -------
    astropy.coordinates.SkyCoord or None
        Coordinates, or None if parsing fails (error printed).
    """
    ra_str, dec_str = str(ra).strip(), str(dec).strip()
    if ':' in ra_str or ':' in dec_str:
        unit = (u.hourangle, u.deg)
    else:
        unit = (u.deg, u.deg)
    try:
        return SkyCoord(ra_str, dec_str, frame='icrs', unit=unit)
    except Exception as e:
        print(f"ERROR: Cannot parse coordinates: {ra} {dec} ({e})")
        return None


def tpeak_to_time(tpeak):
    """Convert tpeak (JD - 2458000) to an astropy Time object.

    Parameters
    ----------
    tpeak : float
        Days relative to JD 2458000.

    Returns
    -------
    astropy.time.Time
        Time in JD format.
    """
    jd = float(tpeak) + JD_OFFSET
    return Time(jd, format='jd')


def check_fov(coord, pointing_ra, pointing_dec, fov_radius=8.5 * u.arcmin):
    """
    Check if coordinates are likely within UVOT FOV.
    
    UVOT FOV is ~17x17 arcmin. Using fov_radius=8.5 arcmin (half diagonal)
    as a conservative estimate for a circular approximation.
    
    Returns (in_fov, separation_arcmin).
    """
    pointing = SkyCoord(ra=pointing_ra * u.deg, dec=pointing_dec * u.deg)
    sep = coord.separation(pointing)
    in_fov = bool(sep < fov_radius)  # Convert numpy bool to Python bool
    return in_fov, float(sep.arcmin)


def get_swift_data(coord, tpeak_time, pre_days=60.0, post_days=365.0, 
                   radius=30.0 * u.arcmin, fov_filter=True, debug=False):
    """
    Query HEASARC for Swift UVOT observations.
    
    Science: tpeak - pre_days to tpeak + post_days
    Template: before tpeak - pre_days
    
    If fov_filter=True, exclude observations where the source is unlikely
    to be in the UVOT FOV based on pointing direction.
    """
    heasarc = Heasarc()
    mission = 'swiftuvlog'
    radius_val = radius.to(u.arcmin).value

    try:
        table = heasarc.query_region(coord, mission=mission, radius=f'{radius_val} arcmin')
    except Exception as e:
        print(f"  No Swift data found or query failed: {e}")
        return None

    if table is None or len(table) == 0:
        print("  No Swift observations found.")
        return None

    if debug:
        print(f"  DEBUG: Table columns: {table.colnames}")
        print(f"  DEBUG: Table has {len(table)} rows")

    # Find the OBSID column (might have different names)
    obsid_col = None
    for col in ['OBSID', 'OBS_ID', 'obsid', 'obs_id', 'OBSERVATION_ID', 'observation_id']:
        if col in table.colnames:
            obsid_col = col
            break
    
    if obsid_col is None:
        print(f"  Warning: No OBSID column found. Available columns: {table.colnames}")
        return None
    
    # Find the time column
    time_col = None
    for col in ['START_TIME', 'TIME', 'start_time', 'MJD', 'mjd', 'START_MJD']:
        if col in table.colnames:
            time_col = col
            break
    
    if time_col is None:
        print(f"  Warning: No time column found. Available columns: {table.colnames}")
        return None
    
    # Find RA/Dec columns for pointing
    ra_col = None
    dec_col = None
    for col in ['RA', 'ra', 'RA_OBJ', 'ra_obj']:
        if col in table.colnames:
            ra_col = col
            break
    for col in ['DEC', 'dec', 'DEC_OBJ', 'dec_obj']:
        if col in table.colnames:
            dec_col = col
            break

    if debug:
        print(f"  DEBUG: Using OBSID column: {obsid_col}")
        print(f"  DEBUG: Using time column: {time_col}")
        if ra_col and dec_col:
            print(f"  DEBUG: Using pointing columns: {ra_col}, {dec_col}")

    # Normalize column names
    table['OBSID'] = [str(i) for i in table[obsid_col]]
    if time_col != 'START_TIME':
        table['START_TIME'] = table[time_col]
    
    table.sort('START_TIME')
    table = unique(table, keys='OBSID', keep='first')

    # Define time windows
    science_start = tpeak_time - TimeDelta(pre_days * u.day)
    science_end = tpeak_time + TimeDelta(post_days * u.day)

    obs_type = []
    fov_status = []
    separations = []
    
    for row in table:
        t = Time(row['START_TIME'], format='mjd')
        
        # Check FOV if pointing info available
        in_fov = True
        sep_arcmin = 0.0
        if fov_filter and ra_col and dec_col:
            try:
                in_fov, sep_arcmin = check_fov(coord, float(row[ra_col]), float(row[dec_col]))
            except Exception:
                in_fov = True  # Can't check, assume OK
                sep_arcmin = -1.0
        
        fov_status.append(in_fov)
        separations.append(sep_arcmin)
        
        if not in_fov:
            obs_type.append('out_of_fov')
        elif science_start <= t <= science_end:
            obs_type.append('science')
        elif t < science_start:
            obs_type.append('template')
        else:
            obs_type.append('excluded')

    table.add_column(Column(obs_type, name='OBS_TYPE'))
    table.add_column(Column(fov_status, name='IN_FOV'))
    table.add_column(Column(separations, name='SEP_ARCMIN'))
    
    # Report FOV filtering
    n_total = len(table)
    n_in_fov = sum(fov_status)
    n_out_fov = n_total - n_in_fov
    if fov_filter and n_out_fov > 0 and debug:
        print(f"  DEBUG: {n_out_fov}/{n_total} observations excluded (source not in FOV)")
    
    return table


def download_swift_data(obstable, outdir='.', archive_dir=None, sky_only=True, debug=False):
    """
    Download Swift UVOT data for observations in table.
    
    If archive_dir is provided, downloads go to the archive and symbolic links
    are created in outdir. This avoids re-downloading data that's already
    been fetched for another object.
    
    Parameters
    ----------
    obstable : astropy.table.Table
        Table of observations with OBS_TYPE column
    outdir : str
        Output directory for this object (will contain symlinks if archive_dir is set)
    archive_dir : str or None
        Shared archive directory for all downloaded data. If None, downloads
        directly to outdir (original behavior).
    sky_only : bool
        If True (default), only download *_sk.img* files needed for photometry.
        If False, download all UVOT files (exposure maps, raw images, hk, etc.).
    debug : bool
        Print debug information
        
    Returns
    -------
    dict
        Statistics: n_downloaded, n_linked, n_skipped_fov, n_skipped_time
    """
    os.makedirs(outdir, exist_ok=True)
    if archive_dir:
        os.makedirs(archive_dir, exist_ok=True)
    
    obstable.sort('OBSID')
    
    stats = {
        'n_downloaded': 0,
        'n_linked': 0,
        'n_skipped_fov': 0,
        'n_skipped_time': 0
    }

    for row in obstable:
        obs_type = row['OBS_TYPE']
        
        if obs_type == 'excluded':
            stats['n_skipped_time'] += 1
            continue
        
        if obs_type == 'out_of_fov':
            stats['n_skipped_fov'] += 1
            if debug:
                sep = row.get('SEP_ARCMIN', 0)
                print(f"  Skipping {row['OBSID']}: source {sep:.1f}' from pointing (out of FOV)")
            continue

        date = Time(row['START_TIME'], format='mjd')
        month = date.datetime.strftime('%m')
        year = date.datetime.strftime('%Y')
        obsid = row['OBSID']
        sep = row.get('SEP_ARCMIN', 0)

        if archive_dir:
            # Use archive directory with symlinks
            archive_obsid_dir = os.path.join(archive_dir, obsid)
            target_link = os.path.join(outdir, obsid)
            
            # Check if already in archive
            if os.path.isdir(archive_obsid_dir):
                # Already downloaded - just create symlink
                if not os.path.exists(target_link):
                    os.symlink(archive_obsid_dir, target_link)
                    if debug:
                        print(f"  Linked {obsid} (already in archive)")
                    else:
                        print(f"  Linked {obsid} (cached)")
                stats['n_linked'] += 1
            else:
                # Download to archive, then link
                cmd = f'wget -q -nH --no-clobber --no-check-certificate --cut-dirs=5 '
                cmd += f'-c -np -R \'index*\' -erobots=off --retr-symlinks '
                
                if sky_only:
                    # Only download sky images from /uvot/image/ directory
                    # -l 1: only this directory (no recursion into subdirs)
                    # -A: accept only *_sk.img.gz files
                    # This avoids products/, hk/, and other unwanted files
                    cmd += f'-r -l 1 -A \'*_sk.img.gz\' '
                    url = f'https://heasarc.gsfc.nasa.gov/FTP/swift/data/obs/{year}_{month}/{obsid}/uvot/image/'
                else:
                    # Download all UVOT files (recursive)
                    cmd += f'-r -l0 '
                    url = f'https://heasarc.gsfc.nasa.gov/FTP/swift/data/obs/{year}_{month}/{obsid}/uvot/'
                
                cmd += f'-P {archive_dir} {url}'

                if debug and sep > 0:
                    print(f"  Downloading {obsid} ({obs_type}, {sep:.1f}' from target)...")
                else:
                    print(f"  Downloading {obsid}...")
                os.system(cmd)
                
                # Create symlink from object dir to archive
                if os.path.isdir(archive_obsid_dir) and not os.path.exists(target_link):
                    os.symlink(archive_obsid_dir, target_link)
                stats['n_downloaded'] += 1
        else:
            # Original behavior: download directly to outdir
            cmd = f'wget -q -nH --no-clobber --no-check-certificate --cut-dirs=5 '
            cmd += f'-c -np -R \'index*\' -erobots=off --retr-symlinks '
            
            if sky_only:
                # Only download sky images from /uvot/image/ directory
                # -l 1: only this directory (no recursion into subdirs)
                # -A: accept only *_sk.img.gz files
                cmd += f'-r -l 1 -A \'*_sk.img.gz\' '
                url = f'https://heasarc.gsfc.nasa.gov/FTP/swift/data/obs/{year}_{month}/{obsid}/uvot/image/'
            else:
                # Download all UVOT files (recursive)
                cmd += f'-r -l0 '
                url = f'https://heasarc.gsfc.nasa.gov/FTP/swift/data/obs/{year}_{month}/{obsid}/uvot/'
            
            cmd += f'-P {outdir} {url}'

            if debug and sep > 0:
                print(f"  Downloading {obsid} ({obs_type}, {sep:.1f}' from target)...")
            else:
                print(f"  Downloading {obsid}...")
            os.system(cmd)
            stats['n_downloaded'] += 1
    
    # Report summary
    if stats['n_skipped_fov'] > 0:
        print(f"  Skipped {stats['n_skipped_fov']} observations (source not in FOV)")
    if stats['n_linked'] > 0:
        print(f"  Linked {stats['n_linked']} observations from archive (already downloaded)")
    
    return stats


def check_coord_in_image(coord, fits_file, debug=False):
    """Check if coordinates fall within the FOV of a UVOT FITS image using WCS.

    Parameters
    ----------
    coord : astropy.coordinates.SkyCoord
        Source position.
    fits_file : str
        Path to a UVOT sky or product FITS file.
    debug : bool, optional
        If True, add WCS error info to details.

    Returns
    -------
    in_fov : bool
        True if the coordinate is inside a valid image extension.
    details : dict
        Keys: 'file', 'in_fov', 'reason', 'filter', 'obsid'; optionally 'pixel_x', 'pixel_y'.
    """
    details = {'file': fits_file, 'in_fov': False, 'reason': None}
    
    try:
        with fits.open(fits_file) as hdu:
            filt = hdu[0].header.get('FILTER', '').strip().upper()
            details['filter'] = filt
            
            if filt not in ['U', 'B', 'V', 'UVW1', 'UVW2', 'UVM2', 'WHITE']:
                details['reason'] = f'unsupported filter: {filt}'
                return False, details
            
            obsid = hdu[0].header.get('OBS_ID', '')
            details['obsid'] = obsid
            
            # Check each image extension
            for i, h in enumerate(hdu):
                if i == 0:
                    continue
                if h.data is None or len(h.data.shape) != 2:
                    continue
                    
                try:
                    w = wcs.WCS(h.header)
                    if not w.has_celestial:
                        continue
                    
                    naxis1 = h.header.get('NAXIS1', h.data.shape[1])
                    naxis2 = h.header.get('NAXIS2', h.data.shape[0])
                    
                    # Convert world coords to pixel
                    px, py = w.wcs_world2pix(coord.ra.deg, coord.dec.deg, 0)
                    
                    details['pixel_x'] = float(px)
                    details['pixel_y'] = float(py)
                    details['naxis1'] = naxis1
                    details['naxis2'] = naxis2
                    
                    # Check if within bounds (with small margin for edge effects)
                    margin = 5  # pixels
                    if margin <= px <= naxis1 - margin and margin <= py <= naxis2 - margin:
                        details['in_fov'] = True
                        details['reason'] = 'in FOV'
                        return True, details
                    else:
                        details['reason'] = f'outside bounds: px={px:.1f}, py={py:.1f} vs ({naxis1}x{naxis2})'
                        
                except Exception as e:
                    if debug:
                        details['wcs_error'] = str(e)
                    continue
            
            if details['reason'] is None:
                details['reason'] = 'no valid WCS extensions'
                
    except Exception as e:
        details['reason'] = f'error: {e}'
    
    return False, details


def create_run_files(coord, obstable, outdir='.', phot_radius=3.0 * u.arcsec,
                     max_template=50, debug=False):
    """Create region files and science/template image list files for photometry.

    Writes sn.reg, bkg.reg, science.lst, template.lst under outdir. Science/template
    split uses OBS_TYPE and FOV checks; template list is capped by max_template.

    Parameters
    ----------
    coord : astropy.coordinates.SkyCoord
        Source position.
    obstable : astropy.table.Table
        Table with OBSID, OBS_TYPE, IN_FOV, etc. (from get_swift_data).
    outdir : str, optional
        Output directory (default '.').
    phot_radius : astropy.units.Quantity, optional
        Source aperture radius (default 3 arcsec).
    max_template : int, optional
        Maximum number of template images to include; 0 = unlimited (default 50).
    debug : bool, optional
        Print debug messages.

    Returns
    -------
    sn_file : str
        Path to source region file.
    bkg_file : str
        Path to background region file.
    science_file : str
        Path to science image list.
    template_file : str
        Path to template image list.
    n_science : int
        Number of science images.
    n_template : int
        Number of template images.
    """
    phot_radius_val = phot_radius.to(u.arcsec).value
    ra_hms, dec_dms = coord.to_string(style='hmsdms', precision=2, sep=':').split()

    sn_file = os.path.join(outdir, 'sn.reg')
    with open(sn_file, 'w') as f:
        f.write(f'fk5;circle({ra_hms},{dec_dms},{phot_radius_val}")\n')

    bkg_file = os.path.join(outdir, 'bkg.reg')
    with open(bkg_file, 'w') as f:
        inner_radius = 2 * phot_radius_val
        outer_radius = 4 * phot_radius_val
        f.write(f'fk5;annulus({ra_hms},{dec_dms},{inner_radius}",{outer_radius}")\n')

    import glob
    globstr = os.path.join(outdir, '*', 'uvot', 'image', '*_sk.img.gz')
    all_files = glob.glob(globstr)

    science_file = os.path.join(outdir, 'science.lst')
    template_file = os.path.join(outdir, 'template.lst')

    science_list = []
    template_list = []
    
    # Track reasons for exclusion
    n_wrong_filter = 0
    n_out_of_fov = 0
    n_no_obsid_match = 0
    excluded_details = []

    for file in all_files:
        in_fov, details = check_coord_in_image(coord, file, debug=debug)
        
        if not in_fov:
            reason = details.get('reason', 'unknown')
            if 'unsupported filter' in reason:
                n_wrong_filter += 1
            else:
                n_out_of_fov += 1
                if debug:
                    excluded_details.append(details)
            continue
        
        obsid = details.get('obsid', '')
        mask = obstable['OBSID'] == obsid
        if not any(mask):
            n_no_obsid_match += 1
            continue

        obs_type = obstable[mask][0]['OBS_TYPE']
        if obs_type == 'science':
            science_list.append(file)
        elif obs_type == 'template':
            template_list.append(file)

    # Limit template images to prevent memory issues
    n_template_total = len(template_list)
    if max_template > 0 and len(template_list) > max_template:
        # Sort by filename (which includes date) to get a representative sample
        template_list.sort()
        # Take evenly spaced samples
        step = len(template_list) / max_template
        template_list = [template_list[int(i * step)] for i in range(max_template)]
        print(f"  Limiting templates: {n_template_total} -> {len(template_list)} (--max-template={max_template})")

    # Write output files
    with open(science_file, 'w') as f:
        for s in science_list:
            f.write(s + '\n')

    with open(template_file, 'w') as f:
        for t in template_list:
            f.write(t + '\n')

    # Report diagnostics
    if debug and excluded_details:
        print(f"  FOV check details for excluded images:")
        for d in excluded_details[:5]:  # Show first 5
            print(f"    {os.path.basename(d['file'])}: {d.get('reason', 'unknown')}")
        if len(excluded_details) > 5:
            print(f"    ... and {len(excluded_details) - 5} more")

    return sn_file, bkg_file, science_file, template_file, len(science_list), len(template_list)


def run_photometry(sn_file, bkg_file, science_file, template_file, outdir, name,
                   ab_mag=True, det_limit=3.0, allow_different_frametime=False):
    """Run the Swift UVOT photometry pipeline (create products, uvotmaghist, extract mags).

    Changes cwd to outdir, builds product files per filter, runs uvotmaghist for
    object and template, extracts photometry, and writes reduction/ and .phot.
    Restores cwd on exit.

    Parameters
    ----------
    sn_file : str
        Source region file path.
    bkg_file : str
        Background region file path.
    science_file : str
        Path to science image list.
    template_file : str
        Path to template image list.
    outdir : str
        Working directory for reduction (and where reduction/ is created).
    name : str
        Object name for output files.
    ab_mag : bool, optional
        Use AB magnitudes (default True).
    det_limit : float, optional
        S/N detection threshold (default 3.0).
    allow_different_frametime : bool, optional
        Allow merging extensions with different FRAMTIME.

    Returns
    -------
    dict or None
        Magnitude dict from output_mags, or None if no science data or on error.
    """
    orig_dir = os.getcwd()
    os.chdir(outdir)

    try:
        # Check if we have science data
        with open(science_file) as f:
            sci_files = [l.strip() for l in f if l.strip()]
        if not sci_files:
            print(f"  No science data for {name}")
            return None

        # Check template
        with open(template_file) as f:
            tmpl_files = [l.strip() for l in f if l.strip()]

        if tmpl_files:
            infile = [science_file, template_file]
        else:
            infile = [science_file]
            print(f"  No template data for {name}, running simple aperture photometry")

        obj_file_list, tem_file_list = up.interpret_infile(infile)
        obj_file_list = up.sort_file_list(obj_file_list)
        tem_file_list = up.sort_file_list(tem_file_list)

        reduction_dir = os.path.join(outdir, 'reduction')
        if os.path.isdir(reduction_dir):
            shutil.rmtree(reduction_dir)
        os.makedirs(reduction_dir)

        ap_size = up.get_aperture_size(sn_file)
        user_ap = ap_size + '_arcsec'
        mag = {user_ap: [], '5_arcsec': []}

        filt_list = up.sort_filters('ALL')

        for filt in filt_list:
            if filt not in obj_file_list:
                continue

            filter_dir = os.path.join(reduction_dir, filt)
            os.makedirs(filter_dir, exist_ok=True)

            print(f"  Processing filter {filt}...")
            prod_file = up.create_product(obj_file_list[filt], filt, no_combine=False, allow_different_frametime=allow_different_frametime)
            phot_file = up.run_uvotmaghist(prod_file, sn_file, bkg_file, filt)

            if filt in tem_file_list:
                prod_file_t = up.create_product(tem_file_list[filt], filt, template=1, no_combine=False, allow_different_frametime=allow_different_frametime)
                templ_file = up.run_uvotmaghist(prod_file_t, sn_file, bkg_file, filt)
                mag_filter = up.extract_photometry(phot_file, ab_mag, det_limit, ap_size, templ_file)
            else:
                mag_filter = up.extract_photometry(phot_file, ab_mag, det_limit, ap_size)

            for ap in mag_filter:
                mag[ap] = mag[ap] + mag_filter[ap]

        up.output_mags(mag, ap_size, obj=name)
        return mag

    except Exception as e:
        print(f"  Error running photometry: {e}")
        return None
    finally:
        os.chdir(orig_dir)


def parse_input_file(filepath):
    """Parse input file of sources with name, ra, dec, tpeak (JD - 2458000).

    Supports CSV (with header) or whitespace-separated. Accepts multiple
    column naming conventions (e.g. BTS: ZTFID, IAUID, RA, Dec, peakt).

    Parameters
    ----------
    filepath : str
        Path to the input file.

    Returns
    -------
    list of dict
        Each dict has keys 'name', 'ra', 'dec', 'tpeak' (float). Rows missing
        required fields are skipped.
    """
    sources = []

    with open(filepath, 'r') as f:
        content = f.read().strip()

    lines = content.split('\n')

    # Detect format
    if ',' in lines[0]:
        # CSV format
        reader = csv.DictReader(lines)
        for row in reader:
            # Handle various column name possibilities
            # Name: prefer IAUID, then name, then ZTFID
            name = (row.get('IAUID') or row.get('iauid') or 
                    row.get('name') or row.get('Name') or row.get('NAME') or
                    row.get('ZTFID') or row.get('ztfid') or '')
            
            # RA/Dec
            ra = row.get('RA') or row.get('ra') or row.get('Ra') or ''
            dec = row.get('Dec') or row.get('dec') or row.get('DEC') or ''
            
            # tpeak: try peakt (BTS format), then tpeak, then t_peak
            tpeak_str = (row.get('peakt') or row.get('peakT') or row.get('PEAKT') or
                         row.get('tpeak') or row.get('Tpeak') or row.get('TPEAK') or 
                         row.get('t_peak') or '')
            
            # Skip if missing required fields
            if not name or not ra or not dec or not tpeak_str:
                continue
            
            # Handle values starting with '>' (e.g., '>16.002')
            tpeak_str = tpeak_str.lstrip('>')
            
            try:
                tpeak = float(tpeak_str)
            except (ValueError, TypeError):
                continue
                
            sources.append({
                'name': name.strip(),
                'ra': ra.strip(),
                'dec': dec.strip(),
                'tpeak': tpeak
            })
    else:
        # Whitespace-separated (skip header if present)
        for i, line in enumerate(lines):
            parts = line.split()
            if len(parts) >= 4:
                # Check if first line is header
                if i == 0 and not is_number(parts[3]):
                    continue
                try:
                    sources.append({
                        'name': parts[0],
                        'ra': parts[1],
                        'dec': parts[2],
                        'tpeak': float(parts[3])
                    })
                except ValueError:
                    continue

    return sources


def check_heasoft_environment():
    """Check that HEASoft and CALDB are configured and uvotmaghist is available.

    Returns
    -------
    ok : bool
        True if HEADAS, CALDB, CALDBCONFIG are set and valid and uvotmaghist is in PATH.
    issues : list of str
        List of issue descriptions if ok is False; empty list if ok is True.
    """
    issues = []
    
    # Check HEADAS
    headas = os.environ.get('HEADAS')
    if not headas:
        issues.append("HEADAS not set")
    elif not os.path.isdir(headas):
        issues.append(f"HEADAS directory does not exist: {headas}")
    
    # Check CALDB
    caldb = os.environ.get('CALDB')
    if not caldb:
        issues.append("CALDB not set")
    elif not os.path.isdir(caldb):
        issues.append(f"CALDB directory does not exist: {caldb}")
    
    # Check CALDBCONFIG
    caldbconfig = os.environ.get('CALDBCONFIG')
    if not caldbconfig:
        issues.append("CALDBCONFIG not set")
    elif not os.path.isfile(caldbconfig):
        issues.append(f"CALDBCONFIG file does not exist: {caldbconfig}")
    
    # Check if uvotmaghist command exists
    import shutil
    if not shutil.which('uvotmaghist'):
        issues.append("uvotmaghist command not found in PATH")
    
    if issues:
        return False, issues
    return True, []


def main():
    parser = argparse.ArgumentParser(
        description="Run Swift UVOT photometry for sources from input file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("input_file", help="Input file with columns: name, ra, dec, tpeak (JD-2458000)")
    parser.add_argument("-o", "--outdir", default="/Users/ckilpatrick/Downloads",
                        help="Base output directory")
    parser.add_argument("--pre-days", type=float, default=60.0,
                        help="Days before tpeak for science start (template before this)")
    parser.add_argument("--post-days", type=float, default=365.0,
                        help="Days after tpeak for science end")
    parser.add_argument("--radius", type=float, default=30.0,
                        help="Search radius in arcmin")
    parser.add_argument("--phot-radius", type=float, default=3.0,
                        help="Photometry aperture radius in arcsec")
    parser.add_argument("--max-template", type=int, default=50,
                        help="Maximum number of template images to use (prevents memory issues). "
                             "Set to 0 for unlimited.")
    parser.add_argument("--no-download", action="store_true",
                        help="Skip downloading data (use existing)")
    parser.add_argument("--archive-dir", default=None,
                        help="Archive directory for shared downloads. Data is downloaded here "
                             "and symlinked to object directories. Default: <outdir>/archive/")
    parser.add_argument("--no-archive", action="store_true",
                        help="Disable archive (download directly to each object directory)")
    parser.add_argument("--download-all", action="store_true",
                        help="Download all UVOT files (exposure maps, raw, hk). "
                             "Default: only sky images (*_sk.img*) needed for photometry")
    parser.add_argument("-a", "--ab", action="store_true", default=True,
                        help="Use AB magnitudes")
    parser.add_argument("-d", "--detection", type=float, default=3.0,
                        help="Detection S/N limit")
    parser.add_argument("--allow-different-frametime", dest="allow_different_frametime", action="store_true",
                        help="Combine extensions with different FRAMTIME (photometry may be less accurate)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without executing")
    parser.add_argument("--debug", action="store_true",
                        help="Print debug information")
    parser.add_argument("--no-fov-filter", action="store_true",
                        help="Download all observations without pre-filtering by FOV")
    parser.add_argument("--skip-heasoft-check", action="store_true",
                        help="Skip HEASoft environment check (use with --dry-run)")
    args = parser.parse_args()

    # Start total timer
    total_start_time = time.time()

    # Check HEASoft environment (skip for dry-run if requested)
    if not args.dry_run and not args.skip_heasoft_check:
        ok, issues = check_heasoft_environment()
        if not ok:
            print("ERROR: HEASoft environment not properly configured.")
            print("Issues found:")
            for issue in issues:
                print(f"  - {issue}")
            print("\nTo fix this, you need to initialize HEASoft and CALDB:")
            print("  1. Source HEASoft initialization:")
            print("     source $HEADAS/headas-init.sh  (or .csh)")
            print("  2. Source CALDB initialization:")
            print("     source $CALDB/software/tools/caldbinit.sh  (or .csh)")
            print("\nIf using conda-installed HEASoft, these may be:")
            print("     source $CONDA_PREFIX/headas-init.sh")
            print("     export CALDB=$CONDA_PREFIX/caldb")
            print("     export CALDBCONFIG=$CALDB/software/tools/caldb.config")
            print("     export CALDBALIAS=$CALDB/software/tools/alias_config.fits")
            print("\nAlternatively, use --dry-run to test without running photometry.")
            sys.exit(1)
        else:
            if args.debug:
                print("HEASoft environment OK:")
                print(f"  HEADAS: {os.environ.get('HEADAS')}")
                print(f"  CALDB: {os.environ.get('CALDB')}")
                print(f"  CALDBCONFIG: {os.environ.get('CALDBCONFIG')}")
                print()

    # Parse input file
    print(f"Parsing input file: {args.input_file}")
    sources = parse_input_file(args.input_file)

    if not sources:
        print("ERROR: No valid sources found in input file.")
        print("Expected format: name, ra, dec, tpeak (where tpeak is JD-2458000)")
        sys.exit(1)

    print(f"Found {len(sources)} sources to process.\n")

    # Set up archive directory for shared downloads
    if args.no_archive:
        archive_dir = None
    elif args.archive_dir:
        archive_dir = args.archive_dir
    else:
        archive_dir = os.path.join(args.outdir, 'archive')
    
    if archive_dir:
        os.makedirs(archive_dir, exist_ok=True)
        print(f"Archive directory: {archive_dir}")
        print("  (data downloaded once, symlinked to object directories)\n")

    # Process each source
    results_summary = []
    total_downloaded = 0
    total_linked = 0

    for i, src in enumerate(sources):
        source_start_time = time.time()
        name = src['name']
        ra = src['ra']
        dec = src['dec']
        tpeak = src['tpeak']

        tpeak_time = tpeak_to_time(tpeak)
        science_start = tpeak_time - TimeDelta(args.pre_days * u.day)
        science_end = tpeak_time + TimeDelta(args.post_days * u.day)

        print(f"[{i+1}/{len(sources)}] Processing: {name}")
        print(f"  RA, Dec: {ra}, {dec}")
        print(f"  tpeak: {tpeak} (JD-2458000) = {tpeak_time.iso}")
        print(f"  Science window: {science_start.iso} to {science_end.iso}")
        print(f"  Template: before {science_start.iso}")

        # Create output directory
        outdir = os.path.join(args.outdir, name.replace(' ', '_'))

        if args.dry_run:
            print(f"  Would save to: {outdir}")
            source_elapsed = time.time() - source_start_time
            results_summary.append({'name': name, 'status': 'dry_run', 'time': source_elapsed})
            print()
            continue

        os.makedirs(outdir, exist_ok=True)
        print(f"  Output directory: {outdir}")

        # Parse coordinates
        coord = parse_coord(ra, dec)
        if coord is None:
            print(f"  Skipping {name}: invalid coordinates")
            source_elapsed = time.time() - source_start_time
            results_summary.append({'name': name, 'status': 'invalid_coords', 'time': source_elapsed})
            continue

        # Query Swift data
        print("  Querying HEASARC for Swift observations...")
        obstable = get_swift_data(
            coord, tpeak_time,
            pre_days=args.pre_days,
            post_days=args.post_days,
            radius=args.radius * u.arcmin,
            fov_filter=not args.no_fov_filter,
            debug=args.debug
        )

        if obstable is None:
            source_elapsed = time.time() - source_start_time
            results_summary.append({'name': name, 'status': 'no_data', 'time': source_elapsed})
            print(f"  Time: {source_elapsed:.1f}s")
            print()
            continue

        n_science = sum(obstable['OBS_TYPE'] == 'science')
        n_template = sum(obstable['OBS_TYPE'] == 'template')
        n_out_of_fov = sum(obstable['OBS_TYPE'] == 'out_of_fov')
        msg = f"  Found {n_science} science and {n_template} template observations"
        if n_out_of_fov > 0:
            msg += f" ({n_out_of_fov} excluded: source not in FOV)"
        print(msg)

        # Download data (skip out-of-FOV observations)
        if not args.no_download:
            print("  Downloading Swift data...")
            dl_stats = download_swift_data(
                obstable, outdir,
                archive_dir=archive_dir,
                sky_only=not args.download_all,
                debug=args.debug
            )
            total_downloaded += dl_stats['n_downloaded']
            total_linked += dl_stats['n_linked']
            if args.debug:
                print(f"  Downloaded {dl_stats['n_downloaded']}, linked {dl_stats['n_linked']} observations")

        # Create run files and verify FOV with WCS
        print("  Creating region and file lists...")
        sn_file, bkg_file, science_file, template_file, n_sci, n_tmpl = create_run_files(
            coord, obstable, outdir,
            phot_radius=args.phot_radius * u.arcsec,
            max_template=args.max_template,
            debug=args.debug
        )
        print(f"  Science images in FOV: {n_sci}, Template images: {n_tmpl}")

        if n_sci == 0:
            print(f"  No science images with source in FOV for {name}")
            source_elapsed = time.time() - source_start_time
            results_summary.append({'name': name, 'status': 'no_science_images', 'time': source_elapsed})
            print(f"  Time: {source_elapsed:.1f}s")
            print()
            continue

        # Run photometry
        print("  Running photometry...")
        mag = run_photometry(
            sn_file, bkg_file, science_file, template_file,
            outdir, name,
            ab_mag=args.ab, det_limit=args.detection,
            allow_different_frametime=args.allow_different_frametime
        )

        source_elapsed = time.time() - source_start_time
        if mag:
            n_meas = len(mag.get('5_arcsec', []))
            results_summary.append({'name': name, 'status': 'success', 'n_measurements': n_meas, 'time': source_elapsed})
            print(f"  Completed! {n_meas} photometry measurements.")
        else:
            results_summary.append({'name': name, 'status': 'photometry_failed', 'time': source_elapsed})

        print(f"  Time: {source_elapsed:.1f}s")
        print()

    # Calculate total time
    total_elapsed = time.time() - total_start_time

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    # Results per source
    for r in results_summary:
        status = r['status']
        time_str = f" ({r.get('time', 0):.1f}s)" if 'time' in r else ""
        if status == 'success':
            print(f"  {r['name']}: {r['n_measurements']} measurements{time_str}")
        else:
            print(f"  {r['name']}: {status}{time_str}")

    # Download statistics
    if not args.no_download and (total_downloaded > 0 or total_linked > 0):
        print()
        print("-" * 60)
        print("DOWNLOADS")
        print("-" * 60)
        print(f"  Observations downloaded: {total_downloaded}")
        print(f"  Observations linked:     {total_linked} (from archive)")
        if archive_dir:
            print(f"  Archive directory:       {archive_dir}")

    # Timing statistics
    print()
    print("-" * 60)
    print("TIMING")
    print("-" * 60)
    
    times = [r.get('time', 0) for r in results_summary if 'time' in r]
    n_processed = len(times)
    
    if n_processed > 0:
        avg_time = sum(times) / n_processed
        min_time = min(times)
        max_time = max(times)
        
        # Format time as hours:minutes:seconds if > 60 seconds
        def format_time(seconds):
            if seconds < 60:
                return f"{seconds:.1f}s"
            elif seconds < 3600:
                mins = int(seconds // 60)
                secs = seconds % 60
                return f"{mins}m {secs:.1f}s"
            else:
                hours = int(seconds // 3600)
                mins = int((seconds % 3600) // 60)
                secs = seconds % 60
                return f"{hours}h {mins}m {secs:.0f}s"
        
        print(f"  Sources processed: {n_processed}")
        print(f"  Total time:        {format_time(total_elapsed)}")
        print(f"  Average per source: {format_time(avg_time)}")
        print(f"  Fastest:           {format_time(min_time)}")
        print(f"  Slowest:           {format_time(max_time)}")
    else:
        print(f"  No sources processed.")
        print(f"  Total time: {total_elapsed:.1f}s")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
