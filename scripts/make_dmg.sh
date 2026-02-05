#!/usr/bin/env bash
set -euo pipefail

APP_NAME="KUKANILEA"
APP_PATH="dist/${APP_NAME}.app"
DMG_PATH="dist/${APP_NAME}.dmg"

if [[ ! -d "$APP_PATH" ]]; then
  echo "Missing ${APP_PATH}. Run scripts/build_mac.sh first." >&2
  exit 1
fi

if command -v dmgbuild >/dev/null 2>&1; then
  python3 -m pip install --upgrade dmgbuild
  dmgbuild -s scripts/dmgbuild_settings.py "$APP_NAME" "$DMG_PATH"
else
  echo "dmgbuild not found; using hdiutil fallback."
  TMP_DIR=$(mktemp -d)
  cp -R "$APP_PATH" "$TMP_DIR/"
  hdiutil create -volname "$APP_NAME" -srcfolder "$TMP_DIR" -ov -format UDZO "$DMG_PATH"
  rm -rf "$TMP_DIR"
fi

echo "DMG ready: ${DMG_PATH}"
