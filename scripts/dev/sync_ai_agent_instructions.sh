#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
CONTRACT="$CORE/docs/ai/AI_AGENT_OPERATING_CONTRACT.md"
REFSTACK="$CORE/docs/ai/GEMINI_REFERENCE_STACK.md"
GLOBAL_GEMINI="$HOME/.gemini/GEMINI.md"

DOMAINS=(
  dashboard
  upload
  emailpostfach
  messenger
  kalender
  aufgaben
  zeiterfassung
  projekte
  excel-docs-visualizer
  einstellungen
  floating-widget-chatbot
)

SYNC_WORKTREES="0"
if [[ "${1:-}" == "--all-worktrees" ]]; then
  SYNC_WORKTREES="1"
fi

if [[ ! -f "$CONTRACT" ]]; then
  echo "Missing contract: $CONTRACT" >&2
  exit 1
fi

if [[ ! -f "$REFSTACK" ]]; then
  echo "Missing reference stack: $REFSTACK" >&2
  exit 1
fi

apply_workspace_files() {
  local ws="$1"
  mkdir -p "$ws/.github"

  cat > "$ws/GEMINI.md" <<EOF
# KUKANILEA Gemini Workspace Instructions

Read and follow these files before any implementation:

1. $CONTRACT
2. $REFSTACK
3. $ws/app/agents/config/AGENTS.md

Rules:
- Keep changes scoped to this workspace/domain.
- No destructive git operations.
- Run healthcheck/tests and report PASS/FAIL with evidence.
EOF

  cat > "$ws/.github/copilot-instructions.md" <<EOF
# KUKANILEA Copilot Workspace Instructions

Use this context first:
- $CONTRACT
- $REFSTACK
- $ws/app/agents/config/AGENTS.md

Constraints:
- No CDN in product templates.
- White-mode only in Sovereign-11 scope.
- Respect ownership and overlap boundaries.
- Do not use force push or destructive git commands.
EOF
}

echo "Syncing core workspace instructions..."
apply_workspace_files "$CORE"

if [[ "$SYNC_WORKTREES" == "1" ]]; then
  echo "Syncing 11 domain worktrees..."
  for d in "${DOMAINS[@]}"; do
    ws="$ROOT/worktrees/$d"
    if [[ -d "$ws" ]]; then
      apply_workspace_files "$ws"
      echo "  - synced: $ws"
    else
      echo "  - skipped (missing): $ws"
    fi
  done
else
  echo "Skipping worktree file writes (use --all-worktrees to enable)."
fi

mkdir -p "$(dirname "$GLOBAL_GEMINI")"
cat > "$GLOBAL_GEMINI" <<EOF
## Gemini Added Memories
- Always load and follow:
  - $CONTRACT
  - $REFSTACK
- Prioritize KUKANILEA rules: local-first, zero-CDN, white-mode-only, ownership boundaries, evidence-based reports.
- On blocker: stop, report root cause and exact failing command.
EOF

echo "Updated global Gemini memory file: $GLOBAL_GEMINI"
echo "Done."
