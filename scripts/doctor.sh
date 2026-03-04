#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.build_venv"
FAILURES=0

pass() {
  printf 'PASS %s\n' "$1"
}

fail() {
  printf 'FAIL %s\n' "$1"
  FAILURES=$((FAILURES + 1))
}

check_command() {
  local cmd="$1"
  local label="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$label ($(command -v "$cmd"))"
  else
    fail "$label (missing command: $cmd)"
  fi
}

check_command python3 "python3"
check_command pip "pip"
check_command sqlite3 "sqlite3"
check_command rg "ripgrep"
check_command gh "GitHub CLI"

if [[ -d "$VENV_DIR" && -x "$VENV_DIR/bin/python" ]]; then
  pass ".build_venv ($VENV_DIR)"
else
  fail ".build_venv (missing; run ./scripts/bootstrap.sh)"
fi

if command -v playwright >/dev/null 2>&1; then
  pass "playwright CLI ($(command -v playwright))"
elif [[ -x "$VENV_DIR/bin/python" ]] && "$VENV_DIR/bin/python" -m playwright --version >/dev/null 2>&1; then
  pass "playwright module (via .build_venv/bin/python -m playwright)"
else
  fail "playwright (missing CLI/module)"
fi

if [[ "$FAILURES" -gt 0 ]]; then
  echo
  echo "Doctor result: FAIL ($FAILURES check(s) failed)"
  exit 1
fi

echo
echo "Doctor result: PASS"
