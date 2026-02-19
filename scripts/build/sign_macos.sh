#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_PATH="$ROOT_DIR/dist/KUKANILEA.app"
CERT_NAME="${1:-${APPLE_SIGN_IDENTITY:-}}"

if [ -z "$CERT_NAME" ]; then
  echo "Usage: scripts/build/sign_macos.sh \"Developer ID Application: NAME (TEAMID)\"" >&2
  echo "Or set APPLE_SIGN_IDENTITY in your shell." >&2
  exit 1
fi

if [ ! -d "$APP_PATH" ]; then
  echo "Missing app bundle: $APP_PATH" >&2
  exit 1
fi

codesign --deep --force --verify --verbose --sign "$CERT_NAME" "$APP_PATH"

echo "Codesign complete: $APP_PATH"
