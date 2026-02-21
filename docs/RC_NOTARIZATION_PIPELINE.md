# RC_NOTARIZATION_PIPELINE

Date: 2026-02-21

## macOS Notarization Pipeline (CI Checklist)

1. Build app bundle (`KUKANILEA.app`).
2. Codesign app:
   ```bash
   codesign --deep --force --options runtime \
     --sign "Developer ID Application: <NAME> (<TEAMID>)" \
     KUKANILEA.app
   ```
3. Package for notarization (zip/dmg as required).
4. Submit to Apple notarization and wait:
   ```bash
   xcrun notarytool submit KUKANILEA.zip \
     --keychain-profile "<NOTARY_PROFILE>" \
     --wait
   ```
5. Staple notarization ticket:
   ```bash
   xcrun stapler staple KUKANILEA.app
   ```
6. Validate:
   ```bash
   spctl --assess --type open --verbose KUKANILEA.app
   xcrun stapler validate KUKANILEA.app
   ```
7. If distributing DMG:
   - Build DMG.
   - Sign/notarize DMG.
   - Staple DMG ticket.
   - Validate with `stapler validate`.
8. Store all notarization/stapler logs as CI artifacts.

## Notes

- Do not mark gate `PASS` unless both policy assessment and stapled ticket validation succeed.
- Keep credentials in keychain profile only; never commit secrets.

## Reference

- https://developer.apple.com/documentation/security/customizing-the-notarization-workflow
