#!/usr/bin/env bash
set -euo pipefail

EXIT_USAGE=2
EXIT_DEPENDENCY=3
EXIT_GATE=4

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CI_MODE=0
SKIP_PYTEST=0
AUTH_DB="${KUKANILEA_AUTH_DB:-instance/auth.sqlite3}"
HEALTH_LOG="/tmp/kukanilea_healthcheck.log"
PYTHON="${PYTHON:-}"
DOCTOR_STRICT=1
SERVER_PID=""

log() {
  echo "$*" | tee -a "$HEALTH_LOG"
}

fail() {
  local code="$1"
  shift
  log "$*"
  exit "$code"
}

require_cmd() {
  local dep="$1"
  if ! command -v "$dep" >/dev/null 2>&1; then
    fail "$EXIT_DEPENDENCY" "[healthcheck] Missing required dependency: $dep"
  fi
}

run_gate() {
  local gate="$1"
  shift
  if ! "$@"; then
    fail "$EXIT_GATE" "[healthcheck] Gate failed: ${gate}"
  fi
}

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

wait_for_http() {
  local url="$1"
  local retries="${2:-30}"
  local delay="${3:-1}"
  local i code
  for ((i=1; i<=retries; i++)); do
    code="$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)"
    if [[ "$code" == "200" || "$code" == "302" ]]; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --ci)
        CI_MODE=1
        shift
        ;;
      --skip-pytest)
        SKIP_PYTEST=1
        shift
        ;;
      --no-doctor)
        DOCTOR_STRICT=0
        shift
        ;;
      -h|--help)
        cat <<'USAGE'
Usage: ./scripts/ops/healthcheck.sh [--ci] [--skip-pytest] [--no-doctor]

Options:
  --ci           Run in CI mode (non-interactive logging/behavior)
  --skip-pytest  Skip pytest execution (local fallback for environment drift)
  --no-doctor   Skip scripts/dev/doctor.sh --strict
USAGE
        exit 0
        ;;
      *)
        echo "[healthcheck] Unknown argument: $1" >&2
        exit "$EXIT_USAGE"
        ;;
    esac
  done
}

parse_args "$@"

: > "$HEALTH_LOG"

if [[ -z "$PYTHON" ]]; then
  PYTHON="$($ROOT/scripts/dev/resolve_python.sh)"
fi

for dep in curl find xargs sqlite3; do
  require_cmd "$dep"
done

if [[ ! -x "$PYTHON" ]]; then
  fail "$EXIT_DEPENDENCY" "[healthcheck] Python interpreter is not executable: $PYTHON"
fi

if [[ "$DOCTOR_STRICT" -eq 1 ]]; then
  run_gate "doctor" bash -lc "cd '$ROOT' && PYTHON='$PYTHON' scripts/dev/doctor.sh --strict"
fi

log "[healthcheck] Starting at $(date -Iseconds)"
log "[healthcheck] Root=$ROOT"
log "[healthcheck] Python=$PYTHON"
if [[ "$CI_MODE" -eq 1 ]]; then
  log "[healthcheck] CI mode enabled"
fi

log "[1/7] Python compile check..."
run_gate "Python compile check" bash -lc "cd '$ROOT' && find app -name '*.py' -print0 | xargs -0 '$PYTHON' -m py_compile"

log "[2/7] Ensuring DB tables..."
run_gate "DB migration check" bash -lc "cd '$ROOT' && '$PYTHON' app/db/migrations/ensure_agent_memory.py"

log "[3/7] Running unit tests..."
if [[ "$SKIP_PYTEST" -eq 1 ]]; then
  log "[healthcheck] Skipping pytest (--skip-pytest enabled)"
elif ! "$PYTHON" -c 'import pytest' >/dev/null 2>&1; then
  if [[ "$CI_MODE" -eq 1 ]]; then
    fail "$EXIT_DEPENDENCY" "[healthcheck] pytest is not installed for interpreter: $PYTHON"
  fi
  log "[healthcheck] WARNING: pytest not available for interpreter: $PYTHON (continuing outside CI mode)"
else
  run_gate "pytest" bash -lc "cd '$ROOT' && '$PYTHON' -m pytest -q"
fi

HAS_FLASK=0
if "$PYTHON" -c 'import flask' >/dev/null 2>&1; then
  HAS_FLASK=1
elif [[ "$CI_MODE" -eq 1 ]]; then
  fail "$EXIT_DEPENDENCY" "[healthcheck] flask is not installed for interpreter: $PYTHON"
else
  log "[healthcheck] WARNING: flask not available for interpreter: $PYTHON (skipping HTTP route probes)"
fi

if [[ "$HAS_FLASK" -eq 1 ]]; then
  if ! curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5051/" | grep -Eq "^(200|302)$"; then
    log "[healthcheck] No server on :5051 detected, starting temporary local server..."
    (cd "$ROOT" && "$PYTHON" kukanilea_app.py --host 127.0.0.1 --port 5051) >/tmp/kukanilea_healthcheck_server.log 2>&1 &
    SERVER_PID=$!
    if ! wait_for_http "http://127.0.0.1:5051/" 30 1; then
      log "[healthcheck] Server did not become ready on :5051 in time"
      log "[healthcheck] Last server log lines:"
      tail -n 80 /tmp/kukanilea_healthcheck_server.log | tee -a "$HEALTH_LOG"
      fail "$EXIT_GATE" "[healthcheck] Core server readiness failed"
    fi
  fi

  log "[4/7] Checking routes (200/302)..."
  check_routes() {
    local code
    local urls=("/" "/dashboard" "/upload" "/projects" "/tasks" "/messenger" "/email" "/calendar" "/time" "/visualizer" "/settings")
    for u in "${urls[@]}"; do
      code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5051${u}" || true)"
      if [[ "$code" != "200" && "$code" != "302" ]]; then
        log "[healthcheck] Route ${u} returned ${code}"
        return 1
      fi
    done
  }
  run_gate "Route health" check_routes

  log "[5/7] Checking homepage for external URLs..."
  check_external_urls() {
    local external
    external="$(curl -s http://127.0.0.1:5051/ | grep -oE 'https?://[^"'"'"' ]+' | grep -v '127.0.0.1' || true)"
    if [[ -n "$external" ]]; then
      log "[healthcheck] External URLs found:"
      echo "$external" | tee -a "$HEALTH_LOG"
      return 1
    fi
  }
  run_gate "Zero external URLs on homepage" check_external_urls
else
  log "[4/7] Checking routes (200/302)..."
  log "[healthcheck] Skipped (flask missing)"
  log "[5/7] Checking homepage for external URLs..."
  log "[healthcheck] Skipped (flask missing)"
fi

log "[6/7] DB sanity check..."
check_db() {
  if [[ ! -f "$ROOT/$AUTH_DB" ]]; then
    log "[healthcheck] Auth DB not found: $ROOT/$AUTH_DB"
    return 1
  fi
  sqlite3 "$ROOT/$AUTH_DB" "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_memory';" | grep -q "agent_memory"
}
run_gate "agent_memory table" check_db

log "[7/7] Verifying guardrails (CDN & HTMX confirm)..."
run_gate "guardrails verify" bash -lc "cd '$ROOT' && '$PYTHON' scripts/ops/verify_guardrails.py"

log "[healthcheck] All checks passed"
