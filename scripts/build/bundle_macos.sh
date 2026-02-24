#!/bin/bash
# scripts/build/bundle_macos.sh
# KUKANILEA macOS Gold Distribution Pipeline

set -e

APP_NAME="KUKANILEA"
VERSION="1.5.0"
BUNDLE_ID="com.kukanilea.businessos"
SIGNING_IDENTITY="Developer ID Application: Your Company (ID123)" # ANPASSEN

echo "🍎 Starte macOS Gold Distribution v$VERSION..."

# 1. PyInstaller Build
source .venv312/bin/activate
pyinstaller --clean --noconfirm KUKANILEA.spec

# 2. Hardened Runtime Signing
echo "✍️  Signiere App Bundle (Hardened Runtime)..."
if codesign --deep --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" "dist/$APP_NAME.app" 2>/dev/null; then
    echo "✅ Signierung erfolgreich."
else
    echo "⚠️  Signierung übersprungen (Identität nicht gefunden). Erzeuge un-signiertes Bundle."
fi

# 3. Packaging DMG
echo "💿 Erzeuge DMG Installer..."
mkdir -p dist/final
hdiutil create -volname "$APP_NAME Gold" -srcfolder "dist/$APP_NAME.app" -ov -format UDZO "dist/final/$APP_NAME-v$VERSION-macOS.dmg"

echo "✅ macOS Gold Release bereit in dist/final/"
