# RELEASE_CAPTAIN_RUNBOOK

Date: 2026-02-21

## Purpose
Step-by-step execution guide for Beta/RC release readiness with evidence-driven gates.

## Procedure

1. Verify gate statuses in `docs/RELEASE_GATES.md`.
2. Run/update endurance evidence (`REPORT_RC_ENDURANCE_60M.md`).
3. Validate macOS signing/notarization evidence when prerequisites exist.
4. Validate Windows Authenticode evidence when prerequisites exist.
5. Generate SBOM and vulnerability scan summary (`REPORT_SBOM.md`).
6. Generate build manifest and provenance evidence (`REPORT_PROVENANCE.md`).
7. Assemble evidence reports in one release package path.
8. Confirm CI is green in two consecutive runs.
9. Request final gatekeeper sign-off.
10. Tag release and publish artifacts.
11. Prepare rollback communication and fallback instructions.

## Evidence Bundle (minimum)

- `docs/RELEASE_GATES.md`
- `REPORT_HARDENING_SECURITY.md`
- `REPORT_HARDENING_E2E.md`
- `REPORT_HARDENING_PERF.md`
- `REPORT_RC_ENDURANCE_60M.md`
- `REPORT_RC_DISTRIBUTION_MACOS.md`
- `REPORT_RC_DISTRIBUTION_WINDOWS.md`
- `REPORT_SBOM.md`
- `REPORT_PROVENANCE.md`

## Stop Rules

- Any `P0` open => `NO-GO`
- Any mandatory gate `FAIL` or `BLOCKED` => `NO-GO` for RC/Prod
