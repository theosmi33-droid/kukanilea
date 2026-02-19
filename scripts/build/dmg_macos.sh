#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_PATH="$ROOT_DIR/dist/KUKANILEA.app"
VERSION="$(python -c "from app.version import __version__; print(__version__)")"
DMG_PATH="$ROOT_DIR/dist/KUKANILEA-${VERSION}.dmg"

if [ ! -d "$APP_PATH" ]; then
  echo "Missing app bundle: $APP_PATH" >&2
  echo "Run scripts/build/bundle_macos.sh first." >&2
  exit 1
fi

rm -f "$DMG_PATH"

if command -v create-dmg >/dev/null 2>&1; then
  create-dmg \
    --volname "KUKANILEA" \
    --window-pos 200 120 \
    --window-size 800 400 \
    --icon-size 100 \
    --icon "KUKANILEA.app" 200 190 \
    --hide-extension "KUKANILEA.app" \
    --app-drop-link 600 185 \
    "$DMG_PATH" \
    "$APP_PATH"
else
  echo "create-dmg not installed; using hdiutil fallback."
  TMP_DIR="$(mktemp -d)"
  cp -R "$APP_PATH" "$TMP_DIR/"
  ln -s /Applications "$TMP_DIR/Applications"
  hdiutil create -volname "KUKANILEA" -srcfolder "$TMP_DIR" -ov -format UDZO "$DMG_PATH"
  rm -rf "$TMP_DIR"
fi

echo "DMG ready: $DMG_PATH"
