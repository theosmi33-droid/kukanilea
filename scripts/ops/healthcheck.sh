#!/usr/bin/env bash
set -euo pipefail

EXIT_USAGE=2
EXIT_DEPENDENCY=3
EXIT_GATE=4

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CI_MODE=0

log() {
  echo "$*" | tee -a "$HEALTH_LOG"
}

fail() {
  local code="$1"
  shift
  log "$*"
  exit "$code"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ci)
      CI_MODE=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/ops/healthcheck.sh [--ci]

Options:
  --ci    Run in CI mode (non-interactive logging/behavior)
EOF
      exit 0
      ;;
    *)
      echo "[healthcheck] Unknown argument: $1" >&2
      exit "$EXIT_USAGE"
      ;;
  esac
done

if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x "$ROOT/.build_venv/bin/python" ]]; then
    PYTHON="$ROOT/.build_venv/bin/python"
  else
    PYTHON="python3"
  fi
fi
AUTH_DB="${KUKANILEA_AUTH_DB:-instance/auth.sqlite3}"
HEALTH_LOG="/tmp/kukanilea_healthcheck.log"
: > "$HEALTH_LOG"

for dep in curl find xargs sqlite3; do
  if ! command -v "$dep" >/dev/null 2>&1; then
    fail "$EXIT_DEPENDENCY" "[healthcheck] Missing required dependency: $dep"
  fi
done

log "[healthcheck] Starting at $(date)"
if [[ "$CI_MODE" -eq 1 ]]; then
  log "[healthcheck] CI mode enabled"
fi

log "[1/7] Python compile check..."
find app -name '*.py' -print0 | xargs -0 "$PYTHON" -m py_compile

log "[2/7] Ensuring DB tables..."
"$PYTHON" app/db/migrations/ensure_agent_memory.py | tee -a "$HEALTH_LOG"

log "[3/7] Running unit tests..."
if ! "$PYTHON" -c 'import pytest' >/dev/null 2>&1; then
  log "[healthcheck] pytest is not installed for interpreter: $PYTHON"
  fail "$EXIT_DEPENDENCY" "[healthcheck] Install test dependencies (for example: $PYTHON -m pip install -r requirements-dev.txt)"
fi
"$PYTHON" -m pytest -q

SERVER_PID=""
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

if ! curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5051/" | grep -Eq "^(200|302)$"; then
  log "[healthcheck] No server on :5051 detected, starting temporary local server..."
  "$PYTHON" kukanilea_app.py --host 127.0.0.1 --port 5051 >/tmp/kukanilea_healthcheck_server.log 2>&1 &
  SERVER_PID=$!
  if ! wait_for_http "http://127.0.0.1:5051/" 30 1; then
    log "[healthcheck] Server did not become ready on :5051 in time"
    log "[healthcheck] Last server log lines:"
    tail -n 80 /tmp/kukanilea_healthcheck_server.log | tee -a "$HEALTH_LOG"
    exit "$EXIT_GATE"
  fi
fi

log "[4/7] Checking routes (200/302)..."
URLS=("/" "/dashboard" "/upload" "/projects" "/tasks" "/messenger" "/email" "/calendar" "/time" "/visualizer" "/settings")
for u in "${URLS[@]}"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5051${u}" || true)
  if [[ "$code" != "200" && "$code" != "302" ]]; then
    fail "$EXIT_GATE" "[healthcheck] Route $u returned $code"
  fi
done

log "[5/7] Checking homepage for external URLs..."
external=$(curl -s http://127.0.0.1:5051/ | grep -oE 'https?://[^"'"'"' ]+' | grep -v '127.0.0.1' || true)
if [[ -n "$external" ]]; then
  log "[healthcheck] External URLs found:"
  echo "$external" | tee -a "$HEALTH_LOG"
  exit "$EXIT_GATE"
fi

log "[6/7] DB sanity check..."
if ! sqlite3 "$AUTH_DB" "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_memory';" | grep -q "agent_memory"; then
  fail "$EXIT_GATE" "[healthcheck] agent_memory table missing"
fi

log "[7/7] Verifying guardrails (CDN & HTMX confirm)..."
"$PYTHON" scripts/ops/verify_guardrails.py | tee -a "$HEALTH_LOG"

log "[healthcheck] All checks passed"
