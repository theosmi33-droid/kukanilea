# macOS Signing Notes

Stand: 2026-02-19

Signing is optional for internal beta testing. Without signing/notarization, Gatekeeper warnings are expected.

## Sign app bundle

```bash
scripts/build/sign_macos.sh "Developer ID Application: YOUR NAME (TEAMID)"
```

Alternative via environment variable:

```bash
export APPLE_SIGN_IDENTITY="Developer ID Application: YOUR NAME (TEAMID)"
scripts/build/sign_macos.sh
```

## Verify signature

```bash
codesign --verify --verbose dist/KUKANILEA.app
spctl --assess --type execute --verbose dist/KUKANILEA.app
```

## Notarization (future)

Typical follow-up steps:

1. Notarize the `.app`/`.dmg` with `xcrun notarytool`.
2. Staple the ticket to the artifact.
3. Re-verify with `spctl`.

This phase does not automate notarization.
