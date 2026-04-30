#!/usr/bin/env bash
# Wrapper that ensures the candy-crush-saga_playbot conda env is active
# before running any Python script.
#
# Usage:
#   ./run.sh <script.py> [args...]
#   ./run.sh main.py
#   ./run.sh main.py --level 11

set -euo pipefail

ENV_NAME="candy-crush-saga_playbot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/src" && pwd)"

# Locate conda
CONDA_BASE="$(conda info --base 2>/dev/null || echo "/opt/miniconda3")"
if [[ ! -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]]; then
    echo "[run.sh] ERROR: cannot find conda at ${CONDA_BASE}" >&2
    exit 1
fi
source "${CONDA_BASE}/etc/profile.d/conda.sh"

# Verify the target env exists
if ! conda env list | grep -q "^${ENV_NAME}"; then
    echo "[run.sh] ERROR: conda env '${ENV_NAME}' not found." >&2
    echo "         Create it with: conda create -n ${ENV_NAME} python=3.11 pillow numpy -y" >&2
    exit 1
fi

conda activate "${ENV_NAME}"
echo "[run.sh] active env: $(conda info --envs | grep '^\*' | awk '{print $1}')"

# Must receive at least one argument (the script to run)
if [[ $# -eq 0 ]]; then
    echo "[run.sh] Usage: $0 <script.py> [args...]" >&2
    exit 1
fi

SCRIPT="$1"; shift || true
# If path is not absolute, resolve relative to SCRIPT_DIR
if [[ "${SCRIPT}" != /* ]]; then
    SCRIPT="${SCRIPT_DIR}/${SCRIPT}"
fi
exec python "${SCRIPT}" "$@"
