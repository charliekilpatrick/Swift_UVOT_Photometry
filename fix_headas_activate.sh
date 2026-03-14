#!/usr/bin/env bash
# Fix "headas-uninit.sh: ERROR -- set HEADAS before sourcing headas-uninit.sh"
# when activating the swift-photom conda environment.
#
# Run once with the env activated:  conda activate swift-photom && bash fix_headas_activate.sh
# This creates an activate.d script that sets HEADAS (and CALDB if present) before other scripts run.

set -e

if [[ -z "${CONDA_PREFIX}" ]]; then
  echo "Error: CONDA_PREFIX is not set. Activate your conda environment first:"
  echo "  conda activate swift-photom"
  exit 1
fi

ACTIVATE_D="${CONDA_PREFIX}/etc/conda/activate.d"
mkdir -p "${ACTIVATE_D}"
ENV_SH="${ACTIVATE_D}/00_swift_photometry_env.sh"

cat > "${ENV_SH}" << 'ENVEOF'
# Swift UVOT Photometry: set HEASoft/CALDB so they are available before other activate scripts run.
export HEADAS="${CONDA_PREFIX}/heasoft"
export CALDB="${CONDA_PREFIX}/caldb"
export CALDBCONFIG="${CALDB}/software/tools/caldb.config"
export CALDBALIAS="${CALDB}/software/tools/alias_config.fits"
ENVEOF

echo "Wrote ${ENV_SH}"
echo "Next time you run 'conda activate swift-photom', HEADAS (and CALDB) will be set automatically and the headas-uninit error should stop."
echo "Re-activate the env now to pick it up:  conda deactivate && conda activate swift-photom"
