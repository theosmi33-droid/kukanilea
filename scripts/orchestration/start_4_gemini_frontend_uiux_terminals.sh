#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
PROMPTS="$CORE/docs/ai/prompts/live/frontend_uiux"
RUN_DIR="$CORE/docs/reviews/gemini/live"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUNBOOK="$RUN_DIR/RUNBOOK_4_GEMINI_FRONTEND_UIUX_${STAMP}.md"

MODE="${1:-safe}"

need_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: missing required command '$cmd'"
    exit 2
  fi
}

need_cmd osascript
if command -v Gemini >/dev/null 2>&1; then
  GEMINI_CMD="Gemini"
elif command -v gemini >/dev/null 2>&1; then
  GEMINI_CMD="gemini"
else
  echo "error: missing required command 'Gemini' or 'gemini'"
  exit 2
fi

mkdir -p "$RUN_DIR"

count_gemini() {
  (pgrep -if '(^|[ /])gemini([ ]|$)' || true) | wc -l | tr -d ' '
}

open_terminal() {
  local worker="$1"
  local prompt="$2"
  local cmd
  cmd="cd '$ROOT' && clear && printf '[KUKANILEA-GEMINI-FRONTEND] ${worker}\nPrompt: ${prompt}\n\n1) Gemini startet.\n2) Prompt-Datei komplett einfuegen.\n3) Nur Owned Scope bearbeiten (no overlap).\n4) Report unter docs/reviews/gemini/live ablegen.\n\n' && ${GEMINI_CMD}"

  osascript <<OSA
tell application "Terminal"
  activate
  do script "$cmd"
end tell
OSA
}

if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then
  cat <<'USAGE'
Usage: scripts/orchestration/start_4_gemini_frontend_uiux_terminals.sh [mode]

Modes:
  safe      Default. Abort if gemini already running.
  restart   Kill existing gemini processes, then open exactly 4 frontend/UIUX sessions.
  topup     Open missing sessions up to 4 without killing existing ones.
USAGE
  exit 0
fi

running_before="$(count_gemini)"

case "$MODE" in
  safe)
    if [[ "$running_before" -gt 0 ]]; then
      echo "abort: found $running_before running gemini process(es)."
      echo "use mode 'restart' for clean 4-session setup, or 'topup' to fill up to 4."
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

cat > "$RUNBOOK" <<EOF_RB
# KUKANILEA 4-Gemini Frontend/UIUX Runbook (${STAMP})

- Root: ${ROOT}
- Mode: ${MODE}
- Running Gemini before: ${running_before}
- Running Gemini now: ${running_now}
- Terminals opened by script: ${to_open}

## Worker prompts (strict no-overlap)

1. Worker 1: Shell & Navigation
   - ${PROMPTS}/17_worker_frontend_shell_navigation.md
2. Worker 2: Visual System & Components
   - ${PROMPTS}/18_worker_frontend_visual_system.md
3. Worker 3: Interaction & Motion
   - ${PROMPTS}/19_worker_frontend_interaction_motion.md
4. Worker 4: QA, Accessibility, Responsive
   - ${PROMPTS}/20_worker_frontend_qa_accessibility.md

## Overlap policy
- Jeder Worker darf nur den Owned Scope seiner Prompt-Datei aendern.
- Keine Datei darf in zwei Workern parallel bearbeitet werden.
- Shared-Core nur als Scope-Request, nicht direkt in Worker-Sessions.

## Report target
- Write reports under: ${RUN_DIR}
EOF_RB

if [[ "$to_open" -eq 0 ]]; then
  echo "no new terminals opened (already >= 4 gemini sessions)."
  echo "runbook: $RUNBOOK"
  exit 0
fi

if [[ "$to_open" -ge 1 ]]; then
  open_terminal "Worker 1 (Shell & Navigation)" "$PROMPTS/17_worker_frontend_shell_navigation.md"
  sleep 0.4
fi
if [[ "$to_open" -ge 2 ]]; then
  open_terminal "Worker 2 (Visual System & Components)" "$PROMPTS/18_worker_frontend_visual_system.md"
  sleep 0.4
fi
if [[ "$to_open" -ge 3 ]]; then
  open_terminal "Worker 3 (Interaction & Motion)" "$PROMPTS/19_worker_frontend_interaction_motion.md"
  sleep 0.4
fi
if [[ "$to_open" -ge 4 ]]; then
  open_terminal "Worker 4 (QA, Accessibility, Responsive)" "$PROMPTS/20_worker_frontend_qa_accessibility.md"
fi

echo "opened $to_open terminal(s)."
echo "runbook: $RUNBOOK"
echo "next: copy/paste prompt content from the listed files into each gemini session."
