# KUKANILEA Constitution

Last updated: 2026-02-17

## Five Core Principles (Non-negotiable)
1. DB-first truth: lifecycle and ownership are defined in the DB.
2. Tenant isolation: no cross-tenant reads or writes.
3. Default-safe operations: deny by default, explicit allowlists.
4. Offline-first reliability: core workflows run without cloud dependency.
5. Deterministic quality: reproducible behavior, explicit error contracts, auditable changes.

## NEVER DO
- Add dependencies or change stack components without ADR.
- Persist raw PII in eventlog/telemetry.
- Use `subprocess` with `shell=True`.
- Merge mutating endpoints without READ_ONLY guards.
- Bypass tenant scoping in SQL or filesystem mapping.

## ALWAYS DO
- Use `secrets.compare_digest()` for token/code/hash comparisons.
- Redact OCR/mail text before writing to DB.
- Keep migrations additive and idempotent.
- Add tests for security/compliance sensitive paths.
- Run triage + lint + tests before merge.

## Eventlog Payload Policy
Allowed payload content:
- entity IDs
- tenant_id
- status/reason codes
- counters/metrics
- redacted flags and booleans

Disallowed payload content:
- names
- emails
- phone numbers
- subject/body free-text
- IBAN or account details

## Governance Rule
Any stack/dependency change requires an ADR under `docs/adr/ADR-*.md` before merge.
