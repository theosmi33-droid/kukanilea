#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
PY="$CORE/.build_venv/bin/python"

echo "== KUKANILEA CLI Quick Start =="
echo "core=$CORE"

if [[ ! -x "$PY" ]]; then
  echo "missing interpreter: $PY"
  exit 2
fi

if ! command -v gemini >/dev/null 2>&1; then
  echo "missing gemini CLI in PATH"
  echo "install first, then rerun"
  exit 2
fi

chmod +x "$CORE/scripts/ai/gemini_cli.py" \
         "$CORE/scripts/ai/codex_auto_fix.sh" \
         "$CORE/scripts/dev/vscode_guardrails.sh" || true

echo "[1/4] enforce VS Code guardrails"
bash "$CORE/scripts/dev/vscode_guardrails.sh" --apply --install-hooks

echo "[2/4] init shared memory"
"$PY" "$CORE/scripts/shared_memory.py" --db "$ROOT/data/agent_orchestra_shared.db" init >/dev/null

echo "[3/4] gemini wrapper smoke test"
"$PY" "$CORE/scripts/ai/gemini_cli.py" \
  --domain dashboard \
  --cwd "$CORE" \
  --approval-mode default \
  "Antworte nur mit: KUKANILEA_GEMINI_READY" \
  > /tmp/kukanilea_gemini_ready.txt || true
cat /tmp/kukanilea_gemini_ready.txt | sed -n '1,20p'

echo "[4/4] ready check"
bash "$CORE/scripts/vscode_ready_check.sh" || true

echo "== Done =="
echo "Next:"
echo "  cd $CORE"
echo "  ./scripts/orchestration/start_gemini_fleet.sh"
echo "  ./scripts/orchestration/gemini_fleet_status.sh <run_id>"

