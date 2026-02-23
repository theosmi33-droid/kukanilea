#!/usr/bin/env bash
set -euo pipefail

# KUKANILEA macOS Notarization Helper
# Usage: ./notarize_mac.sh "Developer-ID" "App-Store-Connect-Key-Profile"

APP_PATH="dist/KUKANILEA.app"
ZIP_PATH="dist/KUKANILEA_notarization.zip"

if [ ! -d "$APP_PATH" ]; then
    echo "Error: $APP_PATH not found. Run scripts/build/bundle_macos.sh first."
    exit 1
fi

echo "== Zipping app for notarization =="
/usr/bin/ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

echo "== Submitting to Apple Notary Service =="
# xcrun notarytool submit "$ZIP_PATH" --keychain-profile "$2" --wait

echo "Next steps after success:"
echo "1. xcrun stapler staple $APP_PATH"
echo "2. hdiutil create -volname KUKANILEA -srcfolder dist/ -ov -format UDZO dist/KUKANILEA_v1.0.dmg"
