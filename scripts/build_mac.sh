#!/bin/bash
# KUKANILEA macOS Build Script (v1.5.0 Gold)

echo "🛠 Starte macOS Build Prozess..."

# 1. Environment vorbereiten
if [ ! -d ".venv" ]; then
    echo "[ERROR] Virtual Environment nicht gefunden!"
    exit 1
fi

source .venv/bin/activate
pip install pyinstaller dmgbuild

# 2. PyInstaller ausführen
echo "📦 Bündele Applikation via PyInstaller..."
pyinstaller --clean KUKANILEA.spec

# 3. Code-Signing (Placeholder)
# codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/KUKANILEA.app

# 4. DMG erstellen
echo "💿 Erzeuge DMG Installer..."
mkdir -p dist/dmg
# dmgbuild nutzt oft ein JSON-Config File, hier vereinfacht via hdiutil falls kein dmgbuild config
hdiutil create -volname "KUKANILEA-Gold" -srcfolder dist/KUKANILEA.app -ov -format UDZO dist/KUKANILEA-v1.5.0-macOS.dmg

echo "[SUCCESS] Build abgeschlossen: dist/KUKANILEA-v1.5.0-macOS.dmg"
