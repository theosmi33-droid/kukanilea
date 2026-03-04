#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-standard}"

if command -v pytest >/dev/null 2>&1 && pytest --version >/dev/null 2>&1; then
  PYTEST=(pytest)
else
  PYTEST=(python3 -m pytest)
fi

case "$PROFILE" in
  smoke)
    "${PYTEST[@]}" -m "smoke or (unit and not slow)" -q --maxfail=1
    ;;
  standard)
    "${PYTEST[@]}" -m "not full and not external" -q
    ;;
  full)
    "${PYTEST[@]}" -q
    ;;
  *)
    echo "Unknown profile: $PROFILE"
    echo "Usage: $0 {smoke|standard|full}"
    exit 2
    ;;
esac
