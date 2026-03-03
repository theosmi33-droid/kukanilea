#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/gensuminguyen/Kukanilea/kukanilea_production"
MISSION="$ROOT/docs/ai/GEMINI_MISSION_BRIEF.md"
PROMPT="$ROOT/docs/ai/prompts/live/03_github_ci_triage.md"
OUT="$ROOT/docs/reviews/gemini/live/03_github_ci_triage_$(date +%Y%m%d_%H%M%S).md"
cd "$ROOT"
# Ensure GitHub MCP gets a clean PAT value (no "Bearer " prefix in env).
if [[ -z "${GITHUB_MCP_PAT:-}" ]]; then
  GITHUB_MCP_PAT="$(gh auth token 2>/dev/null || true)"
fi
GITHUB_MCP_PAT="${GITHUB_MCP_PAT#Bearer }"
export GITHUB_MCP_PAT
echo "[START] $(date -Iseconds)" | tee "$OUT"
set +e
gemini -m gemini-2.5-pro --approval-mode yolo --include-directories /Users/gensuminguyen/Kukanilea/worktrees --output-format text -p "$(cat "$MISSION")"$'\n\n'"$(cat "$PROMPT")" 2>&1 | tee -a "$OUT"
rc=${PIPESTATUS[0]}
set -e
if [[ $rc -ne 0 ]]; then
  echo "[ERROR] gemini_exit=$rc" | tee -a "$OUT"
  if rg -q "TerminalQuotaError|exhausted your capacity|quota" "$OUT"; then
    echo "[BLOCKED] quota_exhausted" | tee -a "$OUT"
  fi
fi
echo "[DONE] $(date -Iseconds)" | tee -a "$OUT"
