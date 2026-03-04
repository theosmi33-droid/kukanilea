#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.build_venv"
PYTHON_VERSION_FILE="${ROOT_DIR}/.python-version"

log() {
  printf '[bootstrap] %s\n' "$1"
}

if [[ ! -f "${PYTHON_VERSION_FILE}" ]]; then
  echo "[bootstrap] ERROR: missing .python-version in ${ROOT_DIR}" >&2
  exit 3
fi

EXPECTED_VERSION="$(tr -d '[:space:]' < "${PYTHON_VERSION_FILE}")"
if [[ -z "${EXPECTED_VERSION}" ]]; then
  echo "[bootstrap] ERROR: .python-version is empty. Expected e.g. 3.12.0" >&2
  exit 3
fi

ACTIVE_MM="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
EXPECTED_MM="$(python3 -c "v='${EXPECTED_VERSION}'; p=v.split('.'); print('.'.join(p[:2]) if len(p) >= 2 else v)")"

if [[ "${ACTIVE_MM}" != "${EXPECTED_MM}" ]]; then
  echo "[bootstrap] ERROR: Python ${EXPECTED_VERSION} required from .python-version, but found ${ACTIVE_MM}.x." >&2
  echo "[bootstrap]        Use pyenv/asdf or install matching Python before rerunning bootstrap." >&2
  exit 4
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  log "Creating virtual environment at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
else
  log "Virtual environment already exists at ${VENV_DIR} (idempotent reuse)"
fi

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

log "Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

log "Installing runtime and development dependencies"
pip install -r "${ROOT_DIR}/requirements.txt" -r "${ROOT_DIR}/requirements-dev.txt"

log "Installing Playwright browsers (chromium)"
python -m playwright install chromium

if command -v pre-commit >/dev/null 2>&1; then
  log "Installing pre-commit hooks"
  pre-commit install --install-hooks
else
  log "pre-commit not found in PATH; running through virtualenv"
  python -m pre_commit install --install-hooks
fi

log "Bootstrap complete. Activate with: source ${VENV_DIR}/bin/activate"
