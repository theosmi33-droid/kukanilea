#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea/kukanilea_production"
cd "$ROOT"

run_step() {
  local step="$1"
  echo "=== RUN $step ==="
  bash "$ROOT/scripts/ai/runtime/run_gemini_live_${step}.sh"
}

# Sequential execution avoids quota thrashing from parallel sessions.
run_step 01
run_step 02
run_step 03
run_step 04

echo "ALL_DONE $(date -Iseconds)"
