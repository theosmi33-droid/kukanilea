#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PY="${PYTHON_BIN:-python3}"
MODEL="${GEMINI_MODEL:-gemini-3-flash-preview}"
APPROVAL_MODE="${GEMINI_APPROVAL_MODE:-default}"
TIMEOUT_SECONDS="${GEMINI_TIMEOUT_SECONDS:-420}"
EXTENSIONS="${GEMINI_PRECISE_EXTENSIONS:-github}"
LABEL="${1:?label required}"
PROMPT_FILE="${2:?prompt file required}"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "[error] prompt file missing: $PROMPT_FILE" >&2
  exit 2
fi

cd "$ROOT"

TS="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$ROOT/docs/reviews/gemini/live"
OUT_FILE="$OUT_DIR/${LABEL}_${TS}.md"
LOG_FILE="$OUT_DIR/${LABEL}_${TS}.log"
mkdir -p "$OUT_DIR"

{
  echo "[START] $(date -Iseconds)"
  echo "[ROOT] $ROOT"
  echo "[LABEL] $LABEL"
  echo "[PROMPT] $PROMPT_FILE"
  echo "[MODEL] $MODEL"
  echo "[APPROVAL_MODE] $APPROVAL_MODE"
  echo "[TIMEOUT_SECONDS] $TIMEOUT_SECONDS"
  echo "[EXTENSIONS] $EXTENSIONS"
} | tee "$OUT_FILE"

extension_flags=()
IFS=',' read -r -a ext_arr <<< "$EXTENSIONS"
for ext in "${ext_arr[@]}"; do
  clean="$(echo "$ext" | xargs)"
  [[ -z "$clean" ]] && continue
  extension_flags+=(--extension "$clean")
done

set +e
"$PY" "$ROOT/scripts/ai/gemini_cli.py" \
  --cwd "$ROOT" \
  --require-main \
  --skip-alignment \
  --approval-mode "$APPROVAL_MODE" \
  --model "$MODEL" \
  "${extension_flags[@]}" \
  --context-file "$ROOT/AGENTS.md" \
  --prompt-file "$PROMPT_FILE" \
  --output "$OUT_FILE" \
  --log "$LOG_FILE" \
  --timeout-seconds "$TIMEOUT_SECONDS"
rc=$?
set -e

if [[ $rc -ne 0 ]]; then
  echo "[ERROR] gemini_exit=$rc" | tee -a "$OUT_FILE"
  exit $rc
fi

echo "[DONE] $(date -Iseconds)" >> "$OUT_FILE"
echo "[OK] output=$OUT_FILE"
