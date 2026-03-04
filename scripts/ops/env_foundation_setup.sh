#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PY_VERSION="${PYTHON_VERSION:-$(cat .python-version 2>/dev/null || echo 3.12.12)}"
VENV_PATH="${VENV_PATH:-$ROOT/.build_venv}"
PYTHON_BIN=""

log() {
  printf '[env-foundation] %s\n' "$*"
}

resolve_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    return 0
  fi

  if command -v pyenv >/dev/null 2>&1; then
    if PYENV_VERSION="$PY_VERSION" pyenv which python >/dev/null 2>&1; then
      PYTHON_BIN="PYENV_VERSION=$PY_VERSION $(command -v pyenv) exec python"
      return 0
    fi
  fi

  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
    return 0
  fi

  return 1
}

run_python() {
  bash -lc "$PYTHON_BIN $*"
}

resolve_python || {
  log "ERROR: no usable Python interpreter found"
  exit 3
}

log "Using interpreter command: $PYTHON_BIN"
log "Creating/updating venv at $VENV_PATH"
run_python "-m venv '$VENV_PATH'"

PIP="$VENV_PATH/bin/pip"
PY="$VENV_PATH/bin/python"

log "Upgrading pip/setuptools/wheel"
"$PIP" install --upgrade pip setuptools wheel

log "Installing runtime + dev requirements"
"$PIP" install -r requirements.txt -r requirements-dev.txt

log "Installing Playwright browsers (chromium) with retries"
for i in 1 2 3; do
  if "$PY" -m playwright install --with-deps chromium; then
    break
  fi
  if [[ "$i" -eq 3 ]]; then
    log "ERROR: playwright browser install failed after 3 attempts"
    exit 4
  fi
  sleep 5
  log "Retrying Playwright browser install ($((i+1))/3)"
done

log "Environment foundation setup complete"
