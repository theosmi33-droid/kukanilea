#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/gensuminguyen/Kukanilea/kukanilea_production"
PROMPT="$ROOT/docs/ai/prompts/04_pr_watch_and_debug_plan_bounded.md"
OUT="$ROOT/docs/reviews/gemini/04_pr_watch_and_debug_plan_$(date +%Y%m%d_%H%M%S)_bounded.md"
cd "$ROOT"
echo "[START] $(date -Iseconds)" | tee "$OUT"
gemini -m gemini-3-flash-preview --approval-mode yolo --output-format text -p "$(cat "$PROMPT")" | tee -a "$OUT"
echo "[DONE] $(date -Iseconds)" | tee -a "$OUT"
