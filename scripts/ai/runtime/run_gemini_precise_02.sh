#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
bash "$ROOT/scripts/ai/runtime/run_gemini_precise.sh" \
  "precise_02_contract_harmony" \
  "$ROOT/docs/ai/prompts/precise/02_contract_harmony.md"

