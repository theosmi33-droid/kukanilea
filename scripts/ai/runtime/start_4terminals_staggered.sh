#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
bash "$ROOT/scripts/ai/runtime/start_4terminals_precise.sh"
