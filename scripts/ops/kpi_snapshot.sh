#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="$ROOT/docs/status"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$OUT_DIR/KPI_SNAPSHOT_${STAMP}.md"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTEST_CMD="${PYTEST_CMD:-pytest}"

mkdir -p "$OUT_DIR"

measure_seconds() {
  local cmd="$1"
  local tmp
  tmp="$(mktemp)"
  local start end duration rc
  start="$(date +%s)"
  if bash -lc "cd '$ROOT' && $cmd" >"$tmp" 2>&1; then
    rc=0
  else
    rc=$?
  fi
  end="$(date +%s)"
  duration=$((end - start))
  printf '%s|%s|%s\n' "$duration" "$rc" "$tmp"
}

write_section() {
  local title="$1"
  local command="$2"
  local result="$3"
  local sec rc out
  sec="${result%%|*}"
  result="${result#*|}"
  rc="${result%%|*}"
  out="${result#*|}"

  {
    echo "## ${title}"
    echo "- command: ${command}"
    echo "- duration_seconds: ${sec}"
    echo "- exit_code: ${rc}"
    echo '```text'
    sed -n '1,120p' "$out"
    echo '```'
    echo
  } >> "$OUT_FILE"

  rm -f "$out"
}

startup="$(measure_seconds "$PYTHON_BIN -c \"from app import create_app; app=create_app(); print('ok', bool(app))\"")"
unit_tests="$(measure_seconds "$PYTEST_CMD -q tests/security")"
e2e_subset="$(measure_seconds "$PYTEST_CMD -q tests/e2e --maxfail=1")"

{
  echo "# KPI Snapshot"
  echo "- timestamp: $(date -Iseconds)"
  echo "- repo_root: $ROOT"
  echo "- format_version: 1"
  echo
} > "$OUT_FILE"

write_section "Startup timing" "$PYTHON_BIN -c 'create_app smoke'" "$startup"
write_section "Security tests timing" "$PYTEST_CMD -q tests/security" "$unit_tests"
write_section "E2E suite timing" "$PYTEST_CMD -q tests/e2e --maxfail=1" "$e2e_subset"

echo "$OUT_FILE"
