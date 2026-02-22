# DEPENDENCY_EXCEPTION_POLICY

Date: 2026-02-22

## Purpose
Define how dependency vulnerabilities can be exception-approved without losing auditability.

## Default Policy

- RC target: 0 unresolved High findings.
- Any exception must be temporary and explicitly approved.

## Mandatory Fields per Exception

1. Vulnerability identifier (e.g. CVE/GHSA).
2. Affected package and version.
3. Risk rationale (why release can proceed).
4. Mitigation currently in place.
5. Owner.
6. Sunset date (hard deadline for fix/removal).
7. Tracking issue/ticket URL.

## Approval Rules

- Exception requires Security + Release Captain approval.
- Missing sunset date means exception is invalid.
- Expired exceptions automatically convert gate status to `FAIL`.
