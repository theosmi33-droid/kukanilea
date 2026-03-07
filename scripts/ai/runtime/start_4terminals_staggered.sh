#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

cd "$ROOT"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "[error] main-only policy active: current branch is '$CURRENT_BRANCH' (expected 'main')." >&2
  exit 2
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "[error] working tree has local changes. commit/stash first for clean launcher execution." >&2
  exit 2
fi

bash "$ROOT/scripts/ai/runtime/start_4terminals_precise.sh"
