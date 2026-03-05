#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-$($ROOT/scripts/dev/resolve_python.sh)}"
STRICT=0
CI_MODE="${CI:-0}"
MODE_SOURCE="env:CI"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict) STRICT=1 ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/dev/doctor.sh [--strict] [--ci|--local]

Checks local dev tooling for reproducible setup:
- python/pip
- pytest
- flask
- ruff
- playwright

--strict exits non-zero if any required check is missing.
--ci enforces CI requirements (Playwright browser binary availability).
--local forces local-mode semantics even if CI=true is present in env.
USAGE
      exit 0
      ;;
    --ci)
      CI_MODE=1
      MODE_SOURCE="flag:--ci"
      ;;
    --local)
      CI_MODE=0
      MODE_SOURCE="flag:--local"
      ;;
    *)
      echo "[doctor] Unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

failures=0
warn() { echo "[doctor] WARN: $*"; }
fail() { echo "[doctor] FAIL: $*"; failures=$((failures+1)); }
ok() { echo "[doctor] OK: $*"; }

is_truthy() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

if is_truthy "$CI_MODE"; then
  CI_MODE=1
  ok "CI mode enabled (Playwright browser binaries required; source=${MODE_SOURCE})"
else
  CI_MODE=0
  ok "Local mode enabled (Playwright browser binaries optional; source=${MODE_SOURCE})"
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "[doctor] ERROR: resolved python is not executable: $PYTHON" >&2
  exit 3
fi
ok "python=$("$PYTHON" --version 2>&1 | head -n1) ($PYTHON)"

if "$PYTHON" -m pip --version >/dev/null 2>&1; then
  ok "pip available"
else
  fail "pip unavailable for interpreter $PYTHON (recovery: $PYTHON -m ensurepip --upgrade)"
fi

for module in pytest flask ruff playwright; do
  if "$PYTHON" -c "import ${module}" >/dev/null 2>&1; then
    ok "python module '${module}' available"
  else
    fail "python module '${module}' missing (recovery: $PYTHON -m pip install ${module})"
  fi
done

playwright_python_cli=0
playwright_browser_ready=0

if "$PYTHON" -c "import playwright" >/dev/null 2>&1; then
  if "$PYTHON" -m playwright --version >/dev/null 2>&1; then
    playwright_version="$($PYTHON -m playwright --version 2>/dev/null | head -n1)"
    ok "Playwright Python CLI available via '$PYTHON -m playwright' (${playwright_version:-unknown})"
    playwright_python_cli=1
  else
    fail "Playwright Python module found, but '$PYTHON -m playwright' failed (recovery: reinstall module via $PYTHON -m pip install --force-reinstall playwright)"
  fi

  if [[ "$playwright_python_cli" -eq 1 ]]; then
    if "$PYTHON" -m playwright install --list 2>/dev/null | grep -Eq '^\s*chromium\s'; then
      ok "Playwright chromium browser binary present"
      playwright_browser_ready=1
    else
      if [[ "$CI_MODE" -eq 1 ]]; then
        fail "Playwright chromium browser binary missing in CI mode (recovery: $PYTHON -m playwright install chromium)"
      else
        warn "Playwright chromium browser binary missing (optional local warning; recovery: $PYTHON -m playwright install chromium)"
      fi
    fi
  fi
else
  warn "Skipping Playwright runtime checks because python module 'playwright' is unavailable"
fi

if command -v playwright >/dev/null 2>&1; then
  ok "Node Playwright CLI available ($(playwright --version 2>/dev/null || echo unknown)); optional"
else
  warn "Node Playwright CLI missing (optional). Preferred path is '$PYTHON -m playwright'."
fi

if [[ "$failures" -gt 0 ]]; then
  if [[ "$STRICT" -eq 1 ]]; then
    echo "[doctor] FAIL: $failures missing/invalid checks." >&2
    exit 4
  fi
  echo "[doctor] Completed with warnings: $failures"
else
  echo "[doctor] All checks passed"
fi
