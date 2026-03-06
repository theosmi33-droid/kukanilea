# Agentic System Security Checklist + Testsuite Plan (Flask)

This document operationalizes the security guardrails into concrete Flask implementation notes, test ideas, and audit/logging requirements.

## Security Checklist & Test Plan

| Guardrail | Implementation notes (Flask) | Unit test ideas | E2E test ideas | Logging / audit requirements |
|---|---|---|---|---|
| Never show raw errors | Register global handlers (`@app.errorhandler(Exception)` + typed handlers for `HTTPException`) that return sanitized JSON/HTML messages. Disable Flask debugger in non-local environments (`DEBUG=False`, `PROPAGATE_EXCEPTIONS=False`). Use correlation IDs and map internals to generic user-facing errors. | Trigger service-layer exception and assert response payload excludes stacktrace, SQL fragments, file paths, env vars. Assert status code mapping (e.g. 500, 400) and a stable error schema. | Force server-side fault path (mock downstream outage) and verify UI/API only shows generic message, not traceback. | Structured error logs with `error_code`, `correlation_id`, endpoint, tenant/user context (if present), no secrets/PII. Security event when unhandled exceptions spike. |
| Validate redirects allowlist | Centralize redirect target validation (`is_safe_redirect(url, allowed_hosts, allowed_paths)`). Accept only relative URLs or explicit allowlisted domains/schemes (`https`). Reject protocol-relative URLs, `javascript:` and encoded bypasses. | Parametrized tests over payloads (`//evil.com`, `https://evil.com`, `%2f%2fevil.com`, `javascript:...`, CRLF injections). Assert only allowlisted targets pass. | Login flow with `next=` parameter: allowed internal target succeeds, external target is ignored/fallback to dashboard. | Log rejected redirect attempts with source IP, user/session ID, raw + normalized URL, reason code (`redirect_blocked_not_allowlisted`). |
| Rate limit password reset | Apply per-IP + per-identity throttling on reset request and reset confirm endpoints (Flask-Limiter/Redis sliding window). Add cooldown and abuse-resistant generic responses (“If account exists, email sent”). | Simulate repeated requests by same IP/email and assert 429 after threshold. Assert generic response text remains constant for existing vs non-existing email. | Script burst reset requests and verify limiting + cooldown behavior; verify account still usable after legitimate reset interval. | Audit `password_reset_requested`, `password_reset_rate_limited`, `password_reset_completed`; retain timestamp, actor hash, IP/device fingerprint. Alert on anomaly bursts. |
| Server-side permission checks | Enforce authorization in backend handlers/services (never UI-only): RBAC/ABAC decorators + resource ownership checks in DB queries (`WHERE tenant_id = current_tenant`). Deny by default. | Test role matrix per endpoint/action (viewer/editor/admin). Test IDOR attempts by swapping resource IDs across tenants. | Multi-user scenario: user A cannot read/update user B resource via direct API calls despite hidden UI actions. | Log authorization denials (`authz_denied`) with subject, action, resource, policy decision trace. Periodic review of deny spikes. |
| Verify webhooks signatures | Verify provider signature header using HMAC and constant-time compare (`hmac.compare_digest`). Validate timestamp tolerance and prevent replay (event ID store). Fail closed before parsing business payload. | Valid signature accepted; tampered body/signature rejected; stale timestamp rejected; replayed event ID rejected. | Replay captured webhook with modified payload and old timestamp; expect 401/403 and no side effects. | Log webhook verification outcomes (`webhook_verified`, `webhook_rejected_signature`, `webhook_replay_blocked`) and provider event IDs. |
| Remove debug logs | Replace `print()`/verbose debug with structured logger and environment-based log levels. Add pre-commit/static checks to block accidental debug statements in app code. | Lint/test scan ensuring no forbidden tokens in production paths (`print(`, `pdb`, `console.log` for templates/assets). | Smoke test production-like run and assert no debug-only entries are emitted at INFO/WARN/ERROR streams. | Logging policy: redact tokens, passwords, auth headers; separate audit channel from app diagnostics; retention + access controls documented. |
| CORS not wide open | Configure strict CORS (`flask-cors`) by explicit origin allowlist, methods, headers, credentials policy. No `*` with credentials. Scope CORS only to required routes. | Test preflight and actual requests from allowed/disallowed origins. Assert `Access-Control-Allow-Origin` absent for blocked origins. | Browser-based cross-origin call from malicious origin should fail; trusted frontend origin should pass. | Log denied CORS origin attempts and track top blocked origins for abuse detection. |
| Session expiration + refresh rotation | Set secure session cookie flags (`HttpOnly`, `Secure`, `SameSite`). Enforce idle + absolute timeout. Rotate session IDs on login/privilege changes. For refresh tokens: one-time rotation + revocation list on reuse detection. | Assert cookie flags, timeout config, and session ID rotation on re-auth. Test reused refresh token causes revocation and forced logout. | Simulate stolen refresh token reuse after legitimate rotation; ensure compromise detection invalidates token family and prompts re-login. | Audit `session_created`, `session_rotated`, `session_expired`, `refresh_reuse_detected`, `session_revoked` with device/IP metadata. |
| Update dependencies / audit | Pin versions, run vulnerability scanning (`pip-audit`, `safety`, `npm audit` if frontend), and maintain patch cadence. Enforce lockfile updates and changelog review for auth/security libs. | CI unit check that fails on critical/high vulnerabilities above policy threshold. Test app startup with updated pins to catch regressions early. | Pre-release environment smoke test after dependency bump; verify critical auth/payment/webhook flows still work. | Track dependency SBOM + scan artifacts per build; archive waivers with expiry and owner; alert on newly disclosed CVEs affecting runtime deps. |

