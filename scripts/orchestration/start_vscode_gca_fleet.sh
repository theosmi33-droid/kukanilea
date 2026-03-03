#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
WORKTREES="$ROOT/worktrees"
PROMPTS="$CORE/docs/ai/prompts/live"
FLEET_DIR="$ROOT/.vscode-fleet"

command -v code >/dev/null 2>&1 || {
  echo "error: VS Code CLI 'code' not found in PATH"
  exit 2
}

mkdir -p "$FLEET_DIR"

make_workspace() {
  local name="$1"
  local folder="$2"
  local ws="$FLEET_DIR/${name}.code-workspace"

  cat >"$ws" <<JSON
{
  "folders": [
    { "path": "$folder" }
  ],
  "settings": {
    "python.defaultInterpreterPath": "$CORE/.build_venv/bin/python",
    "python.useEnvironmentsExtension": true,
    "task.allowAutomaticTasks": "on",
    "git.autoRepositoryDetection": "openEditors",
    "git.openRepositoryInParentFolders": "never",
    "git.untrackedChanges": "hidden",
    "git.repositoryScanMaxDepth": 2,
    "files.watcherExclude": {
      "**/.git/objects/**": true,
      "**/.git/subtree-cache/**": true,
      "**/.build_venv/**": true,
      "**/__pycache__/**": true
    }
  }
}
JSON

  echo "$ws"
}

CORE_WS="$(make_workspace "core-integrator" "$CORE")"
DASH_WS="$(make_workspace "dashboard-worker" "$WORKTREES/dashboard")"
MSG_WS="$(make_workspace "messenger-worker" "$WORKTREES/messenger")"
SET_WS="$(make_workspace "einstellungen-worker" "$WORKTREES/einstellungen")"

echo "[1/4] Opening core window..."
code --new-window "$CORE_WS" "$PROMPTS/12_next_wave_integrator.md"
sleep 0.5

echo "[2/4] Opening dashboard window..."
code --new-window "$DASH_WS" "$PROMPTS/09_dashboard_domain_review.md"
sleep 0.5

echo "[3/4] Opening messenger window..."
code --new-window "$MSG_WS" "$PROMPTS/10_messenger_domain_review.md"
sleep 0.5

echo "[4/4] Opening einstellungen window..."
code --new-window "$SET_WS" "$PROMPTS/11_einstellungen_domain_review.md"

echo
echo "VS Code GCA fleet started."
echo "Workspaces:"
echo "  - $CORE_WS"
echo "  - $DASH_WS"
echo "  - $MSG_WS"
echo "  - $SET_WS"
echo
echo "Tip: In each window, open Gemini Code Assist chat and run the opened prompt file."
