#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/gensuminguyen/Kukanilea/kukanilea_production"
PROMPT="$ROOT/docs/ai/prompts/02_actions_triage_bounded.md"
OUT="$ROOT/docs/reviews/gemini/02_actions_triage_$(date +%Y%m%d_%H%M%S)_bounded.md"
cd "$ROOT"
echo "[START] $(date -Iseconds)" | tee "$OUT"
gemini -m gemini-3-flash-preview --approval-mode yolo --output-format text -p "$(cat "$PROMPT")" | tee -a "$OUT"
echo "[DONE] $(date -Iseconds)" | tee -a "$OUT"
