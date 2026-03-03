#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

DESIRED=".githooks"
CURRENT="$(git config --get core.hooksPath || true)"

if [[ "${1:-}" == "--check" ]]; then
  if [[ "$CURRENT" == "$DESIRED" ]]; then
    echo "git-hooks: OK ($DESIRED)"
    exit 0
  fi
  echo "git-hooks: MISSING (expected core.hooksPath=$DESIRED, got=${CURRENT:-<unset>})"
  exit 1
fi

git config core.hooksPath "$DESIRED"
chmod +x "$ROOT/.githooks/pre-commit"
echo "git-hooks: installed ($DESIRED)"
