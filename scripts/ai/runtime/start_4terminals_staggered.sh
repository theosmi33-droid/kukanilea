#!/usr/bin/env bash
set -euo pipefail

# Starts 4 Gemini jobs in Terminal with staggered delays to avoid quota thrashing.
osascript <<'APPLESCRIPT'
tell application "Terminal"
  activate
  do script "clear; bash /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/ai/runtime/run_gemini_live_01.sh"
  do script "clear; sleep 20; bash /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/ai/runtime/run_gemini_live_02.sh"
  do script "clear; sleep 40; bash /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/ai/runtime/run_gemini_live_03.sh"
  do script "clear; sleep 60; bash /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/ai/runtime/run_gemini_live_04.sh"
end tell
APPLESCRIPT

echo "Started 4 terminal jobs (staggered)."
