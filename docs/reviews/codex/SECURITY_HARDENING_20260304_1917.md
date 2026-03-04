# SECURITY_HARDENING Report

## Scope
- CSP hardening
- Confirm-gates for critical write actions
- Injection/Jailbreak guardrail validation
- Auth/session defaults + secret handling

## Changes applied
1. CSP policy expanded with additional hardening directives (`frame-ancestors`, `worker-src`, `manifest-src`, mixed-content blocking, upgrade-insecure-requests).
2. Session security defaults hardened in production-like environments (`SESSION_COOKIE_SECURE=True`, `__Host-` prefixed cookie name, explicit lifetime).
3. Confirm-gates enforced for user disable and backup run actions.
4. Security tests extended to validate new confirm-gate coverage, CSP directives, and secure session defaults.

## Risks and trade-offs
- `script-src 'unsafe-inline'` / `style-src 'unsafe-inline'` are still present for legacy template compatibility.
- `upgrade-insecure-requests` may surface mixed-content issues in legacy deployments.

## Validation status
- Guardrail scripts executed (see command logs).
- Targeted security test suite prepared; execution depends on local pytest availability.

## Remaining recommendations
- Phase out inline scripts/styles via nonces/hashes.
- Add server-side confirmation intent metadata for all destructive endpoints.
- Add CI job enforcing security tests and guardrail scripts on PRs.
