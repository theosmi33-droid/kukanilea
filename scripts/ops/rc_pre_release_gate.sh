#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXIT_GO=0
EXIT_NO_GO=3

warn() { printf '[rc-gate] WARN: %s\n' "$*"; }
pass() { printf '[rc-gate] PASS: %s\n' "$*"; }
fail() { printf '[rc-gate] FAIL: %s\n' "$*"; exit "$EXIT_NO_GO"; }

printf '[rc-gate] KUKANILEA RC/Pre-Release Gate (minimal)\n'

(
  cd "$ROOT"
  python scripts/ops/verify_guardrails.py
) && pass 'Guardrails (Zero-CDN/White-Mode) grün' || fail 'Guardrails fehlgeschlagen'

(
  cd "$ROOT"
  bash scripts/ops/healthcheck.sh --skip-pytest
) && pass 'Ops-Healthcheck grün' || fail 'Healthcheck fehlgeschlagen'

if [[ -n "${RC_PYTEST_TARGETS:-}" ]]; then
  (
    cd "$ROOT"
    # shellcheck disable=SC2086
    pytest -q ${RC_PYTEST_TARGETS}
  ) && pass "Pytest grün (${RC_PYTEST_TARGETS})" || fail "Pytest fehlgeschlagen (${RC_PYTEST_TARGETS})"
else
  warn 'RC_PYTEST_TARGETS nicht gesetzt: nur akzeptiertes Restrisiko möglich (kein zusätzlicher pytest-Lauf in diesem Gate)'
fi

if [[ -n "${RC_RUFF_TARGETS:-}" ]]; then
  (
    cd "$ROOT"
    # shellcheck disable=SC2086
    ruff check ${RC_RUFF_TARGETS}
  ) && pass "Ruff grün (${RC_RUFF_TARGETS})" || fail "Ruff fehlgeschlagen (${RC_RUFF_TARGETS})"
else
  warn 'RC_RUFF_TARGETS nicht gesetzt: Ruff-Schnellprüfung übersprungen (optional)'
fi

printf '[rc-gate] GO: Pflichtgates grün.\n'
exit "$EXIT_GO"
