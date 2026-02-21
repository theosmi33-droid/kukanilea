# REPORT_HARDENING_DISTRIBUTION

Date: 2026-02-21  
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`  
Branch: `codex/bench-and-stability`

## Gate Status (3-State)

| Platform Gate | Status | Reason |
|---|---|---|
| macOS Signing + Notarization + Stapling Evidence | BLOCKED | Missing Developer ID signing assets and notary credentials |
| Windows Authenticode Verification Evidence | BLOCKED | No Windows host/runner with Windows SDK `signtool` in this run |

## Scope
- Artifact verification scripts for distribution evidence:
  - macOS: `scripts/verify_distribution_macos.sh`
  - Windows: `scripts/verify_distribution_windows.ps1`
- No claim of notarization or SmartScreen status without executable proof.

## Pre-run git status
Command:
```bash
git status --porcelain=v1
```

Output:
```text
?? output/
?? scripts/verify_distribution_macos.sh
?? scripts/verify_distribution_windows.ps1
```

## Commands Executed
```bash
scripts/verify_distribution_macos.sh dist/KUKANILEA-1.0.0-beta.2.dmg > output/perf/dist-verify-dmg.log 2>&1
scripts/verify_distribution_macos.sh dist/KUKANILEA.app > output/perf/dist-verify-app.log 2>&1

command -v pwsh >/dev/null 2>&1; echo pwsh_rc=$?
command -v signtool >/dev/null 2>&1; echo signtool_rc=$?
```

## Results

| Gate Item | Expected | Actual | Status |
|---|---|---|---|
| macOS `spctl` assess on `.dmg` | accepted with valid signature context | rejected (`source=Insufficient Context`) | FAIL |
| macOS `stapler validate` on `.dmg` | stapled ticket present | no ticket stapled | FAIL |
| macOS `spctl` assess on `.app` | accepted with valid signature context | rejected (`source=Insufficient Context`) | FAIL |
| macOS `stapler validate` on `.app` | stapled ticket present | no ticket stapled | FAIL |
| Windows verification tooling | executable verification command available on Windows host | local host has no usable Windows verification environment | BLOCKED |

## Prerequisites (to clear BLOCKED)

### macOS
- Developer ID Application signing certificate available to build/sign pipeline.
- Notary credentials configured for `notarytool` (Apple ID app-specific password or App Store Connect API key profile).
- Signed app and/or dmg artifact available for verification commands below.

### Windows
- Windows host or CI runner with Windows SDK installed.
- `signtool` available in `PATH` (or explicit SDK path).
- Signed `.exe` or `.msi` artifact available.

## How to run once prerequisites are available

### macOS
```bash
spctl --assess --type open --verbose <path_to_app_or_dmg>
xcrun stapler validate <path_to_app_or_dmg>
```

Expected PASS patterns:
- `spctl`: output contains `accepted`
- `stapler validate`: success confirmation that ticket validation worked

### Windows
```powershell
signtool verify /pa /v <path_to_exe_or_msi>
```

Expected PASS patterns:
- signature chain verification succeeds under Authenticode policy (`/pa`)
- no verification errors in output

## Evidence Artifacts
- `output/perf/dist-verify-dmg.log`
- `output/perf/dist-verify-app.log`
- `scripts/verify_distribution_macos.sh`
- `scripts/verify_distribution_windows.ps1`

## Notes
- Current local artifacts do not satisfy RC/Prod signing and notarization requirements.
- SmartScreen reputation cannot be validated from this macOS host; needs signed `.exe` verification on Windows (`signtool verify /pa` on release artifact).

## References
- Apple notarization workflow and stapling:
  - https://developer.apple.com/documentation/security/customizing-the-notarization-workflow
  - https://help.apple.com/xcode/mac/current/en.lproj/dev88332a81e.html
- Microsoft SignTool verify (`/pa`) and SDK context:
  - https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool
