#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Resolution policy (highest priority first):
# 1. explicit PYTHON env var
# 2. project virtualenv
# 3. pyenv local interpreter (if configured)
# 4. system python3/python
if [[ -n "${PYTHON:-}" ]]; then
  if command -v "$PYTHON" >/dev/null 2>&1; then
    command -v "$PYTHON"
    exit 0
  fi
  if [[ -x "$PYTHON" ]]; then
    printf '%s\n' "$PYTHON"
    exit 0
  fi
  echo "[resolve-python] PYTHON is set but not executable: $PYTHON" >&2
  exit 3
fi

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  printf '%s\n' "$ROOT/.venv/bin/python"
  exit 0
fi

if command -v pyenv >/dev/null 2>&1; then
  if PYENV_VERSION="$(pyenv version-name 2>/dev/null || true)" && [[ -n "$PYENV_VERSION" ]]; then
    PYENV_PYTHON="$(pyenv which python 2>/dev/null || true)"
    if [[ -n "$PYENV_PYTHON" && -x "$PYENV_PYTHON" ]]; then
      printf '%s\n' "$PYENV_PYTHON"
      exit 0
    fi
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  command -v python3
  exit 0
fi

if command -v python >/dev/null 2>&1; then
  command -v python
  exit 0
fi

echo "[resolve-python] No usable Python interpreter found (PYTHON/.venv/pyenv/python3/python)." >&2
exit 3
