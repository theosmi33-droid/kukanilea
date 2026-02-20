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

## Windows signing (future)

Phase 5.1 introduces automated Windows EXE builds.

Recommended next step:

1. Add signing secrets in GitHub Actions.
2. Build workflows sign artifacts automatically when secrets exist.
3. Verify signatures before uploading release assets.

## CI signing secrets

### macOS (`.github/workflows/build-macos.yml`)

- `APPLE_CERT_P12_BASE64`: Base64 of Developer ID Application certificate (`.p12`)
- `APPLE_CERT_PASSWORD`: Password for the `.p12`
- `APPLE_SIGN_IDENTITY`: Full codesign identity (for example `Developer ID Application: NAME (TEAMID)`)

If these are set on release workflows, CI will:

1. import the certificate into a temporary keychain,
2. sign `dist/KUKANILEA.app`,
3. sign the generated `dist/KUKANILEA-*.dmg`.

### Windows (`.github/workflows/build-windows.yml`)

- `WINDOWS_SIGN_PFX_BASE64`: Base64 of code-signing `.pfx`
- `WINDOWS_SIGN_PFX_PASSWORD`: Password for the `.pfx`

If these are set on release workflows, CI will sign `dist/KUKANILEA.exe` with `signtool`.
