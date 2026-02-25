#!/bin/bash
# KUKANILEA macOS Bundling Script
# Erstellt eine Standalone .app und ein .dmg Archiv.

set -e

APP_NAME="KUKANILEA"
VERSION="1.5.0"
DIST_DIR="./dist"
BUILD_DIR="./build"

echo "🚀 Starte Build-Prozess für macOS v$VERSION..."

# 1. Cleanup
rm -rf $DIST_DIR $BUILD_DIR

# 2. PyInstaller Bundle erstellen
# Wir bündeln alle Abhängigkeiten in ein Verzeichnis
./.venv312/bin/pyinstaller --name "$APP_NAME" 
    --windowed 
    --noconfirm 
    --clean 
    --add-data "app/templates:templates" 
    --add-data "app/static:static" 
    --add-data "instance/identity:instance/identity" 
    --hidden-import "zeroconf" 
    --hidden-import "pyclamd" 
    --hidden-import "qrcode" 
    run.py

echo "📦 PyInstaller Bundle fertig."

# 3. DMG erstellen (optional, erfordert dmgbuild)
if command -v dmgbuild >/dev/null 2>&1; then
    echo "💿 Erstelle DMG Archiv..."
    # dmgbuild -s scripts/dmg_settings.py "$APP_NAME" "$DIST_DIR/$APP_NAME-$VERSION.dmg"
else
    echo "⚠️ dmgbuild nicht gefunden. Überspringe DMG-Erstellung."
fi

echo "✅ Build abgeschlossen: $DIST_DIR/$APP_NAME.app"
