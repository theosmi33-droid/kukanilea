#!/usr/bin/env bash
set -euo pipefail

TOOL_NAME="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE="$(cd "$SCRIPT_DIR/../.." && pwd)"
ROOT="$(cd "$CORE/.." && pwd)"
WORKTREE="$ROOT/worktrees/$TOOL_NAME"

if [[ -z "$TOOL_NAME" ]]; then
  echo "usage: $0 <tool_name>"
  exit 2
fi

if [[ ! -d "$WORKTREE" ]]; then
  echo "worktree not found: $WORKTREE"
  exit 2
fi

echo "== codex_auto_fix: $TOOL_NAME =="
cd "$WORKTREE"

if command -v ruff >/dev/null 2>&1; then
  echo "[1/4] ruff --fix"
  ruff check --fix . || true
else
  echo "[warn] ruff not found"
fi

if command -v black >/dev/null 2>&1; then
  echo "[2/4] black"
  black . || true
else
  echo "[warn] black not found"
fi

echo "[3/4] domain overlap check (changed files only)"
FILES="$(git diff --name-only main || true)"
if [[ -n "$FILES" ]]; then
  PY="$CORE/.build_venv/bin/python"
  if [[ ! -x "$PY" ]]; then
    PY="$(command -v python3 || command -v python)"
  fi
  "$PY" "$CORE/scripts/dev/check_domain_overlap.py" \
    --reiter "$TOOL_NAME" \
    --files $FILES \
    --json || true
else
  echo '{"status":"OK","note":"no local diff vs main"}'
fi

echo "[4/4] git status"
git status --short
