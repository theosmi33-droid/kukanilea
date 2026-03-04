#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
PROMPTS="$CORE/docs/ai/prompts/live"
RUN_DIR="$CORE/docs/reviews/gemini/live"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUNBOOK="$RUN_DIR/RUNBOOK_4_GEMINI_${STAMP}.md"

MODE="${1:-safe}"

need_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: missing required command '$cmd'"
    exit 2
  fi
}

need_cmd osascript
need_cmd gemini

mkdir -p "$RUN_DIR"

count_gemini() {
  pgrep -if '(^|[ /])gemini([ ]|$)' | wc -l | tr -d ' '
}

open_terminal() {
  local worker="$1"
  local prompt="$2"
  local cmd
  cmd="cd '$ROOT' && clear && printf '[KUKANILEA-GEMINI] ${worker}\nPrompt: ${prompt}\n\n1) GEMINI ist gestartet.\n2) Prompt-Datei oeffnen und vollstaendig einfuegen.\n3) Abschlussbericht nach docs/reviews/gemini/live schreiben.\n\n' && gemini"

  osascript <<OSA
tell application "Terminal"
  activate
  do script "$cmd"
end tell
OSA
}

if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then
  cat <<'USAGE'
Usage: scripts/orchestration/start_4_gemini_terminals.sh [mode]

Modes:
  safe      Default. If gemini processes exist, abort to avoid opening too many windows.
  restart   Kill existing gemini processes, then open exactly 4 terminals.
  topup     Open only if currently fewer than 4 gemini processes; does not kill running sessions.
USAGE
  exit 0
fi

running_before="$(count_gemini)"

case "$MODE" in
  safe)
    if [[ "$running_before" -gt 0 ]]; then
      echo "abort: found $running_before running gemini process(es)."
      echo "use mode 'restart' for clean 4-term setup, or 'topup' to fill up to 4."
      exit 1
    fi
    ;;
  restart)
    pkill -if '(^|[ /])gemini([ ]|$)' || true
    sleep 1
    ;;
  topup)
    ;;
  *)
    echo "unknown mode: $MODE"
    echo "use --help for usage"
    exit 2
    ;;
esac

running_now="$(count_gemini)"
to_open=4
if [[ "$MODE" == "topup" ]]; then
  if [[ "$running_now" -ge 4 ]]; then
    to_open=0
  else
    to_open=$((4 - running_now))
  fi
fi

cat > "$RUNBOOK" <<EOF
# KUKANILEA 4-Gemini Runbook (${STAMP})

- Root: ${ROOT}
- Mode: ${MODE}
- Running Gemini before: ${running_before}
- Running Gemini now: ${running_now}
- Terminals opened by script: ${to_open}

## Worker prompts

1. Core Fleet Commander
   - ${PROMPTS}/13_core_fleet_11tabs.md
2. Worker A (Dashboard/Upload/Visualizer)
   - ${PROMPTS}/14_workerA_dashboard_upload_visualizer.md
3. Worker B (Messenger/Email/Chatbot)
   - ${PROMPTS}/15_workerB_messenger_email_chatbot.md
4. Worker C (Kalender/Aufgaben/Zeiterfassung/Projekte/Einstellungen)
   - ${PROMPTS}/16_workerC_kalender_tasks_time_projects_settings.md

## Report target

- Write reports under: ${RUN_DIR}
EOF

if [[ "$to_open" -eq 0 ]]; then
  echo "no new terminals opened (already >= 4 gemini sessions)."
  echo "runbook: $RUNBOOK"
  exit 0
fi

# Always open in deterministic order.
if [[ "$to_open" -ge 1 ]]; then
  open_terminal "Core Fleet Commander" "$PROMPTS/13_core_fleet_11tabs.md"
  sleep 0.4
fi
if [[ "$to_open" -ge 2 ]]; then
  open_terminal "Worker A" "$PROMPTS/14_workerA_dashboard_upload_visualizer.md"
  sleep 0.4
fi
if [[ "$to_open" -ge 3 ]]; then
  open_terminal "Worker B" "$PROMPTS/15_workerB_messenger_email_chatbot.md"
  sleep 0.4
fi
if [[ "$to_open" -ge 4 ]]; then
  open_terminal "Worker C" "$PROMPTS/16_workerC_kalender_tasks_time_projects_settings.md"
fi

echo "opened $to_open terminal(s)."
echo "runbook: $RUNBOOK"
echo "next: copy/paste prompt content from the files listed above into each gemini session."
