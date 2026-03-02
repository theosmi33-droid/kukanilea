#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea/kukanilea_production"
MODEL="${GEMINI_FALLBACK_MODEL:-gemini-3-flash-preview}"

cd "$ROOT"
exec gemini -m "$MODEL" "$@"
