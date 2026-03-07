#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
MODEL="${GEMINI_MODEL:-gemini-3-flash-preview}"
EXTS="${GEMINI_PRECISE_EXTENSIONS:-github}"
TIMEOUT="${GEMINI_TIMEOUT_SECONDS:-420}"

osascript <<APPLESCRIPT
tell application "Terminal"
  activate
  do script "clear; export GEMINI_MODEL='$MODEL'; export GEMINI_PRECISE_EXTENSIONS='$EXTS'; export GEMINI_TIMEOUT_SECONDS='$TIMEOUT'; bash \"$ROOT/scripts/ai/runtime/run_gemini_precise_01.sh\""
  do script "clear; sleep 12; export GEMINI_MODEL='$MODEL'; export GEMINI_PRECISE_EXTENSIONS='$EXTS'; export GEMINI_TIMEOUT_SECONDS='$TIMEOUT'; bash \"$ROOT/scripts/ai/runtime/run_gemini_precise_02.sh\""
  do script "clear; sleep 24; export GEMINI_MODEL='$MODEL'; export GEMINI_PRECISE_EXTENSIONS='$EXTS'; export GEMINI_TIMEOUT_SECONDS='$TIMEOUT'; bash \"$ROOT/scripts/ai/runtime/run_gemini_precise_03.sh\""
  do script "clear; sleep 36; export GEMINI_MODEL='$MODEL'; export GEMINI_PRECISE_EXTENSIONS='$EXTS'; export GEMINI_TIMEOUT_SECONDS='$TIMEOUT'; bash \"$ROOT/scripts/ai/runtime/run_gemini_precise_04.sh\""
end tell
APPLESCRIPT

echo "Started 4 precise Gemini terminals."
