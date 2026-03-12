#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$($ROOT/scripts/dev/resolve_python.sh)"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[first-diagnose] Python interpreter is not executable: $PYTHON_BIN" >&2
  exit 3
fi

echo "[first-diagnose] Root=$ROOT"
echo "[first-diagnose] Python=$PYTHON_BIN"
echo "[first-diagnose] Step 1/2: guardrails baseline"
"$PYTHON_BIN" "$ROOT/scripts/ops/verify_guardrails.py"

echo "[first-diagnose] Step 2/2: fast local healthcheck"
if ! PYTHON="$PYTHON_BIN" "$ROOT/scripts/ops/healthcheck.sh" --skip-pytest --no-doctor; then
  rc=$?
  echo "[first-diagnose] FAILED (rc=$rc)." >&2
  echo "[first-diagnose] Next: run full diagnosis with strict doctor:" >&2
  echo "PYTHON=$PYTHON_BIN scripts/ops/healthcheck.sh --strict-doctor" >&2
  exit "$rc"
fi

echo "[first-diagnose] OK: baseline diagnosis passed."
