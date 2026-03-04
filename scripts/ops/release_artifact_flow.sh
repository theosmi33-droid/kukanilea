#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
DIST_DIR="$ROOT/dist/release_corridor"
ARTIFACT="$DIST_DIR/kukanilea_${STAMP}.tar.gz"
REPORT="$DIST_DIR/RELEASE_ARTIFACT_REPORT_${STAMP}.md"
PYTHON="${PYTHON:-python3}"

mkdir -p "$DIST_DIR"

BUILD_STATUS="PASS"
SMOKE_STATUS="PASS"

{
  echo "# Release Artifact Flow Report"
  echo
  echo "- Timestamp: $(date -Iseconds)"
  echo "- Root: $ROOT"
  echo "- Artifact: $(realpath --relative-to="$ROOT" "$ARTIFACT" 2>/dev/null || echo "$ARTIFACT")"
  echo
  echo "## 1) Build"
  echo 'git archive --format=tar.gz --output <artifact> HEAD'
  if git -C "$ROOT" archive --format=tar.gz --output "$ARTIFACT" HEAD; then
    size_bytes="$(stat -c %s "$ARTIFACT")"
    sha256="$(sha256sum "$ARTIFACT" | awk '{print $1}')"
    echo
    echo "- Status: PASS"
    echo "- Size (bytes): $size_bytes"
    echo "- SHA256: $sha256"
  else
    BUILD_STATUS="FAIL"
    echo
    echo "- Status: FAIL"
  fi

  echo
  echo "## 2) Smoke"
  if command -v "$PYTHON" >/dev/null 2>&1 && "$PYTHON" -c 'import pytest' >/dev/null 2>&1; then
    echo '$PYTHON -m pytest -q tests/test_observability.py'
    if (cd "$ROOT" && "$PYTHON" -m pytest -q tests/test_observability.py); then
      echo
      echo "- Status: PASS"
    else
      SMOKE_STATUS="FAIL"
      echo
      echo "- Status: FAIL"
    fi
  else
    SMOKE_STATUS="WARN"
    echo "- Status: WARN"
    echo "- Note: pytest unavailable for interpreter $PYTHON"
  fi

  echo
  echo "## 3) Summary"
  echo "- Build: $BUILD_STATUS"
  echo "- Smoke: $SMOKE_STATUS"
} > "$REPORT"

printf '%s\n' "$REPORT"

if [[ "$BUILD_STATUS" == "FAIL" || "$SMOKE_STATUS" == "FAIL" ]]; then
  exit 1
fi
