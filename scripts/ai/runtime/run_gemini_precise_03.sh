#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
bash "$ROOT/scripts/ai/runtime/run_gemini_precise.sh" \
  "precise_03_security_confirm_audit" \
  "$ROOT/docs/ai/prompts/precise/03_security_confirm_audit.md"

