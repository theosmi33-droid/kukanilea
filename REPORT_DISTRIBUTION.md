# REPORT_DISTRIBUTION

Date: 2026-02-21
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`

## Scope
- Packaging/build evidence for macOS and Windows
- Installer artifact evidence
- Pass/Fail against Distribution release gate

## Pre-risk git status evidence
Command:
```bash
git status --porcelain=v1
```
Output:
```text
<clean>
```

## Build evidence

### macOS build
Executed:
- `scripts/build/obfuscate.sh`
- `scripts/build/bundle_macos.sh --skip-obfuscate`
- `scripts/build/dmg_macos.sh`

Results:
- `.app` created: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/dist/KUKANILEA.app`
- `.dmg` created: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/dist/KUKANILEA-1.0.0-beta.2.dmg`
- SHA256: `c5f00c726f6a14f3b217490c441ff5f063dd54755453a91c2be3908f9f9ea52c`

Logs:
- `/tmp/kuka_build_obfuscate.log`
- `/tmp/kuka_build_bundle_macos.log`
- `/tmp/kuka_build_dmg_macos.log`

Notes:
- Obfuscation fell back to plain copy due PyArmor trial license limitation (`out of license`).
- DMG was built via `hdiutil` fallback (`create-dmg` not installed).

### Windows build
- Not executed in this macOS-only test session.
- No local `.exe` install verification available.

## Pass/Fail vs Release Gates (Distribution)
| Gate target | Status | Reason | Evidence |
|---|---|---|---|
| Beta: installers build and start | PARTIAL FAIL | macOS build success; Windows build/run not verified in this run | `dist/`, build logs |
| RC: signing active | FAIL | No verified code-signing evidence in this run | logs show signing identity none in PyInstaller phase |
| Prod: signing + notarization/SmartScreen stable | FAIL | No notarization ticket/staple proof; no SmartScreen validation evidence | n/a |

## How to verify
1. Build macOS and Windows artifacts via CI workflows.
2. Install on clean target machines (macOS + Windows).
3. Capture Gatekeeper/SmartScreen behavior with screenshots/logs.
4. Verify signed binaries (`codesign`, notarization checks, Authenticode details).

## Findings
1. macOS packaging pipeline is operational for artifact generation.
2. Distribution gate is blocked by missing verified signing/notarization/SmartScreen evidence.
3. Windows installer validation remains mandatory before Beta gate can be called pass.
