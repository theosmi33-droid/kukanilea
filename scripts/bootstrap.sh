#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.build_venv"
PYTHON_VERSION_FILE="${ROOT_DIR}/.python-version"
SKIP_PLAYWRIGHT="${BOOTSTRAP_SKIP_PLAYWRIGHT:-0}"

log() {
  printf '[bootstrap] %s\n' "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[bootstrap] ERROR: required command '$1' not found in PATH" >&2
    exit 1
  fi
}

if [[ ! -f "$PYTHON_VERSION_FILE" ]]; then
  echo "[bootstrap] ERROR: missing .python-version" >&2
  exit 1
fi

EXPECTED_PYTHON_VERSION="$(tr -d '[:space:]' < "$PYTHON_VERSION_FILE")"
if [[ -z "$EXPECTED_PYTHON_VERSION" ]]; then
  echo "[bootstrap] ERROR: .python-version is empty" >&2
  exit 1
fi

require_command python3

CURRENT_PYTHON_VERSION="$(python3 -c 'import platform; print(platform.python_version())')"
if [[ "$CURRENT_PYTHON_VERSION" != "$EXPECTED_PYTHON_VERSION" ]]; then
  echo "[bootstrap] ERROR: python3 version mismatch" >&2
  echo "[bootstrap] expected: $EXPECTED_PYTHON_VERSION" >&2
  echo "[bootstrap] actual:   $CURRENT_PYTHON_VERSION" >&2
  exit 1
fi

log "Python version OK ($CURRENT_PYTHON_VERSION)"

if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
else
  log "Reusing existing virtual environment at $VENV_DIR"
fi

PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[bootstrap] ERROR: virtualenv python not found at $PYTHON_BIN" >&2
  exit 1
fi

log "Upgrading pip/setuptools/wheel"
"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel

log "Installing runtime and dev dependencies"
"$PIP_BIN" install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/requirements-dev.txt"

if [[ "$SKIP_PLAYWRIGHT" == "1" ]]; then
  log "Skipping playwright browser install (BOOTSTRAP_SKIP_PLAYWRIGHT=1)"
else
  log "Installing Playwright browsers"
  "$PYTHON_BIN" -m playwright install
fi

log "Installing pre-commit hooks"
"$PYTHON_BIN" -m pre_commit install --install-hooks

log "Bootstrap complete"
