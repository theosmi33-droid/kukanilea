#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

START_TS="$(date +%s)"
RUN_HEALTHCHECK=1
RUN_LAUNCH_EVIDENCE=1
SEED_DATA=1
BOOTSTRAP_MARKER=".venv/.bootstrap_complete"
DOCTOR_MODE="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-healthcheck) RUN_HEALTHCHECK=0 ;;
    --skip-launch-evidence) RUN_LAUNCH_EVIDENCE=0 ;;
    --ci) DOCTOR_MODE="ci" ;;
    --local) DOCTOR_MODE="local" ;;
    --skip-seed) SEED_DATA=0 ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/dev_bootstrap.sh [options]

One-command bootstrap for reproducible local setup.

Options:
  --skip-seed             Skip seed scripts
  --skip-healthcheck      Skip scripts/ops/healthcheck.sh
  --skip-launch-evidence  Skip scripts/ops/launch_evidence_gate.sh --fast
  --ci                    Force CI doctor semantics
  --local                 Force local doctor semantics
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
    exit 3
  fi

  if command -v pyenv >/dev/null 2>&1; then
    if [[ -n "$required" ]]; then
      if pyenv versions --bare 2>/dev/null | grep -Fxq "$required"; then
        local vpy
        vpy="$(PYENV_VERSION="$required" pyenv which python 2>/dev/null || true)"
        if [[ -n "$vpy" && -x "$vpy" ]]; then
          printf '%s\n' "$vpy"
          return 0
        fi
      fi
    fi
    local pyenv_python
    pyenv_python="$(pyenv which python 2>/dev/null || true)"
    if [[ -n "$pyenv_python" && -x "$pyenv_python" ]]; then
      printf '%s\n' "$pyenv_python"
      return 0
    fi
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  echo "[bootstrap] No Python interpreter found. Install Python 3.11+ (or pyenv + local version)." >&2
  exit 3
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
  exit 3
fi

"$PYTHON" -m pip -q install -U pip wheel
"$PYTHON" -m pip -q install -r requirements.txt -r requirements-dev.txt

if [[ -n "${CI:-}" ]]; then
  PLAYWRIGHT_ARGS=(install chromium)
else
  PLAYWRIGHT_ARGS=(install --with-deps chromium)
fi

if [[ "$DOCTOR_MODE" == "auto" ]]; then
  if [[ -n "${CI:-}" ]]; then
    DOCTOR_MODE="ci"
  else
    DOCTOR_MODE="local"
  fi
fi

if "$PYTHON" -m playwright --version >/dev/null 2>&1; then
  echo "[bootstrap] Installing Playwright browsers (chromium): ${PLAYWRIGHT_ARGS[*]}"
  if ! "$PYTHON" -m playwright "${PLAYWRIGHT_ARGS[@]}"; then
    if [[ "$DOCTOR_MODE" == "ci" ]]; then
      echo "[bootstrap] ERROR: Playwright browser install failed in CI mode" >&2
      exit 4
    fi
    echo "[bootstrap] WARNING: Playwright browser install failed locally; continuing"
  fi
else
  echo "[bootstrap] WARNING: python playwright module is unavailable in venv"
fi

echo "[bootstrap] Running doctor checks (mode=$DOCTOR_MODE)"
if [[ "$DOCTOR_MODE" == "ci" ]]; then
  PYTHON="$PYTHON" scripts/dev/doctor.sh --strict --ci
else
  PYTHON="$PYTHON" scripts/dev/doctor.sh --strict --local
fi

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
