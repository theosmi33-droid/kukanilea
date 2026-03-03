#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
FLEET="$ROOT/.vscode-fleet"
PROMPTS="$ROOT/kukanilea_production/docs/ai/prompts/live"

command -v code >/dev/null 2>&1 || {
  echo "error: VS Code CLI 'code' not found"
  exit 2
}

code --new-window "$FLEET/core-commander.code-workspace" "$PROMPTS/13_core_fleet_11tabs.md"
sleep 0.5
code --new-window "$FLEET/worker-a.code-workspace" "$PROMPTS/14_workerA_dashboard_upload_visualizer.md"
sleep 0.5
code --new-window "$FLEET/worker-b.code-workspace" "$PROMPTS/15_workerB_messenger_email_chatbot.md"
sleep 0.5
code --new-window "$FLEET/worker-c.code-workspace" "$PROMPTS/16_workerC_kalender_tasks_time_projects_settings.md"

echo "Opened 4 multi-root VS Code fleet windows."
