#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-$($ROOT/scripts/dev/resolve_python.sh)}"
STRICT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict) STRICT=1 ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/dev/doctor.sh [--strict]

Checks local dev tooling for reproducible setup:
- python/pip
- pytest
- flask
- ruff
- playwright

--strict exits non-zero if any check is missing.
USAGE
      exit 0
      ;;
    *)
      echo "[doctor] Unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

failures=0
warn() { echo "[doctor] WARN: $*"; failures=$((failures+1)); }
ok() { echo "[doctor] OK: $*"; }

if [[ ! -x "$PYTHON" ]]; then
  echo "[doctor] ERROR: resolved python is not executable: $PYTHON" >&2
  exit 3
fi
ok "python=$("$PYTHON" --version 2>&1 | head -n1) ($PYTHON)"

if "$PYTHON" -m pip --version >/dev/null 2>&1; then
  ok "pip available"
else
  warn "pip unavailable for interpreter $PYTHON"
fi

for module in pytest flask ruff playwright; do
  if "$PYTHON" -c "import ${module}" >/dev/null 2>&1; then
    ok "python module '${module}' available"
  else
    warn "python module '${module}' missing"
  fi
done

if command -v playwright >/dev/null 2>&1; then
  ok "playwright CLI available ($(playwright --version 2>/dev/null || echo unknown))"
else
  warn "playwright CLI missing (use: $PYTHON -m playwright install --with-deps chromium)"
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
