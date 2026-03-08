#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
source "$ROOT/scripts/ai/runtime/lib_main_only.sh"
main_only_preflight "$ROOT"

bash "$ROOT/scripts/ai/runtime/start_4terminals_precise.sh"
