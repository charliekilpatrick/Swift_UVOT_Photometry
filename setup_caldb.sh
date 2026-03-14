#!/usr/bin/env bash
# One-time CALDB setup for use with a conda environment that has HEASoft.
# Run from an activated conda env:  conda activate swift-photom && bash setup_caldb.sh
#
# CALDB is not shipped by the heasoft conda package; this script downloads the
# CALDB setup files from HEASARC into $CONDA_PREFIX/caldb so that uvotmaghist
# and other HEASoft tools can access calibration data (via remote access by default).
# See: https://heasarc.gsfc.nasa.gov/docs/heasarc/caldb/install.html

set -e

if [[ -z "${CONDA_PREFIX}" ]]; then
  echo "Error: CONDA_PREFIX is not set. Activate your conda environment first, e.g.:"
  echo "  conda activate swift-photom"
  exit 1
fi

CALDB_ROOT="${CONDA_PREFIX}/caldb"
URL="https://heasarc.gsfc.nasa.gov/FTP/caldb/software/tools/caldb_setup_files.tar.Z"

echo "CALDB one-time setup for ${CONDA_PREFIX}"
echo "Target directory: ${CALDB_ROOT}"
echo ""

if [[ -f "${CALDB_ROOT}/software/tools/caldb.config" ]]; then
  echo "CALDB already set up at ${CALDB_ROOT}."
  # Ensure activate.d script exists so HEADAS/CALDB are set on activate (avoids headas-uninit error).
  ACTIVATE_D="${CONDA_PREFIX}/etc/conda/activate.d"
  ENV_SH="${ACTIVATE_D}/00_swift_photometry_env.sh"
  if [[ ! -f "${ENV_SH}" ]]; then
    mkdir -p "${ACTIVATE_D}"
    cat > "${ENV_SH}" << 'ENVEOF'
# Swift UVOT Photometry: set HEASoft/CALDB so they are available in this env and before other activate scripts run.
export HEADAS="${CONDA_PREFIX}/heasoft"
export CALDB="${CONDA_PREFIX}/caldb"
export CALDBCONFIG="${CALDB}/software/tools/caldb.config"
export CALDBALIAS="${CALDB}/software/tools/alias_config.fits"
ENVEOF
    echo "Wrote ${ENV_SH} (HEADAS and CALDB will be set automatically when you activate this env)."
  else
    echo "Run 'conda activate swift-photom' and HEADAS/CALDB will be set automatically."
  fi
  exit 0
fi

mkdir -p "${CALDB_ROOT}"
cd "${CALDB_ROOT}"

if command -v wget &>/dev/null; then
  wget -q -O caldb_setup_files.tar.Z "${URL}"
elif command -v curl &>/dev/null; then
  curl -sL -o caldb_setup_files.tar.Z "${URL}"
else
  echo "Error: need wget or curl to download CALDB setup files."
  exit 1
fi

# Check we got a real archive (not an HTML error page)
if [[ ! -s caldb_setup_files.tar.Z ]]; then
  echo "Error: download failed or empty file."
  exit 1
fi
if head -1 caldb_setup_files.tar.Z 2>/dev/null | grep -q '<!'; then
  echo "Error: server returned HTML instead of CALDB tarball. Try again later."
  exit 1
fi

# .tar.Z is Unix compress format. BSD tar (macOS) does not support -Z; use uncompress + tar.
if command -v uncompress &>/dev/null; then
  uncompress -f caldb_setup_files.tar.Z 2>/dev/null || true
fi
if [[ ! -f caldb_setup_files.tar ]]; then
  # Try GNU tar -Z if available (e.g. Linux)
  if tar -xZf caldb_setup_files.tar.Z 2>/dev/null; then
    rm -f caldb_setup_files.tar.Z
  else
    echo "Error: could not decompress caldb_setup_files.tar.Z (need uncompress or GNU tar)."
    exit 1
  fi
else
  tar -xf caldb_setup_files.tar
  rm -f caldb_setup_files.tar caldb_setup_files.tar.Z 2>/dev/null
fi

# Tarball may put files in current dir or in software/tools/. Normalize to software/tools/.
if [[ -f caldb.config ]] && [[ ! -f software/tools/caldb.config ]]; then
  mkdir -p software/tools
  mv -f caldb.config alias_config.fits caldbinit.sh caldbinit.csh software/tools/ 2>/dev/null || true
fi

if [[ ! -f "${CALDB_ROOT}/software/tools/caldb.config" ]]; then
  echo "Error: CALDB setup files were not extracted correctly (missing caldb.config)."
  exit 1
fi

# Create conda activate.d script so HEADAS and CALDB are set as soon as the env activates.
# This avoids "set HEADAS before sourcing headas-uninit.sh" when switching envs (HEADAS is set before other scripts run).
ACTIVATE_D="${CONDA_PREFIX}/etc/conda/activate.d"
mkdir -p "${ACTIVATE_D}"
ENV_SH="${ACTIVATE_D}/00_swift_photometry_env.sh"
cat > "${ENV_SH}" << 'ENVEOF'
# Swift UVOT Photometry: set HEASoft/CALDB so they are available in this env and before other activate scripts run.
export HEADAS="${CONDA_PREFIX}/heasoft"
export CALDB="${CONDA_PREFIX}/caldb"
export CALDBCONFIG="${CALDB}/software/tools/caldb.config"
export CALDBALIAS="${CALDB}/software/tools/alias_config.fits"
ENVEOF
echo "Wrote ${ENV_SH} (HEADAS and CALDB will be set automatically when you activate this env)."

echo ""
echo "CALDB setup complete."
echo ""
echo "Next time you run 'conda activate swift-photom', HEADAS and CALDB will be set automatically."
echo "In this terminal, run:  source \$CONDA_PREFIX/heasoft/headas-init.sh   (or re-activate the env)"
echo "Then verify with:  caldbinfo INST SWIFT UVOTA"
