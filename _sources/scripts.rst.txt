.. _scripts:

########################
Command-line scripts (bin/)
########################

The package installs the following scripts under ``bin/``. They are also
available as entry points after ``pip install`` (e.g. ``Swift_photom_host.py``).

Swift_photom_host.py
====================

Run aperture or template-subtracted photometry for a **single source**.

- **Inputs:** Object (and optional template) image list(s) or ObsID(s), plus
  source and background region files (DS9 format).
- **Output:** JSON, ``.phot`` file, and per-filter figures under ``reduction/``.

**Typical use:** You already have sky images and region files; you want light
curves for one object (e.g. one transient) with or without template subtraction.

**Example:**

.. code-block:: bash

   Swift_photom_host.py obj.lst -s sn.reg -b snbkg.reg
   Swift_photom_host.py obj.lst templ.lst -s sn.reg -b snbkg.reg

Use ``-h`` for options (e.g. ``-a`` for AB mags, ``-d`` detection threshold).


Swift_photom_csv.py
===================

Same pipeline as ``Swift_photom_host`` for **multiple sources** from a CSV.

- **Inputs:** CSV with columns **name**, **RA**, **Dec** (optionally **date**);
  one object image list (and optional template list).
- **Output:** For each row, temporary region files and results under
  ``reduction_<name>/``; optional combined table (e.g. ``results.csv``).

**Typical use:** One shared set of image lists and many source positions; light
curves for all of them in one run.

**Example:**

.. code-block:: bash

   Swift_photom_csv.py sources.csv obj.lst -o results.csv

Optional flags: ``--ap-arcsec``, ``--bkg-inner``, ``--bkg-outer``, ``-a``, ``-d``.
Run ``Swift_photom_csv.py -h`` for details.


Swift_batch_photom.py
=====================

**End-to-end batch pipeline** for transient surveys.

- **Inputs:** File (CSV or whitespace-separated) with **name**, **RA**, **Dec**,
  **tpeak** (JD − 2458000). Time windows: science = tpeak − 60 to tpeak + 365
  days; template = before tpeak − 60 days.
- **Actions:** Queries HEASARC for Swift UVOT observations, downloads data
  (optional shared archive and symlinks), builds science/template lists, runs
  photometry, writes results to ``<outdir>/<name>/``.

**Typical use:** List of transients (e.g. SNe); automatically fetch Swift data,
split science vs template by epoch, and get template-subtracted light curves.

**Example:**

.. code-block:: bash

   Swift_batch_photom.py sources.txt -o /path/to/output

**Options:** ``--pre-days`` / ``--post-days``, ``--radius``, ``--phot-radius``,
``--archive-dir``, ``--no-archive``, ``--download-all``, ``--no-download``,
``--dry-run``. Run ``Swift_batch_photom.py -h`` for all options.


download_swift.py
=================

**Standalone download and setup** for one position and date range.

- **Actions:** Queries HEASARC, downloads UVOT data by ObsID (no archive or
  symlinks), classifies science vs template by discovery date, creates region
  files and science/template lists. Prints a suggested ``Swift_photom_host``
  command.

**Typical use:** Pull Swift data for a single target with a fixed discovery
date and run photometry yourself; or use simpler download logic without FOV
filtering or shared archive.


Swift_setup.py
==============

**Query and table helpers** for inspecting available data and building minimal
reduction inputs.

- **Actions:** Queries HEASARC for UVOT image table at a position, adds
  science/template tags by relative date, can write region files and
  science/template ``.dat`` lists. Supports dry-run download of selected
  images.

**Typical use:** Table of available observations and science/template split for
inspection or custom pipelines; or minimal reduction files without running the
full photometry pipeline.
