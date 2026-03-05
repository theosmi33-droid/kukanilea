#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

START_TS="$(date +%s)"
RUN_HEALTHCHECK=1
RUN_LAUNCH_EVIDENCE=1
SEED_DATA=1
BOOTSTRAP_MARKER=".venv/.bootstrap_complete"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-healthcheck) RUN_HEALTHCHECK=0 ;;
    --skip-launch-evidence) RUN_LAUNCH_EVIDENCE=0 ;;
    --skip-seed) SEED_DATA=0 ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/dev_bootstrap.sh [options]

One-command bootstrap for reproducible local setup.

Options:
  --skip-seed             Skip seed scripts
  --skip-healthcheck      Skip scripts/ops/healthcheck.sh
  --skip-launch-evidence  Skip scripts/ops/launch_evidence_gate.sh --fast
USAGE
      exit 0
      ;;
    *)
      echo "[bootstrap] Unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

version_matches_required() {
  local required="$1"
  local version="$2"
  [[ -n "$required" ]] || return 0
  [[ "$version" == "$required" || "$version" == "${required}."* ]]
}

choose_base_python() {
  local required=""
  if [[ -f "$ROOT/.python-version" ]]; then
    required="$(tr -d '[:space:]' < "$ROOT/.python-version")"
  fi

  if [[ -n "${PYTHON_BIN:-}" ]]; then
    if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
      command -v "$PYTHON_BIN"
      return 0
    fi
    if [[ -x "$PYTHON_BIN" ]]; then
      printf '%s\n' "$PYTHON_BIN"
      return 0
    fi
    echo "[bootstrap] PYTHON_BIN is set but not executable: $PYTHON_BIN" >&2
    echo "[bootstrap] Action: unset PYTHON_BIN or point it to a valid Python 3.11+ executable." >&2
    exit 3
  fi

  if command -v pyenv >/dev/null 2>&1; then
    if [[ -n "$required" ]] && ! pyenv versions --bare 2>/dev/null | grep -Fxq "$required"; then
      echo "[bootstrap] .python-version requires pyenv Python $required, but it is not installed." >&2
      echo "[bootstrap] Action: run 'pyenv install $required' then retry ./scripts/dev_bootstrap.sh." >&2
      exit 3
    fi

    if [[ -n "$required" ]]; then
      local vpy
      vpy="$(PYENV_VERSION="$required" pyenv which python 2>/dev/null || true)"
      if [[ -n "$vpy" && -x "$vpy" ]]; then
        printf '%s\n' "$vpy"
        return 0
      fi
      echo "[bootstrap] pyenv found but could not resolve Python $required from .python-version." >&2
      echo "[bootstrap] Action: check 'pyenv versions' and 'pyenv local $required'." >&2
      exit 3
    fi

    local pyenv_python
    pyenv_python="$(pyenv which python 2>/dev/null || true)"
    if [[ -n "$pyenv_python" && -x "$pyenv_python" ]]; then
      printf '%s\n' "$pyenv_python"
      return 0
    fi
  fi

  local candidate=""
  if command -v python3 >/dev/null 2>&1; then
    candidate="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    candidate="$(command -v python)"
  fi

  if [[ -z "$candidate" ]]; then
    echo "[bootstrap] No Python interpreter found." >&2
    echo "[bootstrap] Action: install Python 3.11+ (or pyenv + local version) and rerun ./scripts/dev_bootstrap.sh." >&2
    exit 3
  fi

  if [[ -n "$required" ]]; then
    local actual
    actual="$($candidate -c 'import platform; print(platform.python_version())' 2>/dev/null || true)"
    if ! version_matches_required "$required" "$actual"; then
      echo "[bootstrap] .python-version requires $required but detected $actual at $candidate." >&2
      echo "[bootstrap] Action: install/select $required via pyenv, or set PYTHON_BIN to a matching interpreter." >&2
      exit 3
    fi
  fi

  printf '%s\n' "$candidate"
}

BASE_PYTHON="$(choose_base_python)"
echo "[bootstrap] Base Python: $BASE_PYTHON ($($BASE_PYTHON --version 2>&1 | head -n1))"

if [[ ! -d ".venv" ]]; then
  echo "[bootstrap] Creating project virtualenv (.venv)"
  "$BASE_PYTHON" -m venv .venv
fi

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "[bootstrap] Missing venv python: $PYTHON" >&2
  echo "[bootstrap] Action: remove .venv and rerun ./scripts/dev_bootstrap.sh to recreate the virtual environment." >&2
  exit 3
fi

if ! "$PYTHON" -m pip -q install -U pip wheel; then
  echo "[bootstrap] Failed to install/upgrade pip+wheel in .venv." >&2
  echo "[bootstrap] Action: verify network and rerun: $PYTHON -m pip install -U pip wheel" >&2
  exit 4
fi

if ! "$PYTHON" -m pip -q install -r requirements.txt -r requirements-dev.txt; then
  echo "[bootstrap] Dependency install failed for requirements.txt / requirements-dev.txt." >&2
  echo "[bootstrap] Action: inspect pip output above, then retry: $PYTHON -m pip install -r requirements.txt -r requirements-dev.txt" >&2
  exit 4
fi

if [[ -n "${CI:-}" ]]; then
  PLAYWRIGHT_ARGS=(install chromium)
else
  PLAYWRIGHT_ARGS=(install --with-deps chromium)
fi

if "$PYTHON" -m playwright --version >/dev/null 2>&1; then
  echo "[bootstrap] Installing Playwright browsers (chromium): ${PLAYWRIGHT_ARGS[*]}"
  "$PYTHON" -m playwright "${PLAYWRIGHT_ARGS[@]}"
else
  echo "[bootstrap] WARNING: python playwright module is unavailable in venv" >&2
  echo "[bootstrap] Action: ensure requirements-dev.txt is installed and rerun $PYTHON -m playwright install chromium" >&2
fi

echo "[bootstrap] Running doctor checks"
PYTHON="$PYTHON" scripts/dev/doctor.sh --strict

if [[ "$SEED_DATA" -eq 1 ]]; then
  "$PYTHON" scripts/seed_dev_users.py
  "$PYTHON" scripts/seed_demo_data.py
fi
"$PYTHON" -m app.smoke

if [[ "$RUN_HEALTHCHECK" -eq 1 ]]; then
  echo "[bootstrap] Running healthcheck"
  PYTHON="$PYTHON" scripts/ops/healthcheck.sh
fi

if [[ "$RUN_LAUNCH_EVIDENCE" -eq 1 ]]; then
  echo "[bootstrap] Running launch evidence gate (--fast)"
  PYTHON="$PYTHON" scripts/ops/launch_evidence_gate.sh --fast
fi

touch "$BOOTSTRAP_MARKER"
echo "[bootstrap] Wrote marker: $BOOTSTRAP_MARKER"

END_TS="$(date +%s)"
echo "✅ Bootstrap complete in $((END_TS-START_TS))s"
