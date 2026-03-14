# Swift Host Subtraction

Python package for aperture and template-subtracted photometry on [Swift UVOT](https://swift.gsfc.nasa.gov/about_swift/uvot_desc.html) data. It runs [HEASoft](https://heasarc.gsfc.nasa.gov/docs/software/heasoft/) commands from Python and is aimed at transient studies.

Based on [Peter J. Brown](https://pbrown801.github.io)'s IDL work ([PhD thesis](https://etda.libraries.psu.edu/files/final_submissions/4865)); photometry follows [Brown et al. (2009)](https://ui.adsabs.harvard.edu/abs/2009AJ....137.4517B/abstract), image subtraction [Brown et al. (2014)](https://ui.adsabs.harvard.edu/abs/2014Ap%26SS.354...89B/abstract). See [documentation](https://gterreran.github.io/Swift_host_subtraction/) for details.

---

## Installation

### 1. Prerequisites

- **Python** 3.9 or newer (3.11–3.12 recommended).
- **HEASoft** (Swift/UVOT): required for running photometry. Two options:

  **Option A – Conda (recommended)**  
  HEASoft 6.35+ is available via HEASARC’s conda channel. Use the included environment file:

  ```bash
  conda env create -f environment.yml
  conda activate swift-photom
  ```

  After activating, initialize HEASoft and CALDB in that terminal (or add these lines to your shell profile so they run on every login):

  ```bash
  source $CONDA_PREFIX/headas-init.sh
  export CALDB=$CONDA_PREFIX/caldb
  export CALDBCONFIG=$CALDB/software/tools/caldb.config
  export CALDBALIAS=$CALDB/software/tools/alias_config.fits
  ```

  To install HEASoft into an existing environment:

  ```bash
  conda install -c https://heasarc.gsfc.nasa.gov/FTP/software/conda/ -c conda-forge heasoft
  ```

  Verify with: `caldbinfo INST SWIFT UVOTA`

  **Option B – Manual install**  
  Install from [HEASARC](https://heasarc.gsfc.nasa.gov/docs/software/heasoft/download.html) (Swift packages + [CALDB](https://heasarc.gsfc.nasa.gov/docs/heasarc/caldb/install.html)). Then in each terminal (or in `~/.bashrc`):

  ```bash
  . path/to/headas-init.sh
  source path/to/caldbinit.sh
  ```

  Check with: `caldbinfo INST SWIFT XRT`

### 2. Install the package

From the project root:

```bash
pip install .
```

Editable install (for development):

```bash
pip install -e .
```

Optional extras (docs, tests):

```bash
pip install -e ".[doc,dev]"
```

Run the test suite:

```bash
pytest tests/ -v
```

To run HEASoft integration tests, ensure HEASoft and CALDB are initialized first:

```bash
source $HEADAS/headas-init.sh
export CALDBCONFIG=$CALDB/software/tools/caldb.config
export CALDBALIAS=$CALDB/software/tools/alias_config.fits
pytest tests/test_heasoft.py -v
```

Tests in `test_heasoft.py` are automatically skipped if HEASoft is not available.

---

## Usage

### Single source (image lists + region files)

1. **Region files** (DS9 format): source circle and background region, e.g.  
   - `sn.reg`: `fk5;circle(15:03:49.97,+42:06:50.52,3")`  
   - `snbkg.reg`: background circle or annulus, away from sources.

2. **Image lists**: one file listing science images (and optionally one for templates), e.g.  
   ```bash
   ls */uvot/image/sw*_sk.img.gz > obj.lst
   ```

3. **Run photometry:**
   ```bash
   Swift_photom_host.py obj.lst [templ.lst] -s sn.reg -b snbkg.reg
   ```
   Use `-h` for options (e.g. `-a` for AB mags, `-d` detection threshold). Outputs go in `reduction/` (JSON, `.phot` file, and per-filter figures).

### Multiple sources from a CSV file

Use a CSV with columns **name**, **RA**, **Dec**, and optionally **date** (for reference; does not filter images). RA/Dec can be decimal degrees or sexagesimal (e.g. `15:03:49.97`).

Example `sources.csv`:

```csv
name,ra,dec,date
SN2020oi,229.5927,21.9832,2020-01-07
M51,202.4695,47.1952,
```

Run:

```bash
Swift_photom_csv.py sources.csv obj.lst [templ.lst] -o results.csv
```

- For each row the script writes temporary source and background regions at the given coordinates (default 3" aperture, annulus background), runs the same photometry pipeline, and saves outputs under `reduction_<name>/`.
- A combined table is written to `results.csv` (or the path given after `-o`).

Optional flags: `--ap-arcsec`, `--bkg-inner`, `--bkg-outer`, `-a` (AB mags), `-d` (detection limit). Run `Swift_photom_csv.py -h` for details.

### Batch processing with time constraints

For transient surveys, use `Swift_batch_photom.py` to automatically download Swift data and run photometry with time-based science/template selection.

**Input file format** (CSV or whitespace-separated):

```
name,ra,dec,tpeak
SN2020abc,150.123,+25.456,800.5
SN2021xyz,210.987,-10.234,1200.3
```

Where **tpeak** is JD − 2458000 (days relative to JD 2458000).

**Time constraints:**
- **Science data:** tpeak − 60 days to tpeak + 365 days  
- **Template data:** observations before tpeak − 60 days

**Run:**

```bash
Swift_batch_photom.py sources.txt -o /path/to/output
```

This will:
1. Query HEASARC for Swift UVOT observations of each source
2. Download data to a shared archive (avoids re-downloading)
3. Create symbolic links from object directories to the archive
4. Create region files and image lists
5. Run photometry with template subtraction
6. Save results to `<outdir>/<name>/`

**Archive directory:** By default, downloaded observations are stored in `<outdir>/archive/` and symlinked to each object's directory. If an observation was already downloaded for a previous object, it's reused automatically. Use `--no-archive` to disable this and download directly to each object directory.

**Optimized downloads:** By default, only sky images (`*_sk.img.gz`) needed for photometry are downloaded. Exposure maps, raw images, and housekeeping files are skipped to save bandwidth and disk space. Use `--download-all` to fetch all UVOT files.

**Options:**
- `--pre-days` / `--post-days`: adjust science window (default: −60 to +365)
- `--radius`: HEASARC search radius in arcmin (default: 30)
- `--phot-radius`: photometry aperture in arcsec (default: 3)
- `--archive-dir`: custom archive directory (default: `<outdir>/archive/`)
- `--no-archive`: disable archive, download directly to object directories
- `--download-all`: download all UVOT files (default: only `*_sk.img*`)
- `--no-download`: skip downloading, use existing data
- `--dry-run`: show what would be done without executing

Run `Swift_batch_photom.py -h` for all options.

---

## Repository

- **Package:** `Swift-host-subtraction` (PyPI) / **import:** `SwiftPhotom`
- **Version:** The package uses [setuptools-scm](https://github.com/pypa/setuptools_scm) for versioning; installed version is available as `SwiftPhotom.__version__`.
- **Repo:** [github.com/gterreran/Swift_host_subtraction](https://github.com/gterreran/Swift_host_subtraction)
- **License:** GPLv3+ ([LICENSE](LICENSE))

Build and packaging are driven by **pyproject.toml**; **MANIFEST.in** controls which files are included in source distributions (e.g. `pip sdist`). Unused or obsolete configuration has been removed (e.g. `setup.cfg`, `.codecov.yml`, conda build recipe in `conda/`, and the `scripts/` directory).

**Layout**

| Path | Description |
|------|-------------|
| `SwiftPhotom/` | Main package: `commands` (HEASoft wrappers), `uvot` (filters, aspect correction, products, photometry), `errors`, `help` (CLI strings) |
| `bin/` | Command-line entry points (see below) |
| `tests/` | Pytest suite (unit tests for uvot, commands, errors, help, batch/csv/setup/download scripts; HEASoft integration tests skipped when not configured) |
| `docs/` | Sphinx documentation source |
| `environment.yml` | Conda environment definition (Python + HEASoft + this package) for Option A installation |

**Command-line entry points (`bin/`)**

| Script | Description | Typical use |
|--------|-------------|-------------|
| **Swift_photom_host.py** | Run aperture or template-subtracted photometry for a **single source**. Reads object (and optional template) image lists or ObsIDs, builds stacked products per filter, runs uvotmaghist, writes JSON and `.phot` under `reduction/`. | You already have sky images and region files; you want light curves for one object (e.g. one transient) with or without template subtraction. |
| **Swift_photom_csv.py** | Same pipeline as `Swift_photom_host` for **multiple sources** from a CSV. For each row (name, RA, Dec), writes temporary region files, runs photometry, and saves results under `reduction_<name>/`; optionally writes a combined results CSV. | You have one shared set of image lists (and optional template list) and many source positions; you want light curves for all of them in one run. |
| **Swift_batch_photom.py** | **End-to-end batch pipeline** for transient surveys: reads an input file (name, RA, Dec, tpeak), queries HEASARC for Swift UVOT observations, downloads data (with optional shared archive and symlinks), builds science/template lists by time and FOV, runs photometry, and writes results to `<outdir>/<name>/`. | You have a list of transients (e.g. SNe) and want to automatically fetch Swift data, split science vs template by epoch, and get template-subtracted light curves without preparing image lists by hand. |
| **download_swift.py** | **Standalone download + setup** for one position and date range: queries HEASARC, downloads UVOT data by ObsID (no archive/symlinks), classifies science vs template by discovery date, creates region files and science/template lists. Prints a suggested `Swift_photom_host` command. | You want to pull Swift data for a single target with a fixed discovery date and run photometry yourself; or you prefer the simpler download logic without FOV filtering or shared archive. |
| **Swift_setup.py** | **Query and table helpers**: queries HEASARC for UVOT image table at a position, adds science/template tags by relative date, and can write region files and science/template `.dat` lists. Supports dry-run download of selected images. | You need a table of available observations and science/template split (e.g. for inspection or custom pipelines) or minimal reduction files without running the full photometry pipeline. |

**Code and testing**

- Public modules and functions are documented with **NumPy-style docstrings** (Parameters, Returns, Raises).
- Unit tests live in `tests/` and can be run with `pytest tests/ -v`. For coverage: `pytest tests/ --cov=SwiftPhotom --cov-report=term-missing`. Tests that require HEASoft or CALDB (e.g. `tests/test_heasoft.py`) are skipped automatically when the environment is not set up.
- Build and editable install with dev dependencies: `pip install -e ".[dev]"`.

**Warning:** Each run of `Swift_photom_host` (or each source in the CSV run) overwrites or creates a new `reduction` (or `reduction_<name>`) directory; copy or rename results if you need to keep them.

---

## References

If you use this software in a publication, please cite [Brown et al. (2009)](https://ui.adsabs.harvard.edu/abs/2009AJ....137.4517B/abstract) and [Brown et al. (2014)](https://ui.adsabs.harvard.edu/abs/2014Ap%26SS.354...89B/abstract). You may also cite this repository.
