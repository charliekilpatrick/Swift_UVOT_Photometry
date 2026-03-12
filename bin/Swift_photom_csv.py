#!/usr/bin/env python3
"""
Run Swift UVOT photometry for multiple sources from a CSV file.

CSV must have columns: name, ra, dec
Optional column: date (for reference; not used to filter images)
RA/Dec can be decimal degrees or sexagesimal (e.g. 15:03:49.97).
"""
import argparse
import csv
import json
import os
import shutil
import sys

from astropy.coordinates import SkyCoord
from astropy import units as u

import SwiftPhotom.help as SH
import SwiftPhotom.uvot as up


def parse_coord(ra, dec):
    """Parse RA, Dec (degrees or sexagesimal) to SkyCoord."""
    ra_str, dec_str = str(ra).strip(), str(dec).strip()
    if ":" in ra_str or ":" in dec_str:
        unit = (u.hourangle, u.deg)
    else:
        unit = (u.deg, u.deg)
    return SkyCoord(ra_str, dec_str, frame="icrs", unit=unit)


def write_regions(coord, sn_reg_path, bg_reg_path, ap_arcsec=3.0, bkg_inner=100.0, bkg_outer=200.0):
    """Write DS9 source and background region files."""
    ra_hms, dec_dms = coord.to_string(style="hmsdms", sep=":").split()
    with open(sn_reg_path, "w") as f:
        f.write(f'fk5;circle({ra_hms},{dec_dms},{ap_arcsec}")')
    with open(bg_reg_path, "w") as f:
        f.write(f'fk5;annulus({ra_hms},{dec_dms},{bkg_inner}",{bkg_outer}")')


def run_photometry_for_source(
    name,
    sn_reg,
    bg_reg,
    obj_file_list,
    tem_file_list,
    ab,
    det_limit,
    filt_list,
    no_combine,
):
    """Run the same pipeline as Swift_photom_host for one source."""
    ap_size = up.get_aperture_size(sn_reg)
    user_ap = ap_size + "_arcsec"
    mag = {user_ap: [], "5_arcsec": []}

    for filter in filt_list:
        if filter not in obj_file_list:
            continue
        filter_dir = os.path.join("reduction", filter)
        if not os.path.isdir(filter_dir):
            os.makedirs(filter_dir)

        prod_file = up.create_product(obj_file_list[filter], filter, no_combine=no_combine)
        phot_file = up.run_uvotmaghist(prod_file, sn_reg, bg_reg, filter)

        template_exists = filter in tem_file_list
        if template_exists:
            prod_file_t = up.create_product(
                tem_file_list[filter], filter, template=1, no_combine=no_combine
            )
            templ_file = up.run_uvotmaghist(prod_file_t, sn_reg, bg_reg, filter)
            mag_filter = up.extract_photometry(
                phot_file, ab, det_limit, ap_size, templ_file
            )
        else:
            mag_filter = up.extract_photometry(
                phot_file, ab, det_limit, ap_size
            )

        for ap in mag_filter:
            mag[ap] = mag[ap] + mag_filter[ap]

    up.output_mags(mag, ap_size, obj=name)
    return mag


