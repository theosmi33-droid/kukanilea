#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
START_SCRIPT="$ROOT/kukanilea_production/scripts/orchestration/start_vscode_multiroot_fleet.sh"

echo "[restart] Closing VS Code (graceful)..."
osascript -e 'tell application "Visual Studio Code" to quit' >/dev/null 2>&1 || true
sleep 2

echo "[restart] Killing remaining VS Code processes..."
pkill -f '/Applications/Visual Studio Code.app/Contents/MacOS/Electron' || true
pkill -f 'Visual Studio Code.app/Contents/Frameworks/Code Helper' || true
sleep 2

echo "[restart] Starting 4-window fleet..."
bash "$START_SCRIPT"
sleep 3

echo "[restart] Current VS Code Electron processes:"
pgrep -fl '/Applications/Visual Studio Code.app/Contents/MacOS/Electron' || true

echo "[restart] Done."
