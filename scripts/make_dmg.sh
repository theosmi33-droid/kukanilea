#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="KUKANILEA"
APP_PATH="$ROOT_DIR/dist/${APP_NAME}.app"
DMG_PATH="$ROOT_DIR/dist/${APP_NAME}.dmg"

if [ ! -d "$APP_PATH" ]; then
  echo "Missing $APP_PATH. Run scripts/build_mac.sh first." >&2
  exit 1
fi

rm -f "$DMG_PATH"

if command -v dmgbuild >/dev/null 2>&1; then
  PY_BIN="${PYTHON:-python3}"
  "$PY_BIN" -m pip install --upgrade dmgbuild
  dmgbuild -s "$ROOT_DIR/scripts/dmgbuild_settings.py" "$APP_NAME" "$DMG_PATH"
else
  echo "dmgbuild not found; using hdiutil fallback."
  TMP_DIR="$(mktemp -d)"
  cp -R "$APP_PATH" "$TMP_DIR/"
  ln -s /Applications "$TMP_DIR/Applications"
  hdiutil create -volname "$APP_NAME" -srcfolder "$TMP_DIR" -ov -format UDZO "$DMG_PATH"
  rm -rf "$TMP_DIR"
fi

echo "DMG ready: $DMG_PATH"