## Must-have in CI

1. **Security unit suite is mandatory**: run targeted pytest markers/modules for authz, redirect, session, reset-rate-limit, webhook verification.
2. **Dependency vulnerability gate**: fail build for `high/critical` findings unless time-bound waiver exists.
3. **Static guardrail checks**: block debug statements and unsafe patterns (open redirects, wildcard CORS with credentials, missing signature verification wrappers).
4. **Config policy checks**: enforce production security config (`DEBUG=False`, secure cookies, strict CORS allowlist, session timeout settings).
5. **Replay/abuse regression tests**: automated tests for webhook replay, refresh-token reuse, and password-reset brute-force throttling.
6. **Audit-log contract tests**: assert security-relevant actions emit required structured audit events.
7. **CI artifacts retention**: publish test reports + security scan outputs + SBOM for every protected branch build.
8. **Release blocking rule**: deployment blocked if any mandatory security stage fails or is skipped.

## Evidence Mapping (Security Gate -> Proof Artifact)

| Gate | Required proof artifact | Produced by | Verification command | Failing signal |
|---|---|---|---|---|
| Raw error masking | Sanitized 4xx/5xx payload snapshots | `tests/security/*` | `PYENV_VERSION=3.12.0 pytest -q tests/security -k error` | Response contains traceback/SQL/path |
| Redirect allowlist | Block/allow matrix log | `tests/security/*redirect*` | `PYENV_VERSION=3.12.0 pytest -q tests/security -k redirect` | External redirect passes |
| Password-reset rate limit | 429 threshold evidence | integration tests | `PYENV_VERSION=3.12.0 pytest -q tests/security -k reset` | Unlimited requests possible |
| Session rotation | Session-id change + reuse deny evidence | auth tests | `PYENV_VERSION=3.12.0 pytest -q tests/security -k session` | Session fixation / reused refresh accepted |
| CORS strict mode | Origin allowlist assertions | API security tests | `PYENV_VERSION=3.12.0 pytest -q tests/security -k cors` | `*` or unauthorized origin allowed |
| AuthZ server-side | Cross-tenant denial evidence | integration tests | `PYENV_VERSION=3.12.0 pytest -q tests/integration -k tenant` | IDOR path succeeds |
| Webhook signature | Tampered payload rejection evidence | webhook tests | `PYENV_VERSION=3.12.0 pytest -q tests/security -k webhook` | Tampered body accepted |
| Dependency hygiene | Scan report + policy evaluation | CI pipeline | `./scripts/ops/security_gate.sh` | High/Critical vulnerabilities unresolved |

## Minimal Threat Scenarios (Agentic + Handwerk)

1. **Prompt injection via upload**  
Attack: attacker uploads manipulated PDF with instructions that try to coerce agent execution.  
Control: upload parser is read-only, write actions require confirm-token and tenant match.  
Test: ensure generated plan remains `requires_confirm=true` for write actions.

2. **Cross-tenant task creation**  
Attack: crafted request uses valid token but altered tenant id in body.  
Control: server-side tenant derivation from session; payload tenant ignored.  
Test: API must reject mismatch with deterministic 403 and audit log.

3. **Webhook replay**  
Attack: valid webhook replayed with old timestamp to trigger repeated actions.  
Control: event-id dedup table + timestamp tolerance + HMAC verify first.  
Test: second identical webhook denied, no state mutation.

4. **Session fixation after privilege change**  
Attack: stale session id reused after role elevation.  
Control: session id rotation on login and privilege transitions.  
Test: old session id invalid immediately after rotation.

5. **Brute-force password reset**  
Attack: high-volume reset attempts for one account/email.  
Control: per-IP + per-identity throttle with generic response body.  
Test: consistent text and 429 after threshold.

6. **Unsafe redirect exfiltration**  
Attack: `next=` parameter points to external target for credential theft.  
Control: strict allowlist normalization; fallback to internal route.  
Test: external target blocked even when encoded.

## Review Cadence

- **Per PR**: security checklist delta review for touched domains.
- **Weekly**: failed/blocked security events trend review.
- **Release**: evidence packet must include security gate output + selected pytest evidence.
- **Quarterly**: rotate signing keys and refresh dependency policy waivers.

## Definition of Secure Merge (for this repository)

A PR is security-mergeable only if all statements below are true:

1. No mandatory security gate is skipped in CI.
2. No critical/high dependency issue is unresolved without expiry-bound waiver.
3. State-changing endpoints prove server-side authorization.
4. Error responses are sanitized and correlation-id capable.
5. Session/token lifecycle tests pass for timeout + rotation + reuse detection.
6. Evidence links are present in the PR description.

## Appendix: Practical Command Bundle

```bash
# targeted baseline checks used during PR hardening
PYENV_VERSION=3.12.0 pytest -q tests/security/test_baseline_controls.py
PYENV_VERSION=3.12.0 pytest -q tests/security/test_chatbot_confirm_guardrails.py
PYENV_VERSION=3.12.0 pytest -q tests/security/test_ai_skill_runtime.py
./scripts/ops/security_gate.sh
```

Use this bundle for rapid iteration before running broader suites.
