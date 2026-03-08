#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
source "$ROOT/scripts/ai/runtime/lib_main_only.sh"
cd "$ROOT"

echo "[preflight] repo=$ROOT"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "[preflight] branch=$CURRENT_BRANCH"

if ! main_only_preflight "$ROOT"; then
  exit 2
fi

MODEL="${GEMINI_MODEL:-gemini-3-flash-preview}"

PROMPT_FILE="$(mktemp)"
cat > "$PROMPT_FILE" <<'EOF'
Du arbeitest ausschließlich im Produkt KUKANILEA.

HARTE REGELN:
1) Arbeite nur auf Branch `main`.
2) Erstelle keine neuen Branches.
3) Baue nichts unnötig neu: erweitere nur bestehende Komponenten.
4) Kein Rewrite, kein Big-Bang-Refactor.
5) Erst Root-Cause, dann kleinster sicherer Patch.
6) Bei jeder Aufgabe nur enger Dateiscope.
7) Keine destruktiven Git-Operationen.

ARBEITSMODUS:
- Standard: Fix/Harden/Integrate (ein Modus pro Aufgabe).
- Fokus auf vorhandene Flows, Contracts, Guardrails, Healthchecks.
- Immer kurz berichten: Analyse, Änderung, Validierung, Restrisiko.
EOF

trap 'rm -f "$PROMPT_FILE"' EXIT

echo "[start] launching Gemini interactive (main-only guidance)"
exec gemini \
  --approval-mode default \
  --model "$MODEL" \
  --extensions github \
  --extensions code-review \
  --prompt-interactive "$(cat "$PROMPT_FILE")"
