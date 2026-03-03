#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$ROOT/.build_venv/bin/python"

MODE="check"
INSTALL_HOOKS="0"

for arg in "$@"; do
  case "$arg" in
    --apply) MODE="apply" ;;
    --check) MODE="check" ;;
    --install-hooks) INSTALL_HOOKS="1" ;;
    *)
      echo "unknown argument: $arg"
      exit 2
      ;;
  esac
done

if [[ ! -x "$PY" ]]; then
  echo "missing interpreter: $PY"
  exit 2
fi

if [[ "$MODE" == "apply" ]]; then
  "$PY" "$ROOT/scripts/dev/enforce_vscode_configs.py" --apply
else
  "$PY" "$ROOT/scripts/dev/enforce_vscode_configs.py" --check
fi

if [[ "$INSTALL_HOOKS" == "1" ]]; then
  bash "$ROOT/scripts/dev/install_git_hooks.sh"
fi

