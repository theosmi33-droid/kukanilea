# REPORT_RC_DISTRIBUTION_WINDOWS

Date: 2026-02-21  
Status: BLOCKED

## Blocker

- Missing Windows host/runner and/or Windows SDK (`signtool`) and signing certificate.

## Prerequisites Reference

- `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/docs/RC_WINDOWS_PREREQUISITES.md`

## Commands To Run Once Unblocked

```powershell
signtool verify /pa /v <path_to_exe_or_msi>
```

## PASS Criteria

- `signtool verify /pa /v` exits with code `0`.
- Output confirms successful Authenticode policy verification.

## Evidence Section (to fill when available)

- Artifact path:
- `signtool` output:
- Exit code:
- Verdict: PASS / FAIL
