#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$ROOT_DIR/build_release.log"
BUILD_VENV="$ROOT_DIR/.build_venv"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "== KUKANILEA release build started at $(date -u +%Y-%m-%dT%H:%M:%SZ) =="

if [ ! -d "$BUILD_VENV" ]; then
  python3 -m venv "$BUILD_VENV"
fi

# shellcheck disable=SC1091
source "$BUILD_VENV/bin/activate"
export PYTHON="$BUILD_VENV/bin/python"

python -m pip install --upgrade pip
python -m pip install --upgrade \
  waitress \
  platformdirs \
  cryptography \
  pyinstaller \
  dmgbuild \
  pip-audit

echo "-- release zip --"
bash "$ROOT_DIR/scripts/release_zip.sh"

echo "-- mac app build --"
bash "$ROOT_DIR/scripts/build_mac.sh"

echo "-- dmg build --"
bash "$ROOT_DIR/scripts/make_dmg.sh"

echo "-- security audit (non-blocking) --"
if ! pip-audit; then
  echo "pip-audit reported findings (build continues)."
fi

echo "== release build finished at $(date -u +%Y-%m-%dT%H:%M:%SZ) =="
