#!/usr/bin/env bash
set -euo pipefail

REPO_SLUG="${RELEASE_REPO_SLUG:-theosmi33-droid/kukanilea}"
PROD_REPO_PATH="${PROD_REPO_PATH:-/Users/gensuminguyen/Kukanilea/kukanilea_production}"
LANE="${LANE:-dev-ci}"
PR_NUMBER="${PR_NUMBER:-TBD}"
SCOPE_IN="${SCOPE_IN:-CI guardrails, lane discipline, preflight automation}"
SCOPE_OUT="${SCOPE_OUT:-runtime, ui, security policy changes}"

run_step() {
  local label="$1"
  shift
  echo ""
  echo "--- ${label}"
  if "$@"; then
    echo "[ok] ${label}"
    return 0
  fi
  echo "[warn] ${label} failed"
  return 1
}

run_cmd() {
  local arg
  printf '$'
  for arg in "$@"; do
    printf ' %q' "$arg"
  done
  printf '\n'
  "$@"
}

GH_STATUS="ok"
RUN_STATUS="ok"
PROD_STATUS="ok"

if command -v gh >/dev/null 2>&1; then
  run_step "Open PRs" run_cmd gh pr list --repo "${REPO_SLUG}" --state open --limit 100 || GH_STATUS="warn"
  run_step "Main branch workflows" run_cmd gh run list --repo "${REPO_SLUG}" --branch main --limit 20 || RUN_STATUS="warn"
else
  GH_STATUS="warn"
  RUN_STATUS="warn"
  echo ""
  echo "--- GitHub CLI checks"
  echo "[warn] gh not installed; skipped:"
  echo "  - gh pr list --repo ${REPO_SLUG} --state open --limit 100"
  echo "  - gh run list --repo ${REPO_SLUG} --branch main --limit 20"
fi

if [[ -d "${PROD_REPO_PATH}" ]]; then
  run_step "Production clone status" run_cmd git -C "${PROD_REPO_PATH}" status --short || PROD_STATUS="warn"
else
  PROD_STATUS="warn"
  echo ""
  echo "--- Production clone status"
  echo "[warn] missing path: ${PROD_REPO_PATH}"
  echo "[warn] skipped: git -C '${PROD_REPO_PATH}' status --short"
fi

GUARD_RESULT="NOT_RUN"
TEST_RESULT="NOT_RUN"

if bash scripts/dev/pr_quality_guard.sh --ci; then
  GUARD_RESULT="PASS"
else
  GUARD_RESULT="FAIL"
fi

if [[ "${RUN_PREFLIGHT_TESTS:-0}" == "1" ]]; then
  if command -v pytest >/dev/null 2>&1; then
    if pytest -q tests/test_release_conductor_preflight.py; then
      TEST_RESULT="PASS"
    else
      TEST_RESULT="FAIL"
    fi
  else
    TEST_RESULT="WARN (pytest missing)"
  fi
else
  TEST_RESULT="NOT_RUN (set RUN_PREFLIGHT_TESTS=1)"
fi

EXIT_CODE=0
if [[ "$GUARD_RESULT" == "FAIL" ]]; then
  EXIT_CODE=1
fi
if [[ "$TEST_RESULT" == "FAIL" ]]; then
  EXIT_CODE=1
fi
if [[ "$GH_STATUS" == "warn" || "$RUN_STATUS" == "warn" || "$PROD_STATUS" == "warn" ]]; then
  EXIT_CODE=1
fi

echo ""
echo "=== Release Conductor Summary ==="
echo "Lane: ${LANE}"
echo "Scope In: ${SCOPE_IN}"
echo "Scope Out: ${SCOPE_OUT}"
echo "Guard-Result: ${GUARD_RESULT}"
echo "Test-Result: ${TEST_RESULT}"
echo "PR-Link: https://github.com/${REPO_SLUG}/pull/${PR_NUMBER}"

echo "Checks: gh=${GH_STATUS}, runs=${RUN_STATUS}, prod=${PROD_STATUS}"
exit "$EXIT_CODE"