def main():
    parser = argparse.ArgumentParser(
        description="Run Swift UVOT photometry for multiple sources from a CSV (name, ra, dec, [date])."
    )
    parser.add_argument("csv_file", help="CSV with columns: name, ra, dec; optional: date")
    parser.add_argument("infile", nargs="+", help=SH.infile_help)
    parser.add_argument(
        "-o", "--output",
        default="photometry_results.csv",
        help="Output CSV path for combined results (default: photometry_results.csv)",
    )
    parser.add_argument("--ap-arcsec", type=float, default=3.0, help="Source aperture radius [arcsec]")
    parser.add_argument("--bkg-inner", type=float, default=100.0, help="Background annulus inner radius [arcsec]")
    parser.add_argument("--bkg-outer", type=float, default=200.0, help="Background annulus outer radius [arcsec]")
    parser.add_argument("-d", "--detection", dest="det_limit", type=float, default=3.0, help="Detection S/N limit")
    parser.add_argument("-a", "--ab", dest="ab", action="store_true", help="Use AB magnitudes")
    parser.add_argument("-f", "--filter", dest="filter", default="ALL", help="Filters to use")
    parser.add_argument("--no_combine", dest="no_combine", action="store_true", help="Do not merge extensions")
    parser.add_argument("--sn-reg", dest="sn_reg", default="sn.reg", help="Source region path (written per source)")
    parser.add_argument("--bg-reg", dest="bg_reg", default="snbkg.reg", help="Background region path (written per source)")
    args = parser.parse_args()

    # Parse CSV
    with open(args.csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "name" not in reader.fieldnames or "ra" not in reader.fieldnames or "dec" not in reader.fieldnames:
            print("CSV must have columns: name, ra, dec (optional: date)", file=sys.stderr)
            sys.exit(1)
        rows = list(reader)

    if not rows:
        print("No rows in CSV.", file=sys.stderr)
        sys.exit(1)

    # Single image/list setup (same for all sources)
    obj_file_list, tem_file_list = up.interpret_infile(args.infile)
    obj_file_list = up.sort_file_list(obj_file_list)
    tem_file_list = up.sort_file_list(tem_file_list)
    filt_list = up.sort_filters(args.filter)

    combined_rows = []
    sn_reg = args.sn_reg
    bg_reg = args.bg_reg

    for i, row in enumerate(rows):
        name = row.get("name", "").strip() or f"source_{i+1}"
        ra = row.get("ra", "").strip()
        dec = row.get("dec", "").strip()
        date = row.get("date", "").strip()

        if not ra or not dec:
            print(f"Skipping row {i+1}: missing ra/dec", file=sys.stderr)
            continue

        try:
            coord = parse_coord(ra, dec)
        except Exception as e:
            print(f"Skipping {name}: invalid coordinates ({e})", file=sys.stderr)
            continue

        # Write region files for this source
        write_regions(
            coord,
            sn_reg,
            bg_reg,
            ap_arcsec=args.ap_arcsec,
            bkg_inner=args.bkg_inner,
            bkg_outer=args.bkg_outer,
        )

        if os.path.isdir("reduction"):
            shutil.rmtree("reduction")
        os.makedirs("reduction")

        print(f"Running photometry for: {name}")
        try:
            mag = run_photometry_for_source(
                name,
                sn_reg,
                bg_reg,
                obj_file_list,
                tem_file_list,
                args.ab,
                args.det_limit,
                filt_list,
                args.no_combine,
            )
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            if os.path.isdir("reduction"):
                shutil.rmtree("reduction")
            continue

        # Collect results for combined CSV (use 5_arcsec as canonical)
        json_path = os.path.join("reduction", "5_arcsec_photometry.json")
        if os.path.isfile(json_path):
            with open(json_path) as jf:
                phot_list = json.load(jf)
            for p in phot_list:
                combined_rows.append({
                    "name": name,
                    "date": date,
                    "mjd": p["mjd"],
                    "filter": p["filter"],
                    "mag": p["mag"],
                    "mag_err": p["mag_err"],
                    "upper_limit": p["upper_limit"],
                })

        # Move reduction to reduction_<name>
        out_dir = f"reduction_{name.replace(' ', '_')}"
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir)
        shutil.move("reduction", out_dir)
        print(f"  -> {out_dir}")

    # Write combined results CSV
    if combined_rows:
        outpath = args.output
        with open(outpath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["name", "date", "mjd", "filter", "mag", "mag_err", "upper_limit"],
            )
            writer.writeheader()
            writer.writerows(combined_rows)
        print(f"Combined results written to {outpath}")
    else:
        print("No photometry results to write.", file=sys.stderr)


if __name__ == "__main__":
    main()
