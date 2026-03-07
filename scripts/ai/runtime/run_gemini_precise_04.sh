#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
bash "$ROOT/scripts/ai/runtime/run_gemini_precise.sh" \
  "precise_04_ci_failure_tactical" \
  "$ROOT/docs/ai/prompts/precise/04_ci_failure_tactical.md"

