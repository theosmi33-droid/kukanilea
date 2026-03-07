#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
bash "$ROOT/scripts/ai/runtime/run_gemini_precise.sh" \
  "precise_01_main_health_fix" \
  "$ROOT/docs/ai/prompts/precise/01_main_health_fix.md"

