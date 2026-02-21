#!/usr/bin/env bash
set -uo pipefail

TARGET_PATH="${1:-}"
if [[ -z "${TARGET_PATH}" ]]; then
  echo "usage: $0 <path-to-app-or-dmg>" >&2
  exit 2
fi
if [[ ! -e "${TARGET_PATH}" ]]; then
  echo "target not found: ${TARGET_PATH}" >&2
  exit 2
fi

echo "[verify_distribution_macos] target=${TARGET_PATH}"
rc=0

if command -v spctl >/dev/null 2>&1; then
  echo "[verify_distribution_macos] running spctl assess"
  if ! spctl --assess --type open --verbose "${TARGET_PATH}"; then
    rc=1
  fi
else
  echo "[verify_distribution_macos] spctl not available (manual step required)"
fi

if command -v xcrun >/dev/null 2>&1; then
  echo "[verify_distribution_macos] running stapler validate"
  if ! xcrun stapler validate "${TARGET_PATH}"; then
    rc=1
  fi
else
  echo "[verify_distribution_macos] xcrun not available (manual step required)"
fi

exit "${rc}"
