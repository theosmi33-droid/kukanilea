#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python3}"
AUTH_DB="${KUKANILEA_AUTH_DB:-instance/auth.sqlite3}"
HEALTH_LOG="/tmp/kukanilea_healthcheck.log"
: > "$HEALTH_LOG"

echo "[healthcheck] Starting at $(date)" | tee -a "$HEALTH_LOG"

echo "[1/7] Python compile check..." | tee -a "$HEALTH_LOG"
find app -name '*.py' -print0 | xargs -0 "$PYTHON" -m py_compile

echo "[2/7] Ensuring DB tables..." | tee -a "$HEALTH_LOG"
"$PYTHON" app/db/migrations/ensure_agent_memory.py | tee -a "$HEALTH_LOG"

echo "[3/7] Running unit tests..." | tee -a "$HEALTH_LOG"
pytest -q

SERVER_PID=""
cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if ! curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5051/" | grep -Eq "^(200|302)$"; then
  echo "[healthcheck] No server on :5051 detected, starting temporary local server..." | tee -a "$HEALTH_LOG"
  "$PYTHON" kukanilea_app.py --host 127.0.0.1 --port 5051 >/tmp/kukanilea_healthcheck_server.log 2>&1 &
  SERVER_PID=$!
  sleep 4
fi

echo "[4/7] Checking routes (200/302)..." | tee -a "$HEALTH_LOG"
URLS=("/" "/dashboard" "/upload" "/projects" "/tasks" "/messenger" "/email" "/calendar" "/time" "/visualizer" "/settings")
for u in "${URLS[@]}"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5051${u}" || true)
  if [[ "$code" != "200" && "$code" != "302" ]]; then
    echo "Route $u returned $code" | tee -a "$HEALTH_LOG"
    exit 1
  fi
done

echo "[5/7] Checking homepage for external URLs..." | tee -a "$HEALTH_LOG"
external=$(curl -s http://127.0.0.1:5051/ | grep -oE 'https?://[^"'"'"' ]+' | grep -v '127.0.0.1' || true)
if [[ -n "$external" ]]; then
  echo "External URLs found:" | tee -a "$HEALTH_LOG"
  echo "$external" | tee -a "$HEALTH_LOG"
  exit 1
fi

echo "[6/7] DB sanity check..." | tee -a "$HEALTH_LOG"
if ! sqlite3 "$AUTH_DB" "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_memory';" | grep -q "agent_memory"; then
  echo "agent_memory table missing" | tee -a "$HEALTH_LOG"
  exit 1
fi

echo "[7/7] Verifying guardrails (CDN & HTMX confirm)..." | tee -a "$HEALTH_LOG"
"$PYTHON" scripts/ops/verify_guardrails.py | tee -a "$HEALTH_LOG"

echo "[healthcheck] All checks passed" | tee -a "$HEALTH_LOG"
