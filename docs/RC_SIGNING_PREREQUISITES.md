# RC Signing Prerequisites

Date: 2026-02-21

## Purpose
Define the minimum prerequisites to move Distribution evidence from `BLOCKED` to executable RC checks.

## macOS Prerequisites

- Apple Developer Program access with Developer ID Application certificate.
- Signing identity import available to build host/runner keychain.
- Notarization credentials for `notarytool`:
  - Apple ID + app-specific password workflow, or
  - App Store Connect API key workflow.
- Built and signed `.app` and/or `.dmg` artifact.

### Apple Setup (Step-by-step)

1. Enroll in Apple Developer Program with organization/team context.
2. Create a `Developer ID Application` certificate in Apple Developer portal or Xcode.
3. Export/import certificate (and private key) into CI keychain or local signing machine.
4. Configure `notarytool` credentials via one of these options:
   - Apple ID + app-specific password (requires 2FA).
   - App Store Connect API key (recommended for CI).
5. Store credentials in keychain profile:
   ```bash
   xcrun notarytool store-credentials "<PROFILE_NAME>" \
     --apple-id "<APPLE_ID_EMAIL>" \
     --team-id "<TEAM_ID>" \
     --password "<APP_SPECIFIC_PASSWORD>"
   ```
6. Reference stored profile in automation with `--keychain-profile "<PROFILE_NAME>"`.

### macOS Evidence Commands
```bash
spctl --assess --type open --verbose <path_to_app_or_dmg>
xcrun stapler validate <path_to_app_or_dmg>
```

### macOS CI/Runner Checklist
- Keychain is created/unlocked in non-interactive environment.
- Signing identity is imported into that keychain.
- Notary profile is configured via `notarytool store-credentials` (or equivalent secure credential setup).
- Build step signs artifact before notarization submission.
- Post-notarization step staples ticket to artifact.
- Verification step runs `spctl` and `stapler validate` and stores full logs as artifacts.
- If CI fails with keychain prompt errors (`User interaction is not allowed`), use explicit keychain creation/unlock in non-interactive session.

## Windows Prerequisites

- Windows host or CI runner available.
- Windows SDK installed with `signtool` accessible.
- Code-signing certificate available to signing step.
- Built installer or binary (`.exe` / `.msi`) to verify.

### Windows Evidence Command
```powershell
signtool verify /pa /v <path_to_exe_or_msi>
```

### Windows CI/Runner Checklist
- `signtool` path resolved on runner.
- Signing certificate available securely to pipeline.
- Signing step executed before verification.
- Verification logs uploaded as CI artifacts.

## SmartScreen Note
- Signing is a prerequisite for building reputation over time.
- SmartScreen reputation is probabilistic and not directly exposed as a deterministic pass/fail API.
- Use signed, consistent publisher identity and track field-install outcomes.

## References
- Apple notarization workflow:
  - https://developer.apple.com/documentation/security/customizing-the-notarization-workflow
  - https://help.apple.com/xcode/mac/current/en.lproj/dev88332a81e.html
- Microsoft SignTool:
  - https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool
- SmartScreen reputation context (industry reference):
  - https://signpath.io/knowledge-base/windows-platform
