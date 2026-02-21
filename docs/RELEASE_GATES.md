# RELEASE_GATES

Date: 2026-02-21

## Purpose
Release gates define deterministic pass/fail criteria for Beta, RC, and Prod.

## Status Definitions

- `PASS`: Criterion met and evidence is present.
- `FAIL`: Criterion tested and not met.
- `BLOCKED`: Criterion cannot be executed due to missing prerequisite (must link prerequisite ticket/doc).

## Severity Definitions

- `P0`: Security leak, data loss, install/update blocker, or tenant isolation violation.
- `P1`: Major degradation with user-facing impact.
- `P2`: Non-blocking issue.

## Acceptance Matrix

| Gate | Beta | RC | Prod | Current Status | Evidence / Verify | Owner |
|---|---|---|---|---|---|---|
| Security (Tenant/RBAC/CSP/Session) | No known P0 leaks | 0 open P0, 0 open High | External security check + 0 High | PASS | Run CI gates + security reports in repository | Engineering + Security |
| UX Core Flows (Top-20) | >=80% pass | >=95% pass | 100% pass for critical flows | BLOCKED | E2E expansion still pending (`tests/e2e/test_top20_flows.py`) | QA/UX |
| Error UX (no dead ends) | Error pages provide reload/back/dashboard | + Request-ID consistently shown | + Support runbook verified | PASS | `tests/e2e/test_hardening_smoke.py`, `REPORT_HARDENING_E2E.md` | Engineering |
| Distribution macOS | Installer builds and launches | Signing active + notarization evidence | Signed + notarized + stapled stable | BLOCKED | See `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/docs/RC_SIGNING_PREREQUISITES.md` and macOS report template | Release Captain |
| Distribution Windows | Installer builds and launches | Authenticode verification evidence | Signed installer + stable SmartScreen behavior | BLOCKED | See `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/docs/RC_WINDOWS_PREREQUISITES.md` and Windows report template | Release Captain |
| Update / Rollback | Manual update testable | Rollback demonstrably works | Signed manifest + rollback runbook | PASS | `REPORT_HARDENING_UPDATE_ROLLBACK.md` | Engineering |
| Compliance / Privacy | Asset/request inventory exists | Third-party/license inventory complete | Compliance checklist completed | BLOCKED | See `docs/COMPLIANCE_EU_DE_FOR_FEATURES.md` | Product + Compliance |
| Performance / Stability | 15-20m smoke without blocker | 60m endurance without P1 | Reproducible load test with limits | BLOCKED | `REPORT_RC_ENDURANCE_60M.md` still sanity-only; 60m evidence pending | Engineering |
| AI Availability (primary + fallback) | Primary and fallback work | Provider outage fallback without UI block | Offline-first + recovery runbook | PASS | `REPORT_AI_AVAILABILITY.md` | Engineering |

## Go / No-Go Rules

1. `NO-GO` if any `P0` is open.
2. `NO-GO` if core flow Login/CRM/Tasks/Docs/AI is blocked on a target OS.
3. `NO-GO` if update is shipped without reliable rollback path.
4. `GO` only when all RC criteria are satisfied and two consecutive CI runs are green.
5. `NO-GO` for RC/Prod while any mandatory gate is `BLOCKED` or `FAIL`.

## References

- RC prerequisites: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/docs/RC_SIGNING_PREREQUISITES.md`
- Windows prerequisites: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/docs/RC_WINDOWS_PREREQUISITES.md`
- Endurance evidence: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/REPORT_RC_ENDURANCE_60M.md`
