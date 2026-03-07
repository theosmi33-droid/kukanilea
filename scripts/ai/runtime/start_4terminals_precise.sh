#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
MODEL="${GEMINI_MODEL:-gemini-3-flash-preview}"
EXTS="${GEMINI_PRECISE_EXTENSIONS:-github}"
TIMEOUT="${GEMINI_TIMEOUT_SECONDS:-420}"

if [[ ! "$TIMEOUT" =~ ^[0-9]+$ ]]; then
  echo "[error] GEMINI_TIMEOUT_SECONDS must be numeric." >&2
  exit 2
fi

launch_terminal_command() {
  local cmd="$1"
  osascript - "$cmd" <<'APPLESCRIPT'
on run argv
  set commandText to item 1 of argv
  tell application "Terminal"
    activate
    do script commandText
  end tell
end run
APPLESCRIPT
}

build_command() {
  local delay="$1"
  local runner="$2"
  local prefix=""
  if [[ "$delay" -gt 0 ]]; then
    prefix="sleep $delay; "
  fi
  printf 'clear; %sexport GEMINI_MODEL=%q; export GEMINI_PRECISE_EXTENSIONS=%q; export GEMINI_TIMEOUT_SECONDS=%q; bash %q' \
    "$prefix" "$MODEL" "$EXTS" "$TIMEOUT" "$runner"
}

launch_terminal_command "$(build_command 0 "$ROOT/scripts/ai/runtime/run_gemini_precise_01.sh")"
launch_terminal_command "$(build_command 12 "$ROOT/scripts/ai/runtime/run_gemini_precise_02.sh")"
launch_terminal_command "$(build_command 24 "$ROOT/scripts/ai/runtime/run_gemini_precise_03.sh")"
launch_terminal_command "$(build_command 36 "$ROOT/scripts/ai/runtime/run_gemini_precise_04.sh")"

echo "Started 4 precise Gemini terminals."
