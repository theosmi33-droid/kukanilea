# REPORT_HARDENING_DISTRIBUTION

Date: 2026-02-21  
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`  
Branch: `codex/bench-and-stability`

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
| Windows verification tooling | executable verification command available on Windows host | local host has no `pwsh`; Windows verification not executed here | MANUAL |

## Evidence Artifacts
- `output/perf/dist-verify-dmg.log`
- `output/perf/dist-verify-app.log`
- `scripts/verify_distribution_macos.sh`
- `scripts/verify_distribution_windows.ps1`

## Notes
- Current local artifacts do not satisfy RC/Prod signing and notarization requirements.
- SmartScreen reputation cannot be validated from this macOS host; needs signed `.exe` verification on Windows (`signtool verify /pa` on release artifact).
