#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python3}"
AUTH_DB="${KUKANILEA_AUTH_DB:-instance/auth.sqlite3}"
HEALTH_LOG="/tmp/kukanilea_healthcheck.log"
: > "$HEALTH_LOG"

echo "[healthcheck] Starting at $(date)" | tee -a "$HEALTH_LOG"

echo "[1/6] Python compile check..." | tee -a "$HEALTH_LOG"
find app -name '*.py' -print0 | xargs -0 "$PYTHON" -m py_compile

echo "[2/6] Ensuring DB tables..." | tee -a "$HEALTH_LOG"
"$PYTHON" app/db/migrations/ensure_agent_memory.py | tee -a "$HEALTH_LOG"

echo "[3/6] Running unit tests..." | tee -a "$HEALTH_LOG"
pytest -q

echo "[4/6] Checking routes (200/302)..." | tee -a "$HEALTH_LOG"
URLS=("/" "/dashboard" "/upload" "/projects" "/tasks" "/messenger" "/email" "/calendar" "/time" "/visualizer" "/settings")
for u in "${URLS[@]}"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5051${u}" || true)
  if [[ "$code" != "200" && "$code" != "302" ]]; then
    echo "Route $u returned $code" | tee -a "$HEALTH_LOG"
    exit 1
  fi
done

echo "[5/6] Checking homepage for external URLs..." | tee -a "$HEALTH_LOG"
external=$(curl -s http://127.0.0.1:5051/ | grep -oE 'https?://[^"'"'"' ]+' | grep -v '127.0.0.1' || true)
if [[ -n "$external" ]]; then
  echo "External URLs found:" | tee -a "$HEALTH_LOG"
  echo "$external" | tee -a "$HEALTH_LOG"
  exit 1
fi

echo "[6/6] DB sanity check..." | tee -a "$HEALTH_LOG"
if ! sqlite3 "$AUTH_DB" "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_memory';" | grep -q "agent_memory"; then
  echo "agent_memory table missing" | tee -a "$HEALTH_LOG"
  exit 1
fi

echo "[healthcheck] All checks passed" | tee -a "$HEALTH_LOG"
