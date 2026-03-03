#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.build_venv/bin/python"
DB="/Users/gensuminguyen/Kukanilea/data/agent_orchestra_shared.db"
LOG="/tmp/kukanilea_readycheck.log"
FAIL=0
STARTED_PID=""

ok() { printf "[OK] %s\n" "$1"; }
warn() { printf "[WARN] %s\n" "$1"; }
err() { printf "[FAIL] %s\n" "$1"; FAIL=1; }

cleanup() {
  if [ -n "$STARTED_PID" ] && kill -0 "$STARTED_PID" 2>/dev/null; then
    kill "$STARTED_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$ROOT" || exit 2

echo "=== KUKANILEA VS Code Ready Check ==="
echo "workspace: $ROOT"

echo "-- Interpreter --"
if [ -x "$PY" ]; then
  "$PY" --version && ok "venv python found"
else
  err "missing interpreter: $PY"
fi

echo "-- VS Code Config --"
if bash "$ROOT/scripts/dev/vscode_guardrails.sh" --check >/tmp/kukanilea_vscode_config.log 2>&1; then
  ok "vscode config is aligned"
else
  warn "vscode config drift detected, auto-applying defaults"
  bash "$ROOT/scripts/dev/vscode_guardrails.sh" --apply --install-hooks >/tmp/kukanilea_vscode_config.log 2>&1 || true
fi

echo "-- Shared Memory --"
if [ -f "$ROOT/scripts/shared_memory.py" ]; then
  "$PY" "$ROOT/scripts/shared_memory.py" init >/dev/null 2>&1 && ok "shared db init ok"
  "$PY" "$ROOT/scripts/shared_memory.py" read >/dev/null 2>&1 && ok "shared db read ok"
else
  err "scripts/shared_memory.py not found"
fi

if [ -f "$DB" ]; then
  ok "shared db file exists ($DB)"
else
  err "shared db file missing ($DB)"
fi

echo "-- GitHub CLI --"
if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    ok "gh auth active"
  else
    warn "gh installed but not authenticated"
  fi
else
  warn "gh CLI not installed"
fi

echo "-- LLM Provider --"
PROVIDER_JSON="$($PY - <<'PY'
import json, os
from app.agents.llm import get_default_provider
p = get_default_provider()
print(json.dumps({
  "provider": getattr(p, "name", "unknown"),
  "available": bool(getattr(p, "available", False)),
  "model": getattr(p, "model", None),
  "host": getattr(p, "host", None),
  "OLLAMA_ENABLED": os.environ.get("OLLAMA_ENABLED", "0"),
  "KUKANILEA_REMOTE_LLM_ENABLED": os.environ.get("KUKANILEA_REMOTE_LLM_ENABLED", "0")
}))
PY
)"
echo "$PROVIDER_JSON"

if echo "$PROVIDER_JSON" | grep -q '"provider": "ollama"'; then
  ok "runtime provider = ollama"
else
  err "runtime provider is not ollama (set OLLAMA_ENABLED=1, KUKANILEA_REMOTE_LLM_ENABLED=0)"
fi

if command -v curl >/dev/null 2>&1; then
  TAGS_JSON="$(curl -sS --max-time 3 http://127.0.0.1:11434/api/tags || true)"
  if [ -n "$TAGS_JSON" ] && echo "$TAGS_JSON" | grep -q 'models'; then
    ok "ollama reachable"
    echo "$TAGS_JSON" | grep -q 'nomic-embed-text' || warn "model missing: nomic-embed-text"
    echo "$TAGS_JSON" | grep -q 'qwen2.5:0.5b' || warn "model missing: qwen2.5:0.5b"
  else
    warn "ollama not reachable at 127.0.0.1:11434"
  fi
else
  warn "curl not available"
fi

echo "-- Tests --"
if "$PY" -m pytest -q >/dev/null; then
  ok "pytest suite passes"
else
  err "pytest failed"
fi

echo "-- App Boot & Health --"
if lsof -iTCP:5051 -sTCP:LISTEN >/dev/null 2>&1; then
  ok "app already listening on 127.0.0.1:5051"
else
  nohup "$PY" "$ROOT/kukanilea_app.py" --host 127.0.0.1 --port 5051 >"$LOG" 2>&1 &
  STARTED_PID=$!
  for _ in $(seq 1 20); do
    sleep 1
    if curl -sS --max-time 2 http://127.0.0.1:5051/health >/dev/null 2>&1; then
      break
    fi
  done
fi

if curl -sS --max-time 2 http://127.0.0.1:5051/health >/dev/null 2>&1; then
  ok "GET /health reachable"
else
  err "GET /health failed"
fi

if curl -sS --max-time 2 http://127.0.0.1:5051/api/health >/dev/null 2>&1; then
  ok "GET /api/health reachable"
else
  err "GET /api/health failed"
fi

echo "=== Summary ==="
if [ "$FAIL" -eq 0 ]; then
  echo "READY: workspace startklar"
  exit 0
else
  echo "NOT READY: mindestens ein Pflichtcheck fehlgeschlagen"
  exit 1
fi
