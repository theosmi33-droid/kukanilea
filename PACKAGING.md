# Packaging Plan (macOS DMG)

## Goal
Provide a repeatable DMG build for a local demo. No notarization in this phase.

## Plan
1. Build the macOS app bundle using PyInstaller.
2. Create a DMG using `dmgbuild` or `hdiutil`.
3. Document manual notarization steps for future use.

## Commands
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

scripts/build_mac.sh
scripts/make_dmg.sh
```

## Future (Notarization)
- Register an Apple Developer ID.
- Sign the app with `codesign`.
- Submit to Apple notarization with `xcrun notarytool`.
- Staple the ticket to the app and DMG.
